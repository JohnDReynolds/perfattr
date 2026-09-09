"""Tests for attribution-method schemas and public metadata."""

from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from perfattr import AttributionMethod, AttributionResult, EffectLinkingMethod
from perfattr._prepared_input import _equalize_universe, _normalize_input
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
from perfattr.attribution import _build_period_detail
from perfattr.method import uses_bhb_allocation, uses_explicit_interaction


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


def test_explicit_interaction_policy_identifies_only_three_effect_methods() -> None:
    """Schema routing should exclude both compact reporting methods."""
    assert not uses_explicit_interaction(
        AttributionMethod.BRINSON_FACHLER_TWO_EFFECT
    )
    assert uses_explicit_interaction(
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT
    )
    assert uses_explicit_interaction(
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT
    )
    assert not uses_explicit_interaction(
        AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT
    )


def test_bhb_policy_identifies_both_bhb_reporting_methods() -> None:
    """One policy predicate should identify BHB independently of result shape."""
    assert not uses_bhb_allocation(
        AttributionMethod.BRINSON_FACHLER_TWO_EFFECT
    )
    assert not uses_bhb_allocation(
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT
    )
    assert uses_bhb_allocation(
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT
    )
    assert uses_bhb_allocation(
        AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT
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


def _read_bhb_two_effect_expected(case_name: str) -> pd.DataFrame:
    """Read one original hand-calculated compact BHB expectation table."""
    return pd.read_csv(
        _FIXTURE_ROOT / case_name / "expected_bhb_two_effects.csv"
    ).set_index("identifier")


def _scalar(frame: pd.DataFrame, row: str, column: str) -> float:
    """Return a known scalar fixture value with precise static typing."""
    return cast(float, frame.at[row, column])


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
        assert _scalar(two_effect, identifier, "selection_effect") == pytest.approx(
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
            assert _scalar(detail, str(identifier), str(column)) == pytest.approx(
                _scalar(expected, str(identifier), str(column)),
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
            assert _scalar(bhb, str(identifier), str(column)) == pytest.approx(
                _scalar(expected, str(identifier), str(column)),
                abs=1e-12,
            )
    bhb_allocation = cast(pd.Series, bhb["allocation_effect"])
    bf_allocation = cast(pd.Series, bf["allocation_effect"])
    bhb_a = cast(float, bhb_allocation.at["A"])
    bhb_b = cast(float, bhb_allocation.at["B"])
    bf_a = cast(float, bf_allocation.at["A"])
    bf_b = cast(float, bf_allocation.at["B"])
    assert bhb_a - bf_a == pytest.approx(
        0.30 * 0.036,
        abs=1e-12,
    )
    assert bhb_b - bf_b == pytest.approx(
        -0.30 * 0.036,
        abs=1e-12,
    )
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
            assert _scalar(bhb, str(identifier), str(column)) == pytest.approx(
                _scalar(expected, str(identifier), str(column)),
                abs=1e-12,
            )
        assert _scalar(bhb, str(identifier), "selection_effect") == pytest.approx(
            _scalar(bf, str(identifier), "selection_effect"),
            abs=1e-12,
        )
        assert _scalar(bhb, str(identifier), "interaction_effect") == pytest.approx(
            _scalar(bf, str(identifier), "interaction_effect"),
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


def test_bhb_two_effect_matches_hand_calculated_positive_case() -> None:
    """Compact BHB should absorb interaction without changing allocation or total.

    Group A retains BHB allocation 1.8% and unadjusted total 4.6%. Its compact
    selection is the exact residual 4.6% - 1.8% = 2.8%, independently equal to BHB
    three-effect selection 1.6% plus interaction 1.2%. Group B retains -0.6%
    allocation and total with zero selection. Period allocation 1.2% plus selection
    2.8% therefore reconciles to active return 4.0%.
    """
    portfolio, benchmark, _bf_expected = _read_three_effect_fixture(
        "three_effect_positive"
    )
    expected = _read_bhb_two_effect_expected("three_effect_positive")

    compact = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
    ).set_index("identifier")
    three_effect = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    ).set_index("identifier")
    bf_compact = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
    ).set_index("identifier")

    assert tuple(compact.columns) == tuple(
        column for column in PERIOD_DETAIL_COLUMNS if column != "identifier"
    )
    for identifier in expected.index:
        for column in expected.columns:
            assert _scalar(compact, identifier, column) == pytest.approx(
                _scalar(expected, identifier, column),
                abs=1e-12,
            )
        assert _scalar(compact, identifier, "allocation_effect") == pytest.approx(
            _scalar(three_effect, identifier, "allocation_effect"),
            abs=1e-12,
        )
        assert _scalar(compact, identifier, "total_effect") == pytest.approx(
            _scalar(three_effect, identifier, "total_effect"),
            abs=1e-12,
        )
        assert _scalar(compact, identifier, "selection_effect") == pytest.approx(
            _scalar(three_effect, identifier, "selection_effect")
            + _scalar(three_effect, identifier, "interaction_effect"),
            abs=1e-12,
        )
        assert _scalar(compact, identifier, "selection_effect") == pytest.approx(
            _scalar(bf_compact, identifier, "selection_effect"),
            abs=1e-12,
        )


def test_bhb_two_effect_uses_authoritative_contributions() -> None:
    """Compact BHB should use contribution-implied returns and residual selection.

    Authoritative contributions imply portfolio returns 5% and 10% and benchmark
    returns 4% and 6%, despite deliberately different supplied returns. A retains
    0.4% BHB allocation and 1.0% total, leaving 0.6% compact selection. B retains
    -0.6% allocation and 1.0% total, leaving 1.6% selection. Those selections equal
    the independently calculated BHB three-effect pairs 0.5% + 0.1% and
    2.0% + (-0.4%).
    """
    portfolio, benchmark, _bf_expected = _read_three_effect_fixture(
        "three_effect_authoritative"
    )
    expected = _read_bhb_two_effect_expected("three_effect_authoritative")

    compact = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
    ).set_index("identifier")
    three_effect = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    ).set_index("identifier")

    assert _scalar(compact, "A", "portfolio_return") == pytest.approx(0.05)
    assert _scalar(compact, "A", "benchmark_return") == pytest.approx(0.04)
    assert _scalar(compact, "B", "portfolio_return") == pytest.approx(0.10)
    assert _scalar(compact, "B", "benchmark_return") == pytest.approx(0.06)
    for identifier in expected.index:
        for column in expected.columns:
            assert _scalar(compact, identifier, column) == pytest.approx(
                _scalar(expected, identifier, column),
                abs=1e-12,
            )
        assert _scalar(compact, identifier, "selection_effect") == pytest.approx(
            _scalar(three_effect, identifier, "selection_effect")
            + _scalar(three_effect, identifier, "interaction_effect"),
            abs=1e-12,
        )


def test_bhb_two_effect_preserves_an_undefined_fee_residual() -> None:
    """Compact BHB should retain an unexposed charge without invented interaction.

    The fee has zero portfolio weight, authoritative contribution -0.1%, null
    effective return, and an absent benchmark side. Its active weight and BHB
    allocation are zero, so compact selection retains the entire -0.1% unadjusted
    total. Released BHB three-effect reaches the same compact result through -0.1%
    selection plus its disclosed zero interaction convention.
    """
    case_path = _FIXTURE_ROOT / "single_period_authoritative"
    portfolio = pd.read_csv(case_path / "portfolio.csv")
    benchmark = pd.read_csv(case_path / "benchmark.csv")

    compact = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
    ).set_index("identifier")
    three_effect = _calculate_unlinked_period_detail(
        portfolio,
        benchmark,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    ).set_index("identifier")
    fee = cast(pd.Series, compact.loc["FEE"])

    assert bool(pd.isna(fee["portfolio_return"]))
    assert bool(pd.isna(fee["active_return"]))
    assert "interaction_effect" not in compact.columns
    assert fee["active_weight"] == 0.0
    assert fee["allocation_effect"] == 0.0
    assert fee["selection_effect"] == pytest.approx(-0.001, abs=1e-12)
    assert fee["total_effect"] == pytest.approx(-0.001, abs=1e-12)
    assert _scalar(compact, "FEE", "selection_effect") == pytest.approx(
        _scalar(three_effect, "FEE", "selection_effect")
        + _scalar(three_effect, "FEE", "interaction_effect"),
        abs=1e-12,
    )


def test_attribution_result_policy_defaults_are_independent_of_frames() -> None:
    """Direct construction should receive both released default policy identities."""
    result = AttributionResult(
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
    )

    assert result.method is AttributionMethod.BRINSON_FACHLER_TWO_EFFECT
    assert result.effect_linking_method is EffectLinkingMethod.CARINO

    explicit = AttributionResult(
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )
    assert explicit.effect_linking_method is EffectLinkingMethod.FRONGELLO

    menchero = AttributionResult(
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        effect_linking_method=EffectLinkingMethod.MENCHERO,
    )
    assert menchero.effect_linking_method is EffectLinkingMethod.MENCHERO
