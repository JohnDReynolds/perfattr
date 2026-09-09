"""Test shared performance-row invariants across both portable boundaries."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from perfattr import AttributionError, PreparationError
from perfattr._prepared_input import _normalize_input
from perfattr.preparation import _NormalizedPerformance, _normalize_performance


def _source(
    weights: list[float],
    returns: list[float],
    contributions: list[float] | None = None,
) -> pd.DataFrame:
    """Build one source period for shared row-invariant tests."""
    row_count = len(weights)
    frame = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * row_count,
            "thru_date": ["2024-01-31"] * row_count,
            "identifier": [f"ROW_{index}" for index in range(row_count)],
            "weight": weights,
            "return": returns,
        }
    )
    if contributions is not None:
        frame["contribution"] = contributions
    return frame


def _prepared_input(source: pd.DataFrame) -> pd.DataFrame:
    """Add the calculation boundary's inclusive day-count column."""
    prepared = source.copy(deep=True)
    prepared["quantity_of_days"] = 31
    return prepared


def _normalized_boundaries(
    source: pd.DataFrame,
) -> tuple[_NormalizedPerformance, pd.DataFrame]:
    """Normalize economically identical rows through preparation and calculation."""
    preparation = _normalize_performance(source, "portfolio input")
    calculation = _normalize_input(_prepared_input(source), "portfolio")
    return preparation, calculation


def test_derived_rows_have_identical_values_at_both_boundaries() -> None:
    """Both boundaries must derive the same signed and unexposed contributions.

    The 120% long and 20% short weights net to one. Their contributions are 12% and
    -1%; the zero-weight row has a null input return and derives exactly zero. The
    calculation boundary's effective returns therefore remain 10%, 5%, and zero.
    """
    source = _source(
        [1.2, -0.2, 0.0],
        [0.10, 0.05, np.nan],
    )

    preparation, calculation = _normalized_boundaries(source)

    assert not preparation.contribution_was_supplied
    # Use the contract's literal products so the assertion also requires identical
    # float64 evaluation, rather than rounding the short contribution to decimal text.
    expected_contributions = np.asarray([1.2 * 0.10, -0.2 * 0.05, 0.0])
    np.testing.assert_allclose(
        preparation.frame["contribution"],
        expected_contributions,
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        calculation["contribution"],
        preparation.frame["contribution"],
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        calculation["input_return"],
        [0.10, 0.05, np.nan],
        rtol=0.0,
        atol=0.0,
        equal_nan=True,
    )
    np.testing.assert_allclose(
        calculation["effective_return"],
        [expected_contributions[0] / 1.2, expected_contributions[1] / -0.2, 0.0],
        rtol=0.0,
        atol=0.0,
    )


def test_authoritative_rows_have_identical_values_at_both_boundaries() -> None:
    """Both boundaries must preserve authoritative contribution semantics.

    ROW_0 demonstrates that supplied contribution overrides weight times input return.
    ROW_2 is an unexposed fee with a null effective return. ROW_3 demonstrates the
    exact zero effective return when both weight and contribution are zero.
    """
    source = _source(
        [0.6, 0.4, 0.0, 0.0],
        [0.10, -0.05, np.nan, np.nan],
        [0.07, -0.02, -0.001, 0.0],
    )

    preparation, calculation = _normalized_boundaries(source)

    assert preparation.contribution_was_supplied
    expected_contributions = np.asarray([0.07, -0.02, -0.001, 0.0])
    np.testing.assert_allclose(
        preparation.frame["contribution"],
        expected_contributions,
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        calculation["contribution"],
        expected_contributions,
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        calculation["input_return"],
        [0.10, -0.05, np.nan, np.nan],
        rtol=0.0,
        atol=0.0,
        equal_nan=True,
    )
    np.testing.assert_allclose(
        calculation["effective_return"],
        [0.07 / 0.6, -0.02 / 0.4, np.nan, 0.0],
        rtol=0.0,
        atol=0.0,
        equal_nan=True,
    )


@pytest.mark.parametrize(
    ("weights", "returns", "contributions", "message"),
    (
        pytest.param(
            [0.6, 0.4],
            [-1.0, 0.0],
            None,
            "column 'return' must be greater than -1.0 when present",
            id="minus-one-return",
        ),
        pytest.param(
            [0.6, 0.4],
            [np.nan, 0.0],
            None,
            "contains a nonzero weight with a null return",
            id="nonzero-weight-null-return",
        ),
        pytest.param(
            [1.0, 0.0],
            [0.0, 0.0],
            [0.0, -0.01],
            "requires a null return when weight is zero and contribution is nonzero",
            id="unexposed-contribution-defined-return",
        ),
        pytest.param(
            [1.0, 1e-320],
            [0.0, 0.0],
            [0.0, 1e308],
            "produces a non-finite effective return",
            id="nonfinite-effective-return",
        ),
    ),
)
def test_shared_invalid_rows_retain_boundary_error_type_and_message(
    weights: list[float],
    returns: list[float],
    contributions: list[float] | None,
    message: str,
) -> None:
    """Shared invalid economics must produce each boundary's own domain error."""
    source = _source(weights, returns, contributions)
    expected_message = f"portfolio input {message}"

    with pytest.raises(PreparationError) as preparation_error:
        _normalize_performance(source, "portfolio input")
    assert str(preparation_error.value) == expected_message

    with pytest.raises(AttributionError) as attribution_error:
        _normalize_input(_prepared_input(source), "portfolio")
    assert str(attribution_error.value) == expected_message


def test_derived_overflow_retains_boundary_specific_diagnostics() -> None:
    """The shared guard must retain each boundary's released overflow explanation.

    The first two huge signed weights cancel before the unit row is added, but the
    first weight-times-return product overflows. Preparation diagnoses derivation;
    attribution preserves its existing effective-return diagnostic.
    """
    source = _source(
        [1e308, -1e308, 1.0],
        [1e308, 0.0, 0.0],
    )

    with pytest.raises(PreparationError) as preparation_error:
        _normalize_performance(source, "portfolio input")
    assert str(preparation_error.value) == (
        "portfolio input derives a non-finite contribution"
    )

    with pytest.raises(AttributionError) as attribution_error:
        _normalize_input(_prepared_input(source), "portfolio")
    assert str(attribution_error.value) == (
        "portfolio input produces a non-finite effective return"
    )
