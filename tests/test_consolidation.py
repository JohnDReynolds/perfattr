"""Tests for aligned reporting-frequency consolidation."""

from __future__ import annotations

import datetime as dt
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from perfattr import PreparationError
from perfattr._schemas import NORMALIZED_PERFORMANCE_COLUMNS
from perfattr.consolidation import _consolidate_performance
from perfattr.mapping import _map_performance
from perfattr.preparation import _AlignedPeriods, _normalize_performance


_JANUARY = _AlignedPeriods(((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),), (1,))


def _normalized(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Return validated source rows for a consolidation test."""
    return _normalize_performance(pd.DataFrame(rows), "portfolio input").frame


def _authoritative_two_period_source() -> pd.DataFrame:
    """Return two source periods whose contributions differ from weight times return."""
    return _normalized(
        [
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "A",
                "weight": 0.6,
                "return": 0.10,
                "contribution": 0.07,
            },
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "B",
                "weight": 0.4,
                "return": 0.05,
                "contribution": 0.01,
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "A",
                "weight": 0.5,
                "return": -0.02,
                "contribution": -0.01,
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "B",
                "weight": 0.5,
                "return": 0.04,
                "contribution": 0.03,
            },
        ]
    )


def test_consolidation_links_authoritative_contribution_and_weights_by_days() -> None:
    """Two source periods should follow the independently calculated formulas.

    The source totals are 8% and 2%, so geometric January return is
    ``1.08 * 1.02 - 1 = 10.16%``. Logarithmic coefficients independently evaluate to
    1.0100952539977162 and 1.0396189840091354. Applying those coefficients to A's
    7% and -1% contributions gives 6.031047793974878%; B receives
    4.128952206025122%. The 15- and 16-day weights are 17/31 and 14/31.
    """
    source = _authoritative_two_period_source()
    source_before = source.copy(deep=True)

    consolidated = _consolidate_performance(
        source, _JANUARY, False, "portfolio input"
    )

    assert list(consolidated["identifier"]) == ["A", "B"]
    np.testing.assert_allclose(
        consolidated["weight"],
        [0.5483870967741935, 0.45161290322580644],
        rtol=1e-12,
        atol=1e-12,
    )
    # Unmapped identifier returns compound independently of authoritative
    # contribution: A is 1.10 * 0.98 - 1, and B is 1.05 * 1.04 - 1.
    np.testing.assert_allclose(
        consolidated["return"], [0.078, 0.092], rtol=1e-12, atol=1e-12
    )
    np.testing.assert_allclose(
        consolidated["contribution"],
        [0.06031047793974878, 0.04128952206025122],
        rtol=1e-12,
        atol=1e-12,
    )
    contribution_total = np.asarray(
        consolidated["contribution"], dtype=np.float64
    ).sum()
    assert contribution_total == pytest.approx(0.1016)
    assert consolidated["quantity_of_days"].tolist() == [31, 31]
    pd.testing.assert_frame_equal(source, source_before)


def test_exact_reporting_period_preserves_all_normalized_values() -> None:
    """An already consolidated source period should not be numerically relinked."""
    source = _normalized(
        [
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-31",
                "identifier": "A",
                "weight": 1.0,
                "return": 0.10,
                # The authoritative 12% intentionally differs from weight * return.
                "contribution": 0.12,
            }
        ]
    )

    consolidated = _consolidate_performance(
        source, _JANUARY, False, "portfolio input"
    )

    pd.testing.assert_frame_equal(consolidated, source)


def test_unmapped_identifier_absence_contributes_zero_return_and_weight() -> None:
    """An identifier absent from a source period should use zero, not missing, data.

    A exists only for the first 15 days, so its January return remains 10% and its
    observed-day-weighted exposure is ``15 * 40% / 31``. Its absence from the second
    period supplies the multiplicative identity rather than an explicit null return.
    """
    source = _normalized(
        [
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "A",
                "weight": 0.4,
                "return": 0.10,
            },
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "B",
                "weight": 0.6,
                "return": 0.0,
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "B",
                "weight": 1.0,
                "return": 0.02,
            },
        ]
    )

    consolidated = _consolidate_performance(
        source, _JANUARY, False, "portfolio input"
    )
    asset_a = consolidated.loc[consolidated["identifier"] == "A"].iloc[0]

    assert asset_a["return"] == pytest.approx(0.10)
    assert asset_a["weight"] == pytest.approx(6.0 / 31.0)


def test_mapped_return_uses_final_contribution_and_weight() -> None:
    """Mapped consolidation must not compound intermediate effective returns.

    An explicitly supplied empty mapping retains the identifiers but still invokes
    mapped effective-return semantics. A's linked contribution is
    0.06031047793974878 and its day-weighted exposure is 17/31, producing a final
    effective return of about 10.9978%. Compounding A's intermediate effective returns
    would instead produce a different and invalid answer.
    """
    source = _authoritative_two_period_source()
    empty_mapping = pd.DataFrame(
        columns=["identifier", "classification_identifier"]
    )
    mapped = _map_performance(source, empty_mapping, "portfolio input")

    consolidated = _consolidate_performance(
        mapped, _JANUARY, True, "portfolio input"
    )
    asset_a = consolidated.loc[consolidated["identifier"] == "A"].iloc[0]

    expected_effective_return = 0.06031047793974878 / (17.0 / 31.0)
    assert asset_a["return"] == pytest.approx(expected_effective_return)
    assert asset_a["return"] != pytest.approx((1.0 + 0.07 / 0.6) * (1.0 - 0.02) - 1.0)


@pytest.mark.parametrize(
    ("fee_contributions", "expected_return"),
    [
        pytest.param([0.0, 0.0], 0.0, id="zero-contribution"),
        pytest.param([0.01, 0.02], np.nan, id="nonzero-contribution"),
    ],
)
def test_mapped_zero_weight_uses_contribution_dependent_return(
    fee_contributions: list[float], expected_return: float
) -> None:
    """A mapped zero-weight group should use the exact documented return branch.

    FEE has zero exposure in both source periods. Zero linked contribution gives a
    defined zero return; nonzero authoritative contribution is preserved and requires
    a null effective return rather than an invented ratio.
    """
    source = _normalized(
        [
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "FEE",
                "weight": 0.0,
                "return": np.nan,
                "contribution": fee_contributions[0],
            },
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "ASSET",
                "weight": 1.0,
                "return": 0.02,
                "contribution": 0.02,
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "FEE",
                "weight": 0.0,
                "return": np.nan,
                "contribution": fee_contributions[1],
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "ASSET",
                "weight": 1.0,
                "return": 0.03,
                "contribution": 0.03,
            },
        ]
    )

    consolidated = _consolidate_performance(
        source, _JANUARY, True, "portfolio input"
    )
    fee = consolidated.loc[consolidated["identifier"] == "FEE"].iloc[0]

    assert fee["weight"] == 0.0
    if np.isnan(expected_return):
        assert fee["contribution"] > 0.0
        assert pd.isna(fee["return"])
    else:
        assert fee["contribution"] == 0.0
        assert fee["return"] == expected_return


def test_unmapped_null_return_with_nonzero_consolidated_weight_fails() -> None:
    """Consolidation must reject an undefined return mixed with later exposure.

    A's first-period zero-weight authoritative contribution requires a null return;
    its second-period 50% exposure makes the consolidated weight nonzero. Propagating
    the null is correct, but that result cannot satisfy the prepared core contract, so
    preparation must fail rather than invent a compound return.
    """
    source = _normalized(
        [
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "A",
                "weight": 0.0,
                "return": np.nan,
                "contribution": 0.01,
            },
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "B",
                "weight": 1.0,
                "return": 0.01,
                "contribution": 0.01,
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "A",
                "weight": 0.5,
                "return": 0.10,
                "contribution": 0.05,
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "B",
                "weight": 0.5,
                "return": 0.02,
                "contribution": 0.01,
            },
        ]
    )

    with pytest.raises(
        PreparationError, match="nonzero identifier weight with a null return"
    ):
        _consolidate_performance(source, _JANUARY, False, "portfolio input")


@pytest.mark.parametrize(
    ("source_returns", "expected"),
    [
        pytest.param([0.10, -0.05], 0.045, id="positive-and-negative"),
        pytest.param([-0.10, 0.05], -0.055, id="negative-total"),
        pytest.param([0.0, 0.0], 0.0, id="exact-zero"),
        pytest.param([1e-14, -1e-14], -1e-28, id="near-zero"),
        pytest.param(
            [-0.999999999999, 0.10],
            -0.9999999999989,
            id="approaching-negative-one",
        ),
    ],
)
def test_consolidation_handles_logarithmic_return_boundaries(
    source_returns: list[float], expected: float
) -> None:
    """Stable linking should cover positive, zero, near-zero, and near-loss limits.

    With one unit-weight identifier whose contribution equals return, the linked
    contribution and compounded identifier return must both equal
    ``(1 + r1) * (1 + r2) - 1``. The parameter values exercise exact and limiting
    branches without taking logarithms at the invalid -100% boundary.
    """
    source = _normalized(
        [
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "TOTAL",
                "weight": 1.0,
                "return": source_returns[0],
                "contribution": source_returns[0],
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "TOTAL",
                "weight": 1.0,
                "return": source_returns[1],
                "contribution": source_returns[1],
            },
        ]
    )

    consolidated = _consolidate_performance(
        source, _JANUARY, False, "portfolio input"
    )

    assert consolidated.loc[0, "return"] == pytest.approx(
        expected, rel=1e-12, abs=1e-30
    )
    assert consolidated.loc[0, "contribution"] == pytest.approx(
        expected, rel=1e-12, abs=1e-30
    )


@pytest.mark.parametrize("period_total", [-1.0, -1.01])
def test_consolidation_rejects_source_total_at_or_below_total_loss(
    period_total: float,
) -> None:
    """Logarithmic contribution linking is undefined at or below a -100% total."""
    source = _normalized(
        [
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "TOTAL",
                "weight": 1.0,
                "return": 0.0,
                "contribution": period_total,
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "TOTAL",
                "weight": 1.0,
                "return": 0.0,
                "contribution": 0.01,
            },
        ]
    )

    with pytest.raises(PreparationError, match="greater than -1.0"):
        _consolidate_performance(source, _JANUARY, False, "portfolio input")


def test_consolidation_rejects_compounded_return_overflow() -> None:
    """Individually finite gains must fail if their compounded result overflows."""
    source = _normalized(
        [
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-15",
                "identifier": "TOTAL",
                "weight": 1.0,
                "return": 1e200,
                "contribution": 1e200,
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "TOTAL",
                "weight": 1.0,
                "return": 1e200,
                "contribution": 1e200,
            },
        ]
    )

    with pytest.raises(PreparationError, match="compounded reporting return"):
        _consolidate_performance(source, _JANUARY, False, "portfolio input")


def test_consolidation_uses_leap_day_in_observed_day_weights() -> None:
    """Inclusive day weighting should count February 29 in a leap year.

    The two source spans contain 14 and 15 days. A's weights of 100% and 0% therefore
    consolidate to 14/29, proving that calendar days—not row counts—control exposure.
    """
    february = _AlignedPeriods(
        ((dt.date(2024, 2, 1), dt.date(2024, 2, 29)),), (2,)
    )
    source = _normalized(
        [
            {
                "from_date": "2024-02-01",
                "thru_date": "2024-02-14",
                "identifier": "A",
                "weight": 1.0,
                "return": 0.01,
            },
            {
                "from_date": "2024-02-15",
                "thru_date": "2024-02-29",
                "identifier": "B",
                "weight": 1.0,
                "return": 0.02,
            },
        ]
    )

    consolidated = _consolidate_performance(
        source, february, False, "portfolio input"
    )

    assert consolidated.loc[consolidated["identifier"] == "A", "weight"].iloc[
        0
    ] == pytest.approx(14.0 / 29.0)
    assert consolidated["quantity_of_days"].tolist() == [29, 29]


def test_consolidation_excludes_periods_outside_alignment_and_orders_rows() -> None:
    """Only aligned output periods should survive with deterministic schema and order."""
    source = _authoritative_two_period_source()
    february = _normalized(
        [
            {
                "from_date": "2024-02-01",
                "thru_date": "2024-02-29",
                "identifier": "Z",
                "weight": 1.0,
                "return": 0.01,
            }
        ]
    )
    shuffled = pd.concat([source, february], ignore_index=True).sample(
        frac=1.0, random_state=7
    )

    consolidated = _consolidate_performance(
        shuffled, _JANUARY, False, "portfolio input"
    )

    assert list(consolidated.columns) == list(NORMALIZED_PERFORMANCE_COLUMNS)
    assert list(consolidated["identifier"]) == ["A", "B"]
    assert str(consolidated["identifier"].dtype) == "string"
    assert consolidated["quantity_of_days"].dtype == np.dtype("int64")
    assert all(
        consolidated[column].dtype == np.dtype("float64")
        for column in ("weight", "return", "contribution")
    )


def test_consolidation_rejects_crossed_boundaries_or_incomplete_days() -> None:
    """A direct internal call should not silently consolidate invalid coverage."""
    crossing = _normalized(
        [
            {
                "from_date": "2023-12-31",
                "thru_date": "2024-01-15",
                "identifier": "A",
                "weight": 1.0,
                "return": 0.01,
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "A",
                "weight": 1.0,
                "return": 0.01,
            },
        ]
    )
    with pytest.raises(PreparationError, match="crossing reporting boundaries"):
        _consolidate_performance(crossing, _JANUARY, False, "portfolio input")

    gap = _normalized(
        [
            {
                "from_date": "2024-01-01",
                "thru_date": "2024-01-14",
                "identifier": "A",
                "weight": 1.0,
                "return": 0.01,
            },
            {
                "from_date": "2024-01-16",
                "thru_date": "2024-01-31",
                "identifier": "A",
                "weight": 1.0,
                "return": 0.01,
            },
        ]
    )
    with pytest.raises(PreparationError, match="source-period days total 30"):
        _consolidate_performance(gap, _JANUARY, False, "portfolio input")


@pytest.mark.parametrize("value", [True, "1e-12", 0.0, -1.0, np.inf, np.nan])
def test_consolidation_rejects_invalid_tolerances(value: Any) -> None:
    """Conservation must use only a finite positive numerical tolerance."""
    expected_error = TypeError if isinstance(value, str | bool) else PreparationError

    with pytest.raises(expected_error):
        _consolidate_performance(
            _authoritative_two_period_source(),
            _JANUARY,
            False,
            "portfolio input",
            reconciliation_tolerance=cast(float, value),
        )


def test_consolidation_validates_internal_boundary_types() -> None:
    """Internal composition should fail clearly when passed incompatible state."""
    source = _authoritative_two_period_source()
    with pytest.raises(TypeError, match="must be a pandas DataFrame"):
        _consolidate_performance(
            cast(pd.DataFrame, []), _JANUARY, False, "portfolio input"
        )
    with pytest.raises(TypeError, match="mapping_was_applied must be a bool"):
        _consolidate_performance(
            source, _JANUARY, cast(bool, 1), "portfolio input"
        )
    with pytest.raises(TypeError, match="must be an _AlignedPeriods"):
        _consolidate_performance(
            source,
            cast(_AlignedPeriods, object()),
            False,
            "portfolio input",
        )
