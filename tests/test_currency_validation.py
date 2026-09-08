"""Validation tests for prepared four-frame currency-attribution inputs."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import numpy as np
import pandas as pd
import pytest

from perfattr import AttributionError, calculate_currency_attribution
from perfattr._schemas import (
    CURRENCY_EXPOSURE_INPUT_COLUMNS,
    CURRENCY_MARKET_INPUT_COLUMNS,
)
from perfattr.currency import (
    _NormalizedCurrencyInputs,  # pyright: ignore[reportPrivateUsage]
    _normalize_currency_inputs,  # pyright: ignore[reportPrivateUsage]
)


_CurrencyInputs = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
def _market_rows(*, portfolio: bool) -> pd.DataFrame:
    """Return two periods of intentionally unsorted, padded market facts."""
    asset_returns = (0.025, 0.012, 0.018, 0.009) if portfolio else (
        0.020,
        0.010,
        0.015,
        0.008,
    )
    return pd.DataFrame(
        [
            ("2024-02-01 12:00", "2024-02-29 18:00", " Bonds ", -0.2,
             asset_returns[0], 0.002),
            ("2024-01-01 09:00", "2024-01-31 15:00", "Equity", 1.2,
             asset_returns[1], 0.001),
            ("2024-02-01 12:00", "2024-02-29 18:00", "Equity", 1.2,
             asset_returns[2], 0.002),
            ("2024-01-01 09:00", "2024-01-31 15:00", " Bonds ", -0.2,
             asset_returns[3], 0.001),
        ],
        columns=CURRENCY_MARKET_INPUT_COLUMNS,
    )


def _currency_rows(*, portfolio: bool) -> pd.DataFrame:
    """Return two periods of intentionally unsorted, signed currency exposures."""
    weights = (1.25, -0.25) if portfolio else (1.1, -0.1)
    return pd.DataFrame(
        [
            ("2024-02-01", "2024-02-29", " EUR ", weights[1], 0.003),
            ("2024-01-01", "2024-01-31", "USD", weights[0], 0.001),
            ("2024-02-01", "2024-02-29", "USD", weights[0], 0.002),
            ("2024-01-01", "2024-01-31", " EUR ", weights[1], 0.002),
        ],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )


def _valid_inputs() -> _CurrencyInputs:
    """Return valid market and currency inputs in public argument order."""
    return (
        _market_rows(portfolio=True),
        _market_rows(portfolio=False),
        _currency_rows(portfolio=True),
        _currency_rows(portfolio=False),
    )


def _normalize(inputs: _CurrencyInputs, tolerance: float = 1e-12) -> _NormalizedCurrencyInputs:
    """Call the internal Step 3 boundary without obscuring input order."""
    return _normalize_currency_inputs(*inputs, tolerance)


def _public_call(inputs: _CurrencyInputs) -> None:
    """Call the public boundary while discarding its complete valid result."""
    calculate_currency_attribution(*inputs, base_currency="USD")


def _replace_value(
    inputs: _CurrencyInputs,
    frame_index: int,
    column: str,
    value: object,
) -> None:
    """Replace the first value in one caller-owned test frame."""
    frame = inputs[frame_index]
    if column in {"from_date", "thru_date"} and isinstance(
        value, bool | int | float
    ):
        frame[column] = pd.Series([value] * len(frame), index=frame.index)
        return
    frame[column] = pd.Series(
        [value, *frame[column].iloc[1:].tolist()],
        index=frame.index,
    )


def test_valid_inputs_normalize_without_mutating_callers() -> None:
    """Normalization should own, type, trim, and deterministically order its frames."""
    inputs = _valid_inputs()
    before = tuple(frame.copy(deep=True) for frame in inputs)

    normalized = _normalize(inputs)

    for original, expected in zip(inputs, before, strict=True):
        pd.testing.assert_frame_equal(original, expected)
    for frame in (
        normalized.portfolio_markets,
        normalized.benchmark_markets,
        normalized.portfolio_currencies,
        normalized.benchmark_currencies,
    ):
        assert isinstance(frame.index, pd.RangeIndex)
        assert str(frame["from_date"].dtype) == "datetime64[ns]"
        assert str(frame["thru_date"].dtype) == "datetime64[ns]"
        identifier = next(
            str(column) for column in frame if str(column).endswith("identifier")
        )
        assert str(frame[identifier].dtype) == "string"
        assert frame[identifier].tolist() == ["Bonds", "Equity"] * 2 or frame[
            identifier
        ].tolist() == ["EUR", "USD"] * 2
        numeric_columns = frame.columns.difference(
            ["from_date", "thru_date", identifier]
        )
        assert all(str(frame[column].dtype) == "float64" for column in numeric_columns)


@pytest.mark.parametrize(
    ("frame_index", "mutation", "message"),
    (
        (0, lambda inputs: inputs[0].drop(columns="local_cash_return", inplace=True),
         "missing columns: local_cash_return"),
        (1, lambda inputs: inputs[1].assign(quantity_of_days=31),
         "unexpected columns: quantity_of_days"),
        (2, lambda inputs: inputs[2].rename(columns={"currency_weight": "unexpected"}),
         "missing columns: currency_weight; unexpected columns: unexpected"),
    ),
)
def test_exact_schemas_reject_missing_and_extra_columns(
    frame_index: int,
    mutation: Callable[[_CurrencyInputs], object],
    message: str,
) -> None:
    """Each side-specific frame must contain only its exact governed columns."""
    inputs = _valid_inputs()
    changed = mutation(inputs)
    if isinstance(changed, pd.DataFrame):
        mutable = list(inputs)
        mutable[frame_index] = changed
        inputs = cast(_CurrencyInputs, tuple(mutable))

    with pytest.raises(AttributionError, match=message):
        _public_call(inputs)


def test_duplicate_column_labels_and_empty_frames_are_rejected() -> None:
    """Ambiguous labels and frames with no period facts have no valid meaning."""
    inputs = _valid_inputs()
    duplicate = inputs[0].copy()
    duplicate.columns = [*duplicate.columns[:-1], "local_asset_return"]
    with pytest.raises(AttributionError, match="duplicate column labels"):
        _public_call((duplicate, *inputs[1:]))

    empty = inputs[0].iloc[0:0]
    with pytest.raises(AttributionError, match="portfolio_markets input must not be empty"):
        _public_call((empty, *inputs[1:]))


@pytest.mark.parametrize(
    ("frame_index", "column", "value", "message"),
    (
        (0, "from_date", None, "contains null values"),
        (0, "from_date", 20240101, "must contain dates"),
        (0, "thru_date", "not-a-date", "contains an invalid date"),
        (0, "from_date", "2024-03-01", "from_date after its thru_date"),
        (0, "market_identifier", None, "must contain non-null strings"),
        (0, "market_identifier", 123, "must contain non-null strings"),
        (0, "market_identifier", "   ", "contains an empty string"),
        (0, "market_weight", True, "must contain numbers"),
        (0, "market_weight", None, "contains null values"),
        (0, "market_weight", np.inf, "only finite values"),
        (0, "local_asset_return", "0.01", "must contain numbers"),
        (0, "local_asset_return", None, "contains null values"),
        (0, "local_asset_return", -1.0, "must be greater than -1.0"),
        (0, "local_cash_return", -np.inf, "only finite values"),
        (2, "currency_weight", False, "must contain numbers"),
        (2, "base_currency_cash_return", -1.1, "must be greater than -1.0"),
    ),
)
def test_invalid_scalar_content_fails_before_calculation(
    frame_index: int,
    column: str,
    value: object,
    message: str,
) -> None:
    """Dates, identities, weights, and simple returns retain strict scalar domains."""
    inputs = _valid_inputs()
    _replace_value(inputs, frame_index, column, value)

    with pytest.raises(AttributionError, match=message):
        _public_call(inputs)


def test_timezone_aware_dates_are_rejected() -> None:
    """Timezone-aware period boundaries cannot enter the portable date contract."""
    inputs = _valid_inputs()
    inputs[0]["from_date"] = pd.to_datetime(inputs[0]["from_date"], utc=True)

    with pytest.raises(AttributionError, match="must be timezone-naive"):
        _public_call(inputs)


def test_duplicate_and_overlapping_period_keys_are_rejected() -> None:
    """Normalized keys must be unique and inclusive reporting periods disjoint."""
    inputs = _valid_inputs()
    duplicate = pd.concat([inputs[0], inputs[0].iloc[[0]]], ignore_index=True)
    with pytest.raises(AttributionError, match="duplicate period and identifier key"):
        _public_call((duplicate, *inputs[1:]))

    overlap = inputs[0].copy()
    overlap.loc[overlap["from_date"].str.startswith("2024-02"), "from_date"] = (
        "2024-01-31"
    )
    with pytest.raises(AttributionError, match="overlapping reporting periods"):
        _public_call((overlap, *inputs[1:]))


def test_identifiers_must_remain_unique_after_whitespace_normalization() -> None:
    """Trimming cannot collapse two economic rows into one ambiguous identity."""
    inputs = _valid_inputs()
    inputs[0].loc[0, "market_identifier"] = " Equity "

    with pytest.raises(AttributionError, match="duplicate period and identifier key"):
        _public_call(inputs)


def test_one_thru_date_cannot_name_multiple_periods() -> None:
    """A thru date is the stable period identity and maps to one inclusive range."""
    inputs = _valid_inputs()
    inputs[0].loc[0, "from_date"] = "2024-02-02"

    with pytest.raises(AttributionError, match="maps one thru_date to more than one period"):
        _public_call(inputs)


@pytest.mark.parametrize("frame_index", range(4))
def test_each_frames_weights_must_sum_to_one(frame_index: int) -> None:
    """No market or net-currency side may be silently renormalized."""
    inputs = _valid_inputs()
    weight_column = "market_weight" if frame_index < 2 else "currency_weight"
    current_weight = cast(float, inputs[frame_index].loc[0, weight_column])
    inputs[frame_index].loc[0, weight_column] = current_weight + 0.01

    with pytest.raises(AttributionError, match="weights must sum to 1.0 within tolerance"):
        _public_call(inputs)


@pytest.mark.parametrize("frame_index", range(4))
def test_all_four_frames_must_have_identical_period_sets(frame_index: int) -> None:
    """Market and currency components must describe the same reporting periods."""
    inputs = _valid_inputs()
    changed = inputs[frame_index].loc[
        ~inputs[frame_index]["thru_date"].astype(str).str.startswith("2024-02")
    ]
    mutable = list(inputs)
    mutable[frame_index] = changed
    inputs = cast(_CurrencyInputs, tuple(mutable))

    with pytest.raises(AttributionError, match="periods must match exactly"):
        _public_call(inputs)


@pytest.mark.parametrize(
    ("frame_index", "identifier", "message"),
    (
        (1, "Credit", "market identifier universes must match exactly"),
        (3, "JPY", "currency identifier universes must match exactly"),
    ),
)
def test_portfolio_and_benchmark_universes_must_match(
    frame_index: int,
    identifier: str,
    message: str,
) -> None:
    """Missing exposure is expressed by an explicit zero row, never an absent row."""
    inputs = _valid_inputs()
    identifier_column = "market_identifier" if frame_index == 1 else "currency_identifier"
    inputs[frame_index].loc[0, identifier_column] = identifier

    with pytest.raises(AttributionError, match=message):
        _public_call(inputs)


def test_local_cash_reference_must_match_exactly_between_market_sides() -> None:
    """The shared counterfactual is neither averaged nor compared with a tolerance."""
    inputs = _valid_inputs()
    current_return = cast(float, inputs[1].loc[0, "local_cash_return"])
    inputs[1].loc[0, "local_cash_return"] = current_return + 1e-15

    with pytest.raises(AttributionError, match="local_cash_return must match exactly"):
        _public_call(inputs)


def test_zero_weights_and_large_finite_returns_remain_valid_inputs() -> None:
    """The contract has no positive return ceiling and treats zero as an exposure."""
    inputs = _valid_inputs()
    for frame_index in (0, 1):
        inputs[frame_index].loc[0, "market_weight"] = 0.0
        inputs[frame_index].loc[2, "market_weight"] = 1.0
    for frame_index in (2, 3):
        inputs[frame_index].loc[0, "currency_weight"] = 0.0
        inputs[frame_index].loc[2, "currency_weight"] = 1.0
    inputs[0].loc[0, "local_asset_return"] = 25.0
    inputs[2].loc[0, "base_currency_cash_return"] = 10.0

    _public_call(inputs)


def _random_exposures(random: np.random.Generator, count: int) -> np.ndarray:
    """Return signed weights whose independently constructed sum is exactly one."""
    values = random.uniform(-0.45, 0.8, count - 1)
    return np.append(values, 1.0 - values.sum())


def _randomized_market_frames(
    random: np.random.Generator,
    starts: pd.DatetimeIndex,
    periods: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build shuffled portfolio and benchmark market frames with common cash."""
    markets = ("Bonds", "Equity", "Real Estate", "Commodities")
    market_frames: list[pd.DataFrame] = []
    common_cash = random.uniform(-0.005, 0.01, (len(periods), len(markets)))
    for side in range(2):
        rows = []
        for period_index, (start, end) in enumerate(zip(starts, periods, strict=True)):
            weights = _random_exposures(random, len(markets))
            local_returns = random.uniform(-0.2, 0.25, len(markets))
            rows.extend(
                (start, end, market, weight, local_return,
                 common_cash[period_index, market_index])
                for market_index, (market, weight, local_return) in enumerate(
                    zip(markets, weights, local_returns, strict=True)
                )
            )
        market_frames.append(
            pd.DataFrame(rows, columns=CURRENCY_MARKET_INPUT_COLUMNS).sample(
                frac=1.0, random_state=17 + side
            )
        )
    return market_frames[0], market_frames[1]


def _randomized_currency_frames(
    random: np.random.Generator,
    starts: pd.DatetimeIndex,
    periods: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build shuffled portfolio and benchmark net-currency exposure frames."""
    currencies = ("EUR", "GBP", "JPY", "USD")
    currency_frames: list[pd.DataFrame] = []
    for side in range(2):
        rows = []
        for start, end in zip(starts, periods, strict=True):
            weights = _random_exposures(random, len(currencies))
            cash_returns = random.uniform(-0.05, 0.08, len(currencies))
            rows.extend(
                (start, end, currency, weight, cash_return)
                for currency, weight, cash_return in zip(
                    currencies, weights, cash_returns, strict=True
                )
            )
        currency_frames.append(
            pd.DataFrame(rows, columns=CURRENCY_EXPOSURE_INPUT_COLUMNS).sample(
                frac=1.0, random_state=27 + side
            )
        )
    return currency_frames[0], currency_frames[1]


def test_randomized_valid_inputs_preserve_step_three_invariants() -> None:
    """Random signed exposures should normalize without producing a partial result.

    The generator independently forces each side's final weight to the one-minus-sum
    residual. This exercises signed weights and values above one without testing any
    market or currency attribution formulas or deriving expectations from output.
    """
    random = np.random.default_rng(20260908)
    periods = pd.date_range("2023-01-31", periods=24, freq="ME")
    starts = periods.to_period("M").start_time
    portfolio_markets, benchmark_markets = _randomized_market_frames(
        random, starts, periods
    )
    portfolio_currencies, benchmark_currencies = _randomized_currency_frames(
        random, starts, periods
    )

    inputs: _CurrencyInputs = (
        portfolio_markets,
        benchmark_markets,
        portfolio_currencies,
        benchmark_currencies,
    )
    normalized = _normalize(inputs, tolerance=1e-12)

    for frame, weight_column in (
        (normalized.portfolio_markets, "market_weight"),
        (normalized.benchmark_markets, "market_weight"),
        (normalized.portfolio_currencies, "currency_weight"),
        (normalized.benchmark_currencies, "currency_weight"),
    ):
        totals = frame.groupby(["from_date", "thru_date"])[weight_column].sum()
        np.testing.assert_allclose(totals, 1.0, rtol=1e-12, atol=1e-12)
        assert frame.equals(
            frame.sort_values(
                ["thru_date", "from_date", frame.columns[2]], kind="stable"
            ).reset_index(drop=True)
        )

    _public_call(inputs)
