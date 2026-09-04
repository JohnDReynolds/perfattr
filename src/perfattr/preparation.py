"""Normalize source-period performance data before attribution preparation.

This module starts the portable preparation boundary defined by roadmap 2. It
validates source-neutral pandas inputs and selects one portfolio from an already
loaded frame. Calendar alignment, classification mapping, and consolidation are
added by later roadmap steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd

from perfattr._validation import (
    float_array as _float_array,
    has_true as _has_true,
    is_close as _is_close,
    normalize_dates,
    normalize_identity,
    normalize_numeric,
    normalize_reconciliation_tolerance,
    raise_invalid,
)


_TOLERANCE = 1e-12
_REQUIRED_COLUMNS = tuple("from_date thru_date identifier weight return".split())
_OPTIONAL_COLUMNS = (
    "contribution",
    "portfolio_code",
    "name",
)
_NORMALIZED_COLUMNS = tuple(
    "from_date thru_date quantity_of_days identifier weight return contribution".split()
)


class PreparationError(ValueError):
    """Report invalid preparation input or a failed preparation invariant."""


class PreparationWarning(RuntimeWarning):
    """Report valid preparation input truncated before an incomplete bucket."""


@dataclass
class _NormalizedPerformance:
    """Hold one validated source-period performance stream.

    Attributes:
        frame: Normalized source-period rows owned by this result.
        contribution_was_supplied: Whether the caller supplied authoritative
            contribution rather than requesting weight-times-return derivation.

    Notes:
        This is a package-internal boundary for later preparation steps. The frame is
        independently mutable and does not share writable pandas data with the caller.
    """

    frame: pd.DataFrame
    contribution_was_supplied: bool


def _raise_invalid(context: str, message: str) -> None:
    """Raise a consistently formatted preparation error."""
    raise_invalid(PreparationError, context, message)


def _validate_period_structure(frame: pd.DataFrame, context: str) -> None:
    """Validate unique identifier rows and nonoverlapping inclusive periods."""
    key_columns = ["from_date", "thru_date", "identifier"]
    if frame.duplicated(key_columns).any():
        _raise_invalid(context, "contains a duplicate period and identifier key")
    if (frame["from_date"] > frame["thru_date"]).any():
        _raise_invalid(context, "contains a from_date after its thru_date")

    periods = cast(
        pd.DataFrame,
        frame[["from_date", "thru_date"]].drop_duplicates(),
    ).sort_values(["thru_date", "from_date"], kind="stable")
    thru_dates = cast(pd.Series, periods["thru_date"])
    if _has_true(thru_dates.duplicated()):
        _raise_invalid(context, "maps one thru_date to more than one source period")
    if len(periods) > 1:
        starts = np.asarray(periods["from_date"], dtype="datetime64[ns]")
        ends = np.asarray(periods["thru_date"], dtype="datetime64[ns]")
        if np.any(starts[1:] <= ends[:-1]):
            _raise_invalid(context, "contains overlapping source periods")


def _validate_period_totals(
    frame: pd.DataFrame,
    context: str,
    tolerance: float,
) -> None:
    """Require finite contribution totals and unit net weight by source period.

    The weight check uses the same tolerance as later financial reconciliation.
    Signed constituent weights remain valid; only their net period exposure must be
    one. Contribution totals may differ from weighted returns when contribution is
    authoritative, but their sum must remain finite for subsequent linking.

    Args:
        frame: Normalized source-period performance rows.
        context: Human-readable input label used in errors.
        tolerance: Positive reconciliation tolerance.

    Raises:
        PreparationError: If a period weight does not sum to one or contribution
            summation overflows to a non-finite value.
    """
    grouped = frame.groupby(
        ["from_date", "thru_date"],
        sort=False,
        observed=True,
    )
    summed = cast(
        pd.DataFrame,
        grouped[["weight", "contribution"]].sum(),
    )
    totals = summed.reset_index()
    weights = _float_array(totals, "weight")
    contributions = _float_array(totals, "contribution")
    if not np.isfinite(weights).all():
        _raise_invalid(context, "has a non-finite source-period weight total")
    if not np.isfinite(contributions).all():
        _raise_invalid(context, "has a non-finite source-period contribution total")

    passing_weights = _is_close(weights, np.ones(len(weights)), tolerance)
    if not passing_weights.all():
        first_failure = int(np.flatnonzero(~passing_weights)[0])
        period = totals.iloc[first_failure]
        _raise_invalid(
            context,
            "weights must sum to 1.0 for source period "
            f"{period['from_date'].date()} to {period['thru_date'].date()}; "
            f"received {weights[first_failure]:.17g}",
        )


def _normalize_source_columns(frame: pd.DataFrame, context: str) -> None:
    """Normalize required source columns and derive inclusive period days.

    Args:
        frame: Independently owned source frame modified in place.
        context: Human-readable input label used in errors.

    Notes:
        Mutation is confined to the deep copy made by ``_normalize_performance``;
        caller-owned data is never modified.
    """
    frame["from_date"] = normalize_dates(
        frame, "from_date", context, PreparationError
    )
    frame["thru_date"] = normalize_dates(
        frame, "thru_date", context, PreparationError
    )
    frame["identifier"] = normalize_identity(
        frame, "identifier", context, PreparationError
    )
    frame["weight"] = normalize_numeric(
        frame, "weight", context, PreparationError, nullable=False
    )
    frame["return"] = normalize_numeric(
        frame, "return", context, PreparationError, nullable=True
    )

    if "portfolio_code" in frame.columns:
        frame["portfolio_code"] = normalize_identity(
            frame,
            "portfolio_code",
            context,
            PreparationError,
        )
        if frame["portfolio_code"].nunique() != 1:
            _raise_invalid(
                context,
                "contains multiple portfolio codes; call select_portfolio first",
            )

    _validate_period_structure(frame, context)
    inclusive_days = (frame["thru_date"] - frame["from_date"]).dt.days + 1
    frame["quantity_of_days"] = inclusive_days.astype("int64")


def _normalize_contributions(frame: pd.DataFrame, context: str) -> bool:
    """Normalize authoritative contribution or derive it from weight and return.

    Args:
        frame: Independently owned normalized source frame modified in place.
        context: Human-readable input label used in errors.

    Returns:
        ``True`` when contribution was supplied and authoritative; otherwise
        ``False`` after derived contribution has been added.

    Raises:
        PreparationError: If return/contribution semantics are invalid or would
            produce a non-finite effective return.

    Notes:
        Division is used only to prove that later attribution can form a finite
        effective return. The authoritative contribution remains unchanged.
    """
    weights = _float_array(frame, "weight")
    input_returns = _float_array(frame, "return")
    present_returns = ~np.isnan(input_returns)
    if np.any(input_returns[present_returns] <= -1.0):
        _raise_invalid(context, "column 'return' must be greater than -1.0 when present")
    if np.any((weights != 0.0) & ~present_returns):
        _raise_invalid(context, "contains a nonzero weight with a null return")

    contribution_was_supplied = "contribution" in frame.columns
    if contribution_was_supplied:
        frame["contribution"] = normalize_numeric(
            frame,
            "contribution",
            context,
            PreparationError,
            nullable=False,
        )
        contributions = _float_array(frame, "contribution")
        invalid_undefined_returns = (
            (weights == 0.0) & (contributions != 0.0) & present_returns
        )
        if np.any(invalid_undefined_returns):
            _raise_invalid(
                context,
                "requires a null return when weight is zero and contribution is nonzero",
            )
    else:
        contributions = np.zeros(len(frame), dtype=np.float64)
        # Missing return is valid only at zero weight, where the mathematical
        # contribution is exactly zero and no undefined multiplication is needed.
        with np.errstate(over="ignore", invalid="ignore"):
            np.multiply(
                weights,
                input_returns,
                out=contributions,
                where=present_returns,
            )
        if not np.isfinite(contributions).all():
            _raise_invalid(context, "derives a non-finite contribution")
        frame["contribution"] = contributions

    effective_returns = np.zeros(len(frame), dtype=np.float64)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        np.divide(
            contributions,
            weights,
            out=effective_returns,
            where=weights != 0.0,
        )
    effective_returns[(weights == 0.0) & (contributions != 0.0)] = np.nan
    if not np.isfinite(effective_returns[~np.isnan(effective_returns)]).all():
        _raise_invalid(context, "produces a non-finite effective return")
    return contribution_was_supplied


def _normalize_performance(
    frame: pd.DataFrame,
    context: str,
    reconciliation_tolerance: float = _TOLERANCE,
) -> _NormalizedPerformance:
    """Validate and normalize one source-period performance stream.

    This package-internal function establishes the source-neutral boundary used by
    later alignment, mapping, and consolidation steps. It derives inclusive day counts
    from period dates and derives contribution only when the caller did not supply it.

    Args:
        frame: Source-period performance rows using the preparation specification.
        context: Human-readable input label such as ``"portfolio input"``.
        reconciliation_tolerance: Relative and absolute tolerance for period net-weight
            validation.

    Returns:
        Independently owned normalized rows and whether contribution was supplied.

    Raises:
        TypeError: If ``frame`` is not a pandas DataFrame or the tolerance is not a
            real number.
        PreparationError: If the schema, values, period structure, or financial
            invariants are invalid.

    Notes:
        Returns-only rows use ``weight * return``. A zero-weight row with a null return
        derives zero contribution. Supplied contribution is authoritative, including
        for zero-weight fee or financing rows, and is never reconstructed from return.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{context} must be a pandas DataFrame")
    tolerance = normalize_reconciliation_tolerance(
        reconciliation_tolerance,
        PreparationError,
    )
    if frame.columns.has_duplicates:
        _raise_invalid(context, "contains duplicate column labels")
    missing = [column for column in _REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        _raise_invalid(context, f"is missing required columns: {', '.join(missing)}")
    if frame.empty:
        _raise_invalid(context, "must not be empty")

    selected_columns = [*_REQUIRED_COLUMNS]
    selected_columns.extend(
        column for column in _OPTIONAL_COLUMNS if column in frame.columns
    )
    normalized = cast(
        pd.DataFrame,
        frame.loc[:, selected_columns].copy(deep=True),
    )
    _normalize_source_columns(normalized, context)
    contribution_was_supplied = _normalize_contributions(normalized, context)
    _validate_period_totals(normalized, context, tolerance)
    ordered_columns = [*_NORMALIZED_COLUMNS]
    ordered_columns.extend(
        column for column in ("portfolio_code", "name") if column in normalized.columns
    )
    normalized = cast(
        pd.DataFrame,
        normalized.loc[:, ordered_columns].sort_values(
            ["thru_date", "identifier"],
            kind="stable",
        ),
    ).reset_index(drop=True)
    return _NormalizedPerformance(normalized, contribution_was_supplied)


def select_portfolio(
    performance: pd.DataFrame,
    portfolio_code: str,
) -> pd.DataFrame:
    """Select one portfolio from an in-memory source-neutral performance frame.

    Args:
        performance: Performance rows containing a ``portfolio_code`` column.
        portfolio_code: Exact portfolio identity to select after surrounding
            whitespace is removed.

    Returns:
        Independently owned matching rows with a zero-based RangeIndex. The normalized
        ``portfolio_code`` column is retained for lineage.

    Raises:
        TypeError: If ``performance`` is not a pandas DataFrame or ``portfolio_code``
            is not a string.
        PreparationError: If the frame has duplicate columns, lacks
            ``portfolio_code``, contains an invalid code, receives a blank requested
            code, or has no exact match.

    Notes:
        Selection is deliberately exact and case-sensitive. Vendor discovery,
        composite expansion, and source-level predicate pushdown remain host-adapter
        responsibilities.
    """
    if not isinstance(performance, pd.DataFrame):
        raise TypeError("performance must be a pandas DataFrame")
    if not isinstance(portfolio_code, str):
        raise TypeError("portfolio_code must be a string")
    if performance.columns.has_duplicates:
        _raise_invalid("performance input", "contains duplicate column labels")
    if "portfolio_code" not in performance.columns:
        _raise_invalid("performance input", "is missing required column: portfolio_code")

    requested_code = portfolio_code.strip()
    if not requested_code:
        raise PreparationError("portfolio_code must not be blank")

    selected = performance.copy(deep=True)
    selected["portfolio_code"] = normalize_identity(
        selected,
        "portfolio_code",
        "performance input",
        PreparationError,
    )
    selected = cast(
        pd.DataFrame,
        selected.loc[selected["portfolio_code"] == requested_code].copy(deep=True),
    )
    if selected.empty:
        raise PreparationError(f"no performance rows match portfolio_code {requested_code!r}")
    return selected.reset_index(drop=True)


__all__ = [
    "PreparationError",
    "PreparationWarning",
    "select_portfolio",
]
