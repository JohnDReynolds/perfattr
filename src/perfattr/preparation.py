"""Validate and align source-period performance before attribution preparation.

This module starts the portable preparation boundary defined by roadmap 2. It
validates source-neutral pandas inputs, selects one portfolio from an already-loaded
frame, and aligns portfolio and benchmark source periods. Dedicated modules own the
subsequent classification mapping and consolidation stages.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
import datetime as dt
from typing import cast
import warnings

import numpy as np
import pandas as pd

from perfattr._exceptions import PreparationError, PreparationWarning
from perfattr.frequency import (
    Frequency,
    _date_matches_frequency,
    _frequency_bucket,
    _frequency_bucket_effective_end,
    _frequency_bucket_end,
    _frequency_bucket_label,
)
from perfattr._schemas import NORMALIZED_PERFORMANCE_COLUMNS
from perfattr._validation import (
    float_array as _float_array,
    has_true as _has_true,
    is_close as _is_close,
    normalize_dates,
    normalize_identity,
    normalize_numeric,
    normalize_reconciliation_tolerance,
    raise_invalid,
    sum_by_period as _sum_by_period,
)


_TOLERANCE = 1e-12
_REQUIRED_COLUMNS = tuple("from_date thru_date identifier weight return".split())
_OPTIONAL_COLUMNS = (
    "contribution",
    "portfolio_code",
    "name",
)
_DatePeriod = tuple[dt.date, dt.date]


@dataclass(frozen=True)
class _AlignedPeriods:
    """Hold common reporting periods selected for later consolidation.

    Attributes:
        periods: Common inclusive reporting-period boundaries.
        buckets: Ordered fixed-frequency bucket identifiers. This is empty for
            native-frequency alignment.
    """

    periods: tuple[_DatePeriod, ...]
    buckets: tuple[int, ...]


@dataclass(frozen=True)
class _FrequencyTruncation:
    """Describe the first incomplete nonterminal fixed-frequency bucket.

    Attributes:
        bucket: Ordered identifier of the incomplete reporting bucket.
        actual_end: Latest source endpoint, or ``None`` when none ends in the bucket.
        expected_end: Effective business endpoint required for completion.
    """

    bucket: int
    actual_end: dt.date | None
    expected_end: dt.date


@dataclass(frozen=True)
class _CoverageRequest:
    """Group the calendar policy and boundaries for one coverage check.

    Attributes:
        bucket: Fixed-frequency bucket being aligned.
        endpoint: Required common actual endpoint.
        previous_endpoint: Prior accepted common endpoint, if any.
        frequency: Fixed reporting frequency.
        holidays: Validated nonbusiness dates.
    """

    bucket: int
    endpoint: dt.date
    previous_endpoint: dt.date | None
    frequency: Frequency
    holidays: frozenset[dt.date]


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


def _normalize_holidays(
    holidays: Collection[dt.date],
) -> frozenset[dt.date]:
    """Validate caller-supplied nonbusiness dates and remove duplicates.

    Args:
        holidays: Date values to treat as nonbusiness days.

    Returns:
        Validated unique dates.

    Raises:
        TypeError: If ``holidays`` is not a collection.
        PreparationError: If an item is not a plain ``datetime.date`` value.

    Notes:
        ``datetime.datetime`` and pandas ``Timestamp`` values are deliberately
        rejected even though they subclass ``datetime.date``. Calendar policy accepts
        dates only and never silently removes time or timezone information.
    """
    if isinstance(holidays, str | bytes) or not isinstance(holidays, Collection):
        raise TypeError("holidays must be a collection of datetime.date values")

    normalized: set[dt.date] = set()
    for holiday in holidays:
        if isinstance(holiday, dt.datetime) or not isinstance(holiday, dt.date):
            raise PreparationError(
                "holidays must contain only datetime.date values, not datetime, "
                "strings, nulls, or other types"
            )
        normalized.add(holiday)
    return frozenset(normalized)


def _source_periods(frame: pd.DataFrame) -> tuple[_DatePeriod, ...]:
    """Extract deterministic unique date pairs from a normalized source frame."""
    period_frame = cast(
        pd.DataFrame,
        frame[["from_date", "thru_date"]].drop_duplicates(),
    ).sort_values(["thru_date", "from_date"], kind="stable")
    return tuple(
        (
            cast(pd.Timestamp, from_value).date(),
            cast(pd.Timestamp, thru_value).date(),
        )
        for from_value, thru_value in period_frame.itertuples(index=False, name=None)
    )


def _format_periods(periods: Sequence[_DatePeriod]) -> str:
    """Format inclusive periods for a deterministic alignment error."""
    return "[" + ", ".join(
        f"({from_date.isoformat()}, {thru_date.isoformat()})"
        for from_date, thru_date in periods
    ) + "]"


def _validate_fixed_frequency_coverage(
    periods: Sequence[_DatePeriod],
    frequency: Frequency,
    context: str,
) -> None:
    """Require source coverage in every fixed bucket between the observed bounds.

    A source interval contributes coverage to every calendar bucket it intersects.
    This distinguishes a truly absent bucket, which is invalid, from a bucket having
    data but an incomplete endpoint, which follows the truncation policy.

    Args:
        periods: Validated ordered source-period boundaries.
        frequency: Fixed reporting frequency.
        context: Human-readable side included in errors.

    Raises:
        PreparationError: If one or more intervening reporting buckets have no source
            coverage.
    """
    covered: set[int] = set()
    for from_date, thru_date in periods:
        covered.update(
            range(
                _frequency_bucket(from_date, frequency),
                _frequency_bucket(thru_date, frequency) + 1,
            )
        )
    first_bucket = min(_frequency_bucket(period[0], frequency) for period in periods)
    last_bucket = max(_frequency_bucket(period[1], frequency) for period in periods)
    missing = [
        bucket
        for bucket in range(first_bucket, last_bucket + 1)
        if bucket not in covered
    ]
    if missing:
        labels = [_frequency_bucket_label(bucket, frequency) for bucket in missing]
        _raise_invalid(
            context,
            f"is missing {frequency.value.lower()} coverage for {labels}",
        )


def _validate_source_period_boundaries(
    periods: Sequence[_DatePeriod],
    frequency: Frequency,
    holidays: frozenset[dt.date],
    context: str,
) -> None:
    """Reject a source interval extending before its permitted reporting range.

    Args:
        periods: Validated ordered source-period boundaries.
        frequency: Fixed reporting frequency.
        holidays: Validated nonbusiness dates.
        context: Human-readable side included in errors.

    Raises:
        PreparationError: If a source interval begins before the calendar tail that
            may legitimately follow the prior bucket's effective endpoint.

    Notes:
        A period assigned by its end date may begin after the preceding effective
        endpoint, including on intervening weekend or holiday dates. It cannot begin
        earlier because that would fold prior reporting-bucket coverage into this one.
    """
    for from_date, thru_date in periods:
        bucket = _frequency_bucket(thru_date, frequency)
        earliest_start = _frequency_bucket_effective_end(
            bucket - 1,
            frequency,
            holidays,
        ) + dt.timedelta(days=1)
        if from_date < earliest_start:
            _raise_invalid(
                context,
                f"source period {from_date.isoformat()} to {thru_date.isoformat()} "
                "extends outside the permitted reporting range for "
                f"{_frequency_bucket_label(bucket, frequency)}",
            )


def _completed_bucket_ends(
    periods: Sequence[_DatePeriod],
    frequency: Frequency,
    holidays: frozenset[dt.date],
    context: str,
) -> tuple[dict[int, dt.date], _FrequencyTruncation | None, int | None]:
    """Return the contiguous prefix of complete fixed-frequency buckets.

    Args:
        periods: Validated ordered source-period boundaries.
        frequency: Fixed reporting frequency.
        holidays: Validated nonbusiness dates.
        context: Human-readable side included in errors.

    Returns:
        Complete bucket endpoints, an optional incomplete interior bucket, and an
        optional incomplete terminal bucket identifier.
    """
    _validate_source_period_boundaries(periods, frequency, holidays, context)
    _validate_fixed_frequency_coverage(periods, frequency, context)
    latest_end_by_bucket: dict[int, dt.date] = {}
    for _, thru_date in periods:
        bucket = _frequency_bucket(thru_date, frequency)
        latest_end_by_bucket[bucket] = max(
            thru_date,
            latest_end_by_bucket.get(bucket, dt.date.min),
        )

    first_bucket = min(latest_end_by_bucket)
    last_bucket = max(latest_end_by_bucket)
    complete: dict[int, dt.date] = {}
    for bucket in range(first_bucket, last_bucket + 1):
        actual_end = latest_end_by_bucket.get(bucket)
        if actual_end is not None and _date_matches_frequency(
            actual_end,
            frequency,
            holidays,
        ):
            complete[bucket] = actual_end
            continue
        if bucket == last_bucket:
            return complete, None, bucket
        return (
            complete,
            _FrequencyTruncation(
                bucket=bucket,
                actual_end=actual_end,
                expected_end=_frequency_bucket_effective_end(
                    bucket,
                    frequency,
                    holidays,
                ),
            ),
            None,
        )
    return complete, None, None


def _validate_gapless_periods(
    periods: Sequence[_DatePeriod],
    label: str,
    context: str,
) -> None:
    """Require consecutive inclusive source intervals inside one bucket."""
    for (_, prior_end), (next_start, _) in zip(periods[:-1], periods[1:]):
        expected_start = prior_end + dt.timedelta(days=1)
        if next_start != expected_start:
            _raise_invalid(
                context,
                f"coverage for {label} is not gapless: expected "
                f"{expected_start.isoformat()} after {prior_end.isoformat()}, "
                f"received {next_start.isoformat()}",
            )


def _coverage_start_bounds(
    request: _CoverageRequest,
) -> tuple[dt.date, dt.date, str]:
    """Return the permitted start range and its explanatory error phrase."""
    if request.previous_endpoint is None:
        earliest_start = _frequency_bucket_effective_end(
            request.bucket - 1,
            request.frequency,
            request.holidays,
        ) + dt.timedelta(days=1)
        requirement = "a complete first reporting bucket must start"
    else:
        earliest_start = request.previous_endpoint + dt.timedelta(days=1)
        requirement = "after the preceding aligned endpoint, the next bucket must start"
    latest_start = _frequency_bucket_end(
        request.bucket - 1,
        request.frequency,
    ) + dt.timedelta(days=1)
    return earliest_start, latest_start, requirement


def _fixed_frequency_coverage_start(
    periods: Sequence[_DatePeriod],
    request: _CoverageRequest,
    context: str,
) -> dt.date:
    """Validate one source's gapless bucket coverage and return its actual start.

    Args:
        periods: Validated ordered source-period boundaries.
        request: Calendar policy and reporting boundaries for this check.
        context: Human-readable side included in errors.

    Returns:
        First actual date covered in the reporting bucket.

    Raises:
        PreparationError: If periods are missing, cross the permitted reporting
            boundary, leave an internal gap, or do not cover a complete first bucket.
    """
    label = _frequency_bucket_label(request.bucket, request.frequency)
    bucket_periods = [
        period
        for period in periods
        if _frequency_bucket(period[1], request.frequency) == request.bucket
    ]
    if not bucket_periods:
        _raise_invalid(context, f"has no source periods for {label}")
    if bucket_periods[-1][1] != request.endpoint:
        _raise_invalid(
            context,
            f"coverage for {label} ends {bucket_periods[-1][1].isoformat()}, not "
            f"the aligned endpoint {request.endpoint.isoformat()}",
        )

    _validate_gapless_periods(bucket_periods, label, context)
    actual_start = bucket_periods[0][0]
    earliest_start, latest_start, requirement = _coverage_start_bounds(request)
    if not earliest_start <= actual_start <= latest_start:
        _raise_invalid(
            context,
            f"coverage for {label} starts {actual_start.isoformat()}; {requirement} "
            f"between {earliest_start.isoformat()} and {latest_start.isoformat()}",
        )
    return actual_start


def _align_native_periods(
    portfolio_periods: tuple[_DatePeriod, ...],
    benchmark_periods: tuple[_DatePeriod, ...],
) -> _AlignedPeriods:
    """Align exact common native periods and reject mismatches inside their window."""
    portfolio_set = set(portfolio_periods)
    benchmark_set = set(benchmark_periods)
    common_set = portfolio_set.intersection(benchmark_set)
    common = tuple(sorted(common_set, key=lambda period: (period[1], period[0])))
    if not common:
        raise PreparationError("no common performance periods were found")

    comparison_start = common[0][0]
    comparison_end = common[-1][1]
    unmatched_portfolio = tuple(
        period
        for period in portfolio_periods
        if period not in common_set
        and period[1] >= comparison_start
        and period[0] <= comparison_end
    )
    unmatched_benchmark = tuple(
        period
        for period in benchmark_periods
        if period not in common_set
        and period[1] >= comparison_start
        and period[0] <= comparison_end
    )
    if unmatched_portfolio or unmatched_benchmark:
        raise PreparationError(
            "unmatched native-frequency periods exist inside the common comparison "
            f"window; portfolio-only periods: {_format_periods(unmatched_portfolio)}; "
            f"benchmark-only periods: {_format_periods(unmatched_benchmark)}"
        )
    return _AlignedPeriods(periods=common, buckets=())


def _truncation_message(
    truncations: Sequence[_FrequencyTruncation],
    frequency: Frequency,
) -> str | None:
    """Return one warning message for the earliest incomplete interior bucket."""
    if not truncations:
        return None
    truncation = min(truncations, key=lambda item: item.bucket)
    actual_end = (
        truncation.actual_end.isoformat()
        if truncation.actual_end is not None
        else "missing"
    )
    return (
        f"{frequency.value} output was truncated before "
        f"{_frequency_bucket_label(truncation.bucket, frequency)}: source endpoint "
        f"{actual_end} did not match expected endpoint "
        f"{truncation.expected_end.isoformat()}"
    )


def _validate_terminal_completeness(
    results: tuple[
        tuple[dict[int, dt.date], _FrequencyTruncation | None, int | None],
        tuple[dict[int, dt.date], _FrequencyTruncation | None, int | None],
    ],
    frequency: Frequency,
) -> None:
    """Reject a terminal bucket completed by only one aligned source."""
    complete_by_side = (results[0][0], results[1][0])
    for source_index, result in enumerate(results):
        incomplete_terminal = result[2]
        other_complete = complete_by_side[1 - source_index]
        if incomplete_terminal is not None and incomplete_terminal in other_complete:
            raise PreparationError(
                "portfolio and benchmark terminal-bucket completeness differs for "
                f"{_frequency_bucket_label(incomplete_terminal, frequency)}"
            )


def _align_fixed_bucket(
    portfolio_periods: tuple[_DatePeriod, ...],
    benchmark_periods: tuple[_DatePeriod, ...],
    request: _CoverageRequest,
    benchmark_endpoint: dt.date,
) -> _DatePeriod:
    """Validate equal endpoint and start coverage for one common fixed bucket."""
    label = _frequency_bucket_label(request.bucket, request.frequency)
    if benchmark_endpoint != request.endpoint:
        raise PreparationError(
            f"portfolio and benchmark effective endpoints differ for {label}"
        )
    portfolio_start = _fixed_frequency_coverage_start(
        portfolio_periods,
        request,
        "portfolio input",
    )
    benchmark_start = _fixed_frequency_coverage_start(
        benchmark_periods,
        request,
        "benchmark input",
    )
    if portfolio_start != benchmark_start:
        raise PreparationError(
            "portfolio and benchmark actual source coverage starts differ for "
            f"{label}: {portfolio_start.isoformat()} versus "
            f"{benchmark_start.isoformat()}"
        )
    return portfolio_start, request.endpoint


def _align_fixed_periods(
    portfolio_periods: tuple[_DatePeriod, ...],
    benchmark_periods: tuple[_DatePeriod, ...],
    frequency: Frequency,
    holidays: frozenset[dt.date],
) -> _AlignedPeriods:
    """Align complete fixed-frequency buckets with identical inclusive coverage."""
    results = (
        _completed_bucket_ends(
            portfolio_periods,
            frequency,
            holidays,
            "portfolio input",
        ),
        _completed_bucket_ends(
            benchmark_periods,
            frequency,
            holidays,
            "benchmark input",
        ),
    )
    _validate_terminal_completeness(results, frequency)
    complete_by_side = (results[0][0], results[1][0])

    common_buckets = tuple(
        sorted(set(complete_by_side[0]).intersection(complete_by_side[1]))
    )
    reporting_periods: list[_DatePeriod] = []
    previous_endpoint: dt.date | None = None
    for bucket in common_buckets:
        endpoint = complete_by_side[0][bucket]
        request = _CoverageRequest(
            bucket=bucket,
            endpoint=endpoint,
            previous_endpoint=previous_endpoint,
            frequency=frequency,
            holidays=holidays,
        )
        reporting_period = _align_fixed_bucket(
            portfolio_periods,
            benchmark_periods,
            request,
            complete_by_side[1][bucket],
        )
        reporting_periods.append(reporting_period)
        previous_endpoint = endpoint

    if not reporting_periods:
        raise PreparationError("no complete common reporting buckets were found")

    warning_message = _truncation_message(
        tuple(
            result[1]
            for result in results
            if result[1] is not None
        ),
        frequency,
    )
    if warning_message is not None:
        warnings.warn(warning_message, PreparationWarning, stacklevel=3)
    return _AlignedPeriods(tuple(reporting_periods), common_buckets)


def _align_periods(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    frequency: Frequency = Frequency.AS_OFTEN_AS_POSSIBLE,
    holidays: Collection[dt.date] = (),
) -> _AlignedPeriods:
    """Align validated portfolio and benchmark source-period boundaries.

    Args:
        portfolio: Normalized source-period portfolio rows.
        benchmark: Normalized source-period benchmark rows.
        frequency: Native or fixed reporting frequency.
        holidays: Dates treated as nonbusiness days for fixed endpoints.

    Returns:
        Common reporting periods and fixed bucket identifiers. The input frames are
        never mutated.

    Raises:
        TypeError: If ``frequency`` is not a ``Frequency`` or holidays is not a
            collection.
        PreparationError: If holidays, native periods, fixed-frequency coverage, or
            aligned boundaries violate the preparation specification.

    Notes:
        Source frames must already have passed ``_normalize_performance``. This step
        selects reporting boundaries only; it does not consolidate financial values.
    """
    if not isinstance(frequency, Frequency):
        raise TypeError("frequency must be a Frequency")
    normalized_holidays = _normalize_holidays(holidays)
    portfolio_periods = _source_periods(portfolio)
    benchmark_periods = _source_periods(benchmark)
    if frequency == Frequency.AS_OFTEN_AS_POSSIBLE:
        return _align_native_periods(portfolio_periods, benchmark_periods)
    return _align_fixed_periods(
        portfolio_periods,
        benchmark_periods,
        frequency,
        normalized_holidays,
    )


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
    totals = _sum_by_period(frame, ("weight", "contribution"))
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
    ordered_columns = [*NORMALIZED_PERFORMANCE_COLUMNS]
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

    normalized_codes = normalize_identity(
        performance,
        "portfolio_code",
        "performance input",
        PreparationError,
    )
    matching = normalized_codes.eq(requested_code)
    selected = cast(
        pd.DataFrame,
        performance.loc[matching].copy(deep=True),
    )
    if selected.empty:
        raise PreparationError(f"no performance rows match portfolio_code {requested_code!r}")
    selected["portfolio_code"] = normalized_codes.loc[matching]
    return selected.reset_index(drop=True)


__all__ = [
    "PreparationError",
    "PreparationWarning",
    "select_portfolio",
]
