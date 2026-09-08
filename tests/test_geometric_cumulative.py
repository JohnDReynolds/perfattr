"""Independent tests for geometric compounding and reconciliation."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import numpy as np
import pandas as pd
import pytest

import perfattr.geometric as geometric_module
from perfattr import AttributionError, calculate_geometric_attribution
from perfattr._schemas import (
    GEOMETRIC_CUMULATIVE_COLUMNS,
    GEOMETRIC_CUMULATIVE_RECONCILIATION_CHECKS,
    GEOMETRIC_PERIOD_RECONCILIATION_CHECKS,
    GEOMETRIC_RECONCILIATION_COLUMNS,
    PREPARED_REQUIRED_COLUMNS,
)
from perfattr.geometric import GeometricAttributionResult


def _two_period_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the governing hand example followed by a distinct second period."""
    portfolio = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "A", 0.6, 0.12, 31),
            ("2024-01-01", "2024-01-31", "B", 0.4, 0.03, 31),
            ("2024-02-01", "2024-02-29", "A", 0.5, -0.02, 29),
            ("2024-02-01", "2024-02-29", "B", 0.5, 0.06, 29),
        ],
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    benchmark = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "A", 0.5, 0.08, 31),
            ("2024-01-01", "2024-01-31", "B", 0.5, 0.04, 31),
            ("2024-02-01", "2024-02-29", "A", 0.4, 0.01, 29),
            ("2024-02-01", "2024-02-29", "B", 0.6, 0.03, 29),
        ],
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    return portfolio, benchmark


def test_two_period_cumulative_result_matches_independent_products() -> None:
    """Every final value should match direct multiplication of literal wealth.

    Period one has portfolio, benchmark, and semi-notional returns of 8.4%, 6%, and
    6.4%. Period two has corresponding returns of 2%, 2.2%, and 2%. Direct products
    therefore give 10.568%, 8.332%, and 8.528%. Cumulative allocation is the
    semi-notional-to-benchmark wealth ratio, cumulative selection is the
    portfolio-to-semi-notional ratio, and their product is the complete geometric
    excess return.
    """
    portfolio, benchmark = _two_period_inputs()

    result = calculate_geometric_attribution(portfolio, benchmark)
    final = result.cumulative.iloc[-1]
    portfolio_horizon = 1.084 * 1.020 - 1.0
    benchmark_horizon = 1.060 * 1.022 - 1.0
    semi_notional_horizon = 1.064 * 1.020 - 1.0
    allocation_horizon = (1.0 + semi_notional_horizon) / (
        1.0 + benchmark_horizon
    ) - 1.0
    selection_horizon = (1.0 + portfolio_horizon) / (
        1.0 + semi_notional_horizon
    ) - 1.0
    geometric_horizon = (1.0 + portfolio_horizon) / (
        1.0 + benchmark_horizon
    ) - 1.0

    assert isinstance(result, GeometricAttributionResult)
    assert final["portfolio_return"] == pytest.approx(0.10568, abs=1e-12)
    assert final["benchmark_return"] == pytest.approx(0.08332, abs=1e-12)
    assert final["semi_notional_return"] == pytest.approx(0.08528, abs=1e-12)
    assert final["allocation_effect"] == pytest.approx(allocation_horizon, abs=1e-12)
    assert final["selection_effect"] == pytest.approx(selection_horizon, abs=1e-12)
    assert final["geometric_excess_return"] == pytest.approx(
        geometric_horizon,
        abs=1e-12,
    )
    assert final["total_effect"] == pytest.approx(geometric_horizon, abs=1e-12)
    assert final["from_date"] == pd.Timestamp("2024-01-01")
    assert final["thru_date"] == pd.Timestamp("2024-02-29")
    assert final["quantity_of_days"] == 60


def test_reconciliation_has_every_ordered_period_and_prefix_check() -> None:
    """Two periods should produce six period and nine cumulative checks each."""
    portfolio, benchmark = _two_period_inputs()

    reconciliation = calculate_geometric_attribution(
        portfolio,
        benchmark,
    ).reconciliation

    assert tuple(reconciliation.columns) == GEOMETRIC_RECONCILIATION_COLUMNS
    assert list(reconciliation["scope"]) == ["period"] * 12 + ["cumulative"] * 18
    assert list(reconciliation["check"]) == [
        *GEOMETRIC_PERIOD_RECONCILIATION_CHECKS,
        *GEOMETRIC_PERIOD_RECONCILIATION_CHECKS,
        *GEOMETRIC_CUMULATIVE_RECONCILIATION_CHECKS,
        *GEOMETRIC_CUMULATIVE_RECONCILIATION_CHECKS,
    ]
    assert len(reconciliation) == 30
    assert bool(reconciliation["passed"].to_numpy().all())
    assert str(reconciliation["scope"].dtype) == "string"
    assert str(reconciliation["check"].dtype) == "string"
    assert str(reconciliation["passed"].dtype) == "bool"


def test_one_period_cumulative_values_equal_period_values() -> None:
    """Compounding one period must be the identity for every reported channel."""
    portfolio = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "Asset", 1.0, 0.02, 31)],
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    benchmark = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "Asset", 1.0, 0.01, 31)],
        columns=PREPARED_REQUIRED_COLUMNS,
    )

    result = calculate_geometric_attribution(portfolio, benchmark)

    assert tuple(result.cumulative.columns) == GEOMETRIC_CUMULATIVE_COLUMNS
    for column in GEOMETRIC_CUMULATIVE_COLUMNS[3:]:
        assert result.cumulative.at[0, column] == pytest.approx(
            result.period_summary.at[0, column],
            abs=1e-12,
        )


def _swap_period_facts(frame: pd.DataFrame) -> pd.DataFrame:
    """Exchange January and February facts while retaining chronological keys."""
    swapped = frame.copy(deep=True)
    fact_columns = ["weight", "return"]
    january = frame["thru_date"].eq("2024-01-31")
    february = ~january
    swapped.loc[january, fact_columns] = frame.loc[february, fact_columns].to_numpy()
    swapped.loc[february, fact_columns] = frame.loc[january, fact_columns].to_numpy()
    return swapped


def test_final_horizon_is_invariant_to_complete_period_order() -> None:
    """Reordering whole economic periods may change prefixes but not final wealth."""
    portfolio, benchmark = _two_period_inputs()
    original = calculate_geometric_attribution(portfolio, benchmark)
    reordered = calculate_geometric_attribution(
        _swap_period_facts(portfolio),
        _swap_period_facts(benchmark),
    )
    numeric_columns = GEOMETRIC_CUMULATIVE_COLUMNS[3:]
    original_final = np.asarray(
        original.cumulative.loc[1, list(numeric_columns)],
        dtype=np.float64,
    )
    reordered_final = np.asarray(
        reordered.cumulative.loc[1, list(numeric_columns)],
        dtype=np.float64,
    )
    original_first = np.asarray(
        original.cumulative.loc[0, list(numeric_columns)],
        dtype=np.float64,
    )
    reordered_first = np.asarray(
        reordered.cumulative.loc[0, list(numeric_columns)],
        dtype=np.float64,
    )

    np.testing.assert_allclose(
        original_final,
        reordered_final,
        rtol=1e-12,
        atol=1e-12,
    )
    assert not np.array_equal(original_first, reordered_first)


def _long_history_inputs(period_count: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a deterministic two-identifier daily history without copied fixtures."""
    dates = pd.date_range("2020-01-01", periods=period_count, freq="D")
    angles = np.arange(period_count, dtype=np.float64)
    portfolio_returns = np.column_stack(
        (0.0002 + 0.0001 * np.sin(angles), 0.0001 + 0.0001 * np.cos(angles))
    )
    benchmark_returns = np.column_stack(
        (0.0001 + 0.0001 * np.cos(angles), 0.0002 + 0.0001 * np.sin(angles))
    )
    repeated_dates = np.repeat(dates, 2)
    identifiers = np.tile(["A", "B"], period_count)
    shared = {
        "from_date": repeated_dates,
        "thru_date": repeated_dates,
        "identifier": identifiers,
        "quantity_of_days": 1,
    }
    portfolio = pd.DataFrame(
        {
            **shared,
            "weight": np.tile([0.6, 0.4], period_count),
            "return": portfolio_returns.ravel(),
        },
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    benchmark = pd.DataFrame(
        {
            **shared,
            "weight": np.tile([0.5, 0.5], period_count),
            "return": benchmark_returns.ravel(),
        },
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    return portfolio, benchmark


def test_long_history_compounds_stably_and_reconciles() -> None:
    """A thousand periods should remain finite and close every prefix identity."""
    portfolio, benchmark = _long_history_inputs(1_000)

    result = calculate_geometric_attribution(portfolio, benchmark)

    assert len(result.cumulative) == 1_000
    assert len(result.reconciliation) == 15_000
    assert np.isfinite(
        result.cumulative.loc[:, GEOMETRIC_CUMULATIVE_COLUMNS[3:]].to_numpy()
    ).all()
    assert bool(result.reconciliation["passed"].to_numpy().all())


def test_near_total_loss_remains_finite_and_reconciled() -> None:
    """Strictly positive tiny wealth bases should not be mistaken for total loss.

    Portfolio and benchmark ending wealth are approximately two and one trillionths.
    Because the one identifier has equal weights, the semi-notional leg equals the
    benchmark and allocation is zero. Selection carries the near-100% relative gain.
    """
    portfolio = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "Asset", 1.0, -0.999999999998, 31)],
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    benchmark = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "Asset", 1.0, -0.999999999999, 31)],
        columns=PREPARED_REQUIRED_COLUMNS,
    )

    result = calculate_geometric_attribution(portfolio, benchmark)

    assert np.isfinite(result.cumulative.select_dtypes(include="number")).all().all()
    assert result.cumulative.at[0, "allocation_effect"] == pytest.approx(0.0)
    assert result.cumulative.at[0, "selection_effect"] == pytest.approx(
        (1.0 - 0.999999999998) / (1.0 - 0.999999999999) - 1.0,
        abs=1e-12,
    )
    assert bool(result.reconciliation["passed"].to_numpy().all())


def test_reconciliation_failure_raises_instead_of_returning_partial_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tampered period totals must fail before a public result can escape."""
    portfolio, benchmark = _two_period_inputs()
    original = cast(
        Callable[[pd.DataFrame], pd.DataFrame],
        getattr(geometric_module, "_build_geometric_period_summary"),
    )

    def _tampered_summary(detail: pd.DataFrame) -> pd.DataFrame:
        """Move one summary channel without altering its identifier source rows."""
        summary = original(detail)
        summary.at[0, "selection_effect"] = (
            cast(float, summary.at[0, "selection_effect"]) + 0.01
        )
        return summary

    monkeypatch.setattr(
        geometric_module,
        "_build_geometric_period_summary",
        _tampered_summary,
    )

    with pytest.raises(
        AttributionError,
        match=(
            r"^geometric reconciliation failed for period 2024-01-31 "
            r"identifier_selection$"
        ),
    ):
        calculate_geometric_attribution(portfolio, benchmark)
