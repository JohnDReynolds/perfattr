"""Independent tests for Roadmap 11 single-period geometric mathematics."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
import pytest

from perfattr import AttributionError, calculate_geometric_attribution
from perfattr._schemas import (
    GEOMETRIC_PERIOD_DETAIL_COLUMNS,
    GEOMETRIC_PERIOD_SUMMARY_COLUMNS,
    PREPARED_PERFORMANCE_COLUMNS,
    PREPARED_REQUIRED_COLUMNS,
)
from perfattr.geometric import (
    _calculate_geometric_period_frames,  # pyright: ignore[reportPrivateUsage]
)


def _derived_frame(
    rows: list[tuple[str, str, str, float, float, int]],
) -> pd.DataFrame:
    """Build basic prepared rows whose contributions are weight times return."""
    return pd.DataFrame(rows, columns=PREPARED_REQUIRED_COLUMNS)


def _authoritative_frame(
    rows: list[tuple[str, str, str, float, float | None, float, int]],
) -> pd.DataFrame:
    """Build accounting-integrated rows with authoritative contribution."""
    return pd.DataFrame(rows, columns=PREPARED_PERFORMANCE_COLUMNS)


def _assert_period_identities(detail: pd.DataFrame, summary: pd.DataFrame) -> None:
    """Check the independently stated successive-notional identities by period."""
    grouped = detail.groupby(["from_date", "thru_date"], sort=True, observed=True)
    for (_from_date, raw_thru_date), rows in grouped:
        thru_date = cast(pd.Timestamp, raw_thru_date)
        period = summary.loc[summary["thru_date"].eq(thru_date)].iloc[0]
        portfolio_return = float(rows["portfolio_contribution"].sum())
        benchmark_return = float(rows["benchmark_contribution"].sum())
        semi_notional_return = float(rows["semi_notional_contribution"].sum())
        allocation = float(rows["allocation_effect"].sum())
        selection = float(rows["selection_effect"].sum())
        geometric_excess = (1.0 + portfolio_return) / (1.0 + benchmark_return) - 1.0

        assert allocation == pytest.approx(
            (1.0 + semi_notional_return) / (1.0 + benchmark_return) - 1.0,
            abs=1e-12,
        )
        assert selection == pytest.approx(
            (1.0 + portfolio_return) / (1.0 + semi_notional_return) - 1.0,
            abs=1e-12,
        )
        assert (1.0 + allocation) * (1.0 + selection) - 1.0 == pytest.approx(
            geometric_excess,
            abs=1e-12,
        )
        assert float(period["geometric_excess_return"]) == pytest.approx(
            geometric_excess,
            abs=1e-12,
        )
        assert float(period["total_effect"]) == pytest.approx(
            geometric_excess,
            abs=1e-12,
        )


def test_basic_period_matches_independent_successive_notional_calculation() -> None:
    """Two identifiers should reproduce the governing hand calculation.

    Portfolio return is ``60% * 12% + 40% * 3% = 8.4%``. Benchmark return is
    ``50% * 8% + 50% * 4% = 6%``. Applying portfolio weights to benchmark returns
    gives the 6.4% semi-notional return.

    A's and B's allocations are each ``0.2% / 1.06``. Their selections are
    ``2.4% / 1.064`` and ``-0.4% / 1.064``. These literal numerators are independent
    of the implementation and make opposing identifier selection visible.
    """
    portfolio = _derived_frame(
        [
            ("2024-01-01", "2024-01-31", "A", 0.60, 0.12, 31),
            ("2024-01-01", "2024-01-31", "B", 0.40, 0.03, 31),
        ]
    )
    benchmark = _derived_frame(
        [
            ("2024-01-01", "2024-01-31", "A", 0.50, 0.08, 31),
            ("2024-01-01", "2024-01-31", "B", 0.50, 0.04, 31),
        ]
    )

    detail, summary = _calculate_geometric_period_frames(portfolio, benchmark)
    indexed = detail.set_index("identifier")

    assert tuple(detail.columns) == GEOMETRIC_PERIOD_DETAIL_COLUMNS
    assert tuple(summary.columns) == GEOMETRIC_PERIOD_SUMMARY_COLUMNS
    assert indexed.at["A", "semi_notional_contribution"] == pytest.approx(0.048)
    assert indexed.at["B", "semi_notional_contribution"] == pytest.approx(0.016)
    assert indexed.at["A", "allocation_effect"] == pytest.approx(0.002 / 1.06)
    assert indexed.at["B", "allocation_effect"] == pytest.approx(0.002 / 1.06)
    assert indexed.at["A", "selection_effect"] == pytest.approx(0.024 / 1.064)
    assert indexed.at["B", "selection_effect"] == pytest.approx(-0.004 / 1.064)
    assert summary.at[0, "portfolio_return"] == pytest.approx(0.084)
    assert summary.at[0, "benchmark_return"] == pytest.approx(0.060)
    assert summary.at[0, "semi_notional_return"] == pytest.approx(0.064)
    assert summary.at[0, "allocation_effect"] == pytest.approx(1.064 / 1.060 - 1.0)
    assert summary.at[0, "selection_effect"] == pytest.approx(1.084 / 1.064 - 1.0)
    assert summary.at[0, "total_effect"] == pytest.approx(1.084 / 1.060 - 1.0)
    _assert_period_identities(detail, summary)


def test_authoritative_portfolio_contribution_drives_selection() -> None:
    """A consolidated return and an unexposed fee must remain authoritative.

    Asset's supplied 10% return differs from its authoritative 5% contribution at
    100% weight, so its effective return is 5%. The portfolio fee contributes -0.1%
    at zero weight with a null return. Benchmark contribution implies a 4% effective
    return despite a supplied 7% return. The semi-notional return is therefore 4%,
    and selection is ``(4.9% - 4%) / 1.04``.
    """
    portfolio = _authoritative_frame(
        [
            ("2024-01-01", "2024-01-31", "Asset", 1.0, 0.10, 0.050, 31),
            ("2024-01-01", "2024-01-31", "Fee", 0.0, None, -0.001, 31),
        ]
    )
    benchmark = _authoritative_frame(
        [
            ("2024-01-01", "2024-01-31", "Asset", 1.0, 0.07, 0.040, 31),
            ("2024-01-01", "2024-01-31", "Fee", 0.0, None, 0.000, 31),
        ]
    )

    detail, summary = _calculate_geometric_period_frames(portfolio, benchmark)
    indexed = detail.set_index("identifier")

    assert indexed.at["Asset", "portfolio_return"] == pytest.approx(0.05)
    assert indexed.at["Asset", "benchmark_return"] == pytest.approx(0.04)
    assert pd.isna(indexed.at["Fee", "portfolio_return"])
    assert indexed.at["Fee", "selection_effect"] == pytest.approx(-0.001 / 1.04)
    assert indexed.at["Asset", "selection_effect"] == pytest.approx(0.010 / 1.04)
    assert indexed["allocation_effect"].sum() == pytest.approx(0.0)
    assert summary.at[0, "selection_effect"] == pytest.approx(0.009 / 1.04)
    _assert_period_identities(detail, summary)


def test_benchmark_unexposed_charge_is_an_allocation_accounting_residual() -> None:
    """A benchmark-only charge must not disappear behind its null return.

    Benchmark wealth is 1.039 after its -0.1% unexposed charge, while the
    semi-notional portfolio earns the asset's 4% return. Their allocation ratio is
    therefore ``1.04 / 1.039 - 1``. The charge row carries the equivalent positive
    allocation ``0.001 / 1.039`` through its -0.1% accounting residual.
    """
    portfolio = _derived_frame(
        [("2024-01-01", "2024-01-31", "Asset", 1.0, 0.05, 31)]
    )
    benchmark = _authoritative_frame(
        [
            ("2024-01-01", "2024-01-31", "Asset", 1.0, 0.04, 0.040, 31),
            ("2024-01-01", "2024-01-31", "Benchmark Fee", 0.0, None, -0.001, 31),
        ]
    )

    detail, summary = _calculate_geometric_period_frames(portfolio, benchmark)
    charge = cast(pd.Series, detail.set_index("identifier").loc["Benchmark Fee"])

    assert np.isnan(cast(float, charge["benchmark_return"]))
    assert cast(float, charge["semi_notional_contribution"]) == pytest.approx(0.0)
    assert cast(float, charge["benchmark_accounting_residual"]) == pytest.approx(
        -0.001
    )
    assert cast(float, charge["allocation_effect"]) == pytest.approx(0.001 / 1.039)
    assert summary.at[0, "allocation_effect"] == pytest.approx(1.04 / 1.039 - 1.0)
    _assert_period_identities(detail, summary)


def test_nonzero_portfolio_weight_rejects_null_benchmark_effective_return() -> None:
    """A benchmark charge cannot supply the return on an exposed notional leg.

    The benchmark has a null effective return for Charge because its weight is zero
    and contribution is nonzero. Applying the portfolio's 20% Charge weight to an
    unknown return cannot be made valid by substituting zero.
    """
    portfolio = _authoritative_frame(
        [
            ("2024-01-01", "2024-01-31", "Asset", 0.8, 0.05, 0.040, 31),
            ("2024-01-01", "2024-01-31", "Charge", 0.2, 0.01, 0.002, 31),
        ]
    )
    benchmark = _authoritative_frame(
        [
            ("2024-01-01", "2024-01-31", "Asset", 1.0, 0.04, 0.040, 31),
            ("2024-01-01", "2024-01-31", "Charge", 0.0, None, -0.001, 31),
        ]
    )

    with pytest.raises(
        AttributionError,
        match=(
            r"^geometric semi-notional return is undefined for nonzero portfolio "
            r"weight at 2024-01-31 identifier 'Charge'$"
        ),
    ):
        calculate_geometric_attribution(portfolio, benchmark)


def test_nonpositive_semi_notional_wealth_is_rejected_exactly() -> None:
    """Signed weights may create an invalid notional wealth base.

    Portfolio weights 200% and -100% sum to one. Applying them to benchmark returns
    -90% and +30% gives ``2 * -90% - 1 * 30% = -210%``. Although every input return
    and both actual portfolio/benchmark totals are valid, geometric selection cannot
    divide by ``1 - 2.10``.
    """
    portfolio = _derived_frame(
        [
            ("2024-01-01", "2024-01-31", "A", 2.0, 0.00, 31),
            ("2024-01-01", "2024-01-31", "B", -1.0, 0.00, 31),
        ]
    )
    benchmark = _derived_frame(
        [
            ("2024-01-01", "2024-01-31", "A", 0.5, -0.90, 31),
            ("2024-01-01", "2024-01-31", "B", 0.5, 0.30, 31),
        ]
    )

    with pytest.raises(
        AttributionError,
        match=r"^geometric semi-notional period return must be greater than -1.0$",
    ):
        calculate_geometric_attribution(portfolio, benchmark)


def test_missing_sides_and_cash_use_ordinary_identifier_rules() -> None:
    """Universe equalization should not give cash or missing rows special treatment.

    CASH_USD exists only in the portfolio and earns 10%; Equity exists only in the
    benchmark and earns 5%. The missing benchmark cash return is the released neutral
    zero, giving a zero semi-notional return. Allocation is ``-5% / 1.05`` and
    selection is 10%, which multiply to the 10%-versus-5% geometric excess.
    """
    portfolio = _derived_frame(
        [("2024-01-01", "2024-01-31", "CASH_USD", 1.0, 0.10, 31)]
    )
    benchmark = _derived_frame(
        [("2024-01-01", "2024-01-31", "Equity", 1.0, 0.05, 31)]
    )

    detail, summary = _calculate_geometric_period_frames(portfolio, benchmark)

    assert list(detail["identifier"]) == ["CASH_USD", "Equity"]
    assert summary.at[0, "semi_notional_return"] == pytest.approx(0.0)
    assert summary.at[0, "allocation_effect"] == pytest.approx(-0.05 / 1.05)
    assert summary.at[0, "selection_effect"] == pytest.approx(0.10)
    _assert_period_identities(detail, summary)


def test_signed_weights_reconcile_without_special_branching() -> None:
    """A valid long-short portfolio should use the ordinary geometric formulas."""
    portfolio = _derived_frame(
        [
            ("2024-01-01", "2024-01-31", "Long", 1.2, 0.06, 31),
            ("2024-01-01", "2024-01-31", "Short", -0.2, 0.02, 31),
        ]
    )
    benchmark = _derived_frame(
        [
            ("2024-01-01", "2024-01-31", "Long", 0.7, 0.04, 31),
            ("2024-01-01", "2024-01-31", "Short", 0.3, 0.03, 31),
        ]
    )

    detail, summary = _calculate_geometric_period_frames(portfolio, benchmark)

    assert summary.at[0, "semi_notional_return"] == pytest.approx(0.042)
    _assert_period_identities(detail, summary)


def test_zero_effect_case_remains_exact_zero() -> None:
    """Identical sides should produce exact zero in every geometric effect channel."""
    performance = _derived_frame(
        [
            ("2024-01-01", "2024-01-31", "A", 0.4, 0.05, 31),
            ("2024-01-01", "2024-01-31", "B", 0.6, -0.02, 31),
        ]
    )

    detail, summary = _calculate_geometric_period_frames(
        performance,
        performance.copy(deep=True),
    )

    np.testing.assert_array_equal(detail["allocation_effect"], 0.0)
    np.testing.assert_array_equal(detail["selection_effect"], 0.0)
    assert summary.at[0, "geometric_excess_return"] == 0.0
    assert summary.at[0, "total_effect"] == 0.0


def _randomized_period_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build deterministic inputs and independent dot-product period expectations."""
    random = np.random.default_rng(20260907)
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    portfolio_weights = np.vstack([random.dirichlet(np.ones(8)) for _ in dates])
    benchmark_weights = np.vstack([random.dirichlet(np.ones(8)) for _ in dates])
    portfolio_returns = random.uniform(-0.3, 0.3, (len(dates), 8))
    benchmark_returns = random.uniform(-0.3, 0.3, (len(dates), 8))
    repeated_dates = np.repeat(dates, 8)
    identifiers = np.tile([f"G{number}" for number in range(8)], len(dates))
    shared = {
        "from_date": repeated_dates,
        "thru_date": repeated_dates,
        "identifier": identifiers,
        "quantity_of_days": np.ones(len(repeated_dates), dtype=np.int64),
    }
    portfolio = pd.DataFrame(
        {
            **shared,
            "weight": portfolio_weights.ravel(),
            "return": portfolio_returns.ravel(),
        },
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    benchmark = pd.DataFrame(
        {
            **shared,
            "weight": benchmark_weights.ravel(),
            "return": benchmark_returns.ravel(),
        },
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    expected = pd.DataFrame(
        {
            "thru_date": dates,
            "portfolio_return": np.sum(portfolio_weights * portfolio_returns, axis=1),
            "benchmark_return": np.sum(benchmark_weights * benchmark_returns, axis=1),
            "semi_notional_return": np.sum(
                portfolio_weights * benchmark_returns,
                axis=1,
            ),
        }
    ).set_index("thru_date")
    return portfolio, benchmark, expected


def test_randomized_periods_match_independent_ratio_formulas() -> None:
    """Twenty deterministic periods should close independently calculated ratios.

    Each side uses unrelated positive weights and returns, so this covers 160
    identifier-period effects without importing an implementation oracle. Expected
    portfolio, benchmark, and semi-notional returns are direct dot products of the
    literal generated facts; expected effects are their two wealth ratios.
    """
    portfolio, benchmark, expected = _randomized_period_inputs()
    detail, summary = _calculate_geometric_period_frames(
        portfolio,
        benchmark,
    )

    for row in summary.itertuples(index=False):
        expected_row = cast(
            pd.Series,
            expected.loc[cast(pd.Timestamp, row.thru_date)],
        )
        portfolio_return = float(expected_row["portfolio_return"])
        benchmark_return = float(expected_row["benchmark_return"])
        semi_notional_return = float(expected_row["semi_notional_return"])
        assert row.portfolio_return == pytest.approx(portfolio_return, abs=1e-12)
        assert row.benchmark_return == pytest.approx(benchmark_return, abs=1e-12)
        assert row.semi_notional_return == pytest.approx(
            semi_notional_return,
            abs=1e-12,
        )
        assert row.allocation_effect == pytest.approx(
            (1.0 + semi_notional_return) / (1.0 + benchmark_return) - 1.0,
            abs=1e-12,
        )
        assert row.selection_effect == pytest.approx(
            (1.0 + portfolio_return) / (1.0 + semi_notional_return) - 1.0,
            abs=1e-12,
        )
    _assert_period_identities(detail, summary)


def test_period_calculation_is_deterministic_under_caller_row_order() -> None:
    """Stable canonical ordering should make input row permutation irrelevant."""
    portfolio = _derived_frame(
        [
            ("2024-02-01", "2024-02-29", "B", 0.3, 0.02, 29),
            ("2024-01-01", "2024-01-31", "B", 0.4, 0.03, 31),
            ("2024-02-01", "2024-02-29", "A", 0.7, 0.04, 29),
            ("2024-01-01", "2024-01-31", "A", 0.6, 0.05, 31),
        ]
    )
    benchmark = _derived_frame(
        [
            ("2024-01-01", "2024-01-31", "A", 0.5, 0.04, 31),
            ("2024-02-01", "2024-02-29", "A", 0.4, 0.03, 29),
            ("2024-01-01", "2024-01-31", "B", 0.5, 0.02, 31),
            ("2024-02-01", "2024-02-29", "B", 0.6, 0.01, 29),
        ]
    )

    detail, summary = _calculate_geometric_period_frames(portfolio, benchmark)
    reordered_detail, reordered_summary = _calculate_geometric_period_frames(
        portfolio.iloc[::-1].reset_index(drop=True),
        benchmark.iloc[::-1].reset_index(drop=True),
    )

    pd.testing.assert_frame_equal(detail, reordered_detail)
    pd.testing.assert_frame_equal(summary, reordered_summary)
