"""Consolidate aligned source periods into portable reporting-period rows.

This package-internal stage follows source validation, period alignment, and optional
classification mapping. It preserves authoritative contribution through logarithmic
linking while keeping the public preparation API decision for roadmap step 6.
"""

from __future__ import annotations

import datetime as dt
from typing import cast

import numpy as np
import pandas as pd

from perfattr._exceptions import PreparationError
from perfattr._linking import _smoothing
from perfattr._schemas import NORMALIZED_PERFORMANCE_COLUMNS
from perfattr._validation import (
    float_array as _float_array,
    is_close as _is_close,
    normalize_reconciliation_tolerance,
    raise_invalid,
)
from perfattr.mapping import _derive_mapped_returns
from perfattr.preparation import _AlignedPeriods


_TOLERANCE = 1e-12
_DatePeriod = tuple[dt.date, dt.date]
_PERIOD_COLUMNS = ["from_date", "thru_date"]


def _raise_invalid(context: str, message: str) -> None:
    """Raise a consistently formatted consolidation error."""
    raise_invalid(PreparationError, context, message)


def _validate_aligned_periods(aligned: _AlignedPeriods) -> None:
    """Require ordered, nonoverlapping reporting periods from the alignment stage.

    Args:
        aligned: Common reporting boundaries selected for portfolio and benchmark.

    Raises:
        TypeError: If ``aligned`` is not an alignment result.
        PreparationError: If no reporting period exists or its boundaries are invalid.
    """
    if not isinstance(aligned, _AlignedPeriods):
        raise TypeError("aligned must be an _AlignedPeriods result")
    if not aligned.periods:
        raise PreparationError("aligned reporting periods must not be empty")
    previous_end: dt.date | None = None
    for from_date, thru_date in aligned.periods:
        if from_date > thru_date:
            raise PreparationError("aligned reporting period starts after it ends")
        if previous_end is not None and from_date <= previous_end:
            raise PreparationError("aligned reporting periods must not overlap")
        previous_end = thru_date


def _reporting_source_rows(
    performance: pd.DataFrame,
    reporting_period: _DatePeriod,
    context: str,
) -> pd.DataFrame:
    """Select source rows wholly contained in one aligned reporting period.

    Args:
        performance: Normalized and optionally mapped source-period rows.
        reporting_period: Inclusive aligned reporting boundaries.
        context: Human-readable side included in errors.

    Returns:
        An independently owned subset in source-period order.

    Raises:
        PreparationError: If no source rows cover the period or a source interval
            crosses an aligned reporting boundary.
    """
    reporting_start = pd.Timestamp(reporting_period[0])
    reporting_end = pd.Timestamp(reporting_period[1])
    contained = (performance["from_date"] >= reporting_start) & (
        performance["thru_date"] <= reporting_end
    )
    intersects = (performance["thru_date"] >= reporting_start) & (
        performance["from_date"] <= reporting_end
    )
    if bool(np.asarray(intersects & ~contained, dtype=np.bool_).any()):
        _raise_invalid(
            context,
            f"contains a source period crossing reporting boundaries "
            f"{reporting_period[0].isoformat()} to {reporting_period[1].isoformat()}",
        )
    source = cast(
        pd.DataFrame,
        performance.loc[contained, list(NORMALIZED_PERFORMANCE_COLUMNS)].copy(
            deep=True
        ),
    )
    if source.empty:
        _raise_invalid(
            context,
            f"has no source rows for reporting period "
            f"{reporting_period[0].isoformat()} to {reporting_period[1].isoformat()}",
        )
    return source.sort_values(
        ["thru_date", "identifier"], kind="stable"
    ).reset_index(drop=True)


def _source_period_totals(source: pd.DataFrame, context: str) -> pd.DataFrame:
    """Calculate and validate returns and inclusive days for source periods.

    Args:
        source: Rows contained in one reporting period.
        context: Human-readable side included in errors.

    Returns:
        Chronological source-period contribution totals and day counts.

    Raises:
        PreparationError: If a total cannot enter logarithmic linking or rows disagree
            about their source-period day count.
    """
    grouped = source.groupby(_PERIOD_COLUMNS, sort=True, observed=True)
    day_counts = grouped["quantity_of_days"].agg(["first", "nunique"])
    if bool(np.asarray(day_counts["nunique"] != 1, dtype=np.bool_).any()):
        _raise_invalid(context, "has inconsistent source-period day counts")
    totals = cast(pd.Series, grouped["contribution"].sum()).to_frame(
        "period_return"
    )
    totals["quantity_of_days"] = day_counts["first"].astype("int64")
    period_returns = _float_array(totals, "period_return")
    if not np.isfinite(period_returns).all() or np.any(period_returns <= -1.0):
        _raise_invalid(
            context,
            "source-period total returns must be finite and greater than -1.0 "
            "for consolidation",
        )
    return totals.reset_index()


def _link_source_contributions(
    source: pd.DataFrame,
    period_totals: pd.DataFrame,
    context: str,
) -> tuple[pd.DataFrame, float]:
    """Apply logarithmic coefficients to authoritative source contributions.

    Args:
        source: Identifier rows from one reporting period.
        period_totals: Chronological total returns for its source periods.
        context: Human-readable side included in errors.

    Returns:
        A working copy with linked contributions and the compounded total return.

    Raises:
        PreparationError: If compounding, smoothing, or contribution linking produces
            a non-finite value.

    Notes:
        For source period ``u`` and reporting period ``t``, the coefficient is
        ``s(R[u]) / s(R[t])``, where ``s(x) = log1p(x) / x`` with exact-zero limit 1.
        Multiplying each authoritative contribution by that coefficient makes their
        reporting-period sum equal the geometrically compounded total return. This is
        logarithmic contribution linking, not a reconstruction from weight and return.
    """
    period_returns = _float_array(period_totals, "period_return")
    # Preserve the summed log growth used to form the compound return. Recomputing
    # log1p from a rounded return near -100% loses material precision and can break
    # the contribution identity even though every source return remains valid.
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        log_growth = float(np.log1p(period_returns).sum(dtype=np.float64))
        reporting_return = float(np.expm1(log_growth))
    if not np.isfinite(reporting_return) or reporting_return <= -1.0:
        _raise_invalid(
            context,
            "compounded reporting return must be finite and greater than -1.0",
        )
    reporting_smoothing = (
        1.0 if reporting_return == 0.0 else log_growth / reporting_return
    )
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        coefficients = _smoothing(period_returns) / reporting_smoothing
    if not np.isfinite(coefficients).all():
        _raise_invalid(context, "contribution linking coefficients must be finite")

    coefficient_frame = period_totals.loc[:, _PERIOD_COLUMNS].copy(deep=True)
    coefficient_frame["_linking_coefficient"] = coefficients
    working = source.merge(
        coefficient_frame,
        on=_PERIOD_COLUMNS,
        how="left",
        validate="many_to_one",
        sort=False,
    )
    with np.errstate(over="ignore", invalid="ignore"):
        working["_linked_contribution"] = (
            _float_array(working, "contribution")
            * _float_array(working, "_linking_coefficient")
        )
    if not np.isfinite(_float_array(working, "_linked_contribution")).all():
        _raise_invalid(context, "contribution linking produced a non-finite value")
    return working, reporting_return


def _compound_identifier_returns(source: pd.DataFrame) -> pd.Series:
    """Compound present identifier returns and propagate any explicit null.

    Absent source-period rows contribute the multiplicative identity and therefore
    need no materialized row. A present null is different: it means the identifier
    return is undefined and must remain null after consolidation.
    """
    working = source.loc[:, ["identifier", "return"]].copy(deep=True)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        working["_log_return"] = np.log1p(_float_array(working, "return"))
    grouped = working.groupby("identifier", sort=True, observed=True)
    log_sums = cast(pd.Series, grouped["_log_return"].sum(min_count=1))
    compounded = pd.Series(
        np.expm1(np.asarray(log_sums, dtype=np.float64)),
        index=log_sums.index,
        dtype="float64",
    )
    any_null = grouped["return"].count() != grouped.size()
    compounded.loc[any_null] = np.nan
    return compounded


def _aggregate_reporting_identifiers(
    working: pd.DataFrame,
    source: pd.DataFrame,
    reporting_days: int,
    mapping_was_applied: bool,
    context: str,
) -> pd.DataFrame:
    """Aggregate linked values and calculate reporting-period identifier returns."""
    working["_weighted_weight"] = (
        _float_array(working, "weight")
        * _float_array(working, "quantity_of_days")
    )
    grouped = working.groupby("identifier", sort=True, observed=True)
    consolidated = cast(
        pd.DataFrame,
        grouped[["_weighted_weight", "_linked_contribution"]].sum(),
    ).reset_index()
    consolidated["weight"] = (
        _float_array(consolidated, "_weighted_weight") / reporting_days
    )
    consolidated["contribution"] = consolidated["_linked_contribution"].astype(
        "float64"
    )
    if mapping_was_applied:
        consolidated["return"] = _derive_mapped_returns(consolidated, context)
    else:
        compounded = _compound_identifier_returns(source)
        identifiers = pd.Index(consolidated["identifier"])
        consolidated["return"] = np.asarray(
            compounded.reindex(identifiers), dtype=np.float64
        )
    return consolidated


def _validate_consolidated_values(
    consolidated: pd.DataFrame,
    reporting_return: float,
    context: str,
    tolerance: float,
) -> None:
    """Validate prepared-frame values and financial consolidation identities."""
    weights = _float_array(consolidated, "weight")
    contributions = _float_array(consolidated, "contribution")
    returns = _float_array(consolidated, "return")
    if not np.isfinite(weights).all() or not np.isfinite(contributions).all():
        _raise_invalid(context, "consolidation produced a non-finite financial value")
    defined_returns = ~np.isnan(returns)
    if not np.isfinite(returns[defined_returns]).all() or np.any(
        returns[defined_returns] <= -1.0
    ):
        _raise_invalid(
            context,
            "consolidated returns must be finite and greater than -1.0 when defined",
        )
    if np.any((weights != 0.0) & ~defined_returns):
        _raise_invalid(
            context,
            "consolidation produced a nonzero identifier weight with a null return",
        )

    weight_total = float(weights.sum(dtype=np.float64))
    if not _is_close(
        np.asarray([weight_total]), np.asarray([1.0]), tolerance
    )[0]:
        _raise_invalid(
            context,
            f"consolidated weights sum to {weight_total:.17g}, not 1.0",
        )
    contribution_total = float(contributions.sum(dtype=np.float64))
    if not _is_close(
        np.asarray([contribution_total]),
        np.asarray([reporting_return]),
        tolerance,
    )[0]:
        _raise_invalid(
            context,
            "linked contributions do not reconcile to the compounded reporting return",
        )


def _consolidate_multiple_periods(
    source: pd.DataFrame,
    reporting_period: _DatePeriod,
    mapping_was_applied: bool,
    context: str,
    tolerance: float,
) -> pd.DataFrame:
    """Consolidate two or more source periods into one reporting period.

    Args:
        source: Source rows wholly contained in the reporting period.
        reporting_period: Inclusive output boundaries.
        mapping_was_applied: Whether source rows represent mapped groups whose final
            return must be derived from consolidated contribution and weight.
        context: Human-readable side included in errors.
        tolerance: Relative and absolute reconciliation tolerance.

    Returns:
        Consolidated rows ordered by identifier.

    Raises:
        PreparationError: If coverage or any financial reconciliation fails.
    """
    period_totals = _source_period_totals(source, context)
    reporting_days = (reporting_period[1] - reporting_period[0]).days + 1
    observed_days = int(
        np.asarray(period_totals["quantity_of_days"], dtype=np.int64).sum()
    )
    if observed_days != reporting_days:
        _raise_invalid(
            context,
            f"source-period days total {observed_days}, not reporting-period days "
            f"{reporting_days}",
        )

    working, reporting_return = _link_source_contributions(
        source, period_totals, context
    )
    consolidated = _aggregate_reporting_identifiers(
        working,
        source,
        reporting_days,
        mapping_was_applied,
        context,
    )
    _validate_consolidated_values(
        consolidated, reporting_return, context, tolerance
    )

    consolidated["from_date"] = pd.Timestamp(reporting_period[0])
    consolidated["thru_date"] = pd.Timestamp(reporting_period[1])
    consolidated["quantity_of_days"] = reporting_days
    return cast(
        pd.DataFrame,
        consolidated.loc[:, list(NORMALIZED_PERFORMANCE_COLUMNS)],
    )


def _consolidate_performance(
    performance: pd.DataFrame,
    aligned: _AlignedPeriods,
    mapping_was_applied: bool,
    context: str,
    reconciliation_tolerance: float = _TOLERANCE,
) -> pd.DataFrame:
    """Consolidate one normalized side to aligned reporting periods.

    Args:
        performance: Normalized, optionally mapped source-period rows.
        aligned: Common reporting boundaries returned by ``_align_periods``.
        mapping_was_applied: ``True`` when any mapping DataFrame was supplied, even an
            empty identity mapping. Mapped returns use final effective-return rules.
        context: Human-readable side such as ``"portfolio input"``.
        reconciliation_tolerance: Positive relative and absolute tolerance for weight
            and linked-contribution conservation.

    Returns:
        An independently owned frame at reporting-period and identifier granularity,
        ordered by ``thru_date`` and ``identifier``.

    Raises:
        TypeError: If an argument has the wrong boundary type.
        PreparationError: If coverage, compounding, or reconciliation is invalid.

    Notes:
        A source period already equal to its reporting period is copied exactly. For
        true consolidation, identifier weights are inclusive-day weighted. Unmapped
        identifier returns compound; mapped returns are derived from final linked
        contribution and weight so intermediate effective returns are never compounded.
    """
    if not isinstance(performance, pd.DataFrame):
        raise TypeError(f"{context} must be a pandas DataFrame")
    if not isinstance(mapping_was_applied, bool):
        raise TypeError("mapping_was_applied must be a bool")
    tolerance = normalize_reconciliation_tolerance(
        reconciliation_tolerance, PreparationError
    )
    _validate_aligned_periods(aligned)
    source = cast(
        pd.DataFrame,
        performance.loc[:, list(NORMALIZED_PERFORMANCE_COLUMNS)].copy(deep=True),
    )

    reporting_frames: list[pd.DataFrame] = []
    for reporting_period in aligned.periods:
        reporting_source = _reporting_source_rows(source, reporting_period, context)
        source_periods = reporting_source[_PERIOD_COLUMNS].drop_duplicates()
        if len(source_periods) == 1:
            source_boundary = tuple(
                cast(pd.Timestamp, value).date()
                for value in source_periods.iloc[0]
            )
            if source_boundary == reporting_period:
                reporting_frames.append(reporting_source)
                continue
        reporting_frames.append(
            _consolidate_multiple_periods(
                reporting_source,
                reporting_period,
                mapping_was_applied,
                context,
                tolerance,
            )
        )

    result = pd.concat(reporting_frames, ignore_index=True)
    result["identifier"] = result["identifier"].astype("string[python]")
    result["quantity_of_days"] = result["quantity_of_days"].astype("int64")
    return cast(
        pd.DataFrame,
        result.loc[:, list(NORMALIZED_PERFORMANCE_COLUMNS)].sort_values(
            ["thru_date", "identifier"], kind="stable"
        ),
    ).reset_index(drop=True)


__all__: list[str] = []
