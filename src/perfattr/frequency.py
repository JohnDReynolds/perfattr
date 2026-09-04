"""Define portable reporting frequencies and their calendar endpoints."""

from __future__ import annotations

import calendar
import datetime as dt
from enum import Enum


class Frequency(str, Enum):
    """Identify the supported native and fixed reporting frequencies.

    Attributes:
        AS_OFTEN_AS_POSSIBLE: Preserve exact common native source periods.
        MONTHLY: Align complete calendar-month buckets.
        QUARTERLY: Align complete calendar-quarter buckets.
        YEARLY: Align complete calendar-year buckets.
    """

    AS_OFTEN_AS_POSSIBLE = "Periodic"
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    YEARLY = "Yearly"


def _frequency_bucket(day: dt.date, frequency: Frequency) -> int:
    """Return an ordered integer for the reporting bucket containing ``day``."""
    if frequency == Frequency.MONTHLY:
        return day.year * 12 + day.month - 1
    if frequency == Frequency.QUARTERLY:
        return day.year * 4 + (day.month - 1) // 3
    if frequency == Frequency.YEARLY:
        return day.year
    return day.toordinal()


def _frequency_bucket_end(bucket: int, frequency: Frequency) -> dt.date:
    """Return the nominal calendar endpoint for a reporting bucket."""
    if frequency == Frequency.MONTHLY:
        year, zero_based_month = divmod(bucket, 12)
        month = zero_based_month + 1
        return dt.date(year, month, calendar.monthrange(year, month)[1])
    if frequency == Frequency.QUARTERLY:
        year, zero_based_quarter = divmod(bucket, 4)
        month = (zero_based_quarter + 1) * 3
        return dt.date(year, month, calendar.monthrange(year, month)[1])
    if frequency == Frequency.YEARLY:
        return dt.date(bucket, 12, 31)
    return dt.date.fromordinal(bucket)


def _frequency_bucket_effective_end(
    bucket: int,
    frequency: Frequency,
    holidays: frozenset[dt.date],
) -> dt.date:
    """Roll a nominal endpoint backward over weekends and supplied holidays."""
    endpoint = _frequency_bucket_end(bucket, frequency)
    while endpoint.weekday() >= 5 or endpoint in holidays:
        endpoint -= dt.timedelta(days=1)
    return endpoint


def _date_matches_frequency(
    day: dt.date,
    frequency: Frequency,
    holidays: frozenset[dt.date],
) -> bool:
    """Return whether a date is a permitted endpoint for its reporting bucket."""
    if frequency == Frequency.AS_OFTEN_AS_POSSIBLE:
        return True
    bucket = _frequency_bucket(day, frequency)
    nominal_end = _frequency_bucket_end(bucket, frequency)
    effective_end = _frequency_bucket_effective_end(bucket, frequency, holidays)
    # A literal weekend endpoint is valid when present in source data. A supplied
    # holiday is never accepted merely because it is also the nominal endpoint.
    return (day == nominal_end and nominal_end not in holidays) or day == effective_end


def _frequency_bucket_label(bucket: int, frequency: Frequency) -> str:
    """Return a stable human-readable label for a reporting bucket."""
    if frequency == Frequency.MONTHLY:
        year, zero_based_month = divmod(bucket, 12)
        return f"{year:04d}-{zero_based_month + 1:02d}"
    if frequency == Frequency.QUARTERLY:
        year, zero_based_quarter = divmod(bucket, 4)
        return f"{year:04d}-Q{zero_based_quarter + 1}"
    if frequency == Frequency.YEARLY:
        return str(bucket)
    return _frequency_bucket_end(bucket, frequency).isoformat()


__all__ = ["Frequency"]
