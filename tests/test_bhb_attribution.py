"""Public integration tests for Brinson-Hood-Beebower attribution."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest

from perfattr import AttributionMethod, calculate_attribution


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"


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
