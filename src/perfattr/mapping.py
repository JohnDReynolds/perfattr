"""Validate static classification mappings and roll up source-period rows."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from perfattr._exceptions import PreparationError
from perfattr._schemas import NORMALIZED_PERFORMANCE_COLUMNS
from perfattr._validation import (
    float_array as _float_array,
    is_close as _is_close,
    normalize_identity_pairs,
    normalize_reconciliation_tolerance,
    raise_invalid,
    sum_by_period,
)


_TOLERANCE = 1e-12
_MAPPING_COLUMNS = ("identifier", "classification_identifier")


def _raise_invalid(context: str, message: str) -> None:
    """Raise a consistently formatted mapping error."""
    raise_invalid(PreparationError, context, message)


def _normalize_mapping(mapping: pd.DataFrame, context: str) -> pd.DataFrame:
    """Validate and normalize one static identifier mapping.

    Args:
        mapping: Static source-to-classification identifier pairs.
        context: Human-readable mapping label included in errors.

    Returns:
        Independently owned, deduplicated pairs ordered by source and classification
        identifier.

    Raises:
        TypeError: If ``mapping`` is not a pandas DataFrame.
        PreparationError: If columns or identity values violate the static mapping
            contract, or one source identifier has conflicting classifications.

    Notes:
        Every row is validated before later performance matching. Invalid unused rows
        therefore cannot disappear silently. Exact duplicate pairs are harmless and
        collapse only after surrounding identity whitespace has been removed.
    """
    return normalize_identity_pairs(
        mapping,
        _MAPPING_COLUMNS,
        context,
        PreparationError,
        "maps source identifiers to multiple classifications",
    )


def normalize_mapping(mapping: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize a static classification mapping.

    Args:
        mapping: DataFrame containing exactly ``identifier`` and
            ``classification_identifier`` columns.

    Returns:
        An independently owned, deduplicated mapping in deterministic order.

    Raises:
        TypeError: If ``mapping`` is not a pandas DataFrame.
        PreparationError: If its schema, identities, or one-to-one mapping contract
            is invalid.
    """
    return _normalize_mapping(mapping, "mapping input")


def _mapped_identifiers(
    performance: pd.DataFrame,
    mapping: pd.DataFrame,
) -> pd.Series:
    """Return mapped identifiers with exact identity fallback for absent keys."""
    lookup = dict(
        zip(
            mapping["identifier"],
            mapping["classification_identifier"],
            strict=True,
        )
    )
    identifiers = cast(pd.Series, performance["identifier"])
    mapped = cast(pd.Series, identifiers.map(lookup))
    return cast(
        pd.Series,
        mapped.where(mapped.notna(), identifiers).astype("string[python]"),
    )


def _derive_mapped_returns(frame: pd.DataFrame, context: str) -> pd.Series:
    """Derive effective returns from mapped weight and contribution.

    Args:
        frame: Mapped source-period groups with summed weight and contribution.
        context: Human-readable side included in errors.

    Returns:
        Float64 effective returns using exact-zero branch semantics.

    Raises:
        PreparationError: If aggregation or division produces a non-finite defined
            value.

    Notes:
        A zero-weight, zero-contribution group receives zero. A zero-weight,
        nonzero-contribution group has an undefined return and receives null. A small
        nonzero weight is never treated as zero by the reconciliation tolerance.
    """
    weights = _float_array(frame, "weight")
    contributions = _float_array(frame, "contribution")
    if not np.isfinite(weights).all() or not np.isfinite(contributions).all():
        _raise_invalid(context, "classification aggregation produced a non-finite value")

    mapped_returns = np.zeros(len(frame), dtype=np.float64)
    nonzero_weights = weights != 0.0
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        np.divide(
            contributions,
            weights,
            out=mapped_returns,
            where=nonzero_weights,
        )
    mapped_returns[(weights == 0.0) & (contributions != 0.0)] = np.nan
    if not np.isfinite(mapped_returns[~np.isnan(mapped_returns)]).all():
        _raise_invalid(context, "classification aggregation produced a non-finite return")
    return pd.Series(mapped_returns, index=frame.index, dtype="float64")


def _validate_mapping_conservation(
    source: pd.DataFrame,
    mapped: pd.DataFrame,
    context: str,
    tolerance: float,
) -> None:
    """Require mapping to preserve each source period's weight and contribution.

    Args:
        source: Normalized source-period rows before mapping.
        mapped: Rolled-up source-period rows after mapping.
        context: Human-readable side included in errors.
        tolerance: Positive relative and absolute reconciliation tolerance.

    Raises:
        PreparationError: If period keys change or a financial total is not conserved.
    """
    columns = ("weight", "contribution")
    source_totals = sum_by_period(source, columns)
    mapped_totals = sum_by_period(mapped, columns)
    period_columns = ["from_date", "thru_date"]
    if len(source_totals) != len(mapped_totals) or not source_totals[
        period_columns
    ].equals(mapped_totals[period_columns]):
        _raise_invalid(context, "classification mapping changed source-period keys")

    for column in columns:
        source_values = _float_array(source_totals, column)
        mapped_values = _float_array(mapped_totals, column)
        passing = _is_close(mapped_values, source_values, tolerance)
        if not passing.all():
            failure = int(np.flatnonzero(~passing)[0])
            period = source_totals.iloc[failure]
            _raise_invalid(
                context,
                f"classification mapping did not conserve {column} for source period "
                f"{period['from_date'].date()} to {period['thru_date'].date()}",
            )


def _roll_up_mapping(performance: pd.DataFrame, context: str) -> pd.DataFrame:
    """Aggregate mapped weights and contributions at source-period granularity."""
    group_columns = [
        "from_date",
        "thru_date",
        "quantity_of_days",
        "identifier",
    ]
    grouped = performance.groupby(group_columns, sort=True, observed=True)
    summed = cast(pd.DataFrame, grouped[["weight", "contribution"]].sum())
    mapped = summed.reset_index()
    mapped["return"] = _derive_mapped_returns(mapped, context)
    return cast(
        pd.DataFrame,
        mapped.loc[:, list(NORMALIZED_PERFORMANCE_COLUMNS)],
    ).sort_values(["thru_date", "identifier"], kind="stable").reset_index(drop=True)


def _map_performance(
    performance: pd.DataFrame,
    mapping: pd.DataFrame | None,
    context: str,
    reconciliation_tolerance: float = _TOLERANCE,
) -> pd.DataFrame:
    """Apply an optional static classification mapping to normalized performance.

    Args:
        performance: Source-period rows produced by ``_normalize_performance``.
        mapping: Optional static source-to-classification identifier pairs.
        context: Human-readable side such as ``"portfolio input"``.
        reconciliation_tolerance: Positive relative and absolute tolerance used only
            to verify conservation.

    Returns:
        Independently owned normalized columns at source-period and mapped-identifier
        granularity. Rows are deterministically ordered.

    Raises:
        TypeError: If performance or mapping is not a pandas DataFrame, or the
            tolerance is not a real number.
        PreparationError: If the mapping contract, aggregation, or conservation check
            fails.

    Notes:
        When ``mapping`` is ``None``, identifier returns are preserved exactly. When a
        mapping is supplied, absent identifiers fall back to themselves and collisions
        are intentionally aggregated. Mapping occurs before frequency consolidation so
        a future effective-dated mapping can retain this pipeline order.
    """
    if not isinstance(performance, pd.DataFrame):
        raise TypeError(f"{context} must be a pandas DataFrame")
    tolerance = normalize_reconciliation_tolerance(
        reconciliation_tolerance,
        PreparationError,
    )
    source = cast(
        pd.DataFrame,
        performance.loc[:, list(NORMALIZED_PERFORMANCE_COLUMNS)].copy(deep=True),
    )
    if mapping is None:
        return source.sort_values(
            ["thru_date", "identifier"],
            kind="stable",
        ).reset_index(drop=True)

    normalized_mapping = _normalize_mapping(mapping, f"{context} mapping")
    source["identifier"] = _mapped_identifiers(source, normalized_mapping)
    mapped = _roll_up_mapping(source, context)
    _validate_mapping_conservation(performance, mapped, context, tolerance)
    return mapped


__all__ = ["normalize_mapping"]
