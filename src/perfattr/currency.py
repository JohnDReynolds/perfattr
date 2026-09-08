"""Calculate single-period Karnosky-Singer currency attribution.

The calculation keeps separate market and currency grids, reports four explicit log
effect channels, and reconciles each grid and their combined modeled active return.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd

from perfattr._exceptions import AttributionError
from perfattr._schemas import (
    CURRENCY_DETAIL_COLUMNS,
    CURRENCY_EXPOSURE_INPUT_COLUMNS,
    CURRENCY_MARKET_DETAIL_COLUMNS,
    CURRENCY_MARKET_INPUT_COLUMNS,
    CURRENCY_PERIOD_SUMMARY_COLUMNS,
    CURRENCY_RECONCILIATION_COLUMNS,
)
from perfattr._validation import (
    float_array as _float_array,
    has_true as _has_true,
    is_close as _is_close,
    normalize_dates,
    normalize_identity,
    normalize_numeric,
    normalize_reconciliation_tolerance,
    raise_invalid,
    require_exact_columns,
    sum_by_period as _sum_by_period,
)


_PERIOD_COLUMNS = ("from_date", "thru_date")
_MARKET_GRID_SUMMARY_COLUMNS = CURRENCY_PERIOD_SUMMARY_COLUMNS[:5] + (
    "market_allocation_log_effect",
    "security_selection_log_effect",
    "total_log_effect",
)
_CURRENCY_GRID_SUMMARY_COLUMNS = (
    CURRENCY_PERIOD_SUMMARY_COLUMNS[:2]
    + CURRENCY_PERIOD_SUMMARY_COLUMNS[5:8]
    + (
        "currency_allocation_log_effect",
        "hedge_selection_log_effect",
        "total_log_effect",
    )
)


@dataclass
class CurrencyAttributionResult:
    """Hold single-period currency-attribution result frames and metadata.

    Attributes:
        market_detail: Market allocation and security-selection log effects for each
            period and market.
        currency_detail: Currency allocation and hedge-selection log effects for each
            period and currency.
        period_summary: Modeled log returns and four-channel totals for each period.
        reconciliation: Passing market, currency, and total reconciliation evidence.
        base_currency: Caller-supplied base-currency identity used by every currency
            return in the result.

    Notes:
        Direct construction is ordinary dataclass construction and does not validate
        or copy frames. The calculator will return independently owned frames without
        mutating caller inputs.
    """

    market_detail: pd.DataFrame
    currency_detail: pd.DataFrame
    period_summary: pd.DataFrame
    reconciliation: pd.DataFrame
    base_currency: str


@dataclass
class _NormalizedCurrencyInputs:
    """Hold independently owned, aligned currency-attribution inputs.

    Attributes:
        portfolio_markets: Canonical portfolio market rows.
        benchmark_markets: Canonical benchmark market rows.
        portfolio_currencies: Canonical portfolio net currency-exposure rows.
        benchmark_currencies: Canonical benchmark net currency-exposure rows.
    """

    portfolio_markets: pd.DataFrame
    benchmark_markets: pd.DataFrame
    portfolio_currencies: pd.DataFrame
    benchmark_currencies: pd.DataFrame


@dataclass(frozen=True)
class _CurrencyInputSchema:
    """Describe one of the two accepted currency-attribution frame families."""

    columns: tuple[str, ...]
    identifier_column: str
    weight_column: str
    return_columns: tuple[str, ...]


@dataclass
class _MarketGridResult:
    """Hold an independently calculated and reconciled market grid.

    Attributes:
        detail: One deterministic row of market effects per period and market.
        period_summary: Market returns and effect totals for each period.
    """

    detail: pd.DataFrame
    period_summary: pd.DataFrame


@dataclass
class _CurrencyGridResult:
    """Hold an independently calculated and reconciled currency grid.

    Attributes:
        detail: One deterministic row of currency effects per period and currency.
        period_summary: Currency returns and effect totals for each period.
    """

    detail: pd.DataFrame
    period_summary: pd.DataFrame


_MARKET_INPUT_SCHEMA = _CurrencyInputSchema(
    columns=CURRENCY_MARKET_INPUT_COLUMNS,
    identifier_column="market_identifier",
    weight_column="market_weight",
    return_columns=("local_asset_return", "local_cash_return"),
)
_CURRENCY_INPUT_SCHEMA = _CurrencyInputSchema(
    columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    identifier_column="currency_identifier",
    weight_column="currency_weight",
    return_columns=("base_currency_cash_return",),
)


def _require_dataframe(value: pd.DataFrame, name: str) -> None:
    """Require one public currency-attribution input to be a pandas DataFrame."""
    if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        value,
        pd.DataFrame,
    ):
        raise TypeError(f"{name} must be a pandas DataFrame")


def _normalize_base_currency(base_currency: str) -> str:
    """Validate and preserve the caller's exact base-currency identity.

    Args:
        base_currency: Proposed audit identity for every base-currency return.

    Returns:
        The unchanged valid identity.

    Raises:
        TypeError: If the identity is not a string.
        AttributionError: If the identity is empty or has surrounding whitespace.
    """
    if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        base_currency,
        str,
    ):
        raise TypeError("base_currency must be a string")
    if not base_currency or base_currency != base_currency.strip():
        raise AttributionError(
            "base_currency must be nonempty with no leading or trailing whitespace"
        )
    return base_currency


def _raise_input_error(context: str, message: str) -> None:
    """Raise one consistently contextualized currency input error."""
    raise_invalid(AttributionError, f"{context} input", message)


def _validate_period_structure(
    frame: pd.DataFrame,
    identifier_column: str,
    context: str,
) -> None:
    """Require unique identifiers and finite, nonoverlapping reporting periods."""
    key_columns = [*_PERIOD_COLUMNS, identifier_column]
    if _has_true(cast(pd.Series, frame.duplicated(key_columns))):
        _raise_input_error(context, "contains a duplicate period and identifier key")
    if _has_true(cast(pd.Series, frame["from_date"] > frame["thru_date"])):
        _raise_input_error(context, "contains a from_date after its thru_date")

    periods = cast(
        pd.DataFrame,
        frame.loc[:, list(_PERIOD_COLUMNS)].drop_duplicates(),
    )
    thru_dates = cast(pd.Series, periods["thru_date"])
    if _has_true(thru_dates.duplicated()):
        _raise_input_error(context, "maps one thru_date to more than one period")
    periods = cast(
        pd.DataFrame,
        periods.sort_values(["from_date", "thru_date"], kind="stable"),
    )
    if len(periods) > 1:
        starts = np.asarray(periods["from_date"], dtype="datetime64[ns]")
        ends = np.asarray(periods["thru_date"], dtype="datetime64[ns]")
        if np.any(starts[1:] <= ends[:-1]):
            _raise_input_error(context, "contains overlapping reporting periods")


def _validate_weight_totals(
    frame: pd.DataFrame,
    weight_column: str,
    context: str,
    tolerance: float,
) -> None:
    """Require one unit of total market or net currency exposure per period."""
    totals = cast(
        pd.Series,
        frame.groupby(
            list(_PERIOD_COLUMNS),
            sort=False,
            observed=True,
        )[weight_column].sum(),
    )
    weight_sums = np.asarray(totals, dtype=np.float64)
    if not _is_close(weight_sums, np.ones_like(weight_sums), tolerance).all():
        _raise_input_error(context, "weights must sum to 1.0 within tolerance")


def _normalize_currency_frame(
    frame: pd.DataFrame,
    *,
    schema: _CurrencyInputSchema,
    context: str,
    tolerance: float,
) -> pd.DataFrame:
    """Normalize one market or currency exposure input frame.

    Args:
        frame: Caller-owned input frame.
        schema: Exact columns and semantic roles for this frame family.
        context: Public parameter name used in validation errors.
        tolerance: Accepted relative and absolute weight-total tolerance.

    Returns:
        An independently owned canonical frame in deterministic order.

    Raises:
        AttributionError: If the schema, dates, identifiers, numerical values, return
            domain, period structure, or weight totals violate the accepted contract.
    """
    require_exact_columns(
        frame,
        schema.columns,
        f"{context} input",
        AttributionError,
    )
    if frame.empty:
        _raise_input_error(context, "must not be empty")

    normalized = cast(
        pd.DataFrame,
        frame.loc[:, list(schema.columns)].copy(deep=True),
    )
    for column in _PERIOD_COLUMNS:
        normalized[column] = normalize_dates(
            normalized,
            column,
            f"{context} input",
            AttributionError,
        )
    normalized[schema.identifier_column] = normalize_identity(
        normalized,
        schema.identifier_column,
        f"{context} input",
        AttributionError,
    )
    normalized[schema.weight_column] = normalize_numeric(
        normalized,
        schema.weight_column,
        f"{context} input",
        AttributionError,
        nullable=False,
    )
    for column in schema.return_columns:
        normalized[column] = normalize_numeric(
            normalized,
            column,
            f"{context} input",
            AttributionError,
            nullable=False,
        )
        if np.any(_float_array(normalized, column) <= -1.0):
            _raise_input_error(context, f"column {column!r} must be greater than -1.0")

    _validate_period_structure(normalized, schema.identifier_column, context)
    _validate_weight_totals(normalized, schema.weight_column, context, tolerance)
    return cast(
        pd.DataFrame,
        normalized.sort_values(
            ["thru_date", "from_date", schema.identifier_column],
            kind="stable",
        ),
    ).reset_index(drop=True)


def _period_keys(frame: pd.DataFrame) -> pd.MultiIndex:
    """Return chronologically ordered distinct reporting-period keys."""
    periods = cast(
        pd.DataFrame,
        frame.loc[:, list(_PERIOD_COLUMNS)].drop_duplicates(),
    ).sort_values(["thru_date", "from_date"], kind="stable")
    return pd.MultiIndex.from_frame(periods)


def _validate_aligned_periods(inputs: _NormalizedCurrencyInputs) -> None:
    """Require all four normalized frames to contain identical periods."""
    frames = (
        inputs.portfolio_markets,
        inputs.benchmark_markets,
        inputs.portfolio_currencies,
        inputs.benchmark_currencies,
    )
    expected = _period_keys(frames[0])
    if any(not _period_keys(frame).equals(expected) for frame in frames[1:]):
        raise AttributionError(
            "currency-attribution reporting periods must match exactly across all "
            "four inputs"
        )


def _identifier_keys(frame: pd.DataFrame, identifier_column: str) -> pd.MultiIndex:
    """Return sorted period-and-identifier keys for exact universe comparison."""
    keys = cast(
        pd.DataFrame,
        frame.loc[:, [*_PERIOD_COLUMNS, identifier_column]],
    ).sort_values(["thru_date", "from_date", identifier_column], kind="stable")
    return pd.MultiIndex.from_frame(keys)


def _validate_aligned_universe(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    identifier_column: str,
    family: str,
) -> None:
    """Require explicit zero rows instead of synthesizing a missing side."""
    portfolio_keys = _identifier_keys(portfolio, identifier_column)
    benchmark_keys = _identifier_keys(benchmark, identifier_column)
    if not portfolio_keys.equals(benchmark_keys):
        raise AttributionError(
            f"portfolio and benchmark {family} identifier universes must match "
            "exactly within every period"
        )


def _validate_common_cash_reference(
    portfolio_markets: pd.DataFrame,
    benchmark_markets: pd.DataFrame,
) -> None:
    """Require one exact local cash reference for each market and period."""
    key_columns = [*_PERIOD_COLUMNS, "market_identifier"]
    portfolio_cash = cast(
        pd.DataFrame,
        portfolio_markets.loc[:, [*key_columns, "local_cash_return"]],
    )
    benchmark_cash = cast(
        pd.DataFrame,
        benchmark_markets.loc[:, [*key_columns, "local_cash_return"]],
    )
    aligned = portfolio_cash.merge(
        benchmark_cash,
        on=key_columns,
        how="inner",
        suffixes=("_portfolio", "_benchmark"),
        validate="one_to_one",
        sort=False,
    )
    portfolio_values = _float_array(aligned, "local_cash_return_portfolio")
    benchmark_values = _float_array(aligned, "local_cash_return_benchmark")
    mismatched = portfolio_values != benchmark_values
    if np.any(mismatched):
        invalid = aligned.loc[mismatched].iloc[0]
        raise AttributionError(
            "portfolio and benchmark local_cash_return must match exactly at "
            f"{invalid['thru_date']:%Y-%m-%d} market "
            f"{invalid['market_identifier']!r}"
        )


def _normalize_currency_inputs(
    portfolio_markets: pd.DataFrame,
    benchmark_markets: pd.DataFrame,
    portfolio_currencies: pd.DataFrame,
    benchmark_currencies: pd.DataFrame,
    tolerance: float,
) -> _NormalizedCurrencyInputs:
    """Normalize and align all four currency-attribution input frames.

    Args:
        portfolio_markets: Caller-owned portfolio market rows.
        benchmark_markets: Caller-owned benchmark market rows.
        portfolio_currencies: Caller-owned portfolio currency-exposure rows.
        benchmark_currencies: Caller-owned benchmark currency-exposure rows.
        tolerance: Accepted weight-total tolerance.

    Returns:
        Four independently owned, deterministic, mutually aligned frames.

    Raises:
        AttributionError: If any frame or cross-frame identity violates Roadmap 12.
    """
    normalized = _NormalizedCurrencyInputs(
        portfolio_markets=_normalize_currency_frame(
            portfolio_markets,
            schema=_MARKET_INPUT_SCHEMA,
            context="portfolio_markets",
            tolerance=tolerance,
        ),
        benchmark_markets=_normalize_currency_frame(
            benchmark_markets,
            schema=_MARKET_INPUT_SCHEMA,
            context="benchmark_markets",
            tolerance=tolerance,
        ),
        portfolio_currencies=_normalize_currency_frame(
            portfolio_currencies,
            schema=_CURRENCY_INPUT_SCHEMA,
            context="portfolio_currencies",
            tolerance=tolerance,
        ),
        benchmark_currencies=_normalize_currency_frame(
            benchmark_currencies,
            schema=_CURRENCY_INPUT_SCHEMA,
            context="benchmark_currencies",
            tolerance=tolerance,
        ),
    )
    _validate_aligned_periods(normalized)
    _validate_aligned_universe(
        normalized.portfolio_markets,
        normalized.benchmark_markets,
        "market_identifier",
        "market",
    )
    _validate_aligned_universe(
        normalized.portfolio_currencies,
        normalized.benchmark_currencies,
        "currency_identifier",
        "currency",
    )
    _validate_common_cash_reference(
        normalized.portfolio_markets,
        normalized.benchmark_markets,
    )
    return normalized


def _market_working_frame(inputs: _NormalizedCurrencyInputs) -> pd.DataFrame:
    """Align market facts and calculate local log-return premiums.

    Args:
        inputs: Fully normalized and cross-frame validated inputs.

    Returns:
        A new aligned frame containing input facts, return premiums, and weighted
        market log-return contributions.

    Notes:
        A market return premium is the continuously compounded local asset return
        minus the continuously compounded common local cash return. ``log1p`` converts
        each caller-supplied ordinary simple return without requiring day counts.
    """
    portfolio = inputs.portfolio_markets
    benchmark = inputs.benchmark_markets
    working = pd.DataFrame(
        {
            "from_date": portfolio["from_date"],
            "thru_date": portfolio["thru_date"],
            "market_identifier": portfolio["market_identifier"],
            "portfolio_market_weight": portfolio["market_weight"],
            "portfolio_local_asset_return": portfolio["local_asset_return"],
            "benchmark_market_weight": benchmark["market_weight"],
            "benchmark_local_asset_return": benchmark["local_asset_return"],
            "local_cash_return": portfolio["local_cash_return"],
        }
    )
    with np.errstate(over="ignore", invalid="ignore"):
        cash_log_return = np.log1p(_float_array(working, "local_cash_return"))
        working["portfolio_local_log_return_premium"] = np.log1p(
            _float_array(working, "portfolio_local_asset_return")
        ) - cash_log_return
        working["benchmark_local_log_return_premium"] = np.log1p(
            _float_array(working, "benchmark_local_asset_return")
        ) - cash_log_return
        working["_portfolio_market_log_contribution"] = _float_array(
            working, "portfolio_market_weight"
        ) * _float_array(working, "portfolio_local_log_return_premium")
        working["_benchmark_market_log_contribution"] = _float_array(
            working, "benchmark_market_weight"
        ) * _float_array(working, "benchmark_local_log_return_premium")
    return working


def _market_period_components(working: pd.DataFrame) -> pd.DataFrame:
    """Sum portfolio and benchmark market log-return contributions by period."""
    components = _sum_by_period(
        working,
        (
            "_portfolio_market_log_contribution",
            "_benchmark_market_log_contribution",
        ),
    ).rename(
        columns={
            "_portfolio_market_log_contribution": "portfolio_market_log_return",
            "_benchmark_market_log_contribution": "benchmark_market_log_return",
        }
    )
    components["active_market_log_return"] = (
        _float_array(components, "portfolio_market_log_return")
        - _float_array(components, "benchmark_market_log_return")
    )
    return components


def _calculate_market_detail(
    working: pd.DataFrame,
    period_components: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate the accepted two-channel market attribution detail.

    Market allocation uses the benchmark aggregate return premium as the
    Brinson-Fachler opportunity-set reference. Security selection uses portfolio
    market weight, thereby absorbing the allocation-selection cross-product without
    constructing a separate interaction column.
    """
    aligned = working.merge(
        period_components.loc[
            :, [*_PERIOD_COLUMNS, "benchmark_market_log_return"]
        ],
        on=list(_PERIOD_COLUMNS),
        how="left",
        validate="many_to_one",
        sort=False,
    )
    with np.errstate(over="ignore", invalid="ignore"):
        aligned["active_market_weight"] = (
            _float_array(aligned, "portfolio_market_weight")
            - _float_array(aligned, "benchmark_market_weight")
        )
        aligned["active_local_log_return_premium"] = (
            _float_array(aligned, "portfolio_local_log_return_premium")
            - _float_array(aligned, "benchmark_local_log_return_premium")
        )
        aligned["market_allocation_log_effect"] = _float_array(
            aligned, "active_market_weight"
        ) * (
            _float_array(aligned, "benchmark_local_log_return_premium")
            - _float_array(aligned, "benchmark_market_log_return")
        )
        aligned["security_selection_log_effect"] = _float_array(
            aligned, "portfolio_market_weight"
        ) * _float_array(aligned, "active_local_log_return_premium")
        aligned["total_log_effect"] = (
            _float_array(aligned, "market_allocation_log_effect")
            + _float_array(aligned, "security_selection_log_effect")
        )
    return cast(
        pd.DataFrame,
        aligned.loc[:, list(CURRENCY_MARKET_DETAIL_COLUMNS)].copy(),
    )


def _validate_grid_values(
    detail: pd.DataFrame,
    period_summary: pd.DataFrame,
    active_return_column: str,
    context: str,
    tolerance: float,
) -> None:
    """Require finite grid results and its period effect identity."""
    detail_values = detail.select_dtypes(include=["number"]).to_numpy(dtype=np.float64)
    summary_values = period_summary.select_dtypes(include=["number"]).to_numpy(
        dtype=np.float64
    )
    if not np.isfinite(detail_values).all() or not np.isfinite(summary_values).all():
        raise AttributionError(f"{context}-grid calculation produced a non-finite value")
    if not _is_close(
        _float_array(period_summary, "total_log_effect"),
        _float_array(period_summary, active_return_column),
        tolerance,
    ).all():
        raise AttributionError(f"{context}-grid reconciliation failed")


def _calculate_market_grid(
    inputs: _NormalizedCurrencyInputs,
    tolerance: float,
) -> _MarketGridResult:
    """Calculate and reconcile the Roadmap 12 market grid.

    Args:
        inputs: Fully normalized and cross-frame validated inputs.
        tolerance: Positive relative and absolute reconciliation tolerance.

    Returns:
        Independently owned market detail and period-summary frames.

    Raises:
        AttributionError: If an output is non-finite or market effects do not
            reconcile to the modeled active market log return.
    """
    working = _market_working_frame(inputs)
    period_components = _market_period_components(working)
    detail = _calculate_market_detail(working, period_components)
    effect_totals = _sum_by_period(
        detail,
        (
            "market_allocation_log_effect",
            "security_selection_log_effect",
            "total_log_effect",
        ),
    )
    period_summary = cast(
        pd.DataFrame,
        period_components.merge(
            effect_totals,
            on=list(_PERIOD_COLUMNS),
            how="inner",
            validate="one_to_one",
            sort=False,
        ).loc[:, list(_MARKET_GRID_SUMMARY_COLUMNS)],
    ).reset_index(drop=True)
    _validate_grid_values(
        detail,
        period_summary,
        "active_market_log_return",
        "market",
        tolerance,
    )
    return _MarketGridResult(
        detail=detail.reset_index(drop=True),
        period_summary=period_summary,
    )


def _currency_working_frame(inputs: _NormalizedCurrencyInputs) -> pd.DataFrame:
    """Align currency facts and calculate base-currency cash log returns.

    Args:
        inputs: Fully normalized and cross-frame validated inputs.

    Returns:
        A new aligned frame containing exposures, simple returns, log returns, and
        weighted currency log-return contributions.

    Notes:
        The weights are caller-supplied net currency exposures. This calculation does
        not infer holdings, hedge instruments, notionals, or exposure conventions.
    """
    portfolio = inputs.portfolio_currencies
    benchmark = inputs.benchmark_currencies
    working = pd.DataFrame(
        {
            "from_date": portfolio["from_date"],
            "thru_date": portfolio["thru_date"],
            "currency_identifier": portfolio["currency_identifier"],
            "portfolio_currency_weight": portfolio["currency_weight"],
            "portfolio_base_currency_cash_return": portfolio[
                "base_currency_cash_return"
            ],
            "benchmark_currency_weight": benchmark["currency_weight"],
            "benchmark_base_currency_cash_return": benchmark[
                "base_currency_cash_return"
            ],
        }
    )
    with np.errstate(over="ignore", invalid="ignore"):
        working["portfolio_base_currency_cash_log_return"] = np.log1p(
            _float_array(working, "portfolio_base_currency_cash_return")
        )
        working["benchmark_base_currency_cash_log_return"] = np.log1p(
            _float_array(working, "benchmark_base_currency_cash_return")
        )
        working["_portfolio_currency_log_contribution"] = _float_array(
            working, "portfolio_currency_weight"
        ) * _float_array(working, "portfolio_base_currency_cash_log_return")
        working["_benchmark_currency_log_contribution"] = _float_array(
            working, "benchmark_currency_weight"
        ) * _float_array(working, "benchmark_base_currency_cash_log_return")
    return working


def _currency_period_components(working: pd.DataFrame) -> pd.DataFrame:
    """Sum portfolio and benchmark currency log contributions by period."""
    components = _sum_by_period(
        working,
        (
            "_portfolio_currency_log_contribution",
            "_benchmark_currency_log_contribution",
        ),
    ).rename(
        columns={
            "_portfolio_currency_log_contribution": "portfolio_currency_log_return",
            "_benchmark_currency_log_contribution": "benchmark_currency_log_return",
        }
    )
    components["active_currency_log_return"] = (
        _float_array(components, "portfolio_currency_log_return")
        - _float_array(components, "benchmark_currency_log_return")
    )
    return components


def _calculate_currency_detail(
    working: pd.DataFrame,
    period_components: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate currency allocation and portfolio-weighted hedge selection.

    Currency allocation compares active exposure with the benchmark currency return
    relative to its period aggregate. Hedge selection uses portfolio exposure, so it
    absorbs the allocation-selection cross-product without a separate interaction
    column.
    """
    aligned = working.merge(
        period_components.loc[
            :, [*_PERIOD_COLUMNS, "benchmark_currency_log_return"]
        ],
        on=list(_PERIOD_COLUMNS),
        how="left",
        validate="many_to_one",
        sort=False,
    )
    with np.errstate(over="ignore", invalid="ignore"):
        aligned["active_currency_weight"] = (
            _float_array(aligned, "portfolio_currency_weight")
            - _float_array(aligned, "benchmark_currency_weight")
        )
        aligned["active_base_currency_cash_log_return"] = (
            _float_array(aligned, "portfolio_base_currency_cash_log_return")
            - _float_array(aligned, "benchmark_base_currency_cash_log_return")
        )
        aligned["currency_allocation_log_effect"] = _float_array(
            aligned, "active_currency_weight"
        ) * (
            _float_array(aligned, "benchmark_base_currency_cash_log_return")
            - _float_array(aligned, "benchmark_currency_log_return")
        )
        aligned["hedge_selection_log_effect"] = _float_array(
            aligned, "portfolio_currency_weight"
        ) * _float_array(aligned, "active_base_currency_cash_log_return")
        aligned["total_log_effect"] = (
            _float_array(aligned, "currency_allocation_log_effect")
            + _float_array(aligned, "hedge_selection_log_effect")
        )
    return cast(
        pd.DataFrame,
        aligned.loc[:, list(CURRENCY_DETAIL_COLUMNS)].copy(),
    )


def _calculate_currency_grid(
    inputs: _NormalizedCurrencyInputs,
    tolerance: float,
) -> _CurrencyGridResult:
    """Calculate and reconcile the Roadmap 12 currency grid.

    Args:
        inputs: Fully normalized and cross-frame validated inputs.
        tolerance: Positive relative and absolute reconciliation tolerance.

    Returns:
        Independently owned currency detail and period-summary frames.

    Raises:
        AttributionError: If an output is non-finite or currency effects do not
            reconcile to the modeled active currency log return.
    """
    working = _currency_working_frame(inputs)
    period_components = _currency_period_components(working)
    detail = _calculate_currency_detail(working, period_components)
    effect_totals = _sum_by_period(
        detail,
        (
            "currency_allocation_log_effect",
            "hedge_selection_log_effect",
            "total_log_effect",
        ),
    )
    period_summary = cast(
        pd.DataFrame,
        period_components.merge(
            effect_totals,
            on=list(_PERIOD_COLUMNS),
            how="inner",
            validate="one_to_one",
            sort=False,
        ).loc[:, list(_CURRENCY_GRID_SUMMARY_COLUMNS)],
    ).reset_index(drop=True)
    _validate_grid_values(
        detail,
        period_summary,
        "active_currency_log_return",
        "currency",
        tolerance,
    )
    return _CurrencyGridResult(
        detail=detail.reset_index(drop=True),
        period_summary=period_summary,
    )


def _build_period_summary(
    market: _MarketGridResult,
    currency: _CurrencyGridResult,
) -> pd.DataFrame:
    """Combine both independently reconciled grids into four effect channels."""
    market_summary = market.period_summary.rename(
        columns={"total_log_effect": "_market_log_effect_sum"}
    )
    currency_summary = currency.period_summary.rename(
        columns={"total_log_effect": "_currency_log_effect_sum"}
    )
    summary = market_summary.merge(
        currency_summary,
        on=list(_PERIOD_COLUMNS),
        how="inner",
        validate="one_to_one",
        sort=False,
    )
    with np.errstate(over="ignore", invalid="ignore"):
        summary["portfolio_total_log_return"] = (
            _float_array(summary, "portfolio_market_log_return")
            + _float_array(summary, "portfolio_currency_log_return")
        )
        summary["benchmark_total_log_return"] = (
            _float_array(summary, "benchmark_market_log_return")
            + _float_array(summary, "benchmark_currency_log_return")
        )
        summary["active_total_log_return"] = (
            _float_array(summary, "portfolio_total_log_return")
            - _float_array(summary, "benchmark_total_log_return")
        )
        summary["total_log_effect"] = (
            _float_array(summary, "_market_log_effect_sum")
            + _float_array(summary, "_currency_log_effect_sum")
        )
    return cast(
        pd.DataFrame,
        summary.loc[:, list(CURRENCY_PERIOD_SUMMARY_COLUMNS)].copy(),
    ).reset_index(drop=True)


def _build_currency_reconciliation(
    market: _MarketGridResult,
    currency: _CurrencyGridResult,
    period_summary: pd.DataFrame,
    tolerance: float,
) -> pd.DataFrame:
    """Build and validate the three accepted period reconciliation identities."""
    market_summary = market.period_summary
    currency_summary = currency.period_summary
    reconciliation = pd.DataFrame(
        {
            "from_date": period_summary["from_date"],
            "thru_date": period_summary["thru_date"],
            "market_log_effect_sum": market_summary["total_log_effect"],
            "active_market_log_return": period_summary["active_market_log_return"],
            "currency_log_effect_sum": currency_summary["total_log_effect"],
            "active_currency_log_return": period_summary[
                "active_currency_log_return"
            ],
            "total_log_effect_sum": period_summary["total_log_effect"],
            "active_total_log_return": period_summary["active_total_log_return"],
        }
    )
    reconciliation["market_reconciled"] = _is_close(
        _float_array(reconciliation, "market_log_effect_sum"),
        _float_array(reconciliation, "active_market_log_return"),
        tolerance,
    )
    reconciliation["currency_reconciled"] = _is_close(
        _float_array(reconciliation, "currency_log_effect_sum"),
        _float_array(reconciliation, "active_currency_log_return"),
        tolerance,
    )
    reconciliation["total_reconciled"] = _is_close(
        _float_array(reconciliation, "total_log_effect_sum"),
        _float_array(reconciliation, "active_total_log_return"),
        tolerance,
    )
    reconciliation = cast(
        pd.DataFrame,
        reconciliation.loc[:, list(CURRENCY_RECONCILIATION_COLUMNS)].copy(),
    ).reset_index(drop=True)
    numeric_values = reconciliation.select_dtypes(include=["number"]).to_numpy(
        dtype=np.float64
    )
    flags = reconciliation.loc[
        :, ["market_reconciled", "currency_reconciled", "total_reconciled"]
    ].to_numpy(dtype=np.bool_)
    if not np.isfinite(numeric_values).all():
        raise AttributionError("currency-attribution calculation produced a non-finite value")
    if not flags.all():
        raise AttributionError("currency-attribution reconciliation failed")
    return reconciliation


# Four independent frames and two keyword-only policies are the accepted public
# boundary; combining them would obscure portfolio/benchmark or market/currency roles.
def calculate_currency_attribution(  # pylint: disable=too-many-arguments
    portfolio_markets: pd.DataFrame,
    benchmark_markets: pd.DataFrame,
    portfolio_currencies: pd.DataFrame,
    benchmark_currencies: pd.DataFrame,
    *,
    base_currency: str,
    reconciliation_tolerance: float = 1e-12,
) -> CurrencyAttributionResult:
    """Calculate single-period Karnosky-Singer currency attribution.

    Args:
        portfolio_markets: Prepared portfolio market weights and local returns.
        benchmark_markets: Prepared benchmark market weights and local returns.
        portfolio_currencies: Prepared portfolio net currency exposures and returns.
        benchmark_currencies: Prepared benchmark net currency exposures and returns.
        base_currency: Nonempty audit identity for all base-currency returns.
        reconciliation_tolerance: Positive finite relative and absolute tolerance for
            input validation and financial reconciliation.

    Returns:
        Independently owned market detail, currency detail, period summary, and
        reconciliation frames together with the preserved base-currency identity.

    Raises:
        TypeError: If an input is not a pandas DataFrame, the base currency is not a
            string, or the tolerance is not a non-boolean real number.
        AttributionError: If the base currency, tolerance, any input frame, or their
            cross-frame alignment violates the accepted contract; a calculation is
            non-finite; or a market, currency, or total identity fails.

    Notes:
        Callers supply ordinary simple period returns. Both grids convert their return
        inputs with ``numpy.log1p`` and report effects in log-return units. Currency
        weights are caller-selected net exposures and may be signed. Portfolio-weighted
        selection absorbs each grid's interaction. The function does not infer
        exposures, link periods, roll up hierarchies, or add an accounting residual.

    References:
        Karnosky, Denis S., and Brian D. Singer. *Global Asset Management and
        Performance Attribution*. Research Foundation of the Institute of Chartered
        Financial Analysts, 1994.
    """
    for name, value in (
        ("portfolio_markets", portfolio_markets),
        ("benchmark_markets", benchmark_markets),
        ("portfolio_currencies", portfolio_currencies),
        ("benchmark_currencies", benchmark_currencies),
    ):
        _require_dataframe(value, name)
    normalized_base_currency = _normalize_base_currency(base_currency)
    tolerance = normalize_reconciliation_tolerance(
        reconciliation_tolerance,
        AttributionError,
    )
    normalized = _normalize_currency_inputs(
        portfolio_markets,
        benchmark_markets,
        portfolio_currencies,
        benchmark_currencies,
        tolerance,
    )
    market = _calculate_market_grid(normalized, tolerance)
    currency = _calculate_currency_grid(normalized, tolerance)
    period_summary = _build_period_summary(market, currency)
    reconciliation = _build_currency_reconciliation(
        market,
        currency,
        period_summary,
        tolerance,
    )
    return CurrencyAttributionResult(
        market_detail=market.detail,
        currency_detail=currency.detail,
        period_summary=period_summary,
        reconciliation=reconciliation,
        base_currency=normalized_base_currency,
    )


__all__ = ["CurrencyAttributionResult", "calculate_currency_attribution"]
