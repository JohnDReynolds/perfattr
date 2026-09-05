"""Public integration tests for Brinson-Hood-Beebower attribution."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest

from perfattr import AttributionMethod, calculate_attribution
from perfattr._schemas import (
    CUMULATIVE_COLUMNS,
    OVERALL_DETAIL_COLUMNS,
    OVERALL_RECONCILIATION_CHECKS,
    PERIOD_DETAIL_COLUMNS,
    PERIOD_RECONCILIATION_CHECKS,
    PERIOD_SUMMARY_COLUMNS,
)


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def _read_bhb_two_effect_linked_expected(case_name: str) -> pd.DataFrame:
    """Read one independently calculated compact BHB linking table."""
    expected = pd.read_csv(
        _FIXTURE_ROOT
        / case_name
        / "expected_bhb_two_effect_period_detail.csv"
    )
    for date_column in ("from_date", "thru_date"):
        expected[date_column] = pd.to_datetime(expected[date_column]).astype(
            "datetime64[ns]"
        )
    expected["identifier"] = expected["identifier"].astype("string[python]")
    return expected


def test_bhb_multi_period_linking_matches_hand_calculation() -> None:
    """BHB should preserve independently calculated effects through every result.

    January's allocations are -0.2% and 0.8%, selections -1.0% and 1.0%, and both
    interactions 0.2%. February's are -0.25% and -0.2%, 0.3% and -0.8%, and -0.05%
    and -0.2%, respectively. Applying the documented Carino coefficients gives final
    linked effects of 0.1258451699584109%, -0.527491055493353%,
    0.1366458855269426%, and -0.265%.
    """
    case_path = _FIXTURE_ROOT / "multi_period_linking"
    portfolio = pd.read_csv(case_path / "portfolio.csv")
    benchmark = pd.read_csv(case_path / "benchmark.csv")
    expected = pd.read_csv(case_path / "expected_bhb_period_detail.csv")
    for date_column in ("from_date", "thru_date"):
        expected[date_column] = pd.to_datetime(expected[date_column]).astype(
            "datetime64[ns]"
        )
    expected["identifier"] = expected["identifier"].astype("string[python]")

    result = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    )

    actual = result.period_detail.loc[:, expected.columns]
    pd.testing.assert_frame_equal(
        actual,
        expected,
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        result.period_summary[
            [
                "allocation_effect",
                "selection_effect",
                "interaction_effect",
                "total_effect",
            ]
        ],
        [[0.006, 0.0, 0.004, 0.010], [-0.0045, -0.005, -0.0025, -0.012]],
        rtol=1e-12,
        atol=1e-12,
    )
    overall = result.overall_detail.set_index("identifier")
    bonds = cast(pd.Series, overall.loc["Bonds"])
    equity = cast(pd.Series, overall.loc["Equity"])
    assert bonds["linked_total_effect"] == pytest.approx(
        -0.010009785331840475,
        abs=1e-12,
    )
    assert equity["linked_total_effect"] == pytest.approx(
        0.007359785331840482,
        abs=1e-12,
    )
    final = cast(pd.Series, result.cumulative.iloc[-1])
    np.testing.assert_allclose(
        np.asarray(
            final.loc[
                [
                    "cumulative_allocation_effect",
                    "cumulative_selection_effect",
                    "cumulative_interaction_effect",
                    "cumulative_total_effect",
                ]
            ],
            dtype=float,
        ),
        [
            0.001258451699584109,
            -0.0052749105549335295,
            0.0013664588552694257,
            -0.00265,
        ],
        rtol=1e-12,
        atol=1e-12,
    )
    assert bool(result.reconciliation["passed"].to_numpy().all())


@pytest.mark.parametrize("case_name", ("multi_period_linking", "linking_boundaries"))
def test_bhb_two_effect_linking_matches_independent_values(case_name: str) -> None:
    """Compact BHB should match literal regular and Carino-boundary values.

    In the regular case, the independently recorded Carino coefficients multiply
    unlinked compact selection values -0.8%, +1.2%, +0.25%, and -1.0%. For example,
    January Equity links to ``1.2% * 1.0009785331840475 =
    1.201174239820857%``. In the boundary case, zero active weights make BHB
    allocation zero; compact selection retains total effects of +/-5% in March and
    -0.000000005% per identifier in April. The March values exercise the analytic
    near-minus-one Carino coefficient ``0.000001000049999195771``.
    """
    case_path = _FIXTURE_ROOT / case_name
    portfolio = pd.read_csv(case_path / "portfolio.csv")
    benchmark = pd.read_csv(case_path / "benchmark.csv")
    expected = _read_bhb_two_effect_linked_expected(case_name)

    result = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
    )

    key_columns = ["from_date", "thru_date", "identifier"]
    numeric_columns = list(expected.columns.difference(key_columns, sort=False))
    pd.testing.assert_frame_equal(
        result.period_detail.loc[:, key_columns],
        expected.loc[:, key_columns],
    )
    np.testing.assert_allclose(
        result.period_detail.loc[:, numeric_columns],
        expected.loc[:, numeric_columns],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        result.period_detail["linked_allocation_effect"]
        + result.period_detail["linked_selection_effect"],
        result.period_detail["linked_total_effect"],
        rtol=1e-12,
        atol=1e-12,
    )
    assert bool(result.reconciliation["passed"].to_numpy().all())


def test_bhb_two_effect_collapse_survives_linking_and_aggregation() -> None:
    """BHB two/three collapse should hold in every linked aggregate frame.

    Hand aggregation of the regular fixture gives linked BHB compact effects of
    0.6005871199104285% allocation, 0.4003914132736190% selection, and
    1.0009785331840475% total in January. February gives -0.4747419499440175%,
    -0.7912365832400293%, and -1.2659785331840468%. Their cumulative allocation
    0.1258451699664110% plus selection -0.3908451699664103% equals the -0.265%
    full-horizon active return.

    Because all effect channels receive the same Carino coefficient, compact
    selection must also equal three-effect selection plus interaction after period
    summarization, identifier aggregation, and cumulative summation.
    """
    case_path = _FIXTURE_ROOT / "multi_period_linking"
    portfolio = pd.read_csv(case_path / "portfolio.csv")
    benchmark = pd.read_csv(case_path / "benchmark.csv")
    compact = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
    )
    three_effect = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    )

    assert tuple(compact.period_detail.columns) == PERIOD_DETAIL_COLUMNS
    assert tuple(compact.period_summary.columns) == PERIOD_SUMMARY_COLUMNS
    assert tuple(compact.overall_detail.columns) == OVERALL_DETAIL_COLUMNS
    assert tuple(compact.cumulative.columns) == CUMULATIVE_COLUMNS
    expected_checks = [
        check
        for _period in range(2)
        for check in PERIOD_RECONCILIATION_CHECKS
    ]
    expected_checks.extend(OVERALL_RECONCILIATION_CHECKS)
    assert list(compact.reconciliation["check"]) == expected_checks

    frame_channels = {
        "period_detail": ("", "linked_"),
        "period_summary": ("", "linked_"),
        "overall_detail": ("linked_",),
        "cumulative": ("linked_", "cumulative_"),
    }
    for frame_name, prefixes in frame_channels.items():
        compact_frame = getattr(compact, frame_name)
        three_effect_frame = getattr(three_effect, frame_name)
        for prefix in prefixes:
            np.testing.assert_allclose(
                compact_frame[f"{prefix}allocation_effect"],
                three_effect_frame[f"{prefix}allocation_effect"],
                rtol=1e-12,
                atol=1e-12,
            )
            np.testing.assert_allclose(
                compact_frame[f"{prefix}selection_effect"],
                three_effect_frame[f"{prefix}selection_effect"]
                + three_effect_frame[f"{prefix}interaction_effect"],
                rtol=1e-12,
                atol=1e-12,
            )
            np.testing.assert_allclose(
                compact_frame[f"{prefix}total_effect"],
                three_effect_frame[f"{prefix}total_effect"],
                rtol=1e-12,
                atol=1e-12,
            )

    np.testing.assert_allclose(
        compact.period_summary["linked_allocation_effect"],
        [0.006005871199104285, -0.004747419499440175],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        compact.period_summary["linked_selection_effect"],
        [0.00400391413273619, -0.007912365832400293],
        rtol=1e-12,
        atol=1e-12,
    )
    final = compact.cumulative.iloc[-1]
    assert final["cumulative_allocation_effect"] == pytest.approx(
        0.00125845169966411,
        abs=1e-12,
    )
    assert final["cumulative_selection_effect"] == pytest.approx(
        -0.003908451699664103,
        abs=1e-12,
    )
    assert final["cumulative_total_effect"] == pytest.approx(-0.00265, abs=1e-12)
    assert bool(compact.reconciliation["passed"].to_numpy().all())


def test_bhb_two_effect_handles_missing_sides_and_signed_weights() -> None:
    """Compact BHB should apply ordinary formulas to an equalized signed universe.

    C exists only in the portfolio with -10% weight and 20% return. Its synthesized
    benchmark side is zero, so BHB allocation is zero and selection carries its -2%
    active contribution. D exists only in the benchmark with 10% weight and 10%
    return: active weight -10% produces -1% BHB allocation and zero selection. E has
    zero weight and contribution on both sides, so every effect is zero. A and B add
    independently positive and negative allocation and selection values.
    """
    case_path = _FIXTURE_ROOT / "single_period_derived"
    portfolio = pd.read_csv(case_path / "portfolio.csv")
    benchmark = pd.read_csv(case_path / "benchmark.csv")
    compact = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
    )
    three_effect = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    )

    detail = compact.period_detail.set_index("identifier")
    np.testing.assert_allclose(
        detail.loc[["A", "B", "C", "D", "E"], "allocation_effect"],
        [0.005, -0.002, 0.0, -0.010, 0.0],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        detail.loc[["A", "B", "C", "D", "E"], "selection_effect"],
        [0.021, -0.004, -0.020, 0.0, 0.0],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        compact.period_detail["selection_effect"],
        three_effect.period_detail["selection_effect"]
        + three_effect.period_detail["interaction_effect"],
        rtol=1e-12,
        atol=1e-12,
    )
    assert bool(compact.reconciliation["passed"].to_numpy().all())


def test_bhb_two_effect_preserves_authoritative_fee_in_public_results() -> None:
    """Compact BHB should link an authoritative charge without inventing a return.

    The FEE row has zero exposure, null supplied and effective returns, and -0.1%
    authoritative portfolio contribution. Its absent benchmark side is neutral.
    Active weight and BHB allocation are therefore zero, while selection and total
    retain the full -0.1% charge in period and full-horizon results.
    """
    case_path = _FIXTURE_ROOT / "single_period_authoritative"
    portfolio = pd.read_csv(case_path / "portfolio.csv")
    benchmark = pd.read_csv(case_path / "benchmark.csv")

    result = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
    )

    period = result.period_detail.set_index("identifier")
    overall = result.overall_detail.set_index("identifier")
    period_fee = cast(pd.Series, period.loc["FEE"])
    overall_fee = cast(pd.Series, overall.loc["FEE"])
    assert bool(pd.isna(period_fee["portfolio_return"]))
    assert bool(pd.isna(period_fee["active_return"]))
    assert period_fee["active_weight"] == 0.0
    assert period_fee["allocation_effect"] == 0.0
    assert period_fee["selection_effect"] == pytest.approx(-0.001, abs=1e-12)
    assert period_fee["total_effect"] == pytest.approx(-0.001, abs=1e-12)
    assert bool(pd.isna(overall_fee["portfolio_return"]))
    assert bool(pd.isna(overall_fee["active_return"]))
    assert overall_fee["linked_selection_effect"] == pytest.approx(
        -0.001,
        abs=1e-12,
    )
    assert overall_fee["linked_total_effect"] == pytest.approx(-0.001, abs=1e-12)
    assert bool(result.reconciliation["passed"].to_numpy().all())
