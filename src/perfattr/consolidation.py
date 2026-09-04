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
_REPORTING_INDEX = "_reporting_period_index"


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


def _assign_reporting_periods(
    source: pd.DataFrame,
    aligned: _AlignedPeriods,
    context: str,
) -> pd.DataFrame:
    """Assign each contained source period to one reporting period.

    Args:
        source: Normalized source-period rows.
        aligned: Ordered, nonoverlapping reporting periods.
        context: Human-readable side included in errors.

    Returns:
        A new frame with an integer ``_reporting_period_index`` column. Rows outside
        the aligned comparison window receive ``-1`` and are ignored later.

    Raises:
        PreparationError: If a source interval crosses an aligned reporting boundary
            or a reporting period contains no source rows.

    Notes:
        Assignment operates on unique source-period keys, then joins those assignments
        to identifier rows once. This preserves the original boundary rules without
        rescanning every identifier row for every reporting period.
    """
    source_periods = cast(
        pd.DataFrame,
        source.loc[:, _PERIOD_COLUMNS]
        .drop_duplicates()
        .sort_values(["thru_date", "from_date"], kind="stable")
        .reset_index(drop=True),
    )
    source_from = source_periods["from_date"].to_numpy(dtype="datetime64[ns]")
    source_thru = source_periods["thru_date"].to_numpy(dtype="datetime64[ns]")
    assignments = np.full(len(source_periods), -1, dtype=np.int64)

    for reporting_index, reporting_period in enumerate(aligned.periods):
        reporting_start = np.datetime64(reporting_period[0], "ns")
        reporting_end = np.datetime64(reporting_period[1], "ns")
        contained = (source_from >= reporting_start) & (source_thru <= reporting_end)
        intersects = (source_thru >= reporting_start) & (source_from <= reporting_end)
        if bool(np.asarray(intersects & ~contained, dtype=np.bool_).any()):
            _raise_invalid(
                context,
                f"contains a source period crossing reporting boundaries "
                f"{reporting_period[0].isoformat()} to "
                f"{reporting_period[1].isoformat()}",
            )
        if not bool(np.asarray(contained, dtype=np.bool_).any()):
            _raise_invalid(
                context,
                f"has no source rows for reporting period "
                f"{reporting_period[0].isoformat()} to "
                f"{reporting_period[1].isoformat()}",
            )
        assignments[contained] = reporting_index

    source_periods[_REPORTING_INDEX] = assignments
    return source.merge(
        source_periods,
        on=_PERIOD_COLUMNS,
        how="left",
        validate="many_to_one",
        sort=False,
    )


def _reporting_groups(frame: pd.DataFrame) -> dict[int, pd.DataFrame]:
    """Group assigned rows once and remove the internal reporting index."""
    selected = frame.loc[frame[_REPORTING_INDEX] >= 0]
    groups: dict[int, pd.DataFrame] = {}
    for reporting_index, group in selected.groupby(
        _REPORTING_INDEX, sort=True, observed=True
    ):
        # pandas exposes a group key as Hashable, while _assign_reporting_periods
        # establishes this private column as an integer index.
        index = int(cast(int, reporting_index))
        groups[index] = cast(
            pd.DataFrame,
            group.drop(columns=_REPORTING_INDEX)
            .sort_values(["thru_date", "identifier"], kind="stable")
            .reset_index(drop=True),
        )
    return groups


def _all_source_period_totals(
    assigned: pd.DataFrame,
    context: str,
) -> pd.DataFrame:
    """Calculate source-period totals for all reporting periods in one grouping.

    Args:
        assigned: Normalized rows carrying their internal reporting-period index.
        context: Human-readable side included in errors.

    Returns:
        Chronological source-period contribution totals and inclusive day counts.

    Raises:
        PreparationError: If rows disagree about a source-period day count or a total
            return cannot enter logarithmic linking.
    """
    group_columns = [_REPORTING_INDEX, *_PERIOD_COLUMNS]
    grouped = assigned.groupby(group_columns, sort=True, observed=True)
    day_counts = grouped["quantity_of_days"].agg(["first", "nunique"])
    if bool(np.asarray(day_counts["nunique"] != 1, dtype=np.bool_).any()):
        _raise_invalid(context, "has inconsistent source-period day counts")
    totals = cast(pd.Series, grouped["contribution"].sum()).to_frame(
        "period_return"
    )
    totals["quantity_of_days"] = day_counts["first"].astype("int64")
    totals = totals.reset_index()
    period_returns = _float_array(totals, "period_return")
    if not np.isfinite(period_returns).all() or np.any(period_returns <= -1.0):
        _raise_invalid(
            context,
            "source-period total returns must be finite and greater than -1.0 "
            "for consolidation",
        )
    return totals


def _validate_reporting_days(
    period_totals: pd.DataFrame,
    aligned: _AlignedPeriods,
    context: str,
) -> None:
    """Require source-period days to cover each consolidated reporting period.

    Args:
        period_totals: One contribution total and day count per source period.
        aligned: Validated reporting-period boundaries.
        context: Human-readable side included in errors.

    Raises:
        PreparationError: If source-period day counts do not exactly cover a reporting
            period's inclusive calendar days.
    """
    observed = cast(
        pd.Series,
        period_totals.groupby(_REPORTING_INDEX, sort=True, observed=True)[
            "quantity_of_days"
        ].sum(),
    )
    reporting_indices = np.asarray(observed.index, dtype=np.int64)
    observed_day_counts = np.asarray(observed, dtype=np.int64)
    for reporting_index, observed_days in zip(
        reporting_indices, observed_day_counts, strict=True
    ):
        reporting_period = aligned.periods[reporting_index]
        reporting_days = (reporting_period[1] - reporting_period[0]).days + 1
        if int(observed_days) != reporting_days:
            _raise_invalid(
                context,
                f"source-period days total {int(observed_days)}, not "
                f"reporting-period days {reporting_days}",
            )


def _link_all_source_contributions(
    assigned: pd.DataFrame,
    period_totals: pd.DataFrame,
    context: str,
) -> pd.DataFrame:
    """Link contributions for every consolidated reporting period at once.

    Args:
        assigned: Identifier rows carrying their reporting-period index.
        period_totals: Source-period contribution totals and day counts.
        context: Human-readable side included in errors.

    Returns:
        Working rows with logarithmic coefficients, linked contributions, and their
        reporting-period return.

    Raises:
        PreparationError: If compounding, smoothing, or contribution linking produces
            a non-finite value.

    Notes:
        For source period ``u`` and reporting period ``t``, the coefficient is
        ``s(R[u]) / s(R[t])``, where ``s(x) = log1p(x) / x`` and ``s(0) = 1``.
        Applying it to authoritative source contribution makes linked contributions
        sum to the geometrically compounded reporting return. The operation is batched
        by reporting-period index; it does not reconstruct contribution from return.
    """
    totals = period_totals.copy(deep=True)
    period_returns = _float_array(totals, "period_return")
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        totals["_log_growth"] = np.log1p(period_returns)
    log_growth = cast(
        pd.Series,
        totals.groupby(_REPORTING_INDEX, sort=True, observed=True)[
            "_log_growth"
        ].sum(),
    )
    with np.errstate(over="ignore", invalid="ignore"):
        reporting_returns = pd.Series(
            np.expm1(np.asarray(log_growth, dtype=np.float64)),
            index=log_growth.index,
            dtype="float64",
        )
    invalid_returns = (~np.isfinite(reporting_returns)) | (reporting_returns <= -1.0)
    if bool(np.asarray(invalid_returns, dtype=np.bool_).any()):
        _raise_invalid(
            context,
            "compounded reporting return must be finite and greater than -1.0",
        )
    reporting_smoothing = log_growth / reporting_returns
    reporting_smoothing.loc[reporting_returns == 0.0] = 1.0
    reporting_keys = pd.Index(totals[_REPORTING_INDEX])
    denominators = reporting_smoothing.reindex(reporting_keys)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        totals["_linking_coefficient"] = (
            _smoothing(period_returns)
            / np.asarray(denominators, dtype=np.float64)
        )
    if not np.isfinite(_float_array(totals, "_linking_coefficient")).all():
        _raise_invalid(context, "contribution linking coefficients must be finite")

    coefficient_columns = [
        _REPORTING_INDEX,
        *_PERIOD_COLUMNS,
        "_linking_coefficient",
    ]
    working = assigned.merge(
        totals.loc[:, coefficient_columns],
        on=[_REPORTING_INDEX, *_PERIOD_COLUMNS],
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
    working["_reporting_return"] = reporting_returns.reindex(
        pd.Index(working[_REPORTING_INDEX])
    ).to_numpy(
        dtype=np.float64
    )
    return working


def _aggregate_all_linked_periods(  # pylint: disable=too-many-locals
    working: pd.DataFrame,
    aligned: _AlignedPeriods,
    mapping_was_applied: bool,
    context: str,
    tolerance: float,
) -> dict[int, pd.DataFrame]:
    """Aggregate all prelinked reporting periods with shared group operations.

    Args:
        working: Source rows with bulk-calculated linking values.
        aligned: Validated reporting-period boundaries.
        mapping_was_applied: Whether final returns use mapped effective-return rules.
        context: Human-readable side included in errors.
        tolerance: Relative and absolute reconciliation tolerance.

    Returns:
        Prepared reporting frames keyed by internal reporting-period index.

    Raises:
        PreparationError: If any financial value or reporting-period conservation
            identity is invalid.

    Notes:
        Weights use inclusive-day weighting. Unmapped identifier returns compound in
        log space and propagate an explicit null; mapped returns are derived from final
        linked contribution and weight. Grouping all periods together changes only
        execution shape, not the per-period formulas.
    """
    working["_weighted_weight"] = (
        _float_array(working, "weight")
        * _float_array(working, "quantity_of_days")
    )
    group_columns = [_REPORTING_INDEX, "identifier"]
    grouped = working.groupby(group_columns, sort=True, observed=True)
    consolidated = cast(
        pd.DataFrame,
        grouped[["_weighted_weight", "_linked_contribution"]].sum(),
    ).reset_index()
    reporting_days = pd.Series(
        [
            (reporting_period[1] - reporting_period[0]).days + 1
            for reporting_period in aligned.periods
        ],
        index=pd.Index(range(len(aligned.periods))),
        dtype="int64",
    )
    denominators = reporting_days.reindex(
        pd.Index(consolidated[_REPORTING_INDEX])
    ).to_numpy(dtype=np.float64)
    consolidated["weight"] = (
        _float_array(consolidated, "_weighted_weight") / denominators
    )
    consolidated["contribution"] = consolidated[
        "_linked_contribution"
    ].astype("float64")
    if mapping_was_applied:
        consolidated["return"] = _derive_mapped_returns(consolidated, context)
    else:
        returns = working.loc[:, [*group_columns, "return"]].copy(deep=True)
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            returns["_log_return"] = np.log1p(_float_array(returns, "return"))
        return_groups = returns.groupby(group_columns, sort=True, observed=True)
        log_sums = cast(pd.Series, return_groups["_log_return"].sum(min_count=1))
        compounded = pd.Series(
            np.expm1(np.asarray(log_sums, dtype=np.float64)),
            index=log_sums.index,
            name="return",
            dtype="float64",
        )
        any_null = return_groups["return"].count() != return_groups.size()
        compounded.loc[any_null] = np.nan
        consolidated = consolidated.merge(
            compounded.reset_index(),
            on=group_columns,
            how="left",
            validate="one_to_one",
            sort=False,
        )

    reporting_returns = cast(
        pd.Series,
        working.groupby(_REPORTING_INDEX, sort=True, observed=True)[
            "_reporting_return"
        ].first(),
    )
    results: dict[int, pd.DataFrame] = {}
    for reporting_index, group in consolidated.groupby(
        _REPORTING_INDEX, sort=True, observed=True
    ):
        index = int(cast(int, reporting_index))
        reporting_period = aligned.periods[index]
        frame = group.drop(columns=_REPORTING_INDEX).reset_index(drop=True)
        _validate_consolidated_values(
            frame,
            float(reporting_returns.loc[index]),
            context,
            tolerance,
        )
        frame["from_date"] = pd.Timestamp(reporting_period[0])
        frame["thru_date"] = pd.Timestamp(reporting_period[1])
        frame["quantity_of_days"] = int(reporting_days.loc[index])
        results[index] = cast(
            pd.DataFrame,
            frame.loc[:, list(NORMALIZED_PERFORMANCE_COLUMNS)],
        )
    return results


def _linked_reporting_groups(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    assigned: pd.DataFrame,
    aligned: _AlignedPeriods,
    consolidation_indices: tuple[int, ...],
    mapping_was_applied: bool,
    context: str,
    tolerance: float,
) -> dict[int, pd.DataFrame]:
    """Prepare consolidated rows only for periods requiring linking."""
    if not consolidation_indices:
        return {}
    selected = assigned.loc[
        assigned[_REPORTING_INDEX].isin(consolidation_indices)
    ]
    period_totals = _all_source_period_totals(selected, context)
    _validate_reporting_days(period_totals, aligned, context)
    working = _link_all_source_contributions(selected, period_totals, context)
    return _aggregate_all_linked_periods(
        working,
        aligned,
        mapping_was_applied,
        context,
        tolerance,
    )


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


def _exact_reporting_indices(
    assigned: pd.DataFrame,
    aligned: _AlignedPeriods,
) -> frozenset[int]:
    """Return indices whose source already has the exact reporting boundary."""
    source_periods = assigned.loc[
        assigned[_REPORTING_INDEX] >= 0,
        [_REPORTING_INDEX, *_PERIOD_COLUMNS],
    ].drop_duplicates()
    exact: set[int] = set()
    for reporting_index, group in source_periods.groupby(
        _REPORTING_INDEX, sort=True, observed=True
    ):
        if len(group) != 1:
            continue
        index = int(cast(int, reporting_index))
        row = group.iloc[0]
        boundary = (
            cast(pd.Timestamp, row["from_date"]).date(),
            cast(pd.Timestamp, row["thru_date"]).date(),
        )
        if boundary == aligned.periods[index]:
            exact.add(index)
    return frozenset(exact)


def _exact_reporting_groups(
    assigned: pd.DataFrame,
    exact_indices: frozenset[int],
) -> dict[int, pd.DataFrame]:
    """Return original rows only for reporting periods needing no consolidation."""
    if not exact_indices:
        return {}
    exact_rows = assigned.loc[
        assigned[_REPORTING_INDEX].isin(tuple(sorted(exact_indices)))
    ]
    return _reporting_groups(exact_rows)


def _source_period_sequence(source: pd.DataFrame) -> tuple[_DatePeriod, ...]:
    """Return the source's chronological unique inclusive period boundaries."""
    periods = source.loc[:, _PERIOD_COLUMNS].drop_duplicates().sort_values(
        ["thru_date", "from_date"], kind="stable"
    )
    return tuple(
        (
            cast(pd.Timestamp, from_date).date(),
            cast(pd.Timestamp, thru_date).date(),
        )
        for from_date, thru_date in periods.itertuples(index=False, name=None)
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
    if _source_period_sequence(source) == aligned.periods:
        return source.sort_values(
            ["thru_date", "identifier"], kind="stable"
        ).reset_index(drop=True)

    assigned = _assign_reporting_periods(source, aligned, context)
    exact_indices = _exact_reporting_indices(assigned, aligned)
    source_groups = _exact_reporting_groups(assigned, exact_indices)
    consolidation_indices = tuple(
        index
        for index in range(len(aligned.periods))
        if index not in exact_indices
    )
    linked_groups = _linked_reporting_groups(
        assigned,
        aligned,
        consolidation_indices,
        mapping_was_applied,
        context,
        tolerance,
    )

    reporting_frames = [
        source_groups[index]
        if index not in linked_groups
        else linked_groups[index]
        for index, reporting_period in enumerate(aligned.periods)
    ]

    result = pd.concat(reporting_frames, ignore_index=True)
    for column in ("from_date", "thru_date"):
        result[column] = result[column].astype("datetime64[ns]")
    result["identifier"] = result["identifier"].astype("string[python]")
    result["quantity_of_days"] = result["quantity_of_days"].astype("int64")
    return cast(
        pd.DataFrame,
        result.loc[:, list(NORMALIZED_PERFORMANCE_COLUMNS)].sort_values(
            ["thru_date", "identifier"], kind="stable"
        ),
    ).reset_index(drop=True)


__all__: list[str] = []
