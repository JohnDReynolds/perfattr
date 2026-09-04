"""Shared low-level validation primitives for portable pandas boundaries."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NoReturn, cast

import numpy as np
import numpy.typing as npt
import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_dtype, is_numeric_dtype


def float_array(frame: pd.DataFrame, column: str) -> npt.NDArray[np.float64]:
    """Return a DataFrame column as a float64 NumPy array."""
    return np.asarray(frame[column], dtype=np.float64)


def has_true(values: pd.Series) -> bool:
    """Return whether a boolean Series contains a true value."""
    return bool(np.asarray(values, dtype=np.bool_).any())


def is_close(
    actual: npt.NDArray[np.float64],
    expected: npt.NDArray[np.float64],
    tolerance: float,
) -> npt.NDArray[np.bool_]:
    """Apply the project's symmetric relative and absolute tolerance."""
    difference = np.abs(actual - expected)
    scale = np.maximum(np.abs(actual), np.abs(expected))
    return difference <= np.maximum(tolerance * scale, tolerance)


def sum_by_period(
    frame: pd.DataFrame,
    columns: Sequence[str],
) -> pd.DataFrame:
    """Sum numeric columns by deterministic inclusive period boundaries.

    Args:
        frame: Frame containing normalized ``from_date`` and ``thru_date`` columns.
        columns: Numeric columns to sum.

    Returns:
        One chronologically ordered row per inclusive period.
    """
    grouped = frame.groupby(
        ["from_date", "thru_date"],
        sort=True,
        observed=True,
    )
    summed = cast(pd.DataFrame, grouped[list(columns)].sum())
    return summed.reset_index()


def raise_invalid(
    error_type: type[ValueError],
    context: str,
    message: str,
) -> NoReturn:
    """Raise one domain-specific validation error with consistent context."""
    raise error_type(f"{context} {message}")


def normalize_reconciliation_tolerance(
    value: float,
    error_type: type[ValueError],
) -> float:
    """Require a finite, positive, non-boolean reconciliation tolerance.

    Args:
        value: Candidate relative and absolute tolerance.
        error_type: Domain error raised for a numeric value outside the contract.

    Returns:
        Validated ordinary float.

    Raises:
        TypeError: If ``value`` is not a non-boolean real number.
        ValueError: Using ``error_type`` when the numeric value is non-finite or not
            positive.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("reconciliation_tolerance must be a real number")
    tolerance = float(value)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise error_type(
            "reconciliation_tolerance must be finite and greater than zero"
        )
    return tolerance


def normalize_dates(
    frame: pd.DataFrame,
    column: str,
    context: str,
    error_type: type[ValueError],
) -> pd.Series:
    """Normalize one required date column to timezone-naive midnight values.

    Args:
        frame: DataFrame containing the date column.
        column: Column to normalize.
        context: Human-readable boundary included in errors.
        error_type: Domain error raised for invalid values.

    Returns:
        A timezone-naive ``datetime64[ns]`` Series normalized to midnight.

    Raises:
        ValueError: Using ``error_type`` for null, numeric, invalid, or timezone-aware
            values.
    """
    values = cast(pd.Series, frame[column])
    if has_true(values.isna()):
        raise_invalid(error_type, context, f"column {column!r} contains null values")
    if is_numeric_dtype(values.dtype) or is_bool_dtype(values.dtype):
        raise_invalid(error_type, context, f"column {column!r} must contain dates")

    try:
        normalized = pd.to_datetime(values, errors="raise", format="mixed")
    except (TypeError, ValueError, OverflowError) as error:
        raise error_type(f"{context} column {column!r} contains an invalid date") from error

    if isinstance(normalized.dtype, pd.DatetimeTZDtype):
        raise_invalid(error_type, context, f"column {column!r} must be timezone-naive")
    if not is_datetime64_dtype(normalized.dtype):
        raise_invalid(error_type, context, f"column {column!r} must be timezone-naive")
    return cast(
        pd.Series,
        normalized.dt.normalize().astype("datetime64[ns]"),
    )


def normalize_numeric(
    frame: pd.DataFrame,
    column: str,
    context: str,
    error_type: type[ValueError],
    *,
    nullable: bool,
) -> pd.Series:
    """Validate and normalize one financial numeric column.

    Args:
        frame: DataFrame containing the numeric column.
        column: Column to normalize.
        context: Human-readable boundary included in errors.
        error_type: Domain error raised for invalid values.
        nullable: Whether null values are valid.

    Returns:
        A float64 Series with allowed nulls preserved.

    Raises:
        ValueError: Using ``error_type`` for strings, booleans, forbidden nulls, or
            non-finite values.
    """
    values = cast(pd.Series, frame[column])
    if is_bool_dtype(values.dtype) or not is_numeric_dtype(values.dtype):
        raise_invalid(
            error_type,
            context,
            f"column {column!r} must contain numbers, not strings or booleans",
        )
    if not nullable and has_true(values.isna()):
        raise_invalid(error_type, context, f"column {column!r} contains null values")

    normalized = cast(pd.Series, values.astype("float64"))
    finite_values = np.asarray(normalized.dropna(), dtype=np.float64)
    if not np.isfinite(finite_values).all():
        raise_invalid(
            error_type,
            context,
            f"column {column!r} must contain only finite values",
        )
    return normalized


def normalize_identity(
    frame: pd.DataFrame,
    column: str,
    context: str,
    error_type: type[ValueError],
) -> pd.Series:
    """Validate and trim an identity column without coercing its values.

    Args:
        frame: DataFrame containing the identity column.
        column: Column to normalize.
        context: Human-readable boundary included in errors.
        error_type: Domain error raised for invalid values.

    Returns:
        A ``string[python]`` Series with surrounding whitespace removed.

    Raises:
        ValueError: Using ``error_type`` for null, non-string, or blank identities.

    Notes:
        Avoiding coercion preserves leading zeroes and prevents numeric identifiers
        from being silently reinterpreted.
    """
    values = cast(pd.Series, frame[column])
    value_types = cast(pd.Series, values.map(lambda value: isinstance(value, str)))
    if has_true(values.isna()) or not bool(
        np.asarray(value_types, dtype=np.bool_).all()
    ):
        raise_invalid(
            error_type,
            context,
            f"column {column!r} must contain non-null strings",
        )
    normalized = cast(pd.Series, values.astype("string[python]").str.strip())
    if has_true(normalized.eq("")):
        raise_invalid(error_type, context, f"column {column!r} contains an empty string")
    return normalized


def require_exact_columns(
    frame: pd.DataFrame,
    columns: Sequence[str],
    context: str,
    error_type: type[ValueError],
) -> None:
    """Require a DataFrame to contain exactly one set of unique column labels.

    Args:
        frame: Candidate pandas boundary frame.
        columns: Exact required column labels.
        context: Human-readable boundary included in errors.
        error_type: Domain error raised for an invalid schema.

    Raises:
        TypeError: If ``frame`` is not a pandas DataFrame.
        ValueError: Using ``error_type`` for duplicate, missing, or additional labels.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{context} must be a pandas DataFrame")
    if frame.columns.has_duplicates:
        raise_invalid(error_type, context, "contains duplicate column labels")

    missing = [column for column in columns if column not in frame.columns]
    extra = [column for column in frame.columns if column not in columns]
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing columns: {', '.join(missing)}")
        if extra:
            labels = ", ".join(str(column) for column in extra)
            details.append(f"unexpected columns: {labels}")
        raise_invalid(
            error_type,
            context,
            "must contain exactly the required columns; " + "; ".join(details),
        )


def normalize_identity_pairs(
    frame: pd.DataFrame,
    columns: tuple[str, str],
    context: str,
    error_type: type[ValueError],
    conflict_message: str,
) -> pd.DataFrame:
    """Validate an exact, one-to-one pair of textual identity columns.

    Args:
        frame: Candidate two-column metadata or mapping frame.
        columns: Exact ordered column names required by the boundary.
        context: Human-readable boundary included in errors.
        error_type: Domain error raised for invalid values.
        conflict_message: Explanation placed before conflicting key values.

    Returns:
        Independently owned, trimmed, deduplicated pairs in deterministic order.

    Raises:
        TypeError: If ``frame`` is not a pandas DataFrame.
        ValueError: Using ``error_type`` for invalid schema, identities, or conflicting
            pairs.
    """
    require_exact_columns(frame, columns, context, error_type)

    normalized = cast(pd.DataFrame, frame.loc[:, list(columns)].copy(deep=True))
    for column in columns:
        normalized[column] = normalize_identity(
            normalized,
            column,
            context,
            error_type,
        )
    normalized = normalized.drop_duplicates(ignore_index=True)

    conflicts = cast(
        pd.Series,
        normalized.loc[normalized.duplicated(columns[0], keep=False), columns[0]],
    )
    if not conflicts.empty:
        identifiers = sorted(str(value) for value in conflicts.unique())
        raise_invalid(error_type, context, f"{conflict_message}: {identifiers}")
    return normalized.sort_values(list(columns), kind="stable").reset_index(drop=True)
