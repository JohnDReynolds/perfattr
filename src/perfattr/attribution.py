"""Portable Brinson-Fachler performance-attribution calculations.

The initial vertical slice implements one already-aligned reporting period. It keeps
input normalization, financial validation, calculation, and reconciliation together
so the financial path remains easy to audit before multi-period behavior is added.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import cast

import numpy as np
import numpy.typing as npt
import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_dtype, is_numeric_dtype


_TOLERANCE = 1e-12
_REQUIRED_COLUMNS = (
    "from_date",
    "thru_date",
    "identifier",
    "weight",
    "return",
    "quantity_of_days",
)
_PERIOD_DETAIL_COLUMNS = (
    "from_date",
    "thru_date",
    "quantity_of_days",
    "identifier",
    "portfolio_weight",
    "portfolio_return",
    "portfolio_contribution",
    "benchmark_weight",
    "benchmark_return",
    "benchmark_contribution",
    "active_weight",
    "active_return",
    "active_contribution",
    "allocation_effect",
    "selection_effect",
    "total_effect",
    "linked_portfolio_contribution",
    "linked_benchmark_contribution",
    "linked_active_contribution",
    "linked_allocation_effect",
    "linked_selection_effect",
    "linked_total_effect",
)
_PERIOD_SUMMARY_COLUMNS = (
    "from_date",
    "thru_date",
    "quantity_of_days",
    "portfolio_return",
    "benchmark_return",
    "active_return",
    "portfolio_contribution",
    "benchmark_contribution",
    "active_contribution",
    "allocation_effect",
    "selection_effect",
    "total_effect",
    "linked_portfolio_contribution",
    "linked_benchmark_contribution",
    "linked_active_contribution",
    "linked_allocation_effect",
    "linked_selection_effect",
    "linked_total_effect",
)
_OVERALL_DETAIL_COLUMNS = (
    "from_date",
    "thru_date",
    "identifier",
    "portfolio_weight",
    "portfolio_return",
    "linked_portfolio_contribution",
    "benchmark_weight",
    "benchmark_return",
    "linked_benchmark_contribution",
    "active_weight",
    "active_return",
    "linked_active_contribution",
    "linked_allocation_effect",
    "linked_selection_effect",
    "linked_total_effect",
)
_CUMULATIVE_COLUMNS = (
    "from_date",
    "thru_date",
    "portfolio_return",
    "benchmark_return",
    "active_return",
    "cumulative_portfolio_return",
    "cumulative_benchmark_return",
    "cumulative_active_return",
    "linked_portfolio_contribution",
    "linked_benchmark_contribution",
    "linked_active_contribution",
    "cumulative_portfolio_contribution",
    "cumulative_benchmark_contribution",
    "cumulative_active_contribution",
    "linked_allocation_effect",
    "linked_selection_effect",
    "linked_total_effect",
    "cumulative_allocation_effect",
    "cumulative_selection_effect",
    "cumulative_total_effect",
)
_RECONCILIATION_COLUMNS = (
    "scope",
    "from_date",
    "thru_date",
    "check",
    "actual",
    "expected",
    "residual",
    "tolerance",
    "passed",
)


class AttributionError(ValueError):
    """Report invalid financial input or a failed calculation invariant."""


@dataclass
class AttributionResult:
    """Hold portable attribution result frames.

    Attributes:
        period_detail: Attribution values for each period and identifier.
        period_summary: Attribution totals for each period.
        overall_detail: Full-horizon values for each identifier.
        cumulative: Chronological period and cumulative totals.
        reconciliation: Passing financial reconciliation evidence.

    Notes:
        The calculator does not mutate caller-supplied frames. Returned frames belong
        to the caller and are independently mutable.
    """

    period_detail: pd.DataFrame
    period_summary: pd.DataFrame
    overall_detail: pd.DataFrame
    cumulative: pd.DataFrame
    reconciliation: pd.DataFrame


def _float_array(frame: pd.DataFrame, column: str) -> npt.NDArray[np.float64]:
    """Return a DataFrame column as a float64 NumPy array."""
    return np.asarray(frame[column], dtype=np.float64)


def _int_scalar(frame: pd.DataFrame, column: str) -> int:
    """Return the first value of an integer column as an ordinary int."""
    values = np.asarray(frame[column], dtype=np.int64)
    return int(values[0])


def _has_true(values: pd.Series) -> bool:
    """Return whether a boolean Series contains a true value."""
    return bool(np.asarray(values, dtype=np.bool_).any())


def _raise_invalid(side: str, message: str) -> None:
    """Raise a consistently formatted input error."""
    raise AttributionError(f"{side} input {message}")


def _normalize_dates(frame: pd.DataFrame, column: str, side: str) -> pd.Series:
    """Normalize a required date column to timezone-naive midnight values."""
    values = cast(pd.Series, frame[column])
    if _has_true(values.isna()):
        _raise_invalid(side, f"column {column!r} contains null values")
    if is_numeric_dtype(values.dtype) or is_bool_dtype(values.dtype):
        _raise_invalid(side, f"column {column!r} must contain dates")

    try:
        normalized = pd.to_datetime(values, errors="raise", format="mixed")
    except (TypeError, ValueError, OverflowError) as error:
        raise AttributionError(
            f"{side} input column {column!r} contains an invalid date"
        ) from error

    if isinstance(normalized.dtype, pd.DatetimeTZDtype):
        _raise_invalid(side, f"column {column!r} must be timezone-naive")
    if not is_datetime64_dtype(normalized.dtype):
        _raise_invalid(side, f"column {column!r} must be timezone-naive")
    return cast(
        pd.Series,
        normalized.dt.normalize().astype("datetime64[ns]"),
    )


def _normalize_numeric(
    frame: pd.DataFrame,
    column: str,
    side: str,
    *,
    nullable: bool,
) -> pd.Series:
    """Validate and normalize one financial numeric column."""
    values = cast(pd.Series, frame[column])
    if is_bool_dtype(values.dtype) or not is_numeric_dtype(values.dtype):
        _raise_invalid(side, f"column {column!r} must contain numbers, not strings or booleans")
    if not nullable and _has_true(values.isna()):
        _raise_invalid(side, f"column {column!r} contains null values")

    normalized = cast(pd.Series, values.astype("float64"))
    finite_values = np.asarray(normalized.dropna(), dtype=np.float64)
    if not np.isfinite(finite_values).all():
        _raise_invalid(side, f"column {column!r} must contain only finite values")
    return normalized


def _normalize_identifiers(frame: pd.DataFrame, side: str) -> pd.Series:
    """Validate identifiers without coercing their values."""
    identifiers = cast(pd.Series, frame["identifier"])
    identifier_types = cast(
        pd.Series, identifiers.map(lambda value: isinstance(value, str))
    )
    if _has_true(identifiers.isna()) or not bool(
        np.asarray(identifier_types, dtype=np.bool_).all()
    ):
        _raise_invalid(side, "column 'identifier' must contain non-null strings")
    normalized = cast(pd.Series, identifiers.astype("string[python]").str.strip())
    if _has_true(normalized.eq("")):
        _raise_invalid(side, "column 'identifier' contains an empty string")
    return normalized


def _validate_period_structure(frame: pd.DataFrame, side: str) -> None:
    """Validate dates, unique keys, non-overlap, and constant day counts."""
    key_columns = ["from_date", "thru_date", "identifier"]
    if frame.duplicated(key_columns).any():
        _raise_invalid(side, "contains a duplicate period and identifier key")
    if (frame["from_date"] > frame["thru_date"]).any():
        _raise_invalid(side, "contains a from_date after its thru_date")

    periods = cast(
        pd.DataFrame,
        frame[["from_date", "thru_date", "quantity_of_days"]].drop_duplicates(),
    ).sort_values(["thru_date", "from_date"], kind="stable")
    thru_dates = cast(pd.Series, periods["thru_date"])
    if _has_true(thru_dates.duplicated()):
        _raise_invalid(side, "maps one thru_date to more than one reporting period")
    day_counts = cast(
        pd.Series,
        frame.groupby(["from_date", "thru_date"])["quantity_of_days"].nunique(),
    )
    if _has_true(day_counts.gt(1)):
        _raise_invalid(side, "has inconsistent quantity_of_days within a period")
    if len(periods) > 1:
        starts = np.asarray(periods["from_date"], dtype="datetime64[ns]")
        ends = np.asarray(periods["thru_date"], dtype="datetime64[ns]")
        if np.any(starts[1:] <= ends[:-1]):
            _raise_invalid(side, "contains overlapping reporting periods")


def _normalize_input(frame: pd.DataFrame, side: str) -> pd.DataFrame:
    """Validate and copy one caller-owned prepared attribution frame."""
    if frame.columns.has_duplicates:
        _raise_invalid(side, "contains duplicate column labels")
    missing = [column for column in _REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        _raise_invalid(side, f"is missing required columns: {', '.join(missing)}")
    if frame.empty:
        _raise_invalid(side, "must not be empty")

    selected_columns = [*_REQUIRED_COLUMNS]
    if "contribution" in frame.columns:
        selected_columns.append("contribution")
    normalized = cast(pd.DataFrame, frame.loc[:, selected_columns].copy(deep=True))
    normalized["from_date"] = _normalize_dates(normalized, "from_date", side)
    normalized["thru_date"] = _normalize_dates(normalized, "thru_date", side)
    normalized["identifier"] = _normalize_identifiers(normalized, side)
    normalized["weight"] = _normalize_numeric(
        normalized, "weight", side, nullable=False
    )
    normalized["return"] = _normalize_numeric(
        normalized, "return", side, nullable=True
    )
    day_values = _normalize_numeric(
        normalized, "quantity_of_days", side, nullable=False
    )
    day_array = np.asarray(day_values, dtype=np.float64)
    if np.any(day_array <= 0.0) or np.any(day_array != np.floor(day_array)):
        _raise_invalid(side, "column 'quantity_of_days' must contain positive integers")
    normalized["quantity_of_days"] = day_values.astype("int64")

    input_returns = _float_array(normalized, "return")
    weights = _float_array(normalized, "weight")
    present_returns = ~np.isnan(input_returns)
    if np.any(input_returns[present_returns] <= -1.0):
        _raise_invalid(side, "column 'return' must be greater than -1.0 when present")
    if np.any((weights != 0.0) & ~present_returns):
        _raise_invalid(side, "contains a nonzero weight with a null return")

    if "contribution" in normalized.columns:
        normalized["contribution"] = _normalize_numeric(
            normalized, "contribution", side, nullable=False
        )
        contributions = _float_array(normalized, "contribution")
        invalid_undefined_returns = (
            (weights == 0.0) & (contributions != 0.0) & present_returns
        )
        if np.any(invalid_undefined_returns):
            _raise_invalid(
                side,
                "requires a null return when weight is zero and contribution is nonzero",
            )
    else:
        contributions = np.zeros(len(normalized), dtype=np.float64)
        np.multiply(weights, input_returns, out=contributions, where=present_returns)
        normalized["contribution"] = contributions

    effective_returns = np.zeros(len(normalized), dtype=np.float64)
    nonzero_weights = weights != 0.0
    np.divide(
        contributions,
        weights,
        out=effective_returns,
        where=nonzero_weights,
    )
    effective_returns[(weights == 0.0) & (contributions != 0.0)] = np.nan
    if not np.isfinite(effective_returns[~np.isnan(effective_returns)]).all():
        _raise_invalid(side, "produces a non-finite effective return")

    normalized["input_return"] = input_returns
    normalized["effective_return"] = effective_returns
    _validate_period_structure(normalized, side)
    return normalized.reset_index(drop=True)


def _period_keys(frame: pd.DataFrame) -> pd.MultiIndex:
    """Return the distinct normalized reporting-period keys."""
    periods = cast(
        pd.DataFrame, frame[["from_date", "thru_date"]].drop_duplicates()
    ).sort_values(["thru_date", "from_date"], kind="stable")
    return pd.MultiIndex.from_frame(periods)


def _validate_matched_period(portfolio: pd.DataFrame, benchmark: pd.DataFrame) -> None:
    """Validate cross-side period, day-count, weight, and return contracts."""
    portfolio_periods = _period_keys(portfolio)
    benchmark_periods = _period_keys(benchmark)
    if not portfolio_periods.equals(benchmark_periods):
        raise AttributionError("portfolio and benchmark reporting periods must match exactly")
    if len(portfolio_periods) != 1:
        raise AttributionError(
            "the 0.1.0a1 vertical slice supports exactly one reporting period"
        )

    portfolio_days = _int_scalar(portfolio, "quantity_of_days")
    benchmark_days = _int_scalar(benchmark, "quantity_of_days")
    if portfolio_days != benchmark_days:
        raise AttributionError(
            "portfolio and benchmark quantity_of_days must match for each period"
        )
    for side, frame in (("portfolio", portfolio), ("benchmark", benchmark)):
        weight_sum = float(_float_array(frame, "weight").sum())
        if not math.isclose(weight_sum, 1.0, rel_tol=_TOLERANCE, abs_tol=_TOLERANCE):
            _raise_invalid(side, "weights must sum to 1.0 within tolerance")
        period_return = float(_float_array(frame, "contribution").sum())
        if period_return <= -1.0:
            _raise_invalid(side, "period return must be greater than -1.0")


def _equalize_universe(portfolio: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    """Outer-join the two sides and synthesize neutral missing rows."""
    key_columns = ["from_date", "thru_date", "identifier"]
    side_columns = [
        *key_columns,
        "quantity_of_days",
        "weight",
        "input_return",
        "effective_return",
        "contribution",
    ]
    portfolio_side = cast(pd.DataFrame, portfolio.loc[:, side_columns]).assign(
        portfolio_present=True
    )
    benchmark_side = cast(pd.DataFrame, benchmark.loc[:, side_columns]).assign(
        benchmark_present=True
    )
    equalized = portfolio_side.merge(
        benchmark_side,
        on=key_columns,
        how="outer",
        suffixes=("_portfolio", "_benchmark"),
        validate="one_to_one",
        sort=False,
    )

    for side in ("portfolio", "benchmark"):
        missing = equalized[f"{side}_present"].isna()
        for column in ("weight", "input_return", "effective_return", "contribution"):
            equalized.loc[missing, f"{column}_{side}"] = 0.0
    equalized["quantity_of_days"] = equalized[
        "quantity_of_days_portfolio"
    ].fillna(equalized["quantity_of_days_benchmark"])

    equalized = cast(
        pd.DataFrame,
        equalized.sort_values(["thru_date", "identifier"], kind="stable"),
    ).reset_index(drop=True)
    return equalized


def _build_period_detail(equalized: pd.DataFrame) -> pd.DataFrame:
    """Calculate equalized single-period contributions and effects."""
    values = {
        "portfolio_weight": _float_array(equalized, "weight_portfolio"),
        "benchmark_weight": _float_array(equalized, "weight_benchmark"),
        "portfolio_return": _float_array(equalized, "effective_return_portfolio"),
        "benchmark_return": _float_array(equalized, "effective_return_benchmark"),
        "portfolio_contribution": _float_array(equalized, "contribution_portfolio"),
        "benchmark_contribution": _float_array(equalized, "contribution_benchmark"),
    }
    benchmark_total_return = float(values["benchmark_contribution"].sum())

    active_weight = values["portfolio_weight"] - values["benchmark_weight"]
    active_return = np.full(len(equalized), np.nan, dtype=np.float64)
    defined_active_return = ~np.isnan(values["portfolio_return"]) & ~np.isnan(
        values["benchmark_return"]
    )
    np.subtract(
        values["portfolio_return"],
        values["benchmark_return"],
        out=active_return,
        where=defined_active_return,
    )
    active_contribution = (
        values["portfolio_contribution"] - values["benchmark_contribution"]
    )
    allocation_effect = np.where(
        np.isnan(values["benchmark_return"]),
        0.0,
        active_weight * (values["benchmark_return"] - benchmark_total_return),
    )
    total_effect = active_contribution - active_weight * benchmark_total_return
    selection_effect = total_effect - allocation_effect

    detail = pd.DataFrame(
        {
            "from_date": equalized["from_date"],
            "thru_date": equalized["thru_date"],
            "quantity_of_days": equalized["quantity_of_days"].astype("int64"),
            "identifier": equalized["identifier"].astype("string[python]"),
            "portfolio_weight": values["portfolio_weight"],
            "portfolio_return": values["portfolio_return"],
            "portfolio_contribution": values["portfolio_contribution"],
            "benchmark_weight": values["benchmark_weight"],
            "benchmark_return": values["benchmark_return"],
            "benchmark_contribution": values["benchmark_contribution"],
            "active_weight": active_weight,
            "active_return": active_return,
            "active_contribution": active_contribution,
            "allocation_effect": allocation_effect,
            "selection_effect": selection_effect,
            "total_effect": total_effect,
            "linked_portfolio_contribution": values[
                "portfolio_contribution"
            ].copy(),
            "linked_benchmark_contribution": values[
                "benchmark_contribution"
            ].copy(),
            "linked_active_contribution": active_contribution.copy(),
            "linked_allocation_effect": allocation_effect.copy(),
            "linked_selection_effect": selection_effect.copy(),
            "linked_total_effect": total_effect.copy(),
        },
        columns=_PERIOD_DETAIL_COLUMNS,
    )
    return detail.reset_index(drop=True)


def _column_sum(frame: pd.DataFrame, column: str) -> float:
    """Return a numeric result column's sum as an ordinary float."""
    return float(_float_array(frame, column).sum())


def _build_period_summary(detail: pd.DataFrame) -> pd.DataFrame:
    """Summarize the one calculated reporting period."""
    portfolio_return = _column_sum(detail, "portfolio_contribution")
    benchmark_return = _column_sum(detail, "benchmark_contribution")
    active_return = portfolio_return - benchmark_return
    summary = pd.DataFrame(
        {
            "from_date": [detail.at[0, "from_date"]],
            "thru_date": [detail.at[0, "thru_date"]],
            "quantity_of_days": [_int_scalar(detail, "quantity_of_days")],
            "portfolio_return": [portfolio_return],
            "benchmark_return": [benchmark_return],
            "active_return": [active_return],
            "portfolio_contribution": [portfolio_return],
            "benchmark_contribution": [benchmark_return],
            "active_contribution": [_column_sum(detail, "active_contribution")],
            "allocation_effect": [_column_sum(detail, "allocation_effect")],
            "selection_effect": [_column_sum(detail, "selection_effect")],
            "total_effect": [_column_sum(detail, "total_effect")],
            "linked_portfolio_contribution": [
                _column_sum(detail, "linked_portfolio_contribution")
            ],
            "linked_benchmark_contribution": [
                _column_sum(detail, "linked_benchmark_contribution")
            ],
            "linked_active_contribution": [
                _column_sum(detail, "linked_active_contribution")
            ],
            "linked_allocation_effect": [
                _column_sum(detail, "linked_allocation_effect")
            ],
            "linked_selection_effect": [
                _column_sum(detail, "linked_selection_effect")
            ],
            "linked_total_effect": [_column_sum(detail, "linked_total_effect")],
        },
        columns=_PERIOD_SUMMARY_COLUMNS,
    )
    return summary.reset_index(drop=True)


def _build_overall_detail(
    equalized: pd.DataFrame, detail: pd.DataFrame
) -> pd.DataFrame:
    """Build single-period overall rows using supplied returns where required."""
    portfolio_return = _float_array(equalized, "input_return_portfolio")
    benchmark_return = _float_array(equalized, "input_return_benchmark")
    active_return = np.full(len(equalized), np.nan, dtype=np.float64)
    defined_active_return = ~np.isnan(portfolio_return) & ~np.isnan(benchmark_return)
    np.subtract(
        portfolio_return,
        benchmark_return,
        out=active_return,
        where=defined_active_return,
    )
    overall = pd.DataFrame(
        {
            "from_date": detail["from_date"].copy(),
            "thru_date": detail["thru_date"].copy(),
            "identifier": detail["identifier"].copy(),
            "portfolio_weight": detail["portfolio_weight"].copy(),
            "portfolio_return": portfolio_return,
            "linked_portfolio_contribution": detail[
                "linked_portfolio_contribution"
            ].copy(),
            "benchmark_weight": detail["benchmark_weight"].copy(),
            "benchmark_return": benchmark_return,
            "linked_benchmark_contribution": detail[
                "linked_benchmark_contribution"
            ].copy(),
            "active_weight": detail["active_weight"].copy(),
            "active_return": active_return,
            "linked_active_contribution": detail[
                "linked_active_contribution"
            ].copy(),
            "linked_allocation_effect": detail["linked_allocation_effect"].copy(),
            "linked_selection_effect": detail["linked_selection_effect"].copy(),
            "linked_total_effect": detail["linked_total_effect"].copy(),
        },
        columns=_OVERALL_DETAIL_COLUMNS,
    )
    return overall.reset_index(drop=True)


def _build_cumulative(summary: pd.DataFrame) -> pd.DataFrame:
    """Build the identity cumulative result for one reporting period."""
    values = {
        "from_date": [summary.at[0, "from_date"]],
        "thru_date": [summary.at[0, "thru_date"]],
        "portfolio_return": [summary.at[0, "portfolio_return"]],
        "benchmark_return": [summary.at[0, "benchmark_return"]],
        "active_return": [summary.at[0, "active_return"]],
        "cumulative_portfolio_return": [summary.at[0, "portfolio_return"]],
        "cumulative_benchmark_return": [summary.at[0, "benchmark_return"]],
        "cumulative_active_return": [summary.at[0, "active_return"]],
        "linked_portfolio_contribution": [
            summary.at[0, "linked_portfolio_contribution"]
        ],
        "linked_benchmark_contribution": [
            summary.at[0, "linked_benchmark_contribution"]
        ],
        "linked_active_contribution": [summary.at[0, "linked_active_contribution"]],
        "cumulative_portfolio_contribution": [
            summary.at[0, "linked_portfolio_contribution"]
        ],
        "cumulative_benchmark_contribution": [
            summary.at[0, "linked_benchmark_contribution"]
        ],
        "cumulative_active_contribution": [
            summary.at[0, "linked_active_contribution"]
        ],
        "linked_allocation_effect": [summary.at[0, "linked_allocation_effect"]],
        "linked_selection_effect": [summary.at[0, "linked_selection_effect"]],
        "linked_total_effect": [summary.at[0, "linked_total_effect"]],
        "cumulative_allocation_effect": [summary.at[0, "linked_allocation_effect"]],
        "cumulative_selection_effect": [summary.at[0, "linked_selection_effect"]],
        "cumulative_total_effect": [summary.at[0, "linked_total_effect"]],
    }
    return pd.DataFrame(values, columns=_CUMULATIVE_COLUMNS).reset_index(drop=True)


def _reconciliation_row(
    scope: str,
    dates: tuple[pd.Timestamp, pd.Timestamp],
    check: str,
    actual: float,
    expected: float,
) -> dict[str, object]:
    """Create one reconciliation record using the fixed numerical tolerance."""
    return {
        "scope": scope,
        "from_date": dates[0],
        "thru_date": dates[1],
        "check": check,
        "actual": actual,
        "expected": expected,
        "residual": actual - expected,
        "tolerance": _TOLERANCE,
        "passed": math.isclose(
            actual, expected, rel_tol=_TOLERANCE, abs_tol=_TOLERANCE
        ),
    }


def _build_reconciliation(
    detail: pd.DataFrame, summary: pd.DataFrame
) -> pd.DataFrame:
    """Build positive period and overall financial reconciliation evidence."""
    dates = (
        cast(pd.Timestamp, detail.at[0, "from_date"]),
        cast(pd.Timestamp, detail.at[0, "thru_date"]),
    )
    portfolio_return = _column_sum(summary, "portfolio_return")
    benchmark_return = _column_sum(summary, "benchmark_return")
    active_return = portfolio_return - benchmark_return
    period_values = (
        ("portfolio_weight", _column_sum(detail, "portfolio_weight"), 1.0),
        ("benchmark_weight", _column_sum(detail, "benchmark_weight"), 1.0),
        (
            "portfolio_contribution",
            _column_sum(detail, "portfolio_contribution"),
            portfolio_return,
        ),
        (
            "benchmark_contribution",
            _column_sum(detail, "benchmark_contribution"),
            benchmark_return,
        ),
        ("active_contribution", _column_sum(detail, "active_contribution"), active_return),
        (
            "effect_components",
            _column_sum(detail, "allocation_effect")
            + _column_sum(detail, "selection_effect"),
            _column_sum(detail, "total_effect"),
        ),
        ("total_effect", _column_sum(detail, "total_effect"), active_return),
    )
    overall_values = (
        (
            "linked_portfolio_contribution",
            _column_sum(detail, "linked_portfolio_contribution"),
            portfolio_return,
        ),
        (
            "linked_benchmark_contribution",
            _column_sum(detail, "linked_benchmark_contribution"),
            benchmark_return,
        ),
        (
            "linked_active_contribution",
            _column_sum(detail, "linked_active_contribution"),
            active_return,
        ),
        (
            "linked_effect_components",
            _column_sum(detail, "linked_allocation_effect")
            + _column_sum(detail, "linked_selection_effect"),
            _column_sum(detail, "linked_total_effect"),
        ),
        (
            "linked_total_effect",
            _column_sum(detail, "linked_total_effect"),
            active_return,
        ),
    )
    rows = [
        _reconciliation_row("period", dates, check, actual, expected)
        for check, actual, expected in period_values
    ]
    rows.extend(
        _reconciliation_row("overall", dates, check, actual, expected)
        for check, actual, expected in overall_values
    )
    reconciliation = pd.DataFrame(rows, columns=_RECONCILIATION_COLUMNS)
    reconciliation["scope"] = reconciliation["scope"].astype("string[python]")
    reconciliation["check"] = reconciliation["check"].astype("string[python]")
    reconciliation["passed"] = reconciliation["passed"].astype("bool")
    passed = cast(pd.Series, reconciliation["passed"])
    if not bool(np.asarray(passed, dtype=np.bool_).all()):
        failed = cast(
            pd.Series, reconciliation.loc[~reconciliation["passed"], "check"]
        )
        failed_checks = ", ".join(
            cast(pd.Series, failed.astype(str))
        )
        raise AttributionError(f"calculation reconciliation failed: {failed_checks}")
    return reconciliation.reset_index(drop=True)


def calculate_attribution(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> AttributionResult:
    """Calculate portable single-period Brinson-Fachler attribution.

    Args:
        portfolio: Prepared portfolio rows satisfying the portable input contract.
        benchmark: Prepared benchmark rows for the same reporting period.

    Returns:
        Five new, caller-owned result frames containing period, overall, cumulative,
        and reconciliation values.

    Raises:
        TypeError: If either input is not a pandas DataFrame.
        AttributionError: If financial input is invalid, the current single-period
            limitation is exceeded, or a reconciliation invariant fails.

    Notes:
        This first functional vertical slice accepts exactly one reporting period.
        Selection is portfolio-weighted and absorbs interaction. Supplied
        contribution is authoritative; otherwise contribution is derived as weight
        multiplied by return.
    """
    if not isinstance(portfolio, pd.DataFrame):
        raise TypeError("portfolio must be a pandas DataFrame")
    if not isinstance(benchmark, pd.DataFrame):
        raise TypeError("benchmark must be a pandas DataFrame")

    normalized_portfolio = _normalize_input(portfolio, "portfolio")
    normalized_benchmark = _normalize_input(benchmark, "benchmark")
    _validate_matched_period(normalized_portfolio, normalized_benchmark)
    equalized = _equalize_universe(normalized_portfolio, normalized_benchmark)
    period_detail = _build_period_detail(equalized)
    period_summary = _build_period_summary(period_detail)
    overall_detail = _build_overall_detail(equalized, period_detail)
    cumulative = _build_cumulative(period_summary)
    reconciliation = _build_reconciliation(period_detail, period_summary)
    return AttributionResult(
        period_detail=period_detail,
        period_summary=period_summary,
        overall_detail=overall_detail,
        cumulative=cumulative,
        reconciliation=reconciliation,
    )


__all__ = ["AttributionError", "AttributionResult", "calculate_attribution"]
