"""Tests for attribution-method schemas and public metadata."""

from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from perfattr import AttributionMethod, AttributionResult
from perfattr._schemas import (
    CUMULATIVE_COLUMNS,
    OVERALL_DETAIL_COLUMNS,
    OVERALL_RECONCILIATION_CHECKS,
    PERIOD_DETAIL_COLUMNS,
    PERIOD_RECONCILIATION_CHECKS,
    PERIOD_SUMMARY_COLUMNS,
    THREE_EFFECT_CUMULATIVE_COLUMNS,
    THREE_EFFECT_OVERALL_DETAIL_COLUMNS,
    THREE_EFFECT_OVERALL_RECONCILIATION_CHECKS,
    THREE_EFFECT_PERIOD_DETAIL_COLUMNS,
    THREE_EFFECT_PERIOD_RECONCILIATION_CHECKS,
    THREE_EFFECT_PERIOD_SUMMARY_COLUMNS,
)
from perfattr.attribution import (
    _build_period_detail,
    _equalize_universe,
    _normalize_input,
)
from perfattr.method import uses_explicit_interaction


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_SCHEMA_CASES = (
    (
        PERIOD_DETAIL_COLUMNS,
        THREE_EFFECT_PERIOD_DETAIL_COLUMNS,
        (
            ("selection_effect", "interaction_effect"),
            ("linked_selection_effect", "linked_interaction_effect"),
        ),
    ),
    (
        PERIOD_SUMMARY_COLUMNS,
        THREE_EFFECT_PERIOD_SUMMARY_COLUMNS,
        (
            ("selection_effect", "interaction_effect"),
            ("linked_selection_effect", "linked_interaction_effect"),
        ),
    ),
    (
        OVERALL_DETAIL_COLUMNS,
        THREE_EFFECT_OVERALL_DETAIL_COLUMNS,
        (("linked_selection_effect", "linked_interaction_effect"),),
    ),
    (
        CUMULATIVE_COLUMNS,
        THREE_EFFECT_CUMULATIVE_COLUMNS,
        (
            ("linked_selection_effect", "linked_interaction_effect"),
            ("cumulative_selection_effect", "cumulative_interaction_effect"),
        ),
    ),
)


def test_explicit_interaction_policy_identifies_both_three_effect_methods() -> None:
    """Schema routing should include BHB without reclassifying the default method."""
    assert not uses_explicit_interaction(
        AttributionMethod.BRINSON_FACHLER_TWO_EFFECT
    )
    assert uses_explicit_interaction(
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT
    )
    assert uses_explicit_interaction(
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT
    )


def _read_three_effect_fixture(
    case_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read one original hand-calculated three-effect fixture."""
    case_path = _FIXTURE_ROOT / case_name
    return (
        pd.read_csv(case_path / "portfolio.csv"),
        pd.read_csv(case_path / "benchmark.csv"),
        pd.read_csv(case_path / "expected_effects.csv").set_index("identifier"),
    )


def _read_bhb_expected(case_name: str) -> pd.DataFrame:
    """Read one original hand-calculated BHB expectation table."""
    return pd.read_csv(
        _FIXTURE_ROOT / case_name / "expected_bhb_effects.csv"
    ).set_index("identifier")


def _calculate_unlinked_period_detail(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    method: AttributionMethod,
) -> pd.DataFrame:
    """Run the normalized single-period financial decomposition directly.

    Exercising this internal boundary isolates the underlying effect formulas from
    later linking and aggregation so the hand-calculated fixture values identify any
    decomposition error precisely.
    """
    normalized_portfolio = _normalize_input(portfolio, "portfolio")
    normalized_benchmark = _normalize_input(benchmark, "benchmark")
    equalized = _equalize_universe(normalized_portfolio, normalized_benchmark)
    return _build_period_detail(equalized, method)


@pytest.mark.parametrize(("released", "three_effect", "insertions"), _SCHEMA_CASES)
def test_three_effect_schemas_add_only_documented_interaction_columns(
    released: tuple[str, ...],
    three_effect: tuple[str, ...],
    insertions: tuple[tuple[str, str], ...],
) -> None:
    """Each opt-in schema should be the released schema plus ordered interaction.

    This structural test protects the compatibility plan without copying complete
    production column tuples into test code. Removing the new columns must recover the
    released tuple exactly, and each new column must immediately follow its related
    selection channel.
    """
    inserted_columns = tuple(column for _anchor, column in insertions)

    assert tuple(
        column for column in three_effect if column not in inserted_columns
    ) == released
    assert len(three_effect) == len(released) + len(insertions)
    for anchor, column in insertions:
        assert three_effect.index(column) == three_effect.index(anchor) + 1


def test_three_effect_reconciliation_names_disclose_the_extra_component() -> None:
    """Three-effect audit rows should be explicit without changing frame columns."""
    assert THREE_EFFECT_PERIOD_RECONCILIATION_CHECKS == tuple(
        "three_effect_components" if check == "effect_components" else check
        for check in PERIOD_RECONCILIATION_CHECKS
    )
    assert THREE_EFFECT_OVERALL_RECONCILIATION_CHECKS == tuple(
        "linked_three_effect_components"
        if check == "linked_effect_components"
        else check
        for check in OVERALL_RECONCILIATION_CHECKS
    )


def test_three_effect_period_detail_matches_hand_calculated_positive_case() -> None:
    """The third effect should match the specification's independent example.

    The benchmark total return is 3.6%. For A, active weight and active return are
    both positive, so allocation is ``30% * (6% - 3.6%) = 0.72%``, conventional
    benchmark-weighted selection is ``40% * (10% - 6%) = 1.60%``, and interaction
    is ``30% * (10% - 6%) = 1.20%``. B contributes the remaining 0.48% allocation
    and has no selection or interaction. These literal expectations were calculated
    from the governing formulas, independently of the implementation.
    """
    portfolio, benchmark, expected = _read_three_effect_fixture(
        "three_effect_positive"
    )

    three_effect = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    ).set_index("identifier")
    two_effect = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
    ).set_index("identifier")

    for identifier in expected.index:
        row = three_effect.loc[identifier]
        expected_row = expected.loc[identifier]
        assert row["allocation_effect"] == pytest.approx(
            expected_row["allocation_effect"],
            abs=1e-12,
        )
        assert row["selection_effect"] == pytest.approx(
            expected_row["selection_effect"],
            abs=1e-12,
        )
        assert row["interaction_effect"] == pytest.approx(
            expected_row["interaction_effect"],
            abs=1e-12,
        )
        assert row["total_effect"] == pytest.approx(
            expected_row["total_effect"],
            abs=1e-12,
        )
        assert two_effect.loc[identifier, "selection_effect"] == pytest.approx(
            expected_row["selection_effect"] + expected_row["interaction_effect"],
            abs=1e-12,
        )

    assert three_effect["allocation_effect"].sum() == pytest.approx(0.012, abs=1e-12)
    assert three_effect["selection_effect"].sum() == pytest.approx(0.016, abs=1e-12)
    assert three_effect["interaction_effect"].sum() == pytest.approx(0.012, abs=1e-12)
    assert three_effect["total_effect"].sum() == pytest.approx(0.040, abs=1e-12)


def test_three_effect_uses_effective_returns_and_preserves_negative_interaction() -> None:
    """Authoritative contributions should govern a negative-interaction example.

    Contributions imply portfolio effective returns of 5% and 10%, and benchmark
    effective returns of 4% and 6%; deliberately different input returns prove that
    the calculation uses the normalized accounting facts. B has active weight -10%
    and active return +4%, producing interaction -0.4%. Its independently calculated
    allocation, selection, and total are -0.1%, +2.0%, and +1.5%, respectively.
    """
    portfolio, benchmark, expected = _read_three_effect_fixture(
        "three_effect_authoritative"
    )

    detail = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    ).set_index("identifier")

    assert detail.loc["A", "portfolio_return"] == pytest.approx(0.05)
    assert detail.loc["A", "benchmark_return"] == pytest.approx(0.04)
    assert detail.loc["B", "portfolio_return"] == pytest.approx(0.10)
    assert detail.loc["B", "benchmark_return"] == pytest.approx(0.06)
    for identifier in expected.index:
        for column in expected.columns:
            assert detail.loc[identifier, column] == pytest.approx(
                expected.loc[identifier, column],
                abs=1e-12,
            )


def test_bhb_period_detail_matches_hand_calculated_positive_case() -> None:
    """BHB should use absolute benchmark return and unadjusted active contribution.

    The portfolio and benchmark returns are 7.6% and 3.6%. For A, active weight is
    30%, so BHB allocation is ``30% * 6% = 1.8%`` rather than BF allocation of
    ``30% * (6% - 3.6%) = 0.72%``. Selection is 1.6%, interaction is 1.2%, and the
    BHB total is the unadjusted contribution difference
    ``70% * 10% - 40% * 6% = 4.6%``. B has -0.6% allocation and total, leaving both
    methods with the same independently calculated 4.0% period total.
    """
    portfolio, benchmark, _bf_expected = _read_three_effect_fixture(
        "three_effect_positive"
    )
    expected = _read_bhb_expected("three_effect_positive")

    bhb = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    ).set_index("identifier")
    bf = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    ).set_index("identifier")

    for identifier in expected.index:
        for column in expected.columns:
            assert bhb.loc[identifier, column] == pytest.approx(
                expected.loc[identifier, column],
                abs=1e-12,
            )
    assert bhb.loc["A", "allocation_effect"] - bf.loc[
        "A", "allocation_effect"
    ] == pytest.approx(0.30 * 0.036, abs=1e-12)
    assert bhb.loc["B", "allocation_effect"] - bf.loc[
        "B", "allocation_effect"
    ] == pytest.approx(-0.30 * 0.036, abs=1e-12)
    assert bhb["allocation_effect"].sum() == pytest.approx(0.012, abs=1e-12)
    assert bhb["selection_effect"].sum() == pytest.approx(0.016, abs=1e-12)
    assert bhb["interaction_effect"].sum() == pytest.approx(0.012, abs=1e-12)
    assert bhb["total_effect"].sum() == pytest.approx(0.040, abs=1e-12)


def test_bhb_period_detail_uses_authoritative_contributions() -> None:
    """BHB effects should use contribution-implied returns and totals.

    Input returns are deliberately inconsistent with authoritative contributions.
    Those contributions imply effective portfolio returns of 5% and 10% and benchmark
    returns of 4% and 6%. A therefore has 0.4% allocation, 0.5% selection, 0.1%
    interaction, and a 1.0% unadjusted total. B has -0.6%, 2.0%, -0.4%, and 1.0%,
    respectively. The independently calculated period total is 2.0%.
    """
    portfolio, benchmark, _bf_expected = _read_three_effect_fixture(
        "three_effect_authoritative"
    )
    expected = _read_bhb_expected("three_effect_authoritative")

    bhb = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    ).set_index("identifier")
    bf = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    ).set_index("identifier")

    assert bhb.loc["A", "portfolio_return"] == pytest.approx(0.05)
    assert bhb.loc["A", "benchmark_return"] == pytest.approx(0.04)
    assert bhb.loc["B", "portfolio_return"] == pytest.approx(0.10)
    assert bhb.loc["B", "benchmark_return"] == pytest.approx(0.06)
    for identifier in expected.index:
        for column in expected.columns:
            assert bhb.loc[identifier, column] == pytest.approx(
                expected.loc[identifier, column],
                abs=1e-12,
            )
        assert bhb.loc[identifier, "selection_effect"] == pytest.approx(
            bf.loc[identifier, "selection_effect"],
            abs=1e-12,
        )
        assert bhb.loc[identifier, "interaction_effect"] == pytest.approx(
            bf.loc[identifier, "interaction_effect"],
            abs=1e-12,
        )
    assert bhb["total_effect"].sum() == pytest.approx(0.020, abs=1e-12)


def test_bhb_period_detail_preserves_an_undefined_fee_residual() -> None:
    """An unexposed charge should remain in selection without invented interaction.

    The portfolio fee has zero weight, authoritative contribution of -0.1%, and an
    undefined effective return; its absent benchmark side contributes zero facts.
    Active weight and BHB allocation are therefore zero. Because no active return can
    be calculated, interaction is also zero and selection retains the complete -0.1%
    unadjusted active contribution.
    """
    case_path = _FIXTURE_ROOT / "single_period_authoritative"
    portfolio = pd.read_csv(case_path / "portfolio.csv")
    benchmark = pd.read_csv(case_path / "benchmark.csv")

    detail = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    ).set_index("identifier")
    fee = cast(pd.Series, detail.loc["FEE"])

    assert bool(pd.isna(fee["portfolio_return"]))
    assert bool(pd.isna(fee["active_return"]))
    assert fee["active_weight"] == 0.0
    assert fee["allocation_effect"] == 0.0
    assert fee["interaction_effect"] == 0.0
    assert fee["selection_effect"] == pytest.approx(-0.001, abs=1e-12)
    assert fee["total_effect"] == pytest.approx(-0.001, abs=1e-12)


def test_attribution_result_method_default_is_independent_of_frames() -> None:
    """Released construction should receive explicit two-effect method metadata."""
    result = AttributionResult(
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
    )

    assert result.method is AttributionMethod.BRINSON_FACHLER_TWO_EFFECT
