"""Tests for portable reporting-frequency calendars and period alignment."""

from __future__ import annotations

from collections.abc import Collection
import datetime as dt
from typing import Any, cast
import warnings

import pandas as pd
import pytest

from perfattr import Frequency, PreparationError, PreparationWarning
from perfattr.frequency import (
    _date_matches_frequency,
    _frequency_bucket,
    _frequency_bucket_effective_end,
    _frequency_bucket_end,
    _frequency_bucket_label,
)
from perfattr.preparation import (
    _AlignedPeriods,
    _align_periods,
    _normalize_holidays,
    _normalize_performance,
)


_DatePeriod = tuple[dt.date, dt.date]


def _normalized(periods: Collection[_DatePeriod]) -> pd.DataFrame:
    """Build valid one-identifier source rows for independently chosen periods."""
    rows = [
        {
            "from_date": from_date,
            "thru_date": thru_date,
            "identifier": "A",
            "weight": 1.0,
            "return": 0.01,
        }
        for from_date, thru_date in periods
    ]
    return _normalize_performance(pd.DataFrame(rows), "test input").frame


def test_frequency_is_public_with_the_specified_values() -> None:
    """The public enum values should match the accepted preparation contract."""
    assert Frequency.AS_OFTEN_AS_POSSIBLE.value == "Periodic"
    assert Frequency.MONTHLY.value == "Monthly"
    assert Frequency.QUARTERLY.value == "Quarterly"
    assert Frequency.YEARLY.value == "Yearly"


@pytest.mark.parametrize(
    ("day", "frequency", "expected_bucket", "expected_end", "expected_label"),
    [
        pytest.param(
            dt.date(2024, 2, 10),
            Frequency.MONTHLY,
            2024 * 12 + 1,
            dt.date(2024, 2, 29),
            "2024-02",
            id="leap-month",
        ),
        pytest.param(
            dt.date(2024, 5, 10),
            Frequency.QUARTERLY,
            2024 * 4 + 1,
            dt.date(2024, 6, 30),
            "2024-Q2",
            id="quarter",
        ),
        pytest.param(
            dt.date(2024, 8, 10),
            Frequency.YEARLY,
            2024,
            dt.date(2024, 12, 31),
            "2024",
            id="year",
        ),
    ],
)
def test_fixed_frequency_bucket_arithmetic(
    day: dt.date,
    frequency: Frequency,
    expected_bucket: int,
    expected_end: dt.date,
    expected_label: str,
) -> None:
    """Month, quarter, and year buckets should use their calendar boundaries."""
    bucket = _frequency_bucket(day, frequency)

    assert bucket == expected_bucket
    assert _frequency_bucket_end(bucket, frequency) == expected_end
    assert _frequency_bucket_label(bucket, frequency) == expected_label


def test_effective_endpoint_rolls_over_weekends_and_consecutive_holidays() -> None:
    """A year-end should roll backward until a usable weekday remains."""
    bucket = _frequency_bucket(dt.date(2023, 12, 31), Frequency.YEARLY)
    holidays = frozenset((dt.date(2023, 12, 28), dt.date(2023, 12, 29)))

    # December 31 is Sunday, December 30 is Saturday, and the two prior weekdays
    # are supplied holidays, so Wednesday December 27 is the effective endpoint.
    assert (
        _frequency_bucket_effective_end(bucket, Frequency.YEARLY, holidays)
        == dt.date(2023, 12, 27)
    )


def test_literal_weekend_endpoint_and_effective_weekday_are_both_valid() -> None:
    """A source may close on literal month-end or its prior effective weekday."""
    no_holidays: frozenset[dt.date] = frozenset()

    assert _date_matches_frequency(
        dt.date(2023, 12, 31),
        Frequency.MONTHLY,
        no_holidays,
    )
    assert _date_matches_frequency(
        dt.date(2023, 12, 29),
        Frequency.MONTHLY,
        no_holidays,
    )
    assert not _date_matches_frequency(
        dt.date(2023, 12, 28),
        Frequency.MONTHLY,
        no_holidays,
    )


def test_supplied_holiday_displaces_a_nominal_or_effective_endpoint() -> None:
    """A supplied holiday should never qualify as a bucket-closing endpoint."""
    good_friday = frozenset((dt.date(2024, 3, 29),))
    year_end_holiday = frozenset((dt.date(2024, 12, 31),))

    assert not _date_matches_frequency(
        dt.date(2024, 3, 29),
        Frequency.QUARTERLY,
        good_friday,
    )
    assert _date_matches_frequency(
        dt.date(2024, 3, 28),
        Frequency.QUARTERLY,
        good_friday,
    )
    assert not _date_matches_frequency(
        dt.date(2024, 12, 31),
        Frequency.YEARLY,
        year_end_holiday,
    )
    assert _date_matches_frequency(
        dt.date(2024, 12, 30),
        Frequency.YEARLY,
        year_end_holiday,
    )


def test_holiday_normalization_deduplicates_plain_dates() -> None:
    """Repeated plain dates should be harmless and produce an immutable set."""
    holiday = dt.date(2024, 12, 25)

    assert _normalize_holidays([holiday, holiday]) == frozenset((holiday,))


@pytest.mark.parametrize(
    ("holidays", "error_type"),
    [
        pytest.param("2024-12-25", TypeError, id="not-a-collection-of-dates"),
        pytest.param(["2024-12-25"], PreparationError, id="string-item"),
        pytest.param([None], PreparationError, id="null-item"),
        pytest.param(
            [dt.datetime(2024, 12, 25)],
            PreparationError,
            id="datetime-item",
        ),
        pytest.param(
            [pd.Timestamp("2024-12-25")],
            PreparationError,
            id="timestamp-item",
        ),
    ],
)
def test_holiday_normalization_rejects_non_date_values(
    holidays: Any,
    error_type: type[Exception],
) -> None:
    """Calendar inputs should not silently parse or truncate non-date values."""
    with pytest.raises(error_type):
        _normalize_holidays(cast(Collection[dt.date], holidays))


def test_native_alignment_keeps_exact_common_periods_only() -> None:
    """Unmatched native periods wholly outside the shared window should be excluded."""
    december = (dt.date(2023, 12, 1), dt.date(2023, 12, 31))
    january = (dt.date(2024, 1, 1), dt.date(2024, 1, 31))
    february = (dt.date(2024, 2, 1), dt.date(2024, 2, 29))
    march = (dt.date(2024, 3, 1), dt.date(2024, 3, 31))
    portfolio = _normalized((december, january, february))
    benchmark = _normalized((january, february, march))
    portfolio_before = portfolio.copy(deep=True)
    benchmark_before = benchmark.copy(deep=True)

    aligned = _align_periods(portfolio, benchmark)

    assert isinstance(aligned, _AlignedPeriods)
    assert aligned.periods == (january, february)
    assert not aligned.buckets
    pd.testing.assert_frame_equal(portfolio, portfolio_before)
    pd.testing.assert_frame_equal(benchmark, benchmark_before)


def test_native_alignment_rejects_unmatched_periods_inside_common_window() -> None:
    """Exact common endpoints must not hide different native partitions between them."""
    first = (dt.date(2024, 1, 1), dt.date(2024, 1, 10))
    last = (dt.date(2024, 1, 21), dt.date(2024, 1, 31))
    portfolio = _normalized((first, (dt.date(2024, 1, 11), dt.date(2024, 1, 15)), last))
    benchmark = _normalized((first, (dt.date(2024, 1, 16), dt.date(2024, 1, 20)), last))

    with pytest.raises(PreparationError, match="unmatched native-frequency periods"):
        _align_periods(portfolio, benchmark)


def test_native_alignment_requires_a_common_period() -> None:
    """Disjoint native histories should not be relabeled as comparable."""
    portfolio = _normalized(((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),))
    benchmark = _normalized(((dt.date(2024, 2, 1), dt.date(2024, 2, 29)),))

    with pytest.raises(PreparationError, match="no common performance periods"):
        _align_periods(portfolio, benchmark)


def test_fixed_alignment_accepts_different_partitions_of_equal_coverage() -> None:
    """One monthly row and two gapless subperiods can cover the same leap month."""
    portfolio = _normalized(((dt.date(2024, 2, 1), dt.date(2024, 2, 29)),))
    benchmark = _normalized(
        (
            (dt.date(2024, 2, 1), dt.date(2024, 2, 14)),
            (dt.date(2024, 2, 15), dt.date(2024, 2, 29)),
        )
    )

    aligned = _align_periods(portfolio, benchmark, Frequency.MONTHLY)

    assert aligned.periods == ((dt.date(2024, 2, 1), dt.date(2024, 2, 29)),)
    assert aligned.buckets == (2024 * 12 + 1,)


def test_fixed_alignment_accepts_calendar_tail_after_effective_prior_end() -> None:
    """Weekend days after an effective prior endpoint may begin the next bucket."""
    # December 2023 ended on Sunday, with Friday December 29 as its effective end.
    # A January source period may therefore begin on Saturday December 30.
    period = (dt.date(2023, 12, 30), dt.date(2024, 1, 31))
    performance = _normalized((period,))

    aligned = _align_periods(performance, performance, Frequency.MONTHLY)

    assert aligned.periods == (period,)


def test_fixed_alignment_keeps_gapless_consecutive_months() -> None:
    """Accepted buckets should continue immediately across ordinary month ends."""
    periods = (
        (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
        (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
    )
    performance = _normalized(periods)

    aligned = _align_periods(performance, performance, Frequency.MONTHLY)

    assert aligned.periods == periods


def test_fixed_alignment_allows_weekend_tail_between_complete_months() -> None:
    """The next bucket may start after unrepresented prior month-end weekend days."""
    periods = (
        (dt.date(2023, 12, 1), dt.date(2023, 12, 29)),
        (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
    )
    performance = _normalized(periods)

    aligned = _align_periods(performance, performance, Frequency.MONTHLY)

    assert aligned.periods == periods


@pytest.mark.parametrize(
    ("portfolio_periods", "benchmark_periods", "message"),
    [
        pytest.param(
            ((dt.date(2023, 12, 1), dt.date(2023, 12, 29)),),
            ((dt.date(2023, 12, 1), dt.date(2023, 12, 31)),),
            "effective endpoints differ",
            id="different-endpoints",
        ),
        pytest.param(
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            ((dt.date(2024, 1, 2), dt.date(2024, 1, 31)),),
            "coverage for 2024-01 starts 2024-01-02",
            id="partial-first-bucket",
        ),
        pytest.param(
            (
                (dt.date(2024, 1, 1), dt.date(2024, 1, 10)),
                (dt.date(2024, 1, 12), dt.date(2024, 1, 31)),
            ),
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            "expected 2024-01-11",
            id="internal-gap",
        ),
        pytest.param(
            ((dt.date(2024, 1, 1), dt.date(2024, 2, 29)),),
            ((dt.date(2024, 1, 1), dt.date(2024, 2, 29)),),
            "extends outside the permitted reporting range for 2024-02",
            id="period-crosses-reporting-boundary",
        ),
    ],
)
def test_fixed_alignment_rejects_unequal_or_incomplete_coverage(
    portfolio_periods: tuple[_DatePeriod, ...],
    benchmark_periods: tuple[_DatePeriod, ...],
    message: str,
) -> None:
    """Fixed bucket labels must not hide unequal, partial, or gapped coverage."""
    with pytest.raises(PreparationError, match=message):
        _align_periods(
            _normalized(portfolio_periods),
            _normalized(benchmark_periods),
            Frequency.MONTHLY,
        )


def test_fixed_alignment_rejects_a_missing_interior_bucket() -> None:
    """January and March observations cannot silently imply February coverage."""
    periods = (
        (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
        (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
    )
    performance = _normalized(periods)

    with pytest.raises(PreparationError, match="missing monthly coverage.*2024-02"):
        _align_periods(performance, performance, Frequency.MONTHLY)


def test_fixed_alignment_rejects_a_gap_between_completed_buckets() -> None:
    """A later completed month must begin directly after the prior reporting range."""
    periods = (
        (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
        (dt.date(2024, 2, 2), dt.date(2024, 2, 29)),
    )
    performance = _normalized(periods)

    with pytest.raises(PreparationError, match="between 2024-02-01 and 2024-02-01"):
        _align_periods(performance, performance, Frequency.MONTHLY)


def test_fixed_alignment_omits_a_shared_incomplete_terminal_bucket() -> None:
    """A shared partial terminal month should be excluded without a warning."""
    periods = (
        (dt.date(2023, 11, 1), dt.date(2023, 11, 30)),
        (dt.date(2023, 12, 1), dt.date(2023, 12, 28)),
    )
    performance = _normalized(periods)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        aligned = _align_periods(performance, performance, Frequency.MONTHLY)

    assert not caught
    assert aligned.periods == ((dt.date(2023, 11, 1), dt.date(2023, 11, 30)),)


def test_fixed_alignment_rejects_asymmetric_terminal_completeness() -> None:
    """A terminal reporting month completed by only one side is incomparable."""
    portfolio = _normalized(
        (
            (dt.date(2023, 11, 1), dt.date(2023, 11, 30)),
            (dt.date(2023, 12, 1), dt.date(2023, 12, 28)),
        )
    )
    benchmark = _normalized(
        (
            (dt.date(2023, 11, 1), dt.date(2023, 11, 30)),
            (dt.date(2023, 12, 1), dt.date(2023, 12, 31)),
        )
    )

    with pytest.raises(PreparationError, match="terminal-bucket completeness differs"):
        _align_periods(portfolio, benchmark, Frequency.MONTHLY)


def test_fixed_alignment_warns_and_truncates_at_incomplete_interior_bucket() -> None:
    """An incomplete interior month should stop it and all later output explicitly."""
    periods = (
        (dt.date(2023, 11, 1), dt.date(2023, 11, 30)),
        (dt.date(2023, 12, 1), dt.date(2023, 12, 28)),
        (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
    )
    performance = _normalized(periods)

    with pytest.warns(PreparationWarning, match="source endpoint 2023-12-28"):
        aligned = _align_periods(performance, performance, Frequency.MONTHLY)

    assert aligned.periods == ((dt.date(2023, 11, 1), dt.date(2023, 11, 30)),)


def test_fixed_alignment_uses_supplied_holiday_for_quarter_end() -> None:
    """A supplied Good Friday should make the prior Thursday close the quarter."""
    period = (dt.date(2024, 1, 1), dt.date(2024, 3, 28))
    performance = _normalized((period,))

    aligned = _align_periods(
        performance,
        performance,
        Frequency.QUARTERLY,
        holidays=(dt.date(2024, 3, 29),),
    )

    assert aligned.periods == (period,)


def test_alignment_rejects_non_enum_frequency() -> None:
    """Frequency strings should not bypass the explicit public enum contract."""
    period = _normalized(((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),))

    with pytest.raises(TypeError, match="frequency must be a Frequency"):
        _align_periods(period, period, cast(Frequency, "Monthly"))
