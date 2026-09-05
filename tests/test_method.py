"""Tests for attribution-method schemas and public metadata."""

from pathlib import Path

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
