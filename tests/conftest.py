"""Shared pytest fixtures for independently exercised public boundaries."""

from collections.abc import Callable
from typing import cast

import pandas as pd
import pytest

from perfattr import CurrencyAttributionResult, calculate_currency_attribution
from perfattr._schemas import (
    CURRENCY_EXPOSURE_INPUT_COLUMNS,
    CURRENCY_MARKET_INPUT_COLUMNS,
)


@pytest.fixture
def currency_source_result() -> CurrencyAttributionResult:
    """Return one valid released currency result for post-calculation tests."""
    portfolio_markets = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "Equity", 1.0, 0.02, 0.002)],
        columns=CURRENCY_MARKET_INPUT_COLUMNS,
    )
    benchmark_markets = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "Equity", 1.0, 0.01, 0.002)],
        columns=CURRENCY_MARKET_INPUT_COLUMNS,
    )
    portfolio_currencies = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "USD", 1.0, 0.002)],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )
    benchmark_currencies = portfolio_currencies.copy(deep=True)
    inputs = (
        portfolio_markets,
        benchmark_markets,
        portfolio_currencies,
        benchmark_currencies,
    )
    return calculate_currency_attribution(
        *inputs,
        base_currency="USD",
    )


@pytest.fixture
def repeat_currency_result() -> Callable[..., CurrencyAttributionResult]:
    """Return a factory that repeats valid independent currency-result periods."""

    def repeat(
        result: CurrencyAttributionResult,
        count: int,
        *,
        gaps: bool = False,
    ) -> CurrencyAttributionResult:
        """Repeat a valid period at new dates, optionally leaving calendar gaps."""
        repeated = CurrencyAttributionResult(
            market_detail=result.market_detail.copy(deep=True),
            currency_detail=result.currency_detail.copy(deep=True),
            period_summary=result.period_summary.copy(deep=True),
            reconciliation=result.reconciliation.copy(deep=True),
            base_currency=result.base_currency,
        )
        month_increment = 2 if gaps else 1
        frame_names = (
            "market_detail",
            "currency_detail",
            "period_summary",
            "reconciliation",
        )
        for name in frame_names:
            source = cast(pd.DataFrame, getattr(repeated, name))
            periods: list[pd.DataFrame] = []
            for index in range(count):
                frame = source.copy(deep=True)
                start = pd.Timestamp("2024-01-01") + pd.DateOffset(
                    months=index * month_increment
                )
                thru = start + pd.offsets.MonthEnd(1)
                frame["from_date"] = pd.Series(
                    start,
                    index=frame.index,
                    dtype="datetime64[ns]",
                )
                frame["thru_date"] = pd.Series(
                    thru,
                    index=frame.index,
                    dtype="datetime64[ns]",
                )
                periods.append(frame)
            setattr(repeated, name, pd.concat(periods, ignore_index=True))
        return repeated

    return repeat
