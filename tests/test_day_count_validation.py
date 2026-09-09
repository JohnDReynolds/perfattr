"""Tests for exact day-count normalization at the public calculation boundary."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from perfattr import AttributionError, calculate_attribution


def _single_period(day_count: int | float) -> pd.DataFrame:
    """Return one valid prepared row with the requested authoritative day count."""
    return pd.DataFrame(
        {
            "from_date": ["2024-01-01"],
            "thru_date": ["2024-01-31"],
            "identifier": ["TOTAL"],
            "weight": [1.0],
            "return": [0.01],
            "quantity_of_days": [day_count],
        }
    )


def test_day_count_above_int64_range_is_rejected_before_conversion() -> None:
    """An unrepresentable day count must not silently alter horizon weighting.

    ``2**63`` is one greater than the largest signed 64-bit integer. Earlier pandas
    conversion saturated this value at the ``int64`` maximum, which could make two
    distinct requested day counts equal and change their relative horizon weights.
    """
    portfolio = _single_period(float(2**63))
    benchmark = _single_period(31)

    with pytest.raises(AttributionError, match="within the int64 range"):
        calculate_attribution(portfolio, benchmark)


def test_maximum_int64_day_count_remains_exactly_representable() -> None:
    """The range guard should retain the largest value supported by the result schema.

    The value is not a realistic reporting interval; it proves that integer inputs
    are checked before float conversion and that the accepted boundary round-trips
    without saturation or rounding.
    """
    maximum = np.iinfo(np.int64).max
    portfolio = _single_period(maximum)
    benchmark = _single_period(maximum)

    result = calculate_attribution(portfolio, benchmark)

    assert result.period_detail["quantity_of_days"].eq(maximum).all()
