"""Validate mutable currency-attribution results before multi-period roll-up."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import numpy.typing as npt
import pandas as pd

from perfattr._exceptions import AttributionError
from perfattr._reconciliation import _validate_result_values
from perfattr._schemas import (
    CURRENCY_DETAIL_COLUMNS,
    CURRENCY_MARKET_DETAIL_COLUMNS,
    CURRENCY_PERIOD_SUMMARY_COLUMNS,
    CURRENCY_RECONCILIATION_COLUMNS,
)
from perfattr._validation import float_array as _float_array
from perfattr._validation import is_close as _is_close
from perfattr.currency import CurrencyAttributionResult


_PERIOD_COLUMNS = ("from_date", "thru_date")
_DATE_COLUMNS = frozenset(_PERIOD_COLUMNS)
_STRING_COLUMNS = frozenset({"market_identifier", "currency_identifier"})
_FLAG_COLUMNS = (
    "market_reconciled",
    "currency_reconciled",
    "total_reconciled",
)
_FloatArray = npt.NDArray[np.float64]


@dataclass
class _ValidatedCurrencyResult:
    """Hold independently owned, validated source-result values.

    Attributes:
        base_currency: Validated source base-currency identity.
        market_detail: Canonical market rows in deterministic order.
        currency_detail: Canonical currency rows in deterministic order.
        period_summary: Canonical period summaries in chronological order.
        reconciliation: Canonical released reconciliation evidence.
    """

    base_currency: str
    market_detail: pd.DataFrame
    currency_detail: pd.DataFrame
    period_summary: pd.DataFrame
    reconciliation: pd.DataFrame


def _has_canonical_dtype(column: str, values: pd.Series) -> bool:
    """Return whether one source-result column has its released dtype."""
    expected_dtype = np.dtype("float64")
    if column in _DATE_COLUMNS:
        expected_dtype = np.dtype("datetime64[ns]")
    elif column in _FLAG_COLUMNS:
        expected_dtype = np.dtype("bool")
    if column in _STRING_COLUMNS:
        return isinstance(values.dtype, pd.StringDtype) and values.dtype.storage == "python"
    return values.dtype == expected_dtype


def _copy_source_frame(
    name: str,
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    sort_columns: tuple[str, ...],
) -> pd.DataFrame:
    """Validate, copy, and deterministically order one released source frame.

    Args:
        name: Public source-result field name.
        frame: Candidate mutable source frame.
        columns: Exact released column order.
        sort_columns: Keys defining the roll-up's normalized row order.

    Returns:
        An independently owned frame in deterministic order.

    Raises:
        TypeError: If the candidate is not a pandas DataFrame.
        AttributionError: If its schema, values, or identities are not canonical.
    """
    context = f"source result {name}"
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{context} must be a pandas DataFrame")
    if not frame.columns.equals(pd.Index(columns)):
        raise AttributionError(f"{context} must use the exact released column order")
    copied = cast(pd.DataFrame, frame.copy(deep=True))
    for column in columns:
        values = cast(pd.Series, copied[column])
        if not _has_canonical_dtype(column, values):
            raise AttributionError(
                f"{context} column {column!r} does not use its released dtype"
            )
        if bool(values.isna().any()):
            raise AttributionError(f"{context} column {column!r} contains null values")
        if column in _DATE_COLUMNS and not cast(pd.Series, values.dt.normalize()).equals(
            values
        ):
            raise AttributionError(
                f"{context} column {column!r} contains a non-normalized date"
            )
        if column in _STRING_COLUMNS and not _identities_are_canonical(values):
            raise AttributionError(
                f"{context} column {column!r} contains a noncanonical identity"
            )
    _validate_result_values(context, copied)
    return cast(
        pd.DataFrame,
        copied.sort_values(list(sort_columns), kind="stable"),
    ).reset_index(drop=True)


def _identities_are_canonical(values: pd.Series) -> bool:
    """Return whether identities are nonempty and contain no surrounding space."""
    stripped = cast(pd.Series, values.str.strip())
    return not bool(stripped.eq("").any()) and stripped.equals(values)


def _validate_base_currency(base_currency: str) -> str:
    """Require the source result's exact nonempty base-currency identity."""
    if not isinstance(base_currency, str):
        raise TypeError("source result base_currency must be a string")
    if not base_currency or base_currency != base_currency.strip():
        raise AttributionError(
            "source result base_currency must be nonempty with no surrounding whitespace"
        )
    return base_currency


def _validate_unique_keys(
    name: str,
    frame: pd.DataFrame,
    keys: tuple[str, ...],
) -> None:
    """Require one source frame to contain no duplicate semantic keys."""
    if bool(frame.duplicated(list(keys)).any()):
        raise AttributionError(f"source result {name} contains duplicate keys")


def _period_index(frame: pd.DataFrame) -> pd.MultiIndex:
    """Return one frame's unique period set in chronological order."""
    periods = cast(
        pd.DataFrame,
        frame.loc[:, list(_PERIOD_COLUMNS)].drop_duplicates(ignore_index=True),
    )
    ordered = periods.sort_values(["thru_date", "from_date"], kind="stable")
    return pd.MultiIndex.from_arrays(
        [ordered["from_date"], ordered["thru_date"]],
        names=_PERIOD_COLUMNS,
    )


def _validate_periods(result: _ValidatedCurrencyResult) -> None:
    """Require nonempty, valid, aligned, and non-overlapping source periods."""
    frames_by_name = {
        "market_detail": result.market_detail,
        "currency_detail": result.currency_detail,
        "period_summary": result.period_summary,
        "reconciliation": result.reconciliation,
    }
    if any(frame.empty for frame in frames_by_name.values()):
        raise AttributionError("source result frames must not be empty")
    for name, frame in frames_by_name.items():
        if bool((frame["from_date"] > frame["thru_date"]).any()):
            raise AttributionError(f"source result {name} contains an invalid period")

    expected = _period_index(result.period_summary)
    if any(
        not _period_index(frame).equals(expected)
        for frame in frames_by_name.values()
    ):
        raise AttributionError("source result period sets must match exactly")

    periods = result.period_summary.loc[:, list(_PERIOD_COLUMNS)].sort_values(
        ["from_date", "thru_date"],
        kind="stable",
    )
    if len(periods) > 1:
        starts = np.asarray(periods["from_date"], dtype="datetime64[ns]")
        ends = np.asarray(periods["thru_date"], dtype="datetime64[ns]")
        if np.any(starts[1:] <= ends[:-1]):
            raise AttributionError("source result contains overlapping periods")


def _period_sums(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    """Sum source detail columns into chronological period rows."""
    summed = cast(
        pd.DataFrame,
        frame.groupby(
            list(_PERIOD_COLUMNS),
            as_index=False,
            sort=True,
            observed=True,
        )[list(columns)].sum(),
    )
    return summed.sort_values(
        ["thru_date", "from_date"],
        kind="stable",
    ).reset_index(drop=True)


def _require_close(
    actual: _FloatArray,
    expected: _FloatArray,
    tolerance: float,
    message: str,
) -> None:
    """Require one independently reconstructed financial identity."""
    with np.errstate(over="ignore", invalid="ignore"):
        passed = _is_close(actual, expected, tolerance)
    if not passed.all():
        raise AttributionError(f"source result {message}")


def _validate_detail_components(
    result: _ValidatedCurrencyResult,
    tolerance: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate row effects and return period effect totals for both grids."""
    market = result.market_detail
    market_components = _float_array(
        market, "market_allocation_log_effect"
    ) + _float_array(market, "security_selection_log_effect")
    _require_close(
        _float_array(market, "total_log_effect"),
        market_components,
        tolerance,
        "market_detail has invalid effect components",
    )

    currency = result.currency_detail
    currency_components = _float_array(
        currency, "currency_allocation_log_effect"
    ) + _float_array(currency, "hedge_selection_log_effect")
    _require_close(
        _float_array(currency, "total_log_effect"),
        currency_components,
        tolerance,
        "currency_detail has invalid effect components",
    )
    return (
        _period_sums(
            market,
            (
                "market_allocation_log_effect",
                "security_selection_log_effect",
                "total_log_effect",
            ),
        ),
        _period_sums(
            currency,
            (
                "currency_allocation_log_effect",
                "hedge_selection_log_effect",
                "total_log_effect",
            ),
        ),
    )


def _validate_summary_identities(
    summary: pd.DataFrame,
    market_totals: pd.DataFrame,
    currency_totals: pd.DataFrame,
    tolerance: float,
) -> None:
    """Reconstruct every released return and effect identity by period."""
    for family in ("market", "currency", "total"):
        portfolio = _float_array(summary, f"portfolio_{family}_log_return")
        benchmark = _float_array(summary, f"benchmark_{family}_log_return")
        _require_close(
            _float_array(summary, f"active_{family}_log_return"),
            portfolio - benchmark,
            tolerance,
            f"period_summary has invalid active {family} log returns",
        )

    for side in ("portfolio", "benchmark"):
        _require_close(
            _float_array(summary, f"{side}_total_log_return"),
            _float_array(summary, f"{side}_market_log_return")
            + _float_array(summary, f"{side}_currency_log_return"),
            tolerance,
            f"period_summary has invalid {side} total components",
        )
    _require_close(
        _float_array(summary, "active_total_log_return"),
        _float_array(summary, "active_market_log_return")
        + _float_array(summary, "active_currency_log_return"),
        tolerance,
        "period_summary has invalid active total components",
    )

    for column in (
        "market_allocation_log_effect",
        "security_selection_log_effect",
    ):
        _require_close(
            _float_array(summary, column),
            _float_array(market_totals, column),
            tolerance,
            f"period_summary does not match market_detail column {column!r}",
        )
    for column in ("currency_allocation_log_effect", "hedge_selection_log_effect"):
        _require_close(
            _float_array(summary, column),
            _float_array(currency_totals, column),
            tolerance,
            f"period_summary does not match currency_detail column {column!r}",
        )

    _require_close(
        _float_array(market_totals, "total_log_effect"),
        _float_array(summary, "active_market_log_return"),
        tolerance,
        "market_detail does not reconcile to active market log return",
    )
    _require_close(
        _float_array(currency_totals, "total_log_effect"),
        _float_array(summary, "active_currency_log_return"),
        tolerance,
        "currency_detail does not reconcile to active currency log return",
    )
    all_effects = (
        _float_array(summary, "market_allocation_log_effect")
        + _float_array(summary, "security_selection_log_effect")
        + _float_array(summary, "currency_allocation_log_effect")
        + _float_array(summary, "hedge_selection_log_effect")
    )
    _require_close(
        _float_array(summary, "total_log_effect"),
        all_effects,
        tolerance,
        "period_summary has invalid total effect components",
    )
    _require_close(
        _float_array(summary, "total_log_effect"),
        _float_array(summary, "active_total_log_return"),
        tolerance,
        "period_summary does not reconcile to active total log return",
    )


def _validate_reconciliation_evidence(
    reconciliation: pd.DataFrame,
    summary: pd.DataFrame,
    market_totals: pd.DataFrame,
    currency_totals: pd.DataFrame,
    tolerance: float,
) -> None:
    """Require released source evidence to match independently validated values."""
    flags = reconciliation.loc[:, list(_FLAG_COLUMNS)].to_numpy(dtype=np.bool_)
    if not flags.all():
        raise AttributionError("source result reconciliation must contain only passes")

    expected_by_column = {
        "market_log_effect_sum": _float_array(market_totals, "total_log_effect"),
        "active_market_log_return": _float_array(
            summary, "active_market_log_return"
        ),
        "currency_log_effect_sum": _float_array(currency_totals, "total_log_effect"),
        "active_currency_log_return": _float_array(
            summary, "active_currency_log_return"
        ),
        "total_log_effect_sum": _float_array(summary, "total_log_effect"),
        "active_total_log_return": _float_array(summary, "active_total_log_return"),
    }
    for column, expected in expected_by_column.items():
        _require_close(
            _float_array(reconciliation, column),
            expected,
            tolerance,
            f"reconciliation column {column!r} does not match source values",
        )


def validate_source_result(
    result: CurrencyAttributionResult,
    tolerance: float,
) -> _ValidatedCurrencyResult:
    """Validate and copy the currency result required by multi-period roll-up.

    Args:
        result: Candidate mutable currency-attribution result.
        tolerance: Positive finite comparison tolerance already validated publicly.

    Returns:
        Independently owned canonical source frames and base-currency identity.

    Raises:
        TypeError: If source metadata or a frame has the wrong dedicated type.
        AttributionError: If a source value violates its released structural,
            numerical, or financial contract.

    Notes:
        Validation reconstructs released result identities but does not repeat the
        original market-premium, currency-return, exposure, or effect formulas.
    """
    validated = _ValidatedCurrencyResult(
        base_currency=_validate_base_currency(result.base_currency),
        market_detail=_copy_source_frame(
            "market_detail",
            result.market_detail,
            CURRENCY_MARKET_DETAIL_COLUMNS,
            ("thru_date", "from_date", "market_identifier"),
        ),
        currency_detail=_copy_source_frame(
            "currency_detail",
            result.currency_detail,
            CURRENCY_DETAIL_COLUMNS,
            ("thru_date", "from_date", "currency_identifier"),
        ),
        period_summary=_copy_source_frame(
            "period_summary",
            result.period_summary,
            CURRENCY_PERIOD_SUMMARY_COLUMNS,
            ("thru_date", "from_date"),
        ),
        reconciliation=_copy_source_frame(
            "reconciliation",
            result.reconciliation,
            CURRENCY_RECONCILIATION_COLUMNS,
            ("thru_date", "from_date"),
        ),
    )
    _validate_unique_keys(
        "market_detail",
        validated.market_detail,
        (*_PERIOD_COLUMNS, "market_identifier"),
    )
    _validate_unique_keys(
        "currency_detail",
        validated.currency_detail,
        (*_PERIOD_COLUMNS, "currency_identifier"),
    )
    _validate_unique_keys("period_summary", validated.period_summary, _PERIOD_COLUMNS)
    _validate_unique_keys("reconciliation", validated.reconciliation, _PERIOD_COLUMNS)
    _validate_periods(validated)
    market_totals, currency_totals = _validate_detail_components(validated, tolerance)
    _validate_summary_identities(
        validated.period_summary,
        market_totals,
        currency_totals,
        tolerance,
    )
    _validate_reconciliation_evidence(
        validated.reconciliation,
        validated.period_summary,
        market_totals,
        currency_totals,
        tolerance,
    )
    return validated


__all__ = ["_ValidatedCurrencyResult", "validate_source_result"]
