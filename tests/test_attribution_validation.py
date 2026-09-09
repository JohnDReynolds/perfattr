"""Test the public arithmetic attribution input-validation boundary."""

from __future__ import annotations

from typing import cast

import pandas as pd
import pytest

from perfattr import AttributionError, calculate_attribution
from tests.fixture_helpers import read_prepared_inputs


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
    portfolio, benchmark = read_prepared_inputs("single_period_derived")
    if isinstance(invalid_value, str) and column != "identifier":
        portfolio[column] = portfolio[column].astype("object")
    portfolio.loc[0, column] = invalid_value

    with pytest.raises(AttributionError, match=message):
        calculate_attribution(portfolio, benchmark)


def test_partial_or_inconsistent_authoritative_contribution_is_rejected() -> None:
    """Authoritative contribution must be complete and obey undefined-return rules."""
    portfolio, benchmark = read_prepared_inputs("single_period_authoritative")
    portfolio.loc[0, "contribution"] = float("nan")
    with pytest.raises(AttributionError, match="contribution.*null"):
        calculate_attribution(portfolio, benchmark)

    portfolio, benchmark = read_prepared_inputs("single_period_authoritative")
    portfolio.loc[1, "return"] = 0.0
    with pytest.raises(AttributionError, match="requires a null return"):
        calculate_attribution(portfolio, benchmark)


def test_structural_input_contract_is_enforced() -> None:
    """Required schema, unique keys, matched coverage, and net weights are mandatory."""
    portfolio, benchmark = read_prepared_inputs("single_period_derived")
    with pytest.raises(AttributionError, match="missing required columns: return"):
        calculate_attribution(portfolio.drop(columns="return"), benchmark)

    portfolio, benchmark = read_prepared_inputs("single_period_derived")
    duplicate = pd.concat([portfolio, portfolio.iloc[[0]]], ignore_index=True)
    with pytest.raises(AttributionError, match="duplicate period and identifier key"):
        calculate_attribution(duplicate, benchmark)

    portfolio, benchmark = read_prepared_inputs("single_period_derived")
    portfolio.loc[0, "weight"] = 0.71
    with pytest.raises(AttributionError, match="weights must sum to 1.0"):
        calculate_attribution(portfolio, benchmark)

    portfolio, benchmark = read_prepared_inputs("single_period_derived")
    benchmark["quantity_of_days"] = 30
    with pytest.raises(AttributionError, match="quantity_of_days must match"):
        calculate_attribution(portfolio, benchmark)

    portfolio, benchmark = read_prepared_inputs("single_period_derived")
    benchmark["thru_date"] = "2024-02-01"
    with pytest.raises(AttributionError, match="periods must match exactly"):
        calculate_attribution(portfolio, benchmark)


def test_explicit_compatibility_tolerance_preserves_raw_calculation_values() -> None:
    """A wider host tolerance accepts small residuals without normalizing weights."""
    portfolio, benchmark = read_prepared_inputs("single_period_derived")
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
    portfolio, benchmark = read_prepared_inputs("single_period_derived")

    with pytest.raises(error_type, match="reconciliation_tolerance"):
        calculate_attribution(
            portfolio,
            benchmark,
            reconciliation_tolerance=cast(float, tolerance),
        )


def test_nonzero_weight_requires_a_return() -> None:
    """A nonzero exposure cannot have a mathematically undefined input return."""
    portfolio, benchmark = read_prepared_inputs("single_period_derived")
    portfolio.loc[0, "return"] = float("nan")

    with pytest.raises(AttributionError, match="nonzero weight with a null return"):
        calculate_attribution(portfolio, benchmark)


def test_non_dataframe_input_raises_type_error() -> None:
    """The public boundary should distinguish invalid object types from bad data."""
    _, benchmark = read_prepared_inputs("single_period_derived")

    with pytest.raises(TypeError, match="portfolio must be a pandas DataFrame"):
        calculate_attribution([], benchmark)  # type: ignore[arg-type]
