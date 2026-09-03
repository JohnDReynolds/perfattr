"""Tests for the public portable attribution calculation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from perfattr import AttributionError, AttributionResult, calculate_attribution


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


@pytest.mark.parametrize("case_name", _SINGLE_PERIOD_CASES)
def test_calculate_attribution_matches_independent_period_detail(
    case_name: str,
) -> None:
    """The public calculation should match independently calculated fixtures."""
    portfolio, benchmark = _read_inputs(case_name)

    result = calculate_attribution(portfolio, benchmark)

    assert isinstance(result, AttributionResult)
    pd.testing.assert_frame_equal(
        result.period_detail,
        _read_expected_detail(case_name),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
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


def test_authoritative_contribution_preserves_distinct_return_semantics() -> None:
    """Effective period returns must not replace supplied overall returns."""
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
    assert period_asset["portfolio_return"] == pytest.approx(0.051)
    assert overall_asset["portfolio_return"] == pytest.approx(0.05)
    assert overall_asset["linked_portfolio_contribution"] == pytest.approx(0.051)
    assert pd.isna(fee["portfolio_return"])
    assert pd.isna(fee["active_return"])
    assert fee["linked_portfolio_contribution"] == pytest.approx(-0.001)


def test_calculation_is_deterministic_and_does_not_mutate_inputs() -> None:
    """Row order should not matter and caller-owned frames should remain unchanged."""
    portfolio, benchmark = _read_inputs("multi_period_linking")
    portfolio_before = portfolio.copy(deep=True)
    benchmark_before = benchmark.copy(deep=True)

    ordered = calculate_attribution(portfolio, benchmark)
    shuffled = calculate_attribution(
        portfolio.sample(frac=1.0, random_state=7),
        benchmark.sample(frac=1.0, random_state=11),
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
    ordered.period_detail.at[0, "portfolio_weight"] = 999.0
    assert ordered.overall_detail.at[0, "portfolio_weight"] == original_overall_value


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
