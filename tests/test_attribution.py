"""Tests for the public portable attribution calculation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest

from perfattr import (
    AttributionError,
    AttributionMethod,
    AttributionResult,
    calculate_attribution,
)
from perfattr._schemas import (
    THREE_EFFECT_CUMULATIVE_COLUMNS,
    THREE_EFFECT_OVERALL_DETAIL_COLUMNS,
    THREE_EFFECT_OVERALL_RECONCILIATION_CHECKS,
    THREE_EFFECT_PERIOD_DETAIL_COLUMNS,
    THREE_EFFECT_PERIOD_RECONCILIATION_CHECKS,
    THREE_EFFECT_PERIOD_SUMMARY_COLUMNS,
)


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_SINGLE_PERIOD_CASES = (
    "single_period_derived",
    "single_period_authoritative",
)
_PERIOD_SUMMARY_COLUMNS = """
from_date thru_date quantity_of_days portfolio_return benchmark_return active_return
portfolio_contribution benchmark_contribution active_contribution allocation_effect
selection_effect total_effect linked_portfolio_contribution
linked_benchmark_contribution linked_active_contribution linked_allocation_effect
linked_selection_effect linked_total_effect
""".split()
_OVERALL_DETAIL_COLUMNS = """
from_date thru_date identifier portfolio_weight portfolio_return
linked_portfolio_contribution benchmark_weight benchmark_return
linked_benchmark_contribution active_weight active_return linked_active_contribution
linked_allocation_effect linked_selection_effect linked_total_effect
""".split()
_CUMULATIVE_COLUMNS = """
from_date thru_date portfolio_return benchmark_return active_return
cumulative_portfolio_return cumulative_benchmark_return cumulative_active_return
linked_portfolio_contribution linked_benchmark_contribution linked_active_contribution
cumulative_portfolio_contribution cumulative_benchmark_contribution
cumulative_active_contribution linked_allocation_effect linked_selection_effect
linked_total_effect cumulative_allocation_effect cumulative_selection_effect
cumulative_total_effect
""".split()
_RECONCILIATION_COLUMNS = """
scope from_date thru_date check actual expected residual tolerance passed
""".split()


def _read_inputs(case_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read a fixture's two prepared input frames."""
    case_path = _FIXTURE_ROOT / case_name
    return (
        pd.read_csv(case_path / "portfolio.csv"),
        pd.read_csv(case_path / "benchmark.csv"),
    )


def _read_expected_detail(case_name: str) -> pd.DataFrame:
    """Read and normalize a fixture's literal expected detail frame."""
    expected = pd.read_csv(
        _FIXTURE_ROOT / case_name / "expected_period_detail.csv"
    )
    expected["from_date"] = pd.to_datetime(expected["from_date"]).astype(
        "datetime64[ns]"
    )
    expected["thru_date"] = pd.to_datetime(expected["thru_date"]).astype(
        "datetime64[ns]"
    )
    expected["identifier"] = expected["identifier"].astype("string[python]")
    return expected


def _randomized_valid_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create reproducible valid inputs used only for financial invariants."""
    random = np.random.default_rng(20260905)
    periods = (
        ("2024-01-01", "2024-01-31", 31),
        ("2024-02-01", "2024-02-29", 29),
        ("2024-03-01", "2024-03-31", 31),
        ("2024-04-01", "2024-04-30", 30),
    )
    identifiers = tuple(f"G{number}" for number in range(8))
    side_rows: tuple[
        list[tuple[str, str, str, float, float, int]],
        list[tuple[str, str, str, float, float, int]],
    ] = ([], [])
    for from_date, thru_date, quantity_of_days in periods:
        for rows in side_rows:
            weights = random.dirichlet(np.ones(len(identifiers)))
            returns = random.uniform(-0.25, 0.25, len(identifiers))
            rows.extend(
                (
                    from_date,
                    thru_date,
                    identifier,
                    float(weight),
                    float(period_return),
                    quantity_of_days,
                )
                for identifier, weight, period_return in zip(
                    identifiers,
                    weights,
                    returns,
                    strict=True,
                )
            )
    columns = """from_date thru_date identifier weight return
    quantity_of_days""".split()
    return (
        pd.DataFrame(side_rows[0], columns=columns),
        pd.DataFrame(side_rows[1], columns=columns),
    )


@pytest.mark.parametrize("case_name", _SINGLE_PERIOD_CASES)
def test_calculate_attribution_matches_independent_period_detail(
    case_name: str,
) -> None:
    """The public calculation should match independently calculated fixtures."""
    portfolio, benchmark = _read_inputs(case_name)

    result = calculate_attribution(portfolio, benchmark)

    assert isinstance(result, AttributionResult)
    assert result.method is AttributionMethod.BRINSON_FACHLER_TWO_EFFECT
    pd.testing.assert_frame_equal(
        result.period_detail,
        _read_expected_detail(case_name),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def test_calculation_rejects_an_unvalidated_method_string() -> None:
    """A method name must not silently select a financial calculation policy."""
    portfolio, benchmark = _read_inputs("single_period_derived")
    invalid_method = cast(
        AttributionMethod,
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT.value,
    )

    with pytest.raises(TypeError, match="method must be an AttributionMethod"):
        calculate_attribution(portfolio, benchmark, method=invalid_method)


def test_bhb_method_returns_its_complete_public_schema() -> None:
    """The public BHB method should reuse every released three-effect schema."""
    portfolio, benchmark = _read_inputs("single_period_derived")

    result = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    )

    assert result.method is AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT
    assert tuple(result.period_detail.columns) == THREE_EFFECT_PERIOD_DETAIL_COLUMNS
    assert tuple(result.period_summary.columns) == THREE_EFFECT_PERIOD_SUMMARY_COLUMNS
    assert tuple(result.overall_detail.columns) == THREE_EFFECT_OVERALL_DETAIL_COLUMNS
    assert tuple(result.cumulative.columns) == THREE_EFFECT_CUMULATIVE_COLUMNS
    assert list(result.reconciliation["check"]) == [
        *THREE_EFFECT_PERIOD_RECONCILIATION_CHECKS,
        *THREE_EFFECT_OVERALL_RECONCILIATION_CHECKS,
    ]
    assert bool(result.reconciliation["passed"].to_numpy().all())


def test_three_effect_method_returns_its_complete_public_schema() -> None:
    """The opt-in method should expose interaction in every approved result frame."""
    portfolio, benchmark = _read_inputs("single_period_derived")

    result = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    )

    assert result.method is AttributionMethod.BRINSON_FACHLER_THREE_EFFECT
    assert tuple(result.period_detail.columns) == THREE_EFFECT_PERIOD_DETAIL_COLUMNS
    assert tuple(result.period_summary.columns) == THREE_EFFECT_PERIOD_SUMMARY_COLUMNS
    assert tuple(result.overall_detail.columns) == THREE_EFFECT_OVERALL_DETAIL_COLUMNS
    assert tuple(result.cumulative.columns) == THREE_EFFECT_CUMULATIVE_COLUMNS
    assert list(result.reconciliation["check"]) == [
        *THREE_EFFECT_PERIOD_RECONCILIATION_CHECKS,
        *THREE_EFFECT_OVERALL_RECONCILIATION_CHECKS,
    ]
    assert bool(result.reconciliation["passed"].to_numpy().all())


def test_explicit_two_effect_method_is_exactly_the_released_default() -> None:
    """Selecting the released method explicitly must not alter its numerical path.

    Exact frame equality, rather than tolerance-based equality, protects the approved
    promise that adding method selection does not route the default calculation
    through a rewritten formula or change any value, null, dtype, row, or column.
    """
    portfolio, benchmark = _read_inputs("multi_period_linking")

    default_result = calculate_attribution(portfolio, benchmark)
    explicit_result = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
    )

    for frame_name in (
        "period_detail",
        "period_summary",
        "overall_detail",
        "cumulative",
        "reconciliation",
    ):
        pd.testing.assert_frame_equal(
            getattr(default_result, frame_name),
            getattr(explicit_result, frame_name),
            check_exact=True,
        )


def test_result_frames_follow_the_specified_contract() -> None:
    """Every result frame should have stable schemas, ordering, and reconciliations."""
    portfolio, benchmark = _read_inputs("single_period_derived")

    result = calculate_attribution(portfolio, benchmark)

    assert list(result.period_summary.columns) == _PERIOD_SUMMARY_COLUMNS
    assert list(result.overall_detail.columns) == _OVERALL_DETAIL_COLUMNS
    assert list(result.cumulative.columns) == _CUMULATIVE_COLUMNS
    assert list(result.reconciliation.columns) == _RECONCILIATION_COLUMNS
    for frame in (
        result.period_detail,
        result.period_summary,
        result.overall_detail,
        result.cumulative,
        result.reconciliation,
    ):
        assert isinstance(frame.index, pd.RangeIndex)
        assert frame.index.start == 0
        assert frame.index.step == 1

    summary = result.period_summary.iloc[0]
    assert summary["portfolio_return"] == pytest.approx(0.024)
    assert summary["benchmark_return"] == pytest.approx(0.034)
    assert summary["allocation_effect"] == pytest.approx(-0.007)
    assert summary["selection_effect"] == pytest.approx(-0.003)
    assert summary["total_effect"] == pytest.approx(-0.01)
    assert all(result.reconciliation["passed"])
    expected_checks = """portfolio_weight benchmark_weight portfolio_contribution
    benchmark_contribution active_contribution effect_components total_effect
    linked_portfolio_contribution linked_benchmark_contribution
    linked_active_contribution linked_effect_components linked_total_effect""".split()
    assert list(result.reconciliation["check"]) == expected_checks


@pytest.mark.parametrize("method", tuple(AttributionMethod))
def test_identical_inputs_have_zero_active_values_and_effects(
    method: AttributionMethod,
) -> None:
    """Identical portfolio and benchmark facts must produce no active result.

    This portable invariant previously had explicit coverage only through the ppar
    host workflow. Keeping it beside the authoritative calculation protects every
    consumer while allowing the host suite to retain only boundary-focused examples.
    """
    portfolio, _benchmark = _read_inputs("multi_period_linking")

    result = calculate_attribution(
        portfolio,
        portfolio.copy(deep=True),
        method=method,
    )

    zero_columns = """active_weight active_return active_contribution
    allocation_effect selection_effect total_effect linked_active_contribution
    linked_allocation_effect linked_selection_effect linked_total_effect""".split()
    if method is not AttributionMethod.BRINSON_FACHLER_TWO_EFFECT:
        zero_columns.extend(("interaction_effect", "linked_interaction_effect"))
    for column in zero_columns:
        assert result.period_detail[column].abs().max() == pytest.approx(0.0, abs=1e-12)
    assert result.cumulative["cumulative_active_return"].abs().max() == pytest.approx(
        0.0,
        abs=1e-12,
    )


def test_portfolio_weighted_selection_absorbs_interaction() -> None:
    """Released selection equals conventional selection plus interaction.

    For fixture identifier A, portfolio and benchmark weights are 70% and 60%, and
    their returns are 8% and 5%. Conventional benchmark-weighted selection is 1.8%,
    while interaction is 0.3%. The portable two-effect convention reports their 2.1% sum as
    portfolio-weighted selection and does not expose a separate interaction column.
    """
    portfolio, benchmark = _read_inputs("single_period_derived")

    result = calculate_attribution(portfolio, benchmark)

    detail = result.period_detail.set_index("identifier")
    conventional_selection = 0.60 * (0.08 - 0.05)
    conventional_interaction = (0.70 - 0.60) * (0.08 - 0.05)
    assert detail.loc["A", "selection_effect"] == pytest.approx(
        conventional_selection + conventional_interaction,
        abs=1e-12,
    )
    assert "interaction_effect" not in result.period_detail.columns


@pytest.mark.parametrize("cash_weight", [0.10, -0.10, 0.0])
def test_cash_uses_ordinary_identifier_effects(cash_weight: float) -> None:
    """Positive, negative, and zero cash should use the ordinary Brinson formulas.

    The benchmark has no cash row, so universe equalization supplies zero benchmark
    cash exposure and return. With an 8% total benchmark return, cash allocation is
    ``cash_weight * (0% - 8%)``. Portfolio-weighted selection is the cash contribution
    itself, and their sum is the cash total effect. This independently demonstrates
    that neither the identifier text nor the sign of its weight activates special
    cash handling.
    """
    columns = """from_date thru_date identifier weight return
    quantity_of_days""".split()
    portfolio = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "ASSET", 1.0 - cash_weight, 0.10, 31),
            ("2024-01-01", "2024-01-31", "CASH_USD", cash_weight, 0.01, 31),
        ],
        columns=columns,
    )
    benchmark = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "ASSET", 1.0, 0.08, 31)],
        columns=columns,
    )

    result = calculate_attribution(portfolio, benchmark)

    cash = result.period_detail.loc[
        result.period_detail["identifier"] == "CASH_USD"
    ].iloc[0]
    expected_contribution = cash_weight * 0.01
    expected_allocation = cash_weight * (0.0 - 0.08)
    expected_selection = expected_contribution
    expected_effective_return = 0.01 if cash_weight != 0.0 else 0.0
    assert cash["portfolio_weight"] == pytest.approx(cash_weight)
    assert cash["portfolio_return"] == pytest.approx(expected_effective_return)
    assert cash["portfolio_contribution"] == pytest.approx(expected_contribution)
    assert cash["benchmark_weight"] == 0.0
    assert cash["benchmark_return"] == 0.0
    assert cash["allocation_effect"] == pytest.approx(expected_allocation)
    assert cash["selection_effect"] == pytest.approx(expected_selection)
    assert cash["total_effect"] == pytest.approx(
        expected_allocation + expected_selection
    )
    assert all(result.reconciliation["passed"])


def test_authoritative_contribution_preserves_distinct_return_semantics() -> None:
    """Authoritative input returns and unexposed charges retain distinct semantics.

    The asset's supplied 5.0% return remains its compoundable horizon return even
    though its authoritative period contribution implies a 5.1% effective return. The
    independently prepared fixture also assigns a -0.1% fee no exposure and therefore
    no effective return. Zero active weight makes allocation zero; the released
    selection convention carries the full -0.1% active contribution.
    """
    portfolio, benchmark = _read_inputs("single_period_authoritative")

    result = calculate_attribution(portfolio, benchmark)

    period_asset = result.period_detail.loc[
        result.period_detail["identifier"] == "ASSET"
    ].iloc[0]
    overall_asset = result.overall_detail.loc[
        result.overall_detail["identifier"] == "ASSET"
    ].iloc[0]
    fee = result.overall_detail.loc[
        result.overall_detail["identifier"] == "FEE"
    ].iloc[0]
    period_fee = result.period_detail.loc[
        result.period_detail["identifier"] == "FEE"
    ].iloc[0]
    assert period_asset["portfolio_return"] == pytest.approx(0.051)
    assert overall_asset["portfolio_return"] == pytest.approx(0.05)
    assert overall_asset["linked_portfolio_contribution"] == pytest.approx(0.051)
    assert period_fee["portfolio_weight"] == 0.0
    assert period_fee["portfolio_contribution"] == pytest.approx(-0.001)
    assert period_fee["allocation_effect"] == 0.0
    assert period_fee["selection_effect"] == pytest.approx(-0.001)
    assert period_fee["total_effect"] == pytest.approx(-0.001)
    assert pd.isna(fee["portfolio_return"])
    assert pd.isna(fee["active_return"])
    assert fee["linked_portfolio_contribution"] == pytest.approx(-0.001)


@pytest.mark.parametrize(
    "method",
    (
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    ),
)
def test_three_effect_preserves_authoritative_fee_through_public_result(
    method: AttributionMethod,
) -> None:
    """The complete three-effect path should retain an unexposed accounting charge.

    The asset's 5.1% authoritative contribution implies a 5.1% effective period
    return despite its supplied 5.0% input return. The fee has zero weight, null
    return, and -0.1% contribution on the portfolio side and is absent from the
    benchmark. Its active weight is therefore zero: allocation and interaction are
    zero, while selection and total retain the entire -0.1% accounting result.
    """
    portfolio, benchmark = _read_inputs("single_period_authoritative")

    three_effect = calculate_attribution(
        portfolio,
        benchmark,
        method=method,
    )
    two_effect = calculate_attribution(portfolio, benchmark)
    detail = three_effect.period_detail.set_index("identifier")
    fee = cast(pd.Series, detail.loc["FEE"])

    assert detail.loc["ASSET", "portfolio_return"] == pytest.approx(0.051)
    assert bool(pd.isna(fee["portfolio_return"]))
    assert bool(pd.isna(fee["active_return"]))
    assert fee["allocation_effect"] == 0.0
    assert fee["interaction_effect"] == 0.0
    assert fee["selection_effect"] == pytest.approx(-0.001, abs=1e-12)
    assert fee["total_effect"] == pytest.approx(-0.001, abs=1e-12)
    np.testing.assert_allclose(
        three_effect.period_detail["selection_effect"]
        + three_effect.period_detail["interaction_effect"],
        two_effect.period_detail["selection_effect"],
        rtol=1e-12,
        atol=1e-12,
    )


@pytest.mark.parametrize(
    "method",
    (
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    ),
)
def test_three_effect_handles_missing_sides_signed_and_zero_weights(
    method: AttributionMethod,
) -> None:
    """Ordinary universe rules should govern signed, absent, and neutral rows.

    C exists only in the portfolio at weight -10% and return 20%, so its missing
    benchmark side is zero and interaction is ``-10% * 20% = -2%``. D exists only in
    the benchmark at weight 10% and return 10%, producing active weight and return of
    -10% and interaction +1%. E is an explicit zero-weight, null-input-return row;
    normalization gives it zero effective return and every effect remains zero.
    """
    portfolio, benchmark = _read_inputs("single_period_derived")

    result = calculate_attribution(
        portfolio,
        benchmark,
        method=method,
    )
    detail = result.period_detail.set_index("identifier")

    assert detail.loc["C", "benchmark_weight"] == 0.0
    assert detail.loc["C", "benchmark_return"] == 0.0
    assert detail.loc["C", "interaction_effect"] == pytest.approx(-0.02, abs=1e-12)
    assert detail.loc["C", "selection_effect"] == 0.0
    assert detail.loc["D", "portfolio_weight"] == 0.0
    assert detail.loc["D", "portfolio_return"] == 0.0
    assert detail.loc["D", "interaction_effect"] == pytest.approx(0.01, abs=1e-12)
    assert detail.loc["D", "selection_effect"] == pytest.approx(-0.01, abs=1e-12)
    assert detail.loc["E", "portfolio_weight"] == 0.0
    assert detail.loc["E", "portfolio_return"] == 0.0
    assert detail.loc["E", "interaction_effect"] == 0.0
    assert detail.loc["E", "total_effect"] == 0.0


@pytest.mark.parametrize("method", tuple(AttributionMethod))
def test_calculation_is_deterministic_and_does_not_mutate_inputs(
    method: AttributionMethod,
) -> None:
    """Row order should not matter and caller-owned frames should remain unchanged."""
    portfolio, benchmark = _read_inputs("multi_period_linking")
    portfolio_before = portfolio.copy(deep=True)
    benchmark_before = benchmark.copy(deep=True)

    ordered = calculate_attribution(portfolio, benchmark, method=method)
    shuffled = calculate_attribution(
        portfolio.sample(frac=1.0, random_state=7),
        benchmark.sample(frac=1.0, random_state=11),
        method=method,
    )

    pd.testing.assert_frame_equal(portfolio, portfolio_before)
    pd.testing.assert_frame_equal(benchmark, benchmark_before)
    for frame_name in (
        "period_detail",
        "period_summary",
        "overall_detail",
        "cumulative",
        "reconciliation",
    ):
        pd.testing.assert_frame_equal(
            getattr(ordered, frame_name), getattr(shuffled, frame_name)
        )
    original_overall_value = ordered.overall_detail.at[0, "portfolio_weight"]
    original_second_value = shuffled.period_detail.at[0, "portfolio_weight"]
    ordered.period_detail.at[0, "portfolio_weight"] = 999.0
    assert ordered.overall_detail.at[0, "portfolio_weight"] == original_overall_value
    assert shuffled.period_detail.at[0, "portfolio_weight"] == original_second_value


@pytest.mark.parametrize("case_name", ("multi_period_linking", "linking_boundaries"))
def test_multi_period_linking_matches_independent_detail(case_name: str) -> None:
    """Linked detail should match hand-calculated regular and boundary fixtures."""
    portfolio, benchmark = _read_inputs(case_name)

    result = calculate_attribution(portfolio, benchmark)

    pd.testing.assert_frame_equal(
        result.period_detail,
        _read_expected_detail(case_name),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def test_three_effect_multi_period_linking_matches_hand_calculation() -> None:
    """All linked effect channels should match independent two-period values.

    Period-one Carino coefficient 1.0009785331840475 multiplies unlinked interactions
    of 0.2% for both Bonds and Equity. Period two uses coefficient
    1.0549821109867057 on interactions -0.05% and -0.2%. Three-effect selections are
    benchmark weight times active return: -1.0%, +1.0%, +0.3%, and -0.8% before the
    same coefficients are applied. The literals below were hand-derived from those
    values and the independently documented coefficients in the fixture provenance.
    """
    portfolio, benchmark = _read_inputs("multi_period_linking")

    three_effect = calculate_attribution(
        portfolio,
        benchmark,
        method=AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    )
    two_effect = calculate_attribution(portfolio, benchmark)

    detail = three_effect.period_detail.set_index(["thru_date", "identifier"])
    expected = {
        (pd.Timestamp("2024-01-31"), "Bonds"): (
            -0.010009785331840475,
            0.002001957066368095,
        ),
        (pd.Timestamp("2024-01-31"), "Equity"): (
            0.010009785331840475,
            0.002001957066368095,
        ),
        (pd.Timestamp("2024-02-29"), "Bonds"): (
            0.003164946332960117,
            -0.0005274910554933529,
        ),
        (pd.Timestamp("2024-02-29"), "Equity"): (
            -0.008439856887893647,
            -0.0021099642219734116,
        ),
    }
    for key, (selection, interaction) in expected.items():
        assert detail.loc[key, "linked_selection_effect"] == pytest.approx(
            selection,
            abs=1e-12,
        )
        assert detail.loc[key, "linked_interaction_effect"] == pytest.approx(
            interaction,
            abs=1e-12,
        )

    np.testing.assert_allclose(
        three_effect.period_detail["linked_selection_effect"]
        + three_effect.period_detail["linked_interaction_effect"],
        two_effect.period_detail["linked_selection_effect"],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        three_effect.period_summary["linked_interaction_effect"],
        [0.00400391413273619, -0.0026374552774667645],
        rtol=1e-12,
        atol=1e-12,
    )
    overall = three_effect.overall_detail.set_index("identifier")
    assert overall.loc["Bonds", "linked_interaction_effect"] == pytest.approx(
        0.001474466010874742,
        abs=1e-12,
    )
    assert overall.loc["Equity", "linked_interaction_effect"] == pytest.approx(
        -0.00010800715560531663,
        abs=1e-12,
    )
    final = three_effect.cumulative.iloc[-1]
    assert final["cumulative_selection_effect"] == pytest.approx(
        -0.0052749105549335295,
        abs=1e-12,
    )
    assert final["cumulative_interaction_effect"] == pytest.approx(
        0.0013664588552694257,
        abs=1e-12,
    )
    assert (
        final["cumulative_allocation_effect"]
        + final["cumulative_selection_effect"]
        + final["cumulative_interaction_effect"]
    ) == pytest.approx(final["cumulative_total_effect"], abs=1e-12)


@pytest.mark.parametrize(
    "method",
    (
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    ),
)
@pytest.mark.parametrize("case_name", ("multi_period_linking", "linking_boundaries"))
def test_three_effect_linking_limits_reconcile(
    case_name: str,
    method: AttributionMethod,
) -> None:
    """Regular and near-limit Carino cases must retain every additive identity.

    The boundary fixture includes equal active-side period returns and compounded
    returns close to -100%, exercising the released analytic Carino limits. This test
    does not invent separate expected values; it verifies the production
    reconciliation evidence and independently sums the three linked channels for
    every returned detail row.
    """
    portfolio, benchmark = _read_inputs(case_name)

    result = calculate_attribution(
        portfolio,
        benchmark,
        method=method,
    )

    np.testing.assert_allclose(
        result.period_detail["linked_allocation_effect"]
        + result.period_detail["linked_selection_effect"]
        + result.period_detail["linked_interaction_effect"],
        result.period_detail["linked_total_effect"],
        rtol=1e-12,
        atol=1e-12,
    )
    assert bool(result.reconciliation["passed"].to_numpy().all())


@pytest.mark.parametrize(
    "method",
    (
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    ),
)
def test_randomized_three_effect_inputs_preserve_only_independent_invariants(
    method: AttributionMethod,
) -> None:
    """Reproducible varied inputs should preserve every additive identity.

    Random data broadens the combinations of active weights and returns but is never
    used to manufacture expected values. The assertions come independently from the
    governing identities: three-effect selection plus interaction collapses to the
    released two-effect selection, three simple effects equal total per row, and the
    same identity survives Carino linking per row and over the complete horizon.
    """
    portfolio, benchmark = _randomized_valid_inputs()

    two_effect = calculate_attribution(portfolio, benchmark)
    three_effect = calculate_attribution(
        portfolio,
        benchmark,
        method=method,
    )

    np.testing.assert_allclose(
        three_effect.period_detail["selection_effect"]
        + three_effect.period_detail["interaction_effect"],
        two_effect.period_detail["selection_effect"],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        three_effect.period_detail["allocation_effect"]
        + three_effect.period_detail["selection_effect"]
        + three_effect.period_detail["interaction_effect"],
        three_effect.period_detail["total_effect"],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        three_effect.period_detail["linked_allocation_effect"]
        + three_effect.period_detail["linked_selection_effect"]
        + three_effect.period_detail["linked_interaction_effect"],
        three_effect.period_detail["linked_total_effect"],
        rtol=1e-12,
        atol=1e-12,
    )
    final = three_effect.cumulative.iloc[-1]
    assert (
        final["cumulative_allocation_effect"]
        + final["cumulative_selection_effect"]
        + final["cumulative_interaction_effect"]
    ) == pytest.approx(final["cumulative_total_effect"], abs=1e-12)
    assert bool(three_effect.reconciliation["passed"].to_numpy().all())


def test_multi_period_horizon_and_cumulative_contract() -> None:
    """Overall and cumulative frames should follow the full-horizon specification."""
    portfolio, benchmark = _read_inputs("multi_period_linking")

    result = calculate_attribution(portfolio, benchmark)

    assert len(result.period_summary) == 2
    assert len(result.cumulative) == 2
    final_cumulative = result.cumulative.iloc[-1]
    assert final_cumulative["cumulative_portfolio_return"] == pytest.approx(0.0547)
    assert final_cumulative["cumulative_benchmark_return"] == pytest.approx(0.05735)
    assert final_cumulative["cumulative_active_return"] == pytest.approx(-0.00265)
    assert final_cumulative["cumulative_portfolio_contribution"] == pytest.approx(
        0.0547
    )
    assert final_cumulative["cumulative_benchmark_contribution"] == pytest.approx(
        0.05735
    )
    assert final_cumulative["cumulative_total_effect"] == pytest.approx(-0.00265)

    bonds = result.overall_detail.loc[
        result.overall_detail["identifier"] == "Bonds"
    ].iloc[0]
    equity = result.overall_detail.loc[
        result.overall_detail["identifier"] == "Equity"
    ].iloc[0]
    assert bonds["portfolio_weight"] == pytest.approx((0.4 * 31 + 0.5 * 29) / 60)
    assert equity["benchmark_weight"] == pytest.approx((0.5 * 31 + 0.4 * 29) / 60)
    assert bonds["portfolio_return"] == pytest.approx(0.03)
    assert equity["portfolio_return"] == pytest.approx((1.1 * 0.96) - 1.0)
    assert list(result.overall_detail["identifier"]) == ["Bonds", "Equity"]

    assert len(result.reconciliation) == 19
    assert list(result.reconciliation["scope"]) == ["period"] * 14 + ["overall"] * 5
    assert all(result.reconciliation["passed"])


def test_overall_return_preserves_explicit_null_across_periods() -> None:
    """One explicit undefined supplied return should make its horizon return null."""
    portfolio, benchmark = _read_inputs("single_period_authoritative")
    second_portfolio = portfolio.copy(deep=True)
    second_benchmark = benchmark.copy(deep=True)
    for frame in (second_portfolio, second_benchmark):
        frame["from_date"] = "2024-03-01"
        frame["thru_date"] = "2024-03-31"
        frame["quantity_of_days"] = 31
    portfolio = pd.concat([portfolio, second_portfolio], ignore_index=True)
    benchmark = pd.concat([benchmark, second_benchmark], ignore_index=True)

    result = calculate_attribution(portfolio, benchmark)

    asset = result.overall_detail.loc[
        result.overall_detail["identifier"] == "ASSET"
    ].iloc[0]
    fee = result.overall_detail.loc[
        result.overall_detail["identifier"] == "FEE"
    ].iloc[0]
    assert asset["portfolio_return"] == pytest.approx((1.05**2) - 1.0)
    assert pd.isna(fee["portfolio_return"])
    assert pd.isna(fee["active_return"])


def test_identifier_absent_from_a_period_has_neutral_horizon_inputs() -> None:
    """A wholly absent identifier-period should add zero return and zero weight."""
    columns = """from_date thru_date identifier weight return
    quantity_of_days""".split()
    portfolio = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "A", 1.0, 0.1, 31),
            ("2024-02-01", "2024-02-29", "B", 1.0, 0.2, 29),
        ],
        columns=columns,
    )
    benchmark = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "INDEX", 1.0, 0.0, 31),
            ("2024-02-01", "2024-02-29", "INDEX", 1.0, 0.0, 29),
        ],
        columns=columns,
    )

    result = calculate_attribution(portfolio, benchmark)

    asset_a = result.overall_detail.loc[
        result.overall_detail["identifier"] == "A"
    ].iloc[0]
    asset_b = result.overall_detail.loc[
        result.overall_detail["identifier"] == "B"
    ].iloc[0]
    assert asset_a["portfolio_weight"] == pytest.approx(31 / 60)
    assert asset_b["portfolio_weight"] == pytest.approx(29 / 60)
    assert asset_a["portfolio_return"] == pytest.approx(0.1)
    assert asset_b["portfolio_return"] == pytest.approx(0.2)


@pytest.mark.parametrize(
    ("column", "invalid_value", "message"),
    (
        ("weight", "1.0", "numbers, not strings or booleans"),
        ("return", -1.0, "greater than -1.0"),
        ("quantity_of_days", 0, "positive integers"),
        ("identifier", "   ", "empty string"),
    ),
)
def test_invalid_prepared_values_are_rejected(
    column: str,
    invalid_value: str | float,
    message: str,
) -> None:
    """Ambiguous or invalid prepared values should raise clear financial errors."""
    portfolio, benchmark = _read_inputs("single_period_derived")
    if isinstance(invalid_value, str) and column != "identifier":
        portfolio[column] = portfolio[column].astype("object")
    portfolio.loc[0, column] = invalid_value

    with pytest.raises(AttributionError, match=message):
        calculate_attribution(portfolio, benchmark)


def test_partial_or_inconsistent_authoritative_contribution_is_rejected() -> None:
    """Authoritative contribution must be complete and obey undefined-return rules."""
    portfolio, benchmark = _read_inputs("single_period_authoritative")
    portfolio.loc[0, "contribution"] = float("nan")
    with pytest.raises(AttributionError, match="contribution.*null"):
        calculate_attribution(portfolio, benchmark)

    portfolio, benchmark = _read_inputs("single_period_authoritative")
    portfolio.loc[1, "return"] = 0.0
    with pytest.raises(AttributionError, match="requires a null return"):
        calculate_attribution(portfolio, benchmark)


def test_structural_input_contract_is_enforced() -> None:
    """Required schema, unique keys, matched coverage, and net weights are mandatory."""
    portfolio, benchmark = _read_inputs("single_period_derived")
    with pytest.raises(AttributionError, match="missing required columns: return"):
        calculate_attribution(portfolio.drop(columns="return"), benchmark)

    portfolio, benchmark = _read_inputs("single_period_derived")
    duplicate = pd.concat([portfolio, portfolio.iloc[[0]]], ignore_index=True)
    with pytest.raises(AttributionError, match="duplicate period and identifier key"):
        calculate_attribution(duplicate, benchmark)

    portfolio, benchmark = _read_inputs("single_period_derived")
    portfolio.loc[0, "weight"] = 0.71
    with pytest.raises(AttributionError, match="weights must sum to 1.0"):
        calculate_attribution(portfolio, benchmark)

    portfolio, benchmark = _read_inputs("single_period_derived")
    benchmark["quantity_of_days"] = 30
    with pytest.raises(AttributionError, match="quantity_of_days must match"):
        calculate_attribution(portfolio, benchmark)

    portfolio, benchmark = _read_inputs("single_period_derived")
    benchmark["thru_date"] = "2024-02-01"
    with pytest.raises(AttributionError, match="periods must match exactly"):
        calculate_attribution(portfolio, benchmark)


def test_explicit_compatibility_tolerance_preserves_raw_calculation_values() -> None:
    """A wider host tolerance accepts small residuals without normalizing weights."""
    portfolio, benchmark = _read_inputs("single_period_derived")
    adjusted_weight = cast(float, portfolio.at[0, "weight"]) + 3e-10
    portfolio_return = cast(float, portfolio.at[0, "return"])
    portfolio.at[0, "weight"] = adjusted_weight

    with pytest.raises(AttributionError, match="weights must sum to 1.0"):
        calculate_attribution(portfolio, benchmark)

    result = calculate_attribution(
        portfolio,
        benchmark,
        reconciliation_tolerance=5e-9,
    )

    first_row = result.period_detail.iloc[0]
    assert first_row["portfolio_weight"] == adjusted_weight
    assert first_row["portfolio_contribution"] == pytest.approx(
        adjusted_weight * portfolio_return,
        rel=0.0,
        abs=0.0,
    )
    assert (result.reconciliation["tolerance"] == 5e-9).all()
    assert bool(result.reconciliation["passed"].to_numpy().all())


@pytest.mark.parametrize(
    ("tolerance", "error_type"),
    (
        (True, TypeError),
        ("5e-9", TypeError),
        (0.0, AttributionError),
        (-1e-12, AttributionError),
        (float("nan"), AttributionError),
        (float("inf"), AttributionError),
    ),
)
def test_reconciliation_tolerance_must_be_positive_and_finite(
    tolerance: object,
    error_type: type[Exception],
) -> None:
    """Invalid compatibility tolerances fail before financial calculation."""
    portfolio, benchmark = _read_inputs("single_period_derived")

    with pytest.raises(error_type, match="reconciliation_tolerance"):
        calculate_attribution(
            portfolio,
            benchmark,
            reconciliation_tolerance=cast(float, tolerance),
        )


def test_nonzero_weight_requires_a_return() -> None:
    """A nonzero exposure cannot have a mathematically undefined input return."""
    portfolio, benchmark = _read_inputs("single_period_derived")
    portfolio.loc[0, "return"] = float("nan")

    with pytest.raises(AttributionError, match="nonzero weight with a null return"):
        calculate_attribution(portfolio, benchmark)


def test_non_dataframe_input_raises_type_error() -> None:
    """The public boundary should distinguish invalid object types from bad data."""
    _, benchmark = _read_inputs("single_period_derived")

    with pytest.raises(TypeError, match="portfolio must be a pandas DataFrame"):
        calculate_attribution([], benchmark)  # type: ignore[arg-type]
