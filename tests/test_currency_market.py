"""Independent calculation tests for the Roadmap 12 market grid."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from perfattr import AttributionError, calculate_currency_attribution
from perfattr._schemas import (
    CURRENCY_EXPOSURE_INPUT_COLUMNS,
    CURRENCY_MARKET_DETAIL_COLUMNS,
    CURRENCY_MARKET_INPUT_COLUMNS,
)
from perfattr.currency import (
    _MARKET_GRID_SUMMARY_COLUMNS,  # pyright: ignore[reportPrivateUsage]
    _MarketGridResult,  # pyright: ignore[reportPrivateUsage]
    _calculate_market_grid,  # pyright: ignore[reportPrivateUsage]
    _normalize_currency_inputs,  # pyright: ignore[reportPrivateUsage]
)


_CurrencyInputs = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
_RANDOM_MARKETS = tuple(f"Market {index}" for index in range(7))


def _currency_rows(
    starts: pd.DatetimeIndex,
    periods: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Return a neutral currency frame needed only by four-frame normalization."""
    return pd.DataFrame(
        [
            (start, end, "USD", 1.0, 0.0)
            for start, end in zip(starts, periods, strict=True)
        ],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )


def _hand_calculated_inputs() -> _CurrencyInputs:
    """Return a one-period fixture with signed, zero, and ordinary market weights.

    The portfolio weights ``[1.1, -0.1, 0.0]`` sum to one and make the effects of a
    short market and an explicit absent exposure visible. Benchmark weights are
    ``[0.5, 0.3, 0.2]``. Different local cash returns by market ensure that the test
    verifies return premiums rather than attributing raw local asset returns.
    """
    columns = CURRENCY_MARKET_INPUT_COLUMNS
    portfolio = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "C", 0.0, 0.25, 0.002),
            ("2024-01-01", "2024-01-31", "A", 1.1, 0.12, 0.01),
            ("2024-01-01", "2024-01-31", "B", -0.1, 0.03, 0.005),
        ],
        columns=columns,
    )
    benchmark = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "B", 0.3, 0.04, 0.005),
            ("2024-01-01", "2024-01-31", "C", 0.2, 0.05, 0.002),
            ("2024-01-01", "2024-01-31", "A", 0.5, 0.08, 0.01),
        ],
        columns=columns,
    )
    currencies = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "USD", 1.0, 0.0)],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )
    return portfolio, benchmark, currencies, currencies.copy(deep=True)


def _market_grid(inputs: _CurrencyInputs) -> _MarketGridResult:
    """Normalize a four-frame fixture and calculate only its internal market grid."""
    normalized = _normalize_currency_inputs(*inputs, 1e-12)
    return _calculate_market_grid(normalized, 1e-12)


def test_hand_calculated_market_grid_matches_literal_expected_values() -> None:
    """Market allocation and portfolio-weighted selection match hand calculations.

    The literal expectations below were calculated independently from the accepted
    formulas in the specification. For example, market A's benchmark premium is
    ``log(1.08) - log(1.01) = 0.06701071028296024``. The benchmark aggregate premium
    is ``0.053133738935504576``; therefore A allocation is
    ``(1.1 - 0.5) * (0.06701071028296024 - 0.053133738935504576)`` and A selection is
    ``1.1 * (0.10337835445383509 - 0.06701071028296024)``.
    """
    result = _market_grid(_hand_calculated_inputs())
    detail = result.detail.set_index("market_identifier")

    assert tuple(result.detail.columns) == CURRENCY_MARKET_DETAIL_COLUMNS
    assert isinstance(result.detail.index, pd.RangeIndex)
    assert str(result.detail["from_date"].dtype) == "datetime64[ns]"
    assert str(result.detail["thru_date"].dtype) == "datetime64[ns]"
    assert str(result.detail["market_identifier"].dtype) == "string"
    numeric_columns = result.detail.columns.difference(
        ["from_date", "thru_date", "market_identifier"]
    )
    assert all(
        str(result.detail[column].dtype) == "float64" for column in numeric_columns
    )
    assert detail.index.tolist() == ["A", "B", "C"]
    np.testing.assert_allclose(
        detail["portfolio_local_log_return_premium"],
        [0.10337835445383509, 0.02457126073050533, 0.2211455486515367],
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        detail["benchmark_local_log_return_premium"],
        [0.06701071028296024, 0.03423317164224222, 0.04679216150675895],
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        detail["market_allocation_log_effect"],
        [0.0083261828084734, 0.00756022691730494, 0.00126831548574912],
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        detail["security_selection_log_effect"],
        [0.04000440858796234, 0.00096619109117369, 0.0],
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        detail["total_log_effect"],
        [0.04833059139643574, 0.00852641800847863, 0.00126831548574912],
        rtol=0.0,
        atol=1e-15,
    )
    assert detail.loc["C", "security_selection_log_effect"] == 0.0


def test_hand_calculated_market_period_summary_reconciles() -> None:
    """Literal aggregate premiums reconcile to the independently summed effects.

    Portfolio market return ``0.11125906382616807`` minus benchmark market return
    ``0.053133738935504576`` equals both active return and the two effect totals,
    ``0.05812532489066349``.
    """
    summary = _market_grid(_hand_calculated_inputs()).period_summary

    assert tuple(summary.columns) == _MARKET_GRID_SUMMARY_COLUMNS
    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["portfolio_market_log_return"] == pytest.approx(
        0.11125906382616807, abs=1e-15
    )
    assert row["benchmark_market_log_return"] == pytest.approx(
        0.053133738935504576, abs=1e-15
    )
    assert row["active_market_log_return"] == pytest.approx(
        0.05812532489066349, abs=1e-15
    )
    assert row["market_allocation_log_effect"] == pytest.approx(
        0.017154725211527465, abs=1e-15
    )
    assert row["security_selection_log_effect"] == pytest.approx(
        0.04097059967913603, abs=1e-15
    )
    assert row["total_log_effect"] == pytest.approx(
        0.05812532489066349, abs=1e-15
    )


def _signed_weights(random: np.random.Generator, size: int) -> np.ndarray:
    """Construct signed weights with a final one-minus-sum residual."""
    initial = random.uniform(-0.35, 0.55, size - 1)
    return np.append(initial, 1.0 - initial.sum())


def _randomized_period_rows(
    random: np.random.Generator,
    start: pd.Timestamp,
    end: pd.Timestamp,
    identifiers: tuple[str, ...],
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]], float]:
    """Build one random period and its independently weighted active premium."""
    portfolio_weights = _signed_weights(random, len(identifiers))
    benchmark_weights = _signed_weights(random, len(identifiers))
    portfolio_returns = random.uniform(-0.3, 0.4, len(identifiers))
    benchmark_returns = random.uniform(-0.3, 0.4, len(identifiers))
    cash_returns = random.uniform(-0.02, 0.04, len(identifiers))
    portfolio_premiums = np.log1p(portfolio_returns) - np.log1p(cash_returns)
    benchmark_premiums = np.log1p(benchmark_returns) - np.log1p(cash_returns)
    expected_active = float(
        np.dot(portfolio_weights, portfolio_premiums)
        - np.dot(benchmark_weights, benchmark_premiums)
    )
    portfolio_rows: list[tuple[object, ...]] = [
        (start, end, identifier, weight, asset_return, cash_return)
        for identifier, weight, asset_return, cash_return in zip(
            identifiers,
            portfolio_weights,
            portfolio_returns,
            cash_returns,
            strict=True,
        )
    ]
    benchmark_rows: list[tuple[object, ...]] = [
        (start, end, identifier, weight, asset_return, cash_return)
        for identifier, weight, asset_return, cash_return in zip(
            identifiers,
            benchmark_weights,
            benchmark_returns,
            cash_returns,
            strict=True,
        )
    ]
    return portfolio_rows, benchmark_rows, expected_active


def _randomized_market_inputs() -> tuple[_CurrencyInputs, np.ndarray]:
    """Build many market periods and independently calculate their active premiums."""
    random = np.random.default_rng(20260908)
    periods = pd.date_range("2022-01-31", periods=36, freq="ME")
    starts = periods.to_period("M").start_time
    portfolio_rows = []
    benchmark_rows = []
    expected_active = []
    for start, end in zip(starts, periods, strict=True):
        period_portfolio, period_benchmark, period_active = _randomized_period_rows(
            random, start, end, _RANDOM_MARKETS
        )
        portfolio_rows.extend(period_portfolio)
        benchmark_rows.extend(period_benchmark)
        expected_active.append(period_active)
    portfolio = pd.DataFrame(
        portfolio_rows, columns=CURRENCY_MARKET_INPUT_COLUMNS
    ).sample(frac=1.0, random_state=41)
    benchmark = pd.DataFrame(
        benchmark_rows, columns=CURRENCY_MARKET_INPUT_COLUMNS
    ).sample(frac=1.0, random_state=43)
    currencies = _currency_rows(starts, periods)
    inputs: _CurrencyInputs = (
        portfolio,
        benchmark,
        currencies,
        currencies.copy(deep=True),
    )
    return inputs, np.asarray(expected_active, dtype=np.float64)


def test_randomized_market_grid_reconciles_to_independent_active_premiums() -> None:
    """Every randomized period reconciles to direct weighted log-return premiums."""
    inputs, expected_active = _randomized_market_inputs()

    result = _market_grid(inputs)

    np.testing.assert_allclose(
        result.period_summary["active_market_log_return"],
        expected_active,
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        result.period_summary["total_log_effect"],
        expected_active,
        rtol=1e-12,
        atol=1e-12,
    )


def test_nonfinite_market_calculation_is_rejected_without_a_partial_result() -> None:
    """Finite inputs that overflow a weighted log effect must fail explicitly."""
    inputs = _hand_calculated_inputs()
    inputs[0].loc[:, "market_weight"] = [1e308, -1e308, 1.0]
    inputs[1].loc[:, "market_weight"] = [1e308, -1e308, 1.0]
    inputs[0].loc[0, "local_asset_return"] = float.fromhex(
        "0x1.fffffffffffffp+1023"
    )

    with pytest.raises(AttributionError, match="produced a non-finite value"):
        calculate_currency_attribution(*inputs, base_currency="USD")


def test_completed_market_grid_is_preserved_in_the_public_result() -> None:
    """The public result should retain the independently tested market grid exactly."""
    inputs = _hand_calculated_inputs()
    expected = _market_grid(inputs)

    result = calculate_currency_attribution(*inputs, base_currency="USD")

    pd.testing.assert_frame_equal(result.market_detail, expected.detail)
