"""Independent currency-grid and complete-result calculation tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from perfattr import AttributionError, calculate_currency_attribution
from perfattr._schemas import (
    CURRENCY_DETAIL_COLUMNS,
    CURRENCY_EXPOSURE_INPUT_COLUMNS,
    CURRENCY_MARKET_DETAIL_COLUMNS,
    CURRENCY_MARKET_INPUT_COLUMNS,
    CURRENCY_PERIOD_SUMMARY_COLUMNS,
    CURRENCY_RECONCILIATION_COLUMNS,
)


_CurrencyInputs = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
_RANDOM_CURRENCIES = tuple(f"Currency {index}" for index in range(6))


def _complete_hand_fixture() -> _CurrencyInputs:
    """Return an original one-period fixture with all four channels nonzero.

    The market side uses two distinct local cash references. The currency side contains
    an overweight EUR exposure, a short JPY exposure, and an unchanged USD exposure.
    EUR uses the passive instrument return and therefore has zero hedge selection. USD
    changes instrument return despite zero active exposure, isolating portfolio-weighted
    hedge selection. The explicit zero-weight GBP row confirms that absent economic
    exposure remains a real aligned row.
    """
    portfolio_markets = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "B", 0.4, 0.03, 0.005),
            ("2024-01-01", "2024-01-31", "A", 0.6, 0.12, 0.01),
        ],
        columns=CURRENCY_MARKET_INPUT_COLUMNS,
    )
    benchmark_markets = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "A", 0.5, 0.08, 0.01),
            ("2024-01-01", "2024-01-31", "B", 0.5, 0.05, 0.005),
        ],
        columns=CURRENCY_MARKET_INPUT_COLUMNS,
    )
    portfolio_currencies = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "USD", 0.5, 0.03),
            ("2024-01-01", "2024-01-31", "JPY", -0.7, -0.01),
            ("2024-01-01", "2024-01-31", "GBP", 0.0, 0.0),
            ("2024-01-01", "2024-01-31", "EUR", 1.2, 0.04),
        ],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )
    benchmark_currencies = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "GBP", 0.0, 0.0),
            ("2024-01-01", "2024-01-31", "EUR", 0.3, 0.04),
            ("2024-01-01", "2024-01-31", "USD", 0.5, 0.01),
            ("2024-01-01", "2024-01-31", "JPY", 0.2, -0.02),
        ],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )
    return (
        portfolio_markets,
        benchmark_markets,
        portfolio_currencies,
        benchmark_currencies,
    )


def test_hand_calculated_currency_grid_matches_literal_expected_values() -> None:
    """Currency allocation and hedge selection match independent hand calculations.

    For EUR, the benchmark aggregate currency log return is
    ``0.012700837909064538``. Allocation is therefore
    ``(1.2 - 0.3) * (log(1.04) - 0.012700837909064538)``. Its actual and passive
    instrument returns are equal, so hedge selection is exactly zero. The remaining
    literal values apply the same accepted equations independently of production code.
    """
    result = calculate_currency_attribution(
        *_complete_hand_fixture(),
        base_currency="USD",
    )
    detail = result.currency_detail.set_index("currency_identifier")

    assert detail.index.tolist() == ["EUR", "GBP", "JPY", "USD"]
    np.testing.assert_allclose(
        detail["portfolio_base_currency_cash_log_return"],
        [0.03922071315328129, 0.0, -0.01005033585350144, 0.0295588022415444],
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        detail["benchmark_base_currency_cash_log_return"],
        [0.03922071315328129, 0.0, -0.02020270731751945, 0.00995033085316808],
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        detail["currency_allocation_log_effect"],
        [0.02386788771979508, 0.0, 0.02961319070392559, 0.0],
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        detail["hedge_selection_log_effect"],
        [0.0, 0.0, -0.0071066600248126, 0.00980423569418816],
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        detail["total_log_effect"],
        [0.02386788771979508, 0.0, 0.02250653067911298, 0.00980423569418816],
        rtol=0.0,
        atol=1e-15,
    )
    assert detail.loc["EUR", "hedge_selection_log_effect"] == 0.0
    assert detail.loc["USD", "active_currency_weight"] == 0.0
    assert detail.loc["USD", "hedge_selection_log_effect"] != 0.0


def test_complete_hand_calculation_reconciles_all_four_channels() -> None:
    """Literal market, currency, and combined results satisfy all three identities.

    The independently calculated market active log return is
    ``0.01644885049382659`` and currency active log return is
    ``0.05617865409309622``. Their sum, ``0.07262750458692281``, equals both the
    modeled active total and all four effect channels.
    """
    result = calculate_currency_attribution(
        *_complete_hand_fixture(),
        base_currency="usd",
    )
    summary = result.period_summary.iloc[0]

    assert result.base_currency == "usd"
    assert summary["portfolio_currency_log_return"] == pytest.approx(
        0.06887949200216076, abs=1e-15
    )
    assert summary["benchmark_currency_log_return"] == pytest.approx(
        0.012700837909064538, abs=1e-15
    )
    assert summary["active_currency_log_return"] == pytest.approx(
        0.05617865409309622, abs=1e-15
    )
    assert summary["portfolio_total_log_return"] == pytest.approx(
        0.14073500896666394, abs=1e-15
    )
    assert summary["benchmark_total_log_return"] == pytest.approx(
        0.06810750437974113, abs=1e-15
    )
    assert summary["active_total_log_return"] == pytest.approx(
        0.07262750458692281, abs=1e-15
    )
    effect_total = sum(
        float(summary[column])
        for column in (
            "market_allocation_log_effect",
            "security_selection_log_effect",
            "currency_allocation_log_effect",
            "hedge_selection_log_effect",
        )
    )
    assert effect_total == pytest.approx(0.07262750458692281, abs=1e-15)
    assert summary["total_log_effect"] == pytest.approx(effect_total, abs=1e-15)
    assert result.reconciliation[
        ["market_reconciled", "currency_reconciled", "total_reconciled"]
    ].to_numpy(dtype=np.bool_).all()


def test_complete_result_frames_have_canonical_schemas_dtypes_and_ownership() -> None:
    """The released result contract requires four distinct deterministic frames."""
    result = calculate_currency_attribution(
        *_complete_hand_fixture(),
        base_currency="USD",
    )
    expected_schemas = (
        CURRENCY_MARKET_DETAIL_COLUMNS,
        CURRENCY_DETAIL_COLUMNS,
        CURRENCY_PERIOD_SUMMARY_COLUMNS,
        CURRENCY_RECONCILIATION_COLUMNS,
    )
    frames = (
        result.market_detail,
        result.currency_detail,
        result.period_summary,
        result.reconciliation,
    )

    assert len({id(frame) for frame in frames}) == 4
    for frame, columns in zip(frames, expected_schemas, strict=True):
        assert tuple(frame.columns) == columns
        assert isinstance(frame.index, pd.RangeIndex)
        assert str(frame["from_date"].dtype) == "datetime64[ns]"
        assert str(frame["thru_date"].dtype) == "datetime64[ns]"
    assert str(result.market_detail["market_identifier"].dtype) == "string"
    assert str(result.currency_detail["currency_identifier"].dtype) == "string"
    identifier_columns = {"market_identifier", "currency_identifier"}
    flag_columns = {"market_reconciled", "currency_reconciled", "total_reconciled"}
    for frame in frames:
        numeric_columns = frame.columns.difference(
            ["from_date", "thru_date", *identifier_columns, *flag_columns]
        )
        assert all(str(frame[column].dtype) == "float64" for column in numeric_columns)
    for flag in ("market_reconciled", "currency_reconciled", "total_reconciled"):
        assert str(result.reconciliation[flag].dtype) == "bool"


def _hedging_scenario_inputs(portfolio_foreign_weight: float) -> _CurrencyInputs:
    """Represent one unhedged, partially hedged, fully hedged, or cross-hedged case."""
    portfolio_markets = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "Foreign", 0.6, 0.0, 0.0),
            ("2024-01-01", "2024-01-31", "Base", 0.4, 0.0, 0.0),
        ],
        columns=CURRENCY_MARKET_INPUT_COLUMNS,
    )
    benchmark_markets = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "Foreign", 0.4, 0.0, 0.0),
            ("2024-01-01", "2024-01-31", "Base", 0.6, 0.0, 0.0),
        ],
        columns=CURRENCY_MARKET_INPUT_COLUMNS,
    )
    portfolio_currencies = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "EUR", portfolio_foreign_weight, 0.05),
            ("2024-01-01", "2024-01-31", "USD", 1.0 - portfolio_foreign_weight, 0.01),
        ],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )
    benchmark_currencies = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "EUR", 0.4, 0.05),
            ("2024-01-01", "2024-01-31", "USD", 0.6, 0.01),
        ],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )
    return (
        portfolio_markets,
        benchmark_markets,
        portfolio_currencies,
        benchmark_currencies,
    )


@pytest.mark.parametrize(
    ("foreign_weight", "expected_active"),
    (
        (0.6, 0.007767966663252777),
        (0.3, -0.003883983331626397),
        (0.0, -0.015535933326505573),
        (-0.2, -0.023303899989758358),
    ),
    ids=("unhedged", "partially-hedged", "fully-hedged", "cross-hedged"),
)
def test_net_exposures_represent_common_hedging_configurations(
    foreign_weight: float,
    expected_active: float,
) -> None:
    """Hedging labels are host interpretations of the supplied net exposures.

    The market portfolio has 60 percent foreign exposure. Leaving EUR at 60 percent is
    unhedged; reducing it to 30 percent is partially hedged; reducing it to zero is
    fully hedged; and a negative 20 percent EUR exposure is cross-hedged. The core uses
    only these net weights and does not infer or price a hedge transaction.
    """
    result = calculate_currency_attribution(
        *_hedging_scenario_inputs(foreign_weight),
        base_currency="USD",
    )

    summary = result.period_summary.iloc[0]
    assert summary["active_currency_log_return"] == pytest.approx(
        expected_active, abs=1e-15
    )
    assert summary["hedge_selection_log_effect"] == 0.0
    assert summary["currency_allocation_log_effect"] == pytest.approx(
        expected_active, abs=1e-15
    )


def test_primary_monograph_subset_recovers_source_log_return_basis() -> None:
    """A three-country Table 21 subset recovers its reported cash log returns.

    Karnosky and Singer (1994), Table 21 on printed page 66, reports passive and active
    currency weights and U.S.-dollar cash returns for Australia, Japan, and the United
    States. Because the table uses continuously compounded percent returns, this
    fixture converts ``[-3.25%, 5.00%, 4.09%]`` to ordinary inputs with ``expm1``.
    The selected weights are divided by their respective three-country totals so each
    side satisfies this package's unit-sum contract; no reported return is altered.
    Actual and passive cash returns are set equal because Table 21 reports one return
    series, so the independently expected hedge-selection effect is zero.
    """
    countries = ("Australia", "Japan", "United States")
    passive = np.asarray([0.58, 9.83, 75.00], dtype=np.float64)
    active = np.asarray([0.10, 5.05, 84.19], dtype=np.float64)
    source_log_returns = np.asarray([-0.0325, 0.05, 0.0409], dtype=np.float64)
    simple_returns = np.expm1(source_log_returns)
    date_values = ("1992-01-01", "1992-12-31")
    market = pd.DataFrame(
        [(*date_values, "Global", 1.0, 0.0, 0.0)],
        columns=CURRENCY_MARKET_INPUT_COLUMNS,
    )
    portfolio_currencies = pd.DataFrame(
        [
            (*date_values, country, weight, cash_return)
            for country, weight, cash_return in zip(
                countries, active / active.sum(), simple_returns, strict=True
            )
        ],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )
    benchmark_currencies = pd.DataFrame(
        [
            (*date_values, country, weight, cash_return)
            for country, weight, cash_return in zip(
                countries, passive / passive.sum(), simple_returns, strict=True
            )
        ],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )

    result = calculate_currency_attribution(
        market,
        market.copy(deep=True),
        portfolio_currencies,
        benchmark_currencies,
        base_currency="USD",
    )

    np.testing.assert_allclose(
        result.currency_detail["portfolio_base_currency_cash_log_return"],
        source_log_returns,
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        result.currency_detail["benchmark_base_currency_cash_log_return"],
        source_log_returns,
        rtol=0.0,
        atol=1e-15,
    )
    assert result.period_summary.loc[0, "hedge_selection_log_effect"] == 0.0


def _random_net_exposures(random: np.random.Generator) -> np.ndarray:
    """Return signed currency exposures with a one-minus-sum residual."""
    exposures = random.uniform(-0.5, 0.75, len(_RANDOM_CURRENCIES))
    exposures[-1] += 1.0 - exposures.sum()
    return exposures


def _random_currency_period(
    random: np.random.Generator,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]], float]:
    """Build one random currency period and its direct active log return."""
    portfolio_weights = _random_net_exposures(random)
    benchmark_weights = _random_net_exposures(random)
    portfolio_returns = random.uniform(-0.25, 0.3, len(_RANDOM_CURRENCIES))
    benchmark_returns = random.uniform(-0.25, 0.3, len(_RANDOM_CURRENCIES))
    expected_active = float(
        np.dot(portfolio_weights, np.log1p(portfolio_returns))
        - np.dot(benchmark_weights, np.log1p(benchmark_returns))
    )
    portfolio_rows: list[tuple[object, ...]] = [
        (start, end, identifier, weight, cash_return)
        for identifier, weight, cash_return in zip(
            _RANDOM_CURRENCIES,
            portfolio_weights,
            portfolio_returns,
            strict=True,
        )
    ]
    benchmark_rows: list[tuple[object, ...]] = [
        (start, end, identifier, weight, cash_return)
        for identifier, weight, cash_return in zip(
            _RANDOM_CURRENCIES,
            benchmark_weights,
            benchmark_returns,
            strict=True,
        )
    ]
    return portfolio_rows, benchmark_rows, expected_active


def _randomized_currency_inputs() -> tuple[_CurrencyInputs, np.ndarray]:
    """Return 48 shuffled currency periods and independent active expectations."""
    random = np.random.default_rng(20260909)
    periods = pd.date_range("2021-01-31", periods=48, freq="ME")
    starts = periods.to_period("M").start_time
    market = pd.DataFrame(
        [
            (start, end, "Global", 1.0, 0.0, 0.0)
            for start, end in zip(starts, periods, strict=True)
        ],
        columns=CURRENCY_MARKET_INPUT_COLUMNS,
    )
    portfolio_rows = []
    benchmark_rows = []
    expected_active = []
    for start, end in zip(starts, periods, strict=True):
        portfolio, benchmark, active = _random_currency_period(random, start, end)
        portfolio_rows.extend(portfolio)
        benchmark_rows.extend(benchmark)
        expected_active.append(active)
    portfolio_currencies = pd.DataFrame(
        portfolio_rows, columns=CURRENCY_EXPOSURE_INPUT_COLUMNS
    ).sample(frac=1.0, random_state=47)
    benchmark_currencies = pd.DataFrame(
        benchmark_rows, columns=CURRENCY_EXPOSURE_INPUT_COLUMNS
    ).sample(frac=1.0, random_state=53)
    inputs: _CurrencyInputs = (
        market,
        market.copy(deep=True),
        portfolio_currencies,
        benchmark_currencies,
    )
    return inputs, np.asarray(expected_active, dtype=np.float64)


def test_randomized_currency_and_complete_identities_match_direct_calculation() -> None:
    """Random signed exposures reconcile currency and total effects independently.

    The market premium is exactly zero in every period. The expected values are direct
    differences between independently weighted portfolio and benchmark cash log
    returns, so the same array must equal active currency return, active total return,
    and the four-channel total effect without relying on production intermediates.
    """
    inputs, expected_active = _randomized_currency_inputs()

    result = calculate_currency_attribution(*inputs, base_currency="USD")

    for column in (
        "active_currency_log_return",
        "active_total_log_return",
        "total_log_effect",
    ):
        np.testing.assert_allclose(
            result.period_summary[column],
            expected_active,
            rtol=1e-12,
            atol=1e-12,
        )
    assert result.reconciliation[
        ["market_reconciled", "currency_reconciled", "total_reconciled"]
    ].to_numpy(dtype=np.bool_).all()


def test_nonfinite_currency_calculation_is_rejected_without_a_partial_result() -> None:
    """Finite inputs that overflow a weighted currency effect must fail explicitly."""
    inputs = _complete_hand_fixture()
    extreme_weights = [1e308, -1e308, 1.0, 0.0]
    inputs[2].loc[:, "currency_weight"] = extreme_weights
    inputs[3].loc[:, "currency_weight"] = extreme_weights
    inputs[2].loc[0, "base_currency_cash_return"] = float.fromhex(
        "0x1.fffffffffffffp+1023"
    )

    with pytest.raises(
        AttributionError,
        match="currency-grid calculation produced a non-finite",
    ):
        calculate_currency_attribution(*inputs, base_currency="USD")
