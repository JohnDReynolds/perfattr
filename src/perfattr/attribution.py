"""Portable Brinson-Fachler performance-attribution calculations.

Input normalization, financial validation, calculation, linking, and reconciliation
remain in one explicit path so the financial behavior is straightforward to audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import numpy.typing as npt
import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_dtype, is_numeric_dtype

from perfattr._linking import _carino, _compound_returns, _smoothing
from perfattr._schemas import (
    CUMULATIVE_COLUMNS,
    OVERALL_DETAIL_COLUMNS,
    OVERALL_RECONCILIATION_CHECKS,
    PERIOD_DETAIL_COLUMNS,
    PERIOD_RECONCILIATION_CHECKS,
    PERIOD_SUMMARY_COLUMNS,
    RECONCILIATION_COLUMNS,
)

_TOLERANCE = 1e-12
_REQUIRED_COLUMNS = (
    "from_date",
    "thru_date",
    "identifier",
    "weight",
    "return",
    "quantity_of_days",
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


def _is_close(
    actual: npt.NDArray[np.float64],
    expected: npt.NDArray[np.float64],
    tolerance: float,
) -> npt.NDArray[np.bool_]:
    """Vectorize the project's symmetric relative and absolute tolerance."""
    difference = np.abs(actual - expected)
    scale = np.maximum(np.abs(actual), np.abs(expected))
    return difference <= np.maximum(tolerance * scale, tolerance)


def _normalize_reconciliation_tolerance(value: float) -> float:
    """Require a finite, positive, non-boolean reconciliation tolerance."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("reconciliation_tolerance must be a real number")
    tolerance = float(value)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise AttributionError(
            "reconciliation_tolerance must be finite and greater than zero"
        )
    return tolerance


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


def _period_totals(frame: pd.DataFrame) -> pd.DataFrame:
    """Return sorted day, weight, and contribution totals for each period."""
    totals = cast(
        pd.DataFrame,
        frame.groupby(
            ["from_date", "thru_date"],
            as_index=False,
            sort=False,
            observed=True,
        ).agg(
            quantity_of_days=("quantity_of_days", "first"),
            weight=("weight", "sum"),
            period_return=("contribution", "sum"),
        ),
    )
    return cast(
        pd.DataFrame,
        totals.sort_values(["thru_date", "from_date"], kind="stable"),
    ).reset_index(drop=True)


def _validate_matched_periods(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    reconciliation_tolerance: float,
) -> None:
    """Validate cross-side period, day-count, weight, and return contracts."""
    portfolio_periods = _period_keys(portfolio)
    benchmark_periods = _period_keys(benchmark)
    if not portfolio_periods.equals(benchmark_periods):
        raise AttributionError("portfolio and benchmark reporting periods must match exactly")

    portfolio_totals = _period_totals(portfolio)
    benchmark_totals = _period_totals(benchmark)
    portfolio_days = np.asarray(portfolio_totals["quantity_of_days"], dtype=np.int64)
    benchmark_days = np.asarray(benchmark_totals["quantity_of_days"], dtype=np.int64)
    if not np.array_equal(portfolio_days, benchmark_days):
        raise AttributionError(
            "portfolio and benchmark quantity_of_days must match for each period"
        )
    for side, totals in (
        ("portfolio", portfolio_totals),
        ("benchmark", benchmark_totals),
    ):
        weight_sums = _float_array(totals, "weight")
        expected_weights = np.ones_like(weight_sums)
        if not _is_close(
            weight_sums,
            expected_weights,
            reconciliation_tolerance,
        ).all():
            _raise_invalid(side, "weights must sum to 1.0 within tolerance")
        period_returns = _float_array(totals, "period_return")
        if not np.isfinite(period_returns).all():
            _raise_invalid(side, "period returns must be finite")
        if np.any(period_returns <= -1.0):
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
    """Calculate equalized period contributions and unlinked effects."""
    values = {
        "portfolio_weight": _float_array(equalized, "weight_portfolio"),
        "benchmark_weight": _float_array(equalized, "weight_benchmark"),
        "portfolio_return": _float_array(equalized, "effective_return_portfolio"),
        "benchmark_return": _float_array(equalized, "effective_return_benchmark"),
        "portfolio_contribution": _float_array(equalized, "contribution_portfolio"),
        "benchmark_contribution": _float_array(equalized, "contribution_benchmark"),
    }
    benchmark_total_return = np.asarray(
        equalized.groupby(
            ["from_date", "thru_date"], sort=False, observed=True
        )["contribution_benchmark"].transform("sum"),
        dtype=np.float64,
    )

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
        columns=PERIOD_DETAIL_COLUMNS,
    )
    return detail.reset_index(drop=True)


def _link_period_detail(detail: pd.DataFrame) -> pd.DataFrame:
    """Apply full-horizon logarithmic and Carino linking coefficients."""
    period_keys = ["from_date", "thru_date"]
    grouped = detail.groupby(period_keys, sort=False, observed=True)
    portfolio_period_returns = np.asarray(
        grouped["portfolio_contribution"].sum(), dtype=np.float64
    )
    benchmark_period_returns = np.asarray(
        grouped["benchmark_contribution"].sum(), dtype=np.float64
    )
    portfolio_horizon_return = _compound_returns(portfolio_period_returns)
    benchmark_horizon_return = _compound_returns(benchmark_period_returns)
    horizon_returns = np.asarray(
        [portfolio_horizon_return, benchmark_horizon_return], dtype=np.float64
    )
    if np.any(horizon_returns <= -1.0) or not np.isfinite(horizon_returns).all():
        raise AttributionError("compounded horizon returns must be finite and greater than -1.0")

    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        portfolio_coefficients = _smoothing(portfolio_period_returns) / _smoothing(
            np.asarray([portfolio_horizon_return], dtype=np.float64)
        )[0]
        benchmark_coefficients = _smoothing(benchmark_period_returns) / _smoothing(
            np.asarray([benchmark_horizon_return], dtype=np.float64)
        )[0]
        active_coefficients = _carino(
            portfolio_period_returns, benchmark_period_returns
        ) / _carino(
            np.asarray([portfolio_horizon_return], dtype=np.float64),
            np.asarray([benchmark_horizon_return], dtype=np.float64),
        )[0]
    if not all(
        np.isfinite(coefficients).all()
        for coefficients in (
            portfolio_coefficients,
            benchmark_coefficients,
            active_coefficients,
        )
    ):
        raise AttributionError("linking coefficients must be finite")
    period_codes = np.asarray(grouped.ngroup(), dtype=np.int64)
    linked = detail.copy(deep=True)
    linked["linked_portfolio_contribution"] = (
        _float_array(detail, "portfolio_contribution")
        * portfolio_coefficients[period_codes]
    )
    linked["linked_benchmark_contribution"] = (
        _float_array(detail, "benchmark_contribution")
        * benchmark_coefficients[period_codes]
    )
    linked["linked_active_contribution"] = (
        _float_array(linked, "linked_portfolio_contribution")
        - _float_array(linked, "linked_benchmark_contribution")
    )
    for linked_column, simple_column in (
        ("linked_allocation_effect", "allocation_effect"),
        ("linked_selection_effect", "selection_effect"),
        ("linked_total_effect", "total_effect"),
    ):
        linked[linked_column] = (
            _float_array(detail, simple_column) * active_coefficients[period_codes]
        )
    return linked.reset_index(drop=True)


def _column_sum(frame: pd.DataFrame, column: str) -> float:
    """Return a numeric result column's sum as an ordinary float."""
    return float(_float_array(frame, column).sum())


def _build_period_summary(detail: pd.DataFrame) -> pd.DataFrame:
    """Summarize calculated detail rows for every reporting period."""
    value_columns = """portfolio_contribution benchmark_contribution
    active_contribution allocation_effect selection_effect total_effect
    linked_portfolio_contribution linked_benchmark_contribution
    linked_active_contribution linked_allocation_effect linked_selection_effect
    linked_total_effect""".split()
    summary = cast(
        pd.DataFrame,
        detail.groupby(
            ["from_date", "thru_date", "quantity_of_days"],
            as_index=False,
            sort=False,
            observed=True,
        )[value_columns].sum(),
    )
    summary["portfolio_return"] = summary["portfolio_contribution"]
    summary["benchmark_return"] = summary["benchmark_contribution"]
    summary["active_return"] = (
        summary["portfolio_return"] - summary["benchmark_return"]
    )
    return cast(pd.DataFrame, summary.loc[:, PERIOD_SUMMARY_COLUMNS]).reset_index(
        drop=True
    )


def _build_overall_detail(
    equalized: pd.DataFrame, detail: pd.DataFrame
) -> pd.DataFrame:
    """Build full-horizon identifier rows from supplied returns and linked values."""
    period_days = cast(
        pd.Series,
        equalized.groupby(
            ["from_date", "thru_date"], sort=False, observed=True
        )["quantity_of_days"].first(),
    )
    total_days = float(np.asarray(period_days, dtype=np.float64).sum())
    if not np.isfinite(total_days):
        raise AttributionError("the complete horizon quantity_of_days must be finite")
    portfolio = _build_overall_side(equalized, "portfolio", total_days)
    benchmark = _build_overall_side(equalized, "benchmark", total_days)

    linked_columns = """linked_portfolio_contribution
    linked_benchmark_contribution linked_active_contribution
    linked_allocation_effect linked_selection_effect linked_total_effect""".split()
    linked = cast(
        pd.DataFrame,
        detail.groupby(
            "identifier", as_index=False, sort=True, observed=True
        )[linked_columns].sum(),
    )
    overall = portfolio.merge(
        benchmark,
        on="identifier",
        how="inner",
        validate="one_to_one",
    ).merge(linked, on="identifier", how="inner", validate="one_to_one")
    portfolio_return = _float_array(overall, "portfolio_return")
    benchmark_return = _float_array(overall, "benchmark_return")
    active_return = np.full(len(overall), np.nan, dtype=np.float64)
    defined_active_return = ~np.isnan(portfolio_return) & ~np.isnan(benchmark_return)
    np.subtract(
        portfolio_return,
        benchmark_return,
        out=active_return,
        where=defined_active_return,
    )
    horizon = pd.DataFrame(
        {
            "from_date": detail.at[0, "from_date"],
            "thru_date": detail.at[len(detail) - 1, "thru_date"],
            "identifier": overall["identifier"],
            "portfolio_weight": overall["portfolio_weight"],
            "portfolio_return": portfolio_return,
            "linked_portfolio_contribution": overall[
                "linked_portfolio_contribution"
            ],
            "benchmark_weight": overall["benchmark_weight"],
            "benchmark_return": benchmark_return,
            "linked_benchmark_contribution": overall[
                "linked_benchmark_contribution"
            ],
            "active_weight": (
                _float_array(overall, "portfolio_weight")
                - _float_array(overall, "benchmark_weight")
            ),
            "active_return": active_return,
            "linked_active_contribution": overall["linked_active_contribution"],
            "linked_allocation_effect": overall["linked_allocation_effect"],
            "linked_selection_effect": overall["linked_selection_effect"],
            "linked_total_effect": overall["linked_total_effect"],
        },
        columns=OVERALL_DETAIL_COLUMNS,
    )
    return horizon.reset_index(drop=True)


def _build_overall_side(
    equalized: pd.DataFrame, side: str, total_days: float
) -> pd.DataFrame:
    """Aggregate one side's day-weighted exposure and supplied horizon return."""
    input_returns = _float_array(equalized, f"input_return_{side}")
    defined_returns = ~np.isnan(input_returns)
    log_returns = np.zeros(len(equalized), dtype=np.float64)
    np.log1p(input_returns, out=log_returns, where=defined_returns)
    working = pd.DataFrame(
        {
            "identifier": equalized["identifier"],
            "weighted_weight": (
                _float_array(equalized, f"weight_{side}")
                * _float_array(equalized, "quantity_of_days")
            ),
            "log_return": log_returns,
            "undefined_return": ~defined_returns,
        }
    )
    aggregated = cast(
        pd.DataFrame,
        working.groupby(
            "identifier", as_index=False, sort=True, observed=True
        ).agg(
            weighted_weight=("weighted_weight", "sum"),
            log_return=("log_return", "sum"),
            undefined_return=("undefined_return", "max"),
        ),
    )
    with np.errstate(over="ignore", invalid="ignore"):
        compounded_returns = np.expm1(_float_array(aggregated, "log_return"))
    undefined_returns = np.asarray(aggregated["undefined_return"], dtype=np.bool_)
    if not np.isfinite(compounded_returns[~undefined_returns]).all():
        raise AttributionError(f"{side} overall returns must be finite when defined")
    compounded_returns[undefined_returns] = np.nan
    return pd.DataFrame(
        {
            "identifier": aggregated["identifier"].astype("string[python]"),
            f"{side}_weight": (
                _float_array(aggregated, "weighted_weight") / total_days
            ),
            f"{side}_return": compounded_returns,
        }
    )


def _build_cumulative(summary: pd.DataFrame) -> pd.DataFrame:
    """Build chronological period values and their cumulative counterparts."""
    portfolio_returns = _float_array(summary, "portfolio_return")
    benchmark_returns = _float_array(summary, "benchmark_return")
    cumulative_portfolio_returns = np.expm1(np.cumsum(np.log1p(portfolio_returns)))
    cumulative_benchmark_returns = np.expm1(np.cumsum(np.log1p(benchmark_returns)))
    cumulative = pd.DataFrame(
        {
            "from_date": summary["from_date"],
            "thru_date": summary["thru_date"],
            "portfolio_return": portfolio_returns,
            "benchmark_return": benchmark_returns,
            "active_return": _float_array(summary, "active_return"),
            "cumulative_portfolio_return": cumulative_portfolio_returns,
            "cumulative_benchmark_return": cumulative_benchmark_returns,
            "cumulative_active_return": (
                cumulative_portfolio_returns - cumulative_benchmark_returns
            ),
            "linked_portfolio_contribution": summary[
                "linked_portfolio_contribution"
            ],
            "linked_benchmark_contribution": summary[
                "linked_benchmark_contribution"
            ],
            "linked_active_contribution": summary["linked_active_contribution"],
            "cumulative_portfolio_contribution": np.cumsum(
                _float_array(summary, "linked_portfolio_contribution")
            ),
            "cumulative_benchmark_contribution": np.cumsum(
                _float_array(summary, "linked_benchmark_contribution")
            ),
            "cumulative_active_contribution": np.cumsum(
                _float_array(summary, "linked_active_contribution")
            ),
            "linked_allocation_effect": summary["linked_allocation_effect"],
            "linked_selection_effect": summary["linked_selection_effect"],
            "linked_total_effect": summary["linked_total_effect"],
            "cumulative_allocation_effect": np.cumsum(
                _float_array(summary, "linked_allocation_effect")
            ),
            "cumulative_selection_effect": np.cumsum(
                _float_array(summary, "linked_selection_effect")
            ),
            "cumulative_total_effect": np.cumsum(
                _float_array(summary, "linked_total_effect")
            ),
        },
        columns=CUMULATIVE_COLUMNS,
    )
    return cumulative.reset_index(drop=True)


def _build_period_reconciliation(
    detail: pd.DataFrame, summary: pd.DataFrame
) -> pd.DataFrame:
    """Build reconciliation inputs for every reporting period."""
    aggregate_columns = """portfolio_weight benchmark_weight
    portfolio_contribution benchmark_contribution active_contribution
    allocation_effect selection_effect total_effect""".split()
    period_totals = cast(
        pd.DataFrame,
        detail.groupby(
            ["from_date", "thru_date"],
            as_index=False,
            sort=False,
            observed=True,
        )[aggregate_columns].sum(),
    )
    period_actual = np.column_stack(
        (
            _float_array(period_totals, "portfolio_weight"),
            _float_array(period_totals, "benchmark_weight"),
            _float_array(period_totals, "portfolio_contribution"),
            _float_array(period_totals, "benchmark_contribution"),
            _float_array(period_totals, "active_contribution"),
            _float_array(period_totals, "allocation_effect")
            + _float_array(period_totals, "selection_effect"),
            _float_array(period_totals, "total_effect"),
        )
    )
    period_expected = np.column_stack(
        (
            np.ones(len(summary), dtype=np.float64),
            np.ones(len(summary), dtype=np.float64),
            _float_array(summary, "portfolio_return"),
            _float_array(summary, "benchmark_return"),
            _float_array(summary, "active_return"),
            _float_array(summary, "total_effect"),
            _float_array(summary, "active_return"),
        )
    )
    check_count = len(PERIOD_RECONCILIATION_CHECKS)
    return pd.DataFrame(
        {
            "scope": "period",
            "from_date": np.repeat(
                np.asarray(summary["from_date"], dtype="datetime64[ns]"),
                check_count,
            ),
            "thru_date": np.repeat(
                np.asarray(summary["thru_date"], dtype="datetime64[ns]"),
                check_count,
            ),
            "check": np.tile(PERIOD_RECONCILIATION_CHECKS, len(summary)),
            "actual": period_actual.ravel(),
            "expected": period_expected.ravel(),
        }
    )


def _build_overall_reconciliation(
    detail: pd.DataFrame, summary: pd.DataFrame
) -> pd.DataFrame:
    """Build reconciliation inputs for the complete requested horizon."""
    portfolio_return = _compound_returns(_float_array(summary, "portfolio_return"))
    benchmark_return = _compound_returns(_float_array(summary, "benchmark_return"))
    active_return = portfolio_return - benchmark_return
    overall_actual = np.asarray(
        [
            _column_sum(detail, "linked_portfolio_contribution"),
            _column_sum(detail, "linked_benchmark_contribution"),
            _column_sum(detail, "linked_active_contribution"),
            _column_sum(detail, "linked_allocation_effect")
            + _column_sum(detail, "linked_selection_effect"),
            _column_sum(detail, "linked_total_effect"),
        ],
        dtype=np.float64,
    )
    overall_expected = np.asarray(
        [
            portfolio_return,
            benchmark_return,
            active_return,
            overall_actual[4],
            active_return,
        ],
        dtype=np.float64,
    )
    return pd.DataFrame(
        {
            "scope": "overall",
            "from_date": detail.at[0, "from_date"],
            "thru_date": detail.at[len(detail) - 1, "thru_date"],
            "check": OVERALL_RECONCILIATION_CHECKS,
            "actual": overall_actual,
            "expected": overall_expected,
        }
    )


def _build_reconciliation(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    reconciliation_tolerance: float,
) -> pd.DataFrame:
    """Build positive period and overall financial reconciliation evidence."""
    reconciliation = pd.concat(
        [
            _build_period_reconciliation(detail, summary),
            _build_overall_reconciliation(detail, summary),
        ],
        ignore_index=True,
    )
    reconciliation["residual"] = (
        reconciliation["actual"] - reconciliation["expected"]
    )
    reconciliation["tolerance"] = reconciliation_tolerance
    reconciliation["passed"] = _is_close(
        _float_array(reconciliation, "actual"),
        _float_array(reconciliation, "expected"),
        reconciliation_tolerance,
    )
    reconciliation = reconciliation.loc[:, RECONCILIATION_COLUMNS]
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
    return cast(pd.DataFrame, reconciliation.reset_index(drop=True))


def _validate_result_values(
    name: str,
    frame: pd.DataFrame,
    nullable_columns: tuple[str, ...] = (),
) -> None:
    """Require finite result numbers except in specified undefined-return fields."""
    numeric = cast(pd.DataFrame, frame.select_dtypes(include="number"))
    for column in numeric.columns:
        values = _float_array(numeric, column)
        valid = np.isfinite(values)
        if column in nullable_columns:
            valid |= np.isnan(values)
        if not valid.all():
            raise AttributionError(f"{name} column {column!r} contains a non-finite value")


def calculate_attribution(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    reconciliation_tolerance: float = _TOLERANCE,
) -> AttributionResult:
    """Calculate portable multi-period Brinson-Fachler attribution.

    Args:
        portfolio: Prepared portfolio rows satisfying the portable input contract.
        benchmark: Prepared benchmark rows for the same reporting periods.
        reconciliation_tolerance: Positive finite relative and absolute tolerance
            used for input weight totals and returned reconciliation evidence. The
            standalone default is ``1e-12``; a host may explicitly request a wider
            compatibility tolerance without changing any calculation formula.

    Returns:
        Five new, caller-owned result frames containing period, overall, cumulative,
        and reconciliation values.

    Raises:
        TypeError: If either input is not a pandas DataFrame.
        AttributionError: If financial input is invalid or a calculation invariant
            fails.

    Notes:
        Selection is portfolio-weighted and absorbs interaction. Contributions use
        logarithmic linking; active effects use Carino linking. Supplied contribution
        is authoritative; otherwise contribution is derived as weight multiplied by
        return.
    """
    if not isinstance(portfolio, pd.DataFrame):
        raise TypeError("portfolio must be a pandas DataFrame")
    if not isinstance(benchmark, pd.DataFrame):
        raise TypeError("benchmark must be a pandas DataFrame")
    tolerance = _normalize_reconciliation_tolerance(reconciliation_tolerance)

    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        normalized_portfolio = _normalize_input(portfolio, "portfolio")
        normalized_benchmark = _normalize_input(benchmark, "benchmark")
        _validate_matched_periods(
            normalized_portfolio,
            normalized_benchmark,
            tolerance,
        )
        equalized = _equalize_universe(normalized_portfolio, normalized_benchmark)
        period_detail = _link_period_detail(_build_period_detail(equalized))
        period_summary = _build_period_summary(period_detail)
        overall_detail = _build_overall_detail(equalized, period_detail)
        cumulative = _build_cumulative(period_summary)
        reconciliation = _build_reconciliation(
            period_detail,
            period_summary,
            tolerance,
        )
    _validate_result_values(
        "period_detail",
        period_detail,
        ("portfolio_return", "benchmark_return", "active_return"),
    )
    _validate_result_values(
        "overall_detail",
        overall_detail,
        ("portfolio_return", "benchmark_return", "active_return"),
    )
    for name, frame in (
        ("period_summary", period_summary),
        ("cumulative", cumulative),
        ("reconciliation", reconciliation),
    ):
        _validate_result_values(name, frame)
    return AttributionResult(
        period_detail=period_detail,
        period_summary=period_summary,
        overall_detail=overall_detail,
        cumulative=cumulative,
        reconciliation=reconciliation,
    )


__all__ = ["AttributionError", "AttributionResult", "calculate_attribution"]
