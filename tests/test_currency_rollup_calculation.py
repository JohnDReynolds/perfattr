"""Independent calculation tests for Roadmap 13 log-effect roll-up."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
import pytest

from perfattr import calculate_currency_attribution, roll_up_currency_attribution
from perfattr._schemas import (
    CURRENCY_EXPOSURE_INPUT_COLUMNS,
    CURRENCY_MARKET_INPUT_COLUMNS,
    CURRENCY_ROLLUP_CUMULATIVE_COLUMNS,
    CURRENCY_ROLLUP_CURRENCY_OVERALL_COLUMNS,
    CURRENCY_ROLLUP_MARKET_OVERALL_COLUMNS,
)


_MARKET_PERIODS = (
    (
        "2024-01-01",
        "2024-01-31",
        (("A", 0.6, 0.03, 0.5, 0.02), ("B", 0.4, 0.01, 0.5, 0.04)),
    ),
    (
        "2024-02-01",
        "2024-02-29",
        (("A", 0.4, 0.00, 0.5, -0.01), ("C", 0.6, 0.04, 0.5, 0.03)),
    ),
    (
        "2024-03-01",
        "2024-03-31",
        (("B", 0.5, 0.01, 0.2, 0.02), ("C", 0.5, 0.02, 0.8, 0.00)),
    ),
)
_CURRENCY_PERIODS = (
    (
        "2024-01-01",
        "2024-01-31",
        (("EUR", 0.7, 0.02, 0.5, 0.01), ("USD", 0.3, -0.01, 0.5, 0.00)),
    ),
    (
        "2024-02-01",
        "2024-02-29",
        (("JPY", 0.8, -0.01, 0.4, -0.02), ("USD", 0.2, 0.01, 0.6, 0.00)),
    ),
    (
        "2024-03-01",
        "2024-03-31",
        (("EUR", 1.1, 0.00, 0.4, 0.01), ("JPY", -0.1, -0.02, 0.6, 0.00)),
    ),
)
_CUMULATIVE_VALUES = np.asarray(
    [
        [
            0.022,
            0.030,
            -0.008,
            0.011,
            0.005,
            0.006,
            0.033,
            0.035,
            -0.002,
            -0.002,
            -0.006,
            0.002,
            0.004,
            -0.002,
        ],
        [
            0.046,
            0.040,
            0.006,
            0.005,
            -0.003,
            0.008,
            0.051,
            0.037,
            0.014,
            0.002,
            0.004,
            -0.006,
            0.014,
            0.014,
        ],
        [
            0.061,
            0.044,
            0.017,
            0.007,
            0.001,
            0.006,
            0.068,
            0.045,
            0.023,
            0.008,
            0.009,
            0.001,
            0.005,
            0.023,
        ],
    ],
    dtype=np.float64,
)
_MARKET_OVERALL_VALUES = {
    1: (("A", -0.001, 0.006, 0.005), ("B", -0.001, -0.012, -0.013)),
    2: (
        ("A", 0.001, 0.010, 0.011),
        ("B", -0.001, -0.012, -0.013),
        ("C", 0.002, 0.006, 0.008),
    ),
    3: (
        ("A", 0.001, 0.010, 0.011),
        ("B", 0.0038, -0.017, -0.0132),
        ("C", 0.0032, 0.016, 0.0192),
    ),
}
_CURRENCY_OVERALL_VALUES = {
    1: (("EUR", 0.001, 0.007, 0.008), ("USD", 0.001, -0.003, -0.002)),
    2: (
        ("EUR", 0.001, 0.007, 0.008),
        ("JPY", -0.0048, 0.008, 0.0032),
        ("USD", -0.0022, -0.001, -0.0032),
    ),
    3: (
        ("EUR", 0.0052, -0.004, 0.0012),
        ("JPY", -0.002, 0.010, 0.008),
        ("USD", -0.0022, -0.001, -0.0032),
    ),
}


def _simple_return(log_return: float) -> float:
    """Convert a hand-selected log return to the public simple-return input."""
    return float(np.expm1(log_return))


def _source_inputs(
    period_count: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build four valid frames from independently selected log-return facts.

    Local cash is zero, so each market asset's chosen log return is also its local
    log-return premium. Public inputs remain ordinary simple returns through an
    explicit ``expm1`` conversion. Portfolio and benchmark universes match within
    each period while changing across periods to exercise partial-history roll-up.
    """
    portfolio_markets: list[tuple[object, ...]] = []
    benchmark_markets: list[tuple[object, ...]] = []
    for from_date, thru_date, rows in _MARKET_PERIODS[:period_count]:
        for identifier, portfolio_weight, portfolio_log, benchmark_weight, benchmark_log in rows:
            portfolio_markets.append(
                (
                    from_date,
                    thru_date,
                    identifier,
                    portfolio_weight,
                    _simple_return(portfolio_log),
                    0.0,
                )
            )
            benchmark_markets.append(
                (
                    from_date,
                    thru_date,
                    identifier,
                    benchmark_weight,
                    _simple_return(benchmark_log),
                    0.0,
                )
            )

    portfolio_currencies: list[tuple[object, ...]] = []
    benchmark_currencies: list[tuple[object, ...]] = []
    for from_date, thru_date, rows in _CURRENCY_PERIODS[:period_count]:
        for identifier, portfolio_weight, portfolio_log, benchmark_weight, benchmark_log in rows:
            portfolio_currencies.append(
                (
                    from_date,
                    thru_date,
                    identifier,
                    portfolio_weight,
                    _simple_return(portfolio_log),
                )
            )
            benchmark_currencies.append(
                (
                    from_date,
                    thru_date,
                    identifier,
                    benchmark_weight,
                    _simple_return(benchmark_log),
                )
            )
    return (
        pd.DataFrame(portfolio_markets, columns=CURRENCY_MARKET_INPUT_COLUMNS),
        pd.DataFrame(benchmark_markets, columns=CURRENCY_MARKET_INPUT_COLUMNS),
        pd.DataFrame(portfolio_currencies, columns=CURRENCY_EXPOSURE_INPUT_COLUMNS),
        pd.DataFrame(benchmark_currencies, columns=CURRENCY_EXPOSURE_INPUT_COLUMNS),
    )


def _expected_cumulative(period_count: int) -> pd.DataFrame:
    """Return literal cumulative prefixes for the independent three-period case."""
    dates = _MARKET_PERIODS[:period_count]
    expected = pd.DataFrame(
        _CUMULATIVE_VALUES[:period_count],
        columns=CURRENCY_ROLLUP_CUMULATIVE_COLUMNS[2:],
    )
    expected.insert(
        0,
        "thru_date",
        pd.Series([row[1] for row in dates], dtype="datetime64[ns]"),
    )
    expected.insert(
        0,
        "from_date",
        pd.Series([dates[0][0]] * period_count, dtype="datetime64[ns]"),
    )
    return expected


def _expected_overall(
    period_count: int,
    *,
    currency: bool,
) -> pd.DataFrame:
    """Return one literal market or currency full-horizon expected frame."""
    values = (
        _CURRENCY_OVERALL_VALUES[period_count]
        if currency
        else _MARKET_OVERALL_VALUES[period_count]
    )
    columns = (
        CURRENCY_ROLLUP_CURRENCY_OVERALL_COLUMNS
        if currency
        else CURRENCY_ROLLUP_MARKET_OVERALL_COLUMNS
    )
    identifier_column = "currency_identifier" if currency else "market_identifier"
    expected = pd.DataFrame(values, columns=columns[2:])
    expected[identifier_column] = expected[identifier_column].astype("string[python]")
    expected.insert(
        0,
        "thru_date",
        pd.Series(
            [_MARKET_PERIODS[period_count - 1][1]] * len(expected),
            dtype="datetime64[ns]",
        ),
    )
    expected.insert(
        0,
        "from_date",
        pd.Series(
            [_MARKET_PERIODS[0][0]] * len(expected),
            dtype="datetime64[ns]",
        ),
    )
    return cast(pd.DataFrame, expected.loc[:, list(columns)])


@pytest.mark.parametrize("period_count", (1, 2, 3))
def test_log_effect_rollup_matches_every_hand_calculated_value(
    period_count: int,
) -> None:
    """One-, two-, and three-period roll-ups must match literal expected frames.

    In period one, market allocation is ``-0.1% + -0.1% = -0.2%`` and market
    selection is ``0.6% - 1.2% = -0.6%``, giving active market ``-0.8%``.
    Currency allocation is ``0.1% + 0.1% = 0.2%`` and hedge selection is
    ``0.7% - 0.3% = 0.4%``, giving active currency ``0.6%``. The complete horizon
    sums to market active ``1.7%``, currency active ``0.6%``, and total active
    ``2.3%``. Every intermediate value below was calculated from those same literal
    period formulas without using the roll-up implementation.
    """
    source = calculate_currency_attribution(
        *_source_inputs(period_count),
        base_currency="USD",
    )
    result = roll_up_currency_attribution(source)

    pd.testing.assert_frame_equal(
        result.market_overall_detail,
        _expected_overall(period_count, currency=False),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    pd.testing.assert_frame_equal(
        result.currency_overall_detail,
        _expected_overall(period_count, currency=True),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    pd.testing.assert_frame_equal(
        result.cumulative,
        _expected_cumulative(period_count),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def test_calculated_frames_are_canonical_owned_and_leave_source_unchanged() -> None:
    """Step 4 outputs must be distinct canonical frames with no caller mutation."""
    source = calculate_currency_attribution(*_source_inputs(3), base_currency="USD")
    source_names = (
        "market_detail",
        "currency_detail",
        "period_summary",
        "reconciliation",
    )
    before = {
        name: cast(pd.DataFrame, getattr(source, name)).copy(deep=True)
        for name in source_names
    }
    result = roll_up_currency_attribution(source)

    result_frames = {
        "market": result.market_overall_detail,
        "currency": result.currency_overall_detail,
        "cumulative": result.cumulative,
        "reconciliation": result.reconciliation,
    }
    source_frame_ids = {
        id(cast(pd.DataFrame, getattr(source, name))) for name in source_names
    }
    result_frame_ids = {id(frame) for frame in result_frames.values()}
    assert len(source_frame_ids | result_frame_ids) == 8
    assert all(
        isinstance(frame.index, pd.RangeIndex) for frame in result_frames.values()
    )
    for name, expected in before.items():
        pd.testing.assert_frame_equal(
            cast(pd.DataFrame, getattr(source, name)),
            expected,
        )

    result.market_overall_detail.loc[0, "total_log_effect"] = 999.0
    assert 999.0 not in result.currency_overall_detail.to_numpy()
    assert 999.0 not in result.cumulative.to_numpy()
    assert 999.0 not in result.reconciliation.to_numpy()
