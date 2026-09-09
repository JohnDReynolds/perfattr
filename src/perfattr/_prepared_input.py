"""Normalize and align prepared inputs shared by attribution calculations.

Arithmetic and geometric attribution consume the same caller-facing prepared rows.
This module owns that common boundary without owning either calculation's formulas.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from perfattr._exceptions import AttributionError
from perfattr._performance_rows import _normalize_performance_row_values
from perfattr._schemas import PREPARED_REQUIRED_COLUMNS
from perfattr._validation import (
    float_array as _float_array,
    has_true as _has_true,
    is_close as _is_close,
    normalize_dates,
    normalize_identity,
    normalize_numeric,
    normalize_positive_int64,
    raise_invalid,
)


_REQUIRED_COLUMNS = PREPARED_REQUIRED_COLUMNS


def _raise_invalid(side: str, message: str) -> None:
    """Raise a consistently formatted prepared-input error."""
    raise_invalid(AttributionError, f"{side} input", message)


def _normalize_dates(frame: pd.DataFrame, column: str, side: str) -> pd.Series:
    """Normalize a required date column to timezone-naive midnight values."""
    return normalize_dates(frame, column, f"{side} input", AttributionError)


def _normalize_numeric(
    frame: pd.DataFrame,
    column: str,
    side: str,
    *,
    nullable: bool,
) -> pd.Series:
    """Validate and normalize one prepared financial numeric column."""
    return normalize_numeric(
        frame,
        column,
        f"{side} input",
        AttributionError,
        nullable=nullable,
    )


def _normalize_identifiers(frame: pd.DataFrame, side: str) -> pd.Series:
    """Validate prepared identifiers without coercing their values."""
    return normalize_identity(frame, "identifier", f"{side} input", AttributionError)


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
    """Validate and copy one caller-owned prepared attribution frame.

    Args:
        frame: Prepared portfolio or benchmark rows.
        side: ``"portfolio"`` or ``"benchmark"``, included in diagnostics.

    Returns:
        A normalized, independently owned frame containing authoritative or derived
        contribution plus separate input and effective returns.

    Raises:
        AttributionError: If the schema, values, period structure, or financial row
            semantics violate the prepared-input contract.

    Notes:
        Caller data is never mutated. Supplied contribution remains authoritative;
        otherwise it is derived from weight and input return.
    """
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
    normalized["quantity_of_days"] = normalize_positive_int64(
        normalized,
        "quantity_of_days",
        f"{side} input",
        AttributionError,
    )

    row_values = _normalize_performance_row_values(
        normalized,
        f"{side} input",
        AttributionError,
        nonfinite_derived_message="produces a non-finite effective return",
    )
    normalized["input_return"] = row_values.input_returns
    normalized["effective_return"] = row_values.effective_returns
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
    """Validate cross-side period, day-count, weight, and return contracts.

    Args:
        portfolio: Normalized prepared portfolio rows.
        benchmark: Normalized prepared benchmark rows.
        reconciliation_tolerance: Relative and absolute net-weight tolerance.

    Raises:
        AttributionError: If period coverage, day counts, weight totals, or period
            returns violate the shared calculation domain.
    """
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
    """Outer-join two normalized sides and synthesize neutral missing rows.

    Args:
        portfolio: Normalized portfolio rows with validated reporting periods.
        benchmark: Normalized benchmark rows with identical reporting periods.

    Returns:
        One deterministic frame containing the union of both identifier universes.

    Notes:
        An identifier absent from one side receives zero weight, input return,
        effective return, and contribution on that side. A present unexposed row keeps
        its established null effective-return semantics.
    """
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
