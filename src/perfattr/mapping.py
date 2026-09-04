"""Normalize classification mappings and roll up mapped source-period rows."""

from __future__ import annotations

from typing import NoReturn, cast

import numpy as np
import pandas as pd

from perfattr._exceptions import PreparationError
from perfattr._schemas import NORMALIZED_PERFORMANCE_COLUMNS
from perfattr._validation import (
    float_array as _float_array,
    is_close as _is_close,
    normalize_dates,
    normalize_identity,
    normalize_identity_pairs,
    normalize_reconciliation_tolerance,
    raise_invalid,
    require_exact_columns,
    sum_by_period,
)


_TOLERANCE = 1e-12
_STATIC_MAPPING_COLUMNS = ("identifier", "classification_identifier")
_EFFECTIVE_MAPPING_COLUMNS = (
    "from_date",
    "thru_date",
    *_STATIC_MAPPING_COLUMNS,
)
_MAPPING_DATE_COLUMNS = ("from_date", "thru_date")
_EffectiveAssignment = tuple[pd.Timestamp, pd.Timestamp, str]


def _raise_invalid(context: str, message: str) -> NoReturn:
    """Raise a consistently formatted mapping error."""
    raise_invalid(PreparationError, context, message)


def _uses_effective_schema(mapping: pd.DataFrame, context: str) -> bool:
    """Validate the mapping schema and report whether it contains effective dates.

    Args:
        mapping: Candidate static or effective-dated mapping.
        context: Human-readable mapping label included in errors.

    Returns:
        ``True`` for the exact effective-dated schema and ``False`` for the exact
        static schema.

    Raises:
        TypeError: If ``mapping`` is not a pandas DataFrame.
        PreparationError: If columns do not match exactly one supported schema.

    Notes:
        Presence of either date label selects the effective schema for error reporting.
        This makes a partially supplied dated mapping report its missing date or
        identity fields instead of describing its date column as an unrelated static
        extra.
    """
    if not isinstance(mapping, pd.DataFrame):
        raise TypeError(f"{context} must be a pandas DataFrame")

    effective = any(column in mapping.columns for column in _MAPPING_DATE_COLUMNS)
    required = _EFFECTIVE_MAPPING_COLUMNS if effective else _STATIC_MAPPING_COLUMNS
    require_exact_columns(mapping, required, context, PreparationError)
    return effective


def _assignment_sample(mapping: pd.DataFrame) -> str:
    """Return a small deterministic description of invalid dated assignments."""
    descriptions: list[str] = []
    for row in mapping.head(3).itertuples(index=False, name=None):
        from_date, thru_date, identifier, _classification = row
        descriptions.append(
            f"{identifier!r} from {cast(pd.Timestamp, from_date).date()} to "
            f"{cast(pd.Timestamp, thru_date).date()}"
        )
    return f"[{', '.join(descriptions)}]"


def _overlapping_interval_indices(mapping: pd.DataFrame) -> list[int]:
    """Return rows overlapping the latest prior interval for their identifier."""
    latest_thru_by_identifier: dict[str, pd.Timestamp] = {}
    overlap_indices: list[int] = []
    for index, row in enumerate(mapping.itertuples(index=False, name=None)):
        from_value, thru_value, identifier_value, _classification = row
        identifier = str(identifier_value)
        from_date = cast(pd.Timestamp, from_value)
        thru_date = cast(pd.Timestamp, thru_value)
        latest_thru = latest_thru_by_identifier.get(identifier)
        if latest_thru is not None and from_date <= latest_thru:
            overlap_indices.append(index)
        if latest_thru is None or thru_date > latest_thru:
            latest_thru_by_identifier[identifier] = thru_date
    return overlap_indices


def _validate_effective_intervals(mapping: pd.DataFrame, context: str) -> None:
    """Reject reversed or overlapping inclusive assignment intervals.

    Args:
        mapping: Normalized effective-dated assignments in deterministic order.
        context: Human-readable mapping label included in errors.

    Raises:
        PreparationError: If an interval is reversed or overlaps an earlier interval
            for the same source identifier.

    Notes:
        The latest prior end is retained per identifier so nested intervals are
        detected even when the immediately preceding interval ends sooner than an
        earlier containing interval. Exact duplicates have already collapsed.
    """
    reversed_intervals = cast(
        pd.DataFrame,
        mapping.loc[mapping["from_date"] > mapping["thru_date"]],
    )
    if not reversed_intervals.empty:
        _raise_invalid(
            context,
            "contains from_date after thru_date for assignments: "
            f"{_assignment_sample(reversed_intervals)}",
        )

    overlap_indices = _overlapping_interval_indices(mapping)
    if overlap_indices:
        overlapping = cast(pd.DataFrame, mapping.iloc[overlap_indices])
        _raise_invalid(
            context,
            "contains overlapping effective intervals for assignments: "
            f"{_assignment_sample(overlapping)}",
        )


def _normalize_effective_mapping(
    mapping: pd.DataFrame,
    context: str,
) -> pd.DataFrame:
    """Normalize one exact effective-dated identifier mapping.

    Args:
        mapping: Mapping with inclusive dates and textual identity columns.
        context: Human-readable mapping label included in errors.

    Returns:
        Independently owned, deduplicated assignments in deterministic order.

    Raises:
        PreparationError: If dates, identities, interval order, or interval overlap
            violates the effective-dated mapping contract.
    """
    normalized = cast(
        pd.DataFrame,
        mapping.loc[:, list(_EFFECTIVE_MAPPING_COLUMNS)].copy(deep=True),
    )
    for column in _MAPPING_DATE_COLUMNS:
        normalized[column] = normalize_dates(
            normalized,
            column,
            context,
            PreparationError,
        )
    for column in _STATIC_MAPPING_COLUMNS:
        normalized[column] = normalize_identity(
            normalized,
            column,
            context,
            PreparationError,
        )
    normalized = normalized.drop_duplicates(ignore_index=True)
    normalized = normalized.sort_values(
        ["identifier", "from_date", "thru_date", "classification_identifier"],
        kind="stable",
    ).reset_index(drop=True)
    _validate_effective_intervals(normalized, context)
    return normalized


def _normalize_mapping(mapping: pd.DataFrame, context: str) -> pd.DataFrame:
    """Validate and normalize one static or effective-dated identifier mapping.

    Args:
        mapping: Static pairs or inclusive effective-dated assignments.
        context: Human-readable mapping label included in errors.

    Returns:
        Independently owned, deduplicated mapping with canonical columns, dtypes, and
        deterministic order for its schema.

    Raises:
        TypeError: If ``mapping`` is not a pandas DataFrame.
        PreparationError: If the schema, identities, dates, static one-to-one rule, or
            effective interval rules are invalid.

    Notes:
        Every row is validated before later performance matching. Invalid unused rows
        therefore cannot disappear silently. Exact normalized duplicates are harmless.
    """
    if _uses_effective_schema(mapping, context):
        return _normalize_effective_mapping(mapping, context)
    return normalize_identity_pairs(
        mapping,
        _STATIC_MAPPING_COLUMNS,
        context,
        PreparationError,
        "maps source identifiers to multiple classifications",
    )


def normalize_mapping(mapping: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize a static or effective-dated classification mapping.

    Args:
        mapping: DataFrame using exactly the static two-column schema or the
            effective-dated four-column schema.

    Returns:
        An independently owned, deduplicated mapping in deterministic order.

    Raises:
        TypeError: If ``mapping`` is not a pandas DataFrame.
        PreparationError: If its schema, identities, dates, one-to-one static mapping,
            or effective interval contract is invalid.

    Notes:
        Effective-dated rows use required inclusive ``from_date`` and ``thru_date``
        values. Source periods must be fully contained in one dated assignment when
        their identifier appears in that mapping.
    """
    return _normalize_mapping(mapping, "mapping input")


def _static_mapped_identifiers(
    performance: pd.DataFrame,
    mapping: pd.DataFrame,
) -> pd.Series:
    """Return statically mapped identifiers with fallback for absent keys."""
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


def _effective_mapping_lookup(
    mapping: pd.DataFrame,
) -> dict[str, list[_EffectiveAssignment]]:
    """Group normalized dated assignments by source identifier."""
    lookup: dict[str, list[_EffectiveAssignment]] = {}
    for row in mapping.itertuples(index=False, name=None):
        from_value, thru_value, identifier_value, classification_value = row
        identifier = str(identifier_value)
        assignment = (
            cast(pd.Timestamp, from_value),
            cast(pd.Timestamp, thru_value),
            str(classification_value),
        )
        lookup.setdefault(identifier, []).append(assignment)
    return lookup


def _resolve_effective_identifier(
    identifier: str,
    source_from: pd.Timestamp,
    source_thru: pd.Timestamp,
    assignments: list[_EffectiveAssignment],
    context: str,
) -> str:
    """Resolve one source period or raise its precise temporal mapping error.

    Args:
        identifier: Normalized source identifier.
        source_from: Inclusive source-period start.
        source_thru: Inclusive source-period end.
        assignments: Ordered, nonoverlapping assignments for ``identifier``.
        context: Human-readable mapping boundary included in errors.

    Returns:
        The unique classification whose interval fully contains the source period.

    Raises:
        PreparationError: If multiple assignments contain the source period, if a
            classification boundary cuts through it, or if it falls in a mapping gap.
    """
    containing = [
        assignment
        for assignment in assignments
        if assignment[0] <= source_from and source_thru <= assignment[1]
    ]
    period = f"{identifier!r} from {source_from.date()} to {source_thru.date()}"
    if len(containing) == 1:
        return containing[0][2]
    if len(containing) > 1:
        _raise_invalid(
            context,
            f"resolves source period {period} through multiple effective assignments",
        )

    intersects = any(
        assignment[0] <= source_thru and source_from <= assignment[1]
        for assignment in assignments
    )
    if intersects:
        _raise_invalid(
            context,
            f"contains a classification boundary inside source period {period}",
        )
    _raise_invalid(
        context,
        f"has an effective-assignment gap for source period {period}",
    )


def _effective_mapped_identifiers(
    performance: pd.DataFrame,
    mapping: pd.DataFrame,
    context: str,
) -> pd.Series:
    """Resolve normalized source periods against normalized dated assignments.

    Args:
        performance: Normalized source-period performance rows.
        mapping: Normalized, nonoverlapping effective-dated assignments.
        context: Human-readable mapping boundary included in errors.

    Returns:
        A string Series aligned to ``performance`` with identity fallback for source
        identifiers that never appear in ``mapping``.

    Raises:
        PreparationError: If a mapped identifier's source period has a relevant gap,
            crosses a classification boundary, or has multiple containing intervals.

    Notes:
        Assignment is intentionally separate from financial roll-up. It changes only
        the identifier attached to each complete source-period row and never splits or
        prorates weight, return, or authoritative contribution.
    """
    lookup = _effective_mapping_lookup(mapping)
    resolved: list[str] = []
    source_periods = performance.loc[:, ["from_date", "thru_date", "identifier"]]
    for row in source_periods.itertuples(index=False, name=None):
        from_value, thru_value, identifier_value = row
        identifier = str(identifier_value)
        assignments = lookup.get(identifier)
        if assignments is None:
            resolved.append(identifier)
            continue
        resolved.append(
            _resolve_effective_identifier(
                identifier,
                cast(pd.Timestamp, from_value),
                cast(pd.Timestamp, thru_value),
                assignments,
                context,
            )
        )
    return pd.Series(resolved, index=performance.index, dtype="string[python]")


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
    """Apply an optional classification mapping to normalized performance.

    Args:
        performance: Source-period rows produced by ``_normalize_performance``.
        mapping: Optional static pairs or effective-dated assignments.
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
        mapping is supplied, identifiers absent from it fall back to themselves and
        collisions are intentionally aggregated. An identifier present in a dated
        mapping requires exactly one assignment containing each complete source period.
        Mapping occurs before reporting-frequency consolidation.
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

    mapping_context = f"{context} mapping"
    normalized_mapping = _normalize_mapping(mapping, mapping_context)
    if "from_date" in normalized_mapping.columns:
        source["identifier"] = _effective_mapped_identifiers(
            source,
            normalized_mapping,
            mapping_context,
        )
    else:
        source["identifier"] = _static_mapped_identifiers(source, normalized_mapping)
    mapped = _roll_up_mapping(source, context)
    _validate_mapping_conservation(performance, mapped, context, tolerance)
    return mapped


__all__ = ["normalize_mapping"]
