"""Compose portable source preparation for the attribution calculation core."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
import datetime as dt
from typing import TypedDict, cast

import numpy as np
import pandas as pd

from perfattr._exceptions import PreparationError
from perfattr._linking import _compound_returns
from perfattr._schemas import (
    PREPARATION_RECONCILIATION_COLUMNS,
    PREPARED_PERFORMANCE_COLUMNS,
)
from perfattr._validation import (
    float_array as _float_array,
    is_close as _is_close,
    normalize_dates,
    normalize_reconciliation_tolerance,
    sum_by_period,
)
from perfattr.consolidation import _consolidate_performance
from perfattr.frequency import Frequency
from perfattr.mapping import _map_performance
from perfattr.preparation import (
    _AlignedPeriods,
    _NormalizedPerformance,
    _align_periods,
    _normalize_performance,
)


_TOLERANCE = 1e-12
_DatePeriod = tuple[dt.date, dt.date]
_FINANCIAL_COLUMNS = ("actual", "expected", "residual", "tolerance")


class _ReconciliationRow(TypedDict):
    """Describe one typed row in the preparation reconciliation frame."""

    stage: str
    side: str
    from_date: pd.Timestamp
    thru_date: pd.Timestamp
    check: str
    actual: float
    expected: float
    residual: float
    tolerance: float
    passed: bool


@dataclass
class PreparationResult:
    """Hold prepared attribution inputs and their reconciliation evidence.

    Attributes:
        portfolio: Prepared portfolio rows accepted by ``calculate_attribution``.
        benchmark: Prepared benchmark rows accepted by ``calculate_attribution``.
        reconciliation: Passing preparation conservation checks.

    Notes:
        Preparation never mutates caller-supplied frames. These returned frames belong
        to the caller and are independently mutable; the dataclass does not freeze
        either the container or its pandas data.
    """

    portfolio: pd.DataFrame
    benchmark: pd.DataFrame
    reconciliation: pd.DataFrame


@dataclass(frozen=True)
class _PreparedSide:
    """Hold the independently owned frames needed to audit one prepared side.

    Attributes:
        source: Normalized, date-filtered source-period rows.
        contribution_was_supplied: Whether source contribution was authoritative.
        mapped: Source-period rows after optional mapping.
        mapping_was_applied: Whether the caller supplied a mapping DataFrame.
        reporting: Final reporting-period rows.
    """

    source: pd.DataFrame
    contribution_was_supplied: bool
    mapped: pd.DataFrame
    mapping_was_applied: bool
    reporting: pd.DataFrame


def _normalize_window_bound(
    value: str | dt.date | None,
    name: str,
) -> pd.Timestamp | None:
    """Normalize one optional inclusive source-period endpoint bound.

    Args:
        value: Date string, plain date, or ``None``.
        name: Public argument name used in an error.

    Returns:
        A timezone-naive midnight timestamp, or ``None``.

    Raises:
        TypeError: If the bound is neither a string, plain date, nor ``None``.
        PreparationError: If the string is not a valid timezone-naive date.
    """
    if value is None:
        return None
    if isinstance(value, dt.datetime) or not isinstance(value, str | dt.date):
        raise TypeError(f"{name} must be a date string, datetime.date, or None")
    boundary = pd.DataFrame({name: [value]})
    normalized = normalize_dates(boundary, name, "date window", PreparationError)
    return cast(pd.Timestamp, normalized.iloc[0])


def _normalize_date_window(
    from_date: str | dt.date | None,
    thru_date: str | dt.date | None,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Normalize and order the optional inclusive endpoint window."""
    window_start = _normalize_window_bound(from_date, "from_date")
    window_end = _normalize_window_bound(thru_date, "thru_date")
    if window_start is not None and window_end is not None:
        if window_start > window_end:
            raise PreparationError("from_date must not be after thru_date")
    return window_start, window_end


def _filter_performance(
    normalized: _NormalizedPerformance,
    window: tuple[pd.Timestamp | None, pd.Timestamp | None],
    context: str,
) -> _NormalizedPerformance:
    """Filter normalized rows by inclusive source-period endpoint bounds.

    Args:
        normalized: Validated source rows and their contribution provenance.
        window: Optional inclusive lower and upper endpoint bounds.
        context: Human-readable side included in errors.

    Returns:
        Independently owned retained rows with unchanged contribution provenance.

    Raises:
        PreparationError: If no source period remains in the requested window.

    Notes:
        Bounds select whole source periods by ``thru_date``. They never clip dates or
        prorate financial values.
    """
    retained = normalized.frame.copy(deep=True)
    window_start, window_end = window
    if window_start is not None:
        retained = cast(
            pd.DataFrame,
            retained.loc[retained["thru_date"] >= window_start].copy(deep=True),
        )
    if window_end is not None:
        retained = cast(
            pd.DataFrame,
            retained.loc[retained["thru_date"] <= window_end].copy(deep=True),
        )
    if retained.empty:
        raise PreparationError(f"{context} has no rows in the requested date window")
    return _NormalizedPerformance(
        retained.reset_index(drop=True),
        normalized.contribution_was_supplied,
    )


# The reconciliation schema requires these explicit values at one auditable boundary.
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _reconciliation_row(
    stage: str,
    side: str,
    period: _DatePeriod,
    check: str,
    actual: float,
    expected: float,
    tolerance: float,
) -> _ReconciliationRow:
    """Create one passing reconciliation row or raise for a failed invariant.

    Args:
        stage: Preparation stage being audited.
        side: Portfolio or benchmark.
        period: Inclusive period boundaries.
        check: Stable reconciliation check name.
        actual: Value produced by the audited stage.
        expected: Independently recomputed comparison value.
        tolerance: Relative and absolute comparison tolerance.

    Returns:
        One typed passing reconciliation row.

    Raises:
        PreparationError: If either value or their residual is non-finite, or if the
            values differ outside tolerance.
    """
    residual = actual - expected
    finite = np.isfinite([actual, expected, residual]).all()
    passed = bool(
        finite
        and _is_close(
            np.asarray([actual], dtype=np.float64),
            np.asarray([expected], dtype=np.float64),
            tolerance,
        )[0]
    )
    if not passed:
        raise PreparationError(
            f"preparation reconciliation failed for {stage} {side} {check} at "
            f"{period[0].isoformat()} to {period[1].isoformat()}; actual "
            f"{actual:.17g}, expected {expected:.17g}, residual {residual:.17g}"
        )
    return _ReconciliationRow(
        stage=stage,
        side=side,
        from_date=cast(pd.Timestamp, pd.Timestamp(period[0])),
        thru_date=cast(pd.Timestamp, pd.Timestamp(period[1])),
        check=check,
        actual=actual,
        expected=expected,
        residual=residual,
        tolerance=tolerance,
        passed=True,
    )


def _date_period(row: object) -> _DatePeriod:
    """Return plain inclusive dates from a two-value pandas row."""
    values = cast(pd.Series, row)
    return (
        cast(pd.Timestamp, values["from_date"]).date(),
        cast(pd.Timestamp, values["thru_date"]).date(),
    )


def _row_float(row: pd.Series, column: str) -> float:
    """Return one known numeric reconciliation value as an ordinary float."""
    return float(cast(float, row[column]))


def _period_totals(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    """Return chronological period totals for reconciliation."""
    return sum_by_period(frame, columns).sort_values(
        ["thru_date", "from_date"], kind="stable"
    ).reset_index(drop=True)


def _source_reconciliation(
    state: _PreparedSide,
    side: str,
    tolerance: float,
) -> list[_ReconciliationRow]:
    """Audit source-period weight and derived-contribution identities."""
    source = state.source.copy(deep=True)
    if not state.contribution_was_supplied:
        source["_derived_contribution"] = (
            _float_array(source, "weight")
            * np.nan_to_num(_float_array(source, "return"), nan=0.0)
        )
        totals = _period_totals(
            source, ("weight", "contribution", "_derived_contribution")
        )
    else:
        totals = _period_totals(source, ("weight",))

    rows: list[_ReconciliationRow] = []
    for _, total in totals.iterrows():
        period = _date_period(total)
        rows.append(
            _reconciliation_row(
                "source",
                side,
                period,
                "weight_sum",
                _row_float(total, "weight"),
                1.0,
                tolerance,
            )
        )
        if not state.contribution_was_supplied:
            rows.append(
                _reconciliation_row(
                    "source",
                    side,
                    period,
                    "derived_contribution",
                    _row_float(total, "contribution"),
                    _row_float(total, "_derived_contribution"),
                    tolerance,
                )
            )
    return rows


def _mapped_reconciliation(
    state: _PreparedSide,
    side: str,
    tolerance: float,
) -> list[_ReconciliationRow]:
    """Audit mapping conservation at source-period granularity."""
    if not state.mapping_was_applied:
        return []
    source_totals = _period_totals(state.source, ("weight", "contribution"))
    mapped_totals = _period_totals(state.mapped, ("weight", "contribution"))
    compared = source_totals.merge(
        mapped_totals,
        on=["from_date", "thru_date"],
        suffixes=("_source", "_mapped"),
        how="inner",
        validate="one_to_one",
        sort=True,
    )
    if len(compared) != len(source_totals) or len(compared) != len(mapped_totals):
        raise PreparationError("mapped reconciliation changed source-period keys")

    rows: list[_ReconciliationRow] = []
    for _, total in compared.iterrows():
        period = _date_period(total)
        for check, column in (
            ("mapped_weight", "weight"),
            ("mapped_contribution", "contribution"),
        ):
            rows.append(
                _reconciliation_row(
                    "mapped",
                    side,
                    period,
                    check,
                    _row_float(total, f"{column}_mapped"),
                    _row_float(total, f"{column}_source"),
                    tolerance,
                )
            )
    return rows


def _reporting_return_expectations(
    source_period_totals: pd.DataFrame,
    aligned: _AlignedPeriods,
) -> dict[_DatePeriod, float]:
    """Compound source totals for reporting periods that require linking.

    Args:
        source_period_totals: Chronological contribution totals by source period.
        aligned: Validated reporting-period boundaries.

    Returns:
        Independently compounded expected returns keyed by reporting period. Exact
        one-source-period matches are omitted because they require no linking check.

    Notes:
        Boolean selection operates on the small period-total arrays, not the complete
        identifier-level source. ``_compound_returns`` retains the same chronological
        log-space formula used by the scalar reconciliation path.
    """
    source_from = source_period_totals["from_date"].to_numpy(
        dtype="datetime64[ns]"
    )
    source_thru = source_period_totals["thru_date"].to_numpy(
        dtype="datetime64[ns]"
    )
    source_returns = _float_array(source_period_totals, "contribution")
    expectations: dict[_DatePeriod, float] = {}
    for period in aligned.periods:
        reporting_start = np.datetime64(period[0], "ns")
        reporting_end = np.datetime64(period[1], "ns")
        contained = (source_from >= reporting_start) & (source_thru <= reporting_end)
        if int(np.count_nonzero(contained)) > 1:
            expectations[period] = _compound_returns(source_returns[contained])
    return expectations


def _reporting_reconciliation(
    state: _PreparedSide,
    side: str,
    aligned: _AlignedPeriods,
    tolerance: float,
) -> list[_ReconciliationRow]:
    """Audit reporting-period weights and linked contributions."""
    reporting_totals = _period_totals(
        state.reporting, ("weight", "contribution")
    )
    totals_by_period = {
        _date_period(total): total for _, total in reporting_totals.iterrows()
    }
    if tuple(totals_by_period) != aligned.periods:
        raise PreparationError("reporting reconciliation changed aligned period keys")
    # Build independently calculated source-period totals once. Refiltering and
    # regrouping the complete identifier-level source for every reporting period is
    # equivalent but grows unnecessarily with both row count and history length.
    all_source_period_totals = _period_totals(
        state.source, ("contribution",)
    )
    expected_returns = _reporting_return_expectations(
        all_source_period_totals, aligned
    )
    rows: list[_ReconciliationRow] = []
    for period in aligned.periods:
        total = totals_by_period[period]
        rows.append(
            _reconciliation_row(
                "reporting",
                side,
                period,
                "weight_sum",
                _row_float(total, "weight"),
                1.0,
                tolerance,
            )
        )
        if period in expected_returns:
            rows.append(
                _reconciliation_row(
                    "reporting",
                    side,
                    period,
                    "linked_contribution",
                    _row_float(total, "contribution"),
                    expected_returns[period],
                    tolerance,
                )
            )
    return rows


def _build_reconciliation(
    portfolio: _PreparedSide,
    benchmark: _PreparedSide,
    aligned: _AlignedPeriods,
    tolerance: float,
) -> pd.DataFrame:
    """Build stable passing evidence for all auditable preparation stages."""
    sides = (("portfolio", portfolio), ("benchmark", benchmark))
    rows: list[_ReconciliationRow] = []
    for side, state in sides:
        rows.extend(_source_reconciliation(state, side, tolerance))
    for side, state in sides:
        rows.extend(_mapped_reconciliation(state, side, tolerance))
    for side, state in sides:
        rows.extend(_reporting_reconciliation(state, side, aligned, tolerance))

    reconciliation = pd.DataFrame(
        rows, columns=PREPARATION_RECONCILIATION_COLUMNS
    )
    for column in ("stage", "side", "check"):
        reconciliation[column] = reconciliation[column].astype("string[python]")
    for column in ("from_date", "thru_date"):
        reconciliation[column] = reconciliation[column].astype("datetime64[ns]")
    for column in _FINANCIAL_COLUMNS:
        reconciliation[column] = reconciliation[column].astype("float64")
    reconciliation["passed"] = reconciliation["passed"].astype("bool")
    return reconciliation.reset_index(drop=True)


def _prepare_side(
    normalized: _NormalizedPerformance,
    mapping: pd.DataFrame | None,
    aligned: _AlignedPeriods,
    context: str,
    tolerance: float,
) -> _PreparedSide:
    """Map and consolidate one normalized side while retaining audit state."""
    mapped = _map_performance(normalized.frame, mapping, context, tolerance)
    reporting = _consolidate_performance(
        mapped,
        aligned,
        mapping is not None,
        context,
        tolerance,
    )
    return _PreparedSide(
        source=normalized.frame,
        contribution_was_supplied=normalized.contribution_was_supplied,
        mapped=mapped,
        mapping_was_applied=mapping is not None,
        reporting=reporting,
    )


def _prepared_output(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one independently owned frame in the stable public column order."""
    return cast(
        pd.DataFrame,
        frame.loc[:, list(PREPARED_PERFORMANCE_COLUMNS)].copy(deep=True),
    ).reset_index(drop=True)


def _validate_prepared_periods(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> None:
    """Require identical ordered period boundaries and day counts on both sides."""
    columns = ["from_date", "thru_date", "quantity_of_days"]
    portfolio_periods = portfolio.loc[:, columns].drop_duplicates(ignore_index=True)
    benchmark_periods = benchmark.loc[:, columns].drop_duplicates(ignore_index=True)
    if not portfolio_periods.equals(benchmark_periods):
        raise PreparationError(
            "prepared portfolio and benchmark period coverage must match exactly"
        )


# The accepted public contract keeps independent inputs and policies explicit.
# pylint: disable-next=too-many-arguments,too-many-locals
def prepare_attribution(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    frequency: Frequency = Frequency.AS_OFTEN_AS_POSSIBLE,
    holidays: Collection[dt.date] = (),
    from_date: str | dt.date | None = None,
    thru_date: str | dt.date | None = None,
    portfolio_mapping: pd.DataFrame | None = None,
    benchmark_mapping: pd.DataFrame | None = None,
    reconciliation_tolerance: float = _TOLERANCE,
) -> PreparationResult:
    """Prepare source-period portfolio and benchmark rows for attribution.

    Args:
        portfolio: Already-selected source-neutral portfolio performance rows.
        benchmark: Already-selected source-neutral benchmark performance rows.
        frequency: Native or fixed reporting frequency.
        holidays: Plain dates treated as nonbusiness days for fixed endpoints.
        from_date: Optional inclusive lower bound on source-period ``thru_date``.
        thru_date: Optional inclusive upper bound on source-period ``thru_date``.
        portfolio_mapping: Optional static portfolio identifier mapping.
        benchmark_mapping: Optional independent static benchmark identifier mapping.
        reconciliation_tolerance: Positive relative and absolute tolerance used by
            preparation conservation checks.

    Returns:
        Independently owned prepared portfolio, benchmark, and passing reconciliation
        frames. The prepared frames can be passed directly to
        ``calculate_attribution``.

    Raises:
        TypeError: If a DataFrame, frequency, holiday, bound, or tolerance has an
            incompatible boundary type.
        PreparationError: If normalization, date filtering, alignment, mapping,
            consolidation, or financial reconciliation fails.

    Notes:
        The pipeline is deliberately fixed: normalize and filter, align both sides,
        map each side independently, then consolidate to the aligned periods.
        Contribution is derived only when absent from the source; supplied values stay
        authoritative throughout mapping and logarithmic linking.

    Examples:
        Prepare ordinary weights-and-returns inputs and calculate attribution::

            prepared = prepare_attribution(portfolio, benchmark)
            result = calculate_attribution(
                prepared.portfolio,
                prepared.benchmark,
            )
    """
    tolerance = normalize_reconciliation_tolerance(
        reconciliation_tolerance, PreparationError
    )
    window = _normalize_date_window(from_date, thru_date)
    normalized_portfolio = _filter_performance(
        _normalize_performance(portfolio, "portfolio input", tolerance),
        window,
        "portfolio input",
    )
    normalized_benchmark = _filter_performance(
        _normalize_performance(benchmark, "benchmark input", tolerance),
        window,
        "benchmark input",
    )
    aligned = _align_periods(
        normalized_portfolio.frame,
        normalized_benchmark.frame,
        frequency,
        holidays,
    )
    prepared_portfolio = _prepare_side(
        normalized_portfolio,
        portfolio_mapping,
        aligned,
        "portfolio input",
        tolerance,
    )
    prepared_benchmark = _prepare_side(
        normalized_benchmark,
        benchmark_mapping,
        aligned,
        "benchmark input",
        tolerance,
    )
    _validate_prepared_periods(
        prepared_portfolio.reporting,
        prepared_benchmark.reporting,
    )
    reconciliation = _build_reconciliation(
        prepared_portfolio, prepared_benchmark, aligned, tolerance
    )
    return PreparationResult(
        portfolio=_prepared_output(prepared_portfolio.reporting),
        benchmark=_prepared_output(prepared_benchmark.reporting),
        reconciliation=reconciliation,
    )


__all__ = ["PreparationResult", "prepare_attribution"]
