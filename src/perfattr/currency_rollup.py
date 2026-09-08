"""Calculate and reconcile multi-period currency-attribution roll-ups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd

from perfattr._currency_rollup_source import (
    _ValidatedCurrencyResult,
    validate_source_result,
)
from perfattr._exceptions import AttributionError
from perfattr._reconciliation import _validate_result_values
from perfattr._schemas import (
    CURRENCY_ROLLUP_CUMULATIVE_CHECKS,
    CURRENCY_ROLLUP_CUMULATIVE_COLUMNS,
    CURRENCY_ROLLUP_CURRENCY_OVERALL_COLUMNS,
    CURRENCY_ROLLUP_MARKET_OVERALL_COLUMNS,
    CURRENCY_ROLLUP_OVERALL_CHECKS,
    CURRENCY_ROLLUP_RECONCILIATION_COLUMNS,
)
from perfattr._validation import float_array as _float_array
from perfattr._validation import is_close as _is_close
from perfattr._validation import normalize_reconciliation_tolerance
from perfattr.currency import CurrencyAttributionResult


_OVERALL_SCHEMAS = {
    "market_identifier": (
        (
            "market_allocation_log_effect",
            "security_selection_log_effect",
            "total_log_effect",
        ),
        CURRENCY_ROLLUP_MARKET_OVERALL_COLUMNS,
        "currency roll-up market_overall_detail",
    ),
    "currency_identifier": (
        (
            "currency_allocation_log_effect",
            "hedge_selection_log_effect",
            "total_log_effect",
        ),
        CURRENCY_ROLLUP_CURRENCY_OVERALL_COLUMNS,
        "currency roll-up currency_overall_detail",
    ),
}


@dataclass
class CurrencyAttributionRollupResult:
    """Hold cumulative and full-horizon currency-attribution roll-ups.

    Attributes:
        market_overall_detail: Full-horizon log effects by market identifier.
        currency_overall_detail: Full-horizon log effects by currency identifier.
        cumulative: Chronological cumulative log-return and log-effect prefixes.
        reconciliation: Passing cumulative and full-horizon reconciliation evidence.
        base_currency: Base-currency identity preserved from the source result.

    Notes:
        Direct construction is ordinary dataclass construction and does not validate
        or copy frames. The roll-up function returns independently owned frames
        without mutating its source result.
    """

    market_overall_detail: pd.DataFrame
    currency_overall_detail: pd.DataFrame
    cumulative: pd.DataFrame
    reconciliation: pd.DataFrame
    base_currency: str


@dataclass
class _CurrencyRollupFrames:
    """Hold the three calculated financial output frames.

    Attributes:
        market_overall_detail: Full-horizon effects by market identifier.
        currency_overall_detail: Full-horizon effects by currency identifier.
        cumulative: Chronological cumulative log-return and log-effect prefixes.
    """

    market_overall_detail: pd.DataFrame
    currency_overall_detail: pd.DataFrame
    cumulative: pd.DataFrame


def _repeated_date(value: pd.Timestamp, length: int) -> pd.Series:
    """Return one normalized timestamp repeated with exact nanosecond dtype."""
    return pd.Series(
        np.repeat(value.to_datetime64(), length),
        dtype="datetime64[ns]",
    )


def _build_overall_detail(
    detail: pd.DataFrame,
    period_summary: pd.DataFrame,
    identifier_column: str,
) -> pd.DataFrame:
    """Sum one attribution grid's effects by full-horizon identifier.

    Args:
        detail: Validated period-identifier source effects.
        period_summary: Validated chronological source periods.
        identifier_column: Market or currency identity column.

    Returns:
        A new canonical full-horizon identifier-effect frame.

    Raises:
        AttributionError: If aggregation produces a non-finite value.
    """
    effect_columns, result_columns, context = _OVERALL_SCHEMAS[identifier_column]
    totals = cast(
        pd.DataFrame,
        detail.groupby(
            identifier_column,
            as_index=False,
            sort=True,
            observed=True,
        )[list(effect_columns)].sum(),
    ).reset_index(drop=True)
    horizon_start = cast(pd.Timestamp, period_summary.at[0, "from_date"])
    horizon_end = cast(pd.Timestamp, period_summary.at[len(period_summary) - 1, "thru_date"])
    overall = pd.DataFrame(
        {
            "from_date": _repeated_date(horizon_start, len(totals)),
            "thru_date": _repeated_date(horizon_end, len(totals)),
            identifier_column: cast(
                pd.Series,
                totals[identifier_column].reset_index(drop=True),
            ),
            **{
                column: np.asarray(totals[column], dtype=np.float64)
                for column in effect_columns
            },
        },
        columns=result_columns,
    )
    _validate_result_values(context, overall)
    return overall


def _build_cumulative(period_summary: pd.DataFrame) -> pd.DataFrame:
    """Directly sum every period log-return and log-effect column by prefix.

    Args:
        period_summary: Validated chronological source-period values.

    Returns:
        A new canonical frame with one cumulative prefix per supplied period.

    Raises:
        AttributionError: If cumulative addition produces a non-finite value.

    Notes:
        Continuously compounded returns and the accepted effects share one additive
        log-return basis. No weight, return, or day-count averaging is performed.
    """
    numeric_columns = CURRENCY_ROLLUP_CUMULATIVE_COLUMNS[2:]
    source_values = period_summary.loc[:, list(numeric_columns)].to_numpy(
        dtype=np.float64
    )
    with np.errstate(over="ignore", invalid="ignore"):
        cumulative_values = np.cumsum(source_values, axis=0, dtype=np.float64)
    cumulative = pd.DataFrame(cumulative_values, columns=numeric_columns)
    horizon_start = cast(pd.Timestamp, period_summary.at[0, "from_date"])
    cumulative.insert(0, "thru_date", period_summary["thru_date"].reset_index(drop=True))
    cumulative.insert(0, "from_date", _repeated_date(horizon_start, len(cumulative)))
    cumulative = cast(
        pd.DataFrame,
        cumulative.loc[:, list(CURRENCY_ROLLUP_CUMULATIVE_COLUMNS)],
    ).reset_index(drop=True)
    _validate_result_values("currency roll-up cumulative", cumulative)
    return cumulative


def _calculate_currency_rollup(
    result: _ValidatedCurrencyResult,
) -> _CurrencyRollupFrames:
    """Calculate all additive Roadmap 13 financial output frames.

    Args:
        result: Independently copied and validated source-result values.

    Returns:
        Three independently owned frames used to build reconciliation.

    Raises:
        AttributionError: If any aggregate or cumulative value is non-finite.
    """
    return _CurrencyRollupFrames(
        market_overall_detail=_build_overall_detail(
            result.market_detail,
            result.period_summary,
            "market_identifier",
        ),
        currency_overall_detail=_build_overall_detail(
            result.currency_detail,
            result.period_summary,
            "currency_identifier",
        ),
        cumulative=_build_cumulative(result.period_summary),
    )


def _build_cumulative_reconciliation(
    source: _ValidatedCurrencyResult,
    result: _CurrencyRollupFrames,
) -> pd.DataFrame:
    """Build the fifteen accepted checks for every cumulative prefix.

    Args:
        source: Independently validated chronological source periods.
        result: Calculated cumulative and horizon frames.

    Returns:
        Unfinished cumulative reconciliation rows in their exact stable order.

    Notes:
        The six roll-up checks independently accumulate the source portfolio and
        benchmark grid totals. Remaining checks reconstruct active, component, and
        effect identities from the returned cumulative values.
    """
    cumulative = result.cumulative
    values = {
        column: _float_array(cumulative, column)
        for column in CURRENCY_ROLLUP_CUMULATIVE_COLUMNS[2:]
    }
    source_rollups = {
        column: np.add.accumulate(_float_array(source.period_summary, column))
        for column in CURRENCY_ROLLUP_CUMULATIVE_COLUMNS[2:]
    }
    actual = np.column_stack(
        (
            values["portfolio_market_log_return"],
            values["benchmark_market_log_return"],
            values["active_market_log_return"],
            values["market_allocation_log_effect"]
            + values["security_selection_log_effect"],
            values["portfolio_currency_log_return"],
            values["benchmark_currency_log_return"],
            values["active_currency_log_return"],
            values["currency_allocation_log_effect"]
            + values["hedge_selection_log_effect"],
            values["portfolio_total_log_return"],
            values["benchmark_total_log_return"],
            values["portfolio_total_log_return"],
            values["benchmark_total_log_return"],
            values["active_total_log_return"],
            values["active_total_log_return"],
            values["total_log_effect"],
        )
    )
    expected = np.column_stack(
        (
            source_rollups["portfolio_market_log_return"],
            source_rollups["benchmark_market_log_return"],
            values["portfolio_market_log_return"]
            - values["benchmark_market_log_return"],
            values["active_market_log_return"],
            source_rollups["portfolio_currency_log_return"],
            source_rollups["benchmark_currency_log_return"],
            values["portfolio_currency_log_return"]
            - values["benchmark_currency_log_return"],
            values["active_currency_log_return"],
            source_rollups["portfolio_total_log_return"],
            source_rollups["benchmark_total_log_return"],
            values["portfolio_market_log_return"]
            + values["portfolio_currency_log_return"],
            values["benchmark_market_log_return"]
            + values["benchmark_currency_log_return"],
            values["portfolio_total_log_return"]
            - values["benchmark_total_log_return"],
            values["active_market_log_return"]
            + values["active_currency_log_return"],
            values["active_total_log_return"],
        )
    )
    check_count = len(CURRENCY_ROLLUP_CUMULATIVE_CHECKS)
    return pd.DataFrame(
        {
            "scope": "cumulative",
            "from_date": np.repeat(
                np.asarray(cumulative["from_date"], dtype="datetime64[ns]"),
                check_count,
            ),
            "thru_date": np.repeat(
                np.asarray(cumulative["thru_date"], dtype="datetime64[ns]"),
                check_count,
            ),
            "check": np.tile(CURRENCY_ROLLUP_CUMULATIVE_CHECKS, len(cumulative)),
            "actual": actual.ravel(),
            "expected": expected.ravel(),
        }
    )


def _column_sum(frame: pd.DataFrame, column: str) -> float:
    """Return one finite result-column total as an ordinary float."""
    return float(_float_array(frame, column).sum())


def _validate_overall_rows(
    result: _CurrencyRollupFrames,
    tolerance: float,
) -> None:
    """Require every identifier total to equal its two effect components."""
    for name, frame, first_component, second_component in (
        (
            "market_overall_detail",
            result.market_overall_detail,
            "market_allocation_log_effect",
            "security_selection_log_effect",
        ),
        (
            "currency_overall_detail",
            result.currency_overall_detail,
            "currency_allocation_log_effect",
            "hedge_selection_log_effect",
        ),
    ):
        with np.errstate(over="ignore", invalid="ignore"):
            components = _float_array(frame, first_component) + _float_array(
                frame, second_component
            )
            passed = _is_close(
                _float_array(frame, "total_log_effect"),
                components,
                tolerance,
            )
        if not passed.all():
            raise AttributionError(
                f"currency roll-up {name} has invalid effect components"
            )


def _build_overall_reconciliation(
    result: _CurrencyRollupFrames,
    tolerance: float,
) -> pd.DataFrame:
    """Build the six accepted full-horizon identifier-detail checks."""
    _validate_overall_rows(result, tolerance)
    market = result.market_overall_detail
    currency = result.currency_overall_detail
    cumulative = result.cumulative
    final_values = {
        column: cast(float, cumulative.at[len(cumulative) - 1, column])
        for column in CURRENCY_ROLLUP_CUMULATIVE_COLUMNS[2:]
    }
    actual = np.asarray(
        [
            _column_sum(market, "market_allocation_log_effect"),
            _column_sum(market, "security_selection_log_effect"),
            _column_sum(market, "total_log_effect"),
            _column_sum(currency, "currency_allocation_log_effect"),
            _column_sum(currency, "hedge_selection_log_effect"),
            _column_sum(currency, "total_log_effect"),
        ],
        dtype=np.float64,
    )
    expected = np.asarray(
        [
            final_values["market_allocation_log_effect"],
            final_values["security_selection_log_effect"],
            final_values["active_market_log_return"],
            final_values["currency_allocation_log_effect"],
            final_values["hedge_selection_log_effect"],
            final_values["active_currency_log_return"],
        ],
        dtype=np.float64,
    )
    horizon_start = cast(pd.Timestamp, cumulative.at[0, "from_date"])
    horizon_end = cast(pd.Timestamp, cumulative.at[len(cumulative) - 1, "thru_date"])
    return pd.DataFrame(
        {
            "scope": "overall",
            "from_date": _repeated_date(horizon_start, len(actual)),
            "thru_date": _repeated_date(horizon_end, len(actual)),
            "check": CURRENCY_ROLLUP_OVERALL_CHECKS,
            "actual": actual,
            "expected": expected,
        }
    )


def _finalize_reconciliation(
    reconciliation: pd.DataFrame,
    tolerance: float,
) -> pd.DataFrame:
    """Evaluate, canonicalize, and require all roll-up checks to pass."""
    actual = _float_array(reconciliation, "actual")
    expected = _float_array(reconciliation, "expected")
    with np.errstate(over="ignore", invalid="ignore"):
        reconciliation["difference"] = actual - expected
        reconciliation["passed"] = _is_close(actual, expected, tolerance)
    reconciliation["tolerance"] = tolerance
    reconciliation = cast(
        pd.DataFrame,
        reconciliation.loc[:, list(CURRENCY_ROLLUP_RECONCILIATION_COLUMNS)],
    )
    reconciliation["scope"] = reconciliation["scope"].astype("string[python]")
    reconciliation["check"] = reconciliation["check"].astype("string[python]")
    reconciliation["passed"] = reconciliation["passed"].astype("bool")
    _validate_result_values("currency roll-up reconciliation", reconciliation)
    passed = np.asarray(reconciliation["passed"], dtype=np.bool_)
    if not passed.all():
        failed = reconciliation.loc[~reconciliation["passed"]].iloc[0]
        raise AttributionError(
            "currency roll-up reconciliation failed for "
            f"{failed['scope']} {failed['thru_date']:%Y-%m-%d} {failed['check']}"
        )
    return reconciliation.reset_index(drop=True)


def _build_rollup_reconciliation(
    source: _ValidatedCurrencyResult,
    result: _CurrencyRollupFrames,
    tolerance: float,
) -> pd.DataFrame:
    """Build complete positive cumulative and horizon reconciliation evidence."""
    unfinished = pd.concat(
        [
            _build_cumulative_reconciliation(source, result),
            _build_overall_reconciliation(result, tolerance),
        ],
        ignore_index=True,
    )
    return _finalize_reconciliation(unfinished, tolerance)


def roll_up_currency_attribution(
    result: CurrencyAttributionResult,
    *,
    reconciliation_tolerance: float = 1e-12,
) -> CurrencyAttributionRollupResult:
    """Roll period currency attribution into cumulative and horizon log effects.

    Args:
        result: Completed single-period currency-attribution result for one or more
            reporting periods.
        reconciliation_tolerance: Positive finite relative and absolute tolerance for
            source validation and roll-up reconciliation.

    Returns:
        Independently owned market and currency horizon detail, cumulative prefixes,
        reconciliation evidence, and the preserved base-currency identity.

    Raises:
        TypeError: If ``result`` is not a :class:`CurrencyAttributionResult` or the
            tolerance is not a non-boolean real number.
        AttributionError: If the tolerance, source result, calculated aggregates, or
            reconciliation evidence violates the accepted contract.

    Notes:
        Log-return and log-effect values add directly across supplied periods. The
        function does not average weights or returns, fill period gaps, or synthesize
        missing identifier rows. The final cumulative row covers the complete supplied
        horizon. Overall identifier rows contain effects only.

        A gap represents an omitted observation, not a zero-return period. A caller
        may convert an aggregate return with :func:`numpy.expm1`, but must not convert
        individual effects independently because they reconcile additively in log
        units. Accounting reconciliation, separate interactions, hierarchical
        currency attribution, and host integration are outside this operation.

    Examples:
        Roll up a completed result from :func:`calculate_currency_attribution`::

            rollup = roll_up_currency_attribution(currency_result)
            complete_horizon = rollup.cumulative.iloc[-1]
    """
    if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        result,
        CurrencyAttributionResult,
    ):
        raise TypeError("result must be a CurrencyAttributionResult")
    tolerance = normalize_reconciliation_tolerance(
        reconciliation_tolerance,
        AttributionError,
    )
    validated = validate_source_result(result, tolerance)
    calculated = _calculate_currency_rollup(validated)
    reconciliation = _build_rollup_reconciliation(
        validated,
        calculated,
        tolerance,
    )
    return CurrencyAttributionRollupResult(
        market_overall_detail=calculated.market_overall_detail,
        currency_overall_detail=calculated.currency_overall_detail,
        cumulative=calculated.cumulative,
        reconciliation=reconciliation,
        base_currency=validated.base_currency,
    )


__all__ = [
    "CurrencyAttributionRollupResult",
    "roll_up_currency_attribution",
]
