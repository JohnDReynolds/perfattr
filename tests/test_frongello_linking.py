"""Tests for the private Frongello effect-linking calculation boundary."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest

from perfattr import AttributionError, AttributionMethod, EffectLinkingMethod
from perfattr._linking import _frongello
from perfattr.attribution import (
    _calculate_linking_coefficients,
    _link_period_detail,
)


_TOLERANCE = 1e-12


def _two_period_detail(
    portfolio_returns: tuple[float, float],
    benchmark_returns: tuple[float, float],
    allocation_effects: tuple[float, float],
    selection_effects: tuple[float, float],
) -> pd.DataFrame:
    """Build the minimal chronological detail needed to isolate effect linking."""
    return pd.DataFrame(
        {
            "from_date": pd.to_datetime(["2024-01-01", "2024-02-01"]),
            "thru_date": pd.to_datetime(["2024-01-31", "2024-02-29"]),
            "portfolio_contribution": portfolio_returns,
            "benchmark_contribution": benchmark_returns,
            "allocation_effect": allocation_effects,
            "selection_effect": selection_effects,
            "total_effect": tuple(
                allocation + selection
                for allocation, selection in zip(
                    allocation_effects,
                    selection_effects,
                    strict=True,
                )
            ),
        }
    )


def _float_array(frame: pd.DataFrame, column: str) -> npt.NDArray[np.float64]:
    """Return one calculated column as a typed float64 array."""
    return np.asarray(frame[column], dtype=np.float64)


def test_frongello_matches_the_primary_two_period_example() -> None:
    """Link the original example using independently calculated source factors.

    Frongello's first economic period has portfolio and benchmark returns of 20% and
    10%, with 5% allocation and 5% selection. The second has returns of 10% and 5%,
    with 2% allocation and 3% selection. The first source-period factor is the later
    benchmark growth ``1.05``; the second is the earlier portfolio growth ``1.20``.
    Thus allocation links to ``[5% * 1.05, 2% * 1.20] = [5.25%, 2.40%]`` and
    selection to ``[5.25%, 3% * 1.20] = [5.25%, 3.60%]``. Their horizon sums are
    7.65% and 8.85%, reconciling to the independently compounded active return 16.5%.
    """
    detail = _two_period_detail(
        (0.20, 0.10),
        (0.10, 0.05),
        (0.05, 0.02),
        (0.05, 0.03),
    )

    linked = _link_period_detail(
        detail,
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )

    np.testing.assert_allclose(
        _float_array(linked, "linked_allocation_effect"),
        np.asarray([0.0525, 0.0240]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    np.testing.assert_allclose(
        _float_array(linked, "linked_selection_effect"),
        np.asarray([0.0525, 0.0360]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    np.testing.assert_allclose(
        _float_array(linked, "linked_total_effect"),
        np.asarray([0.1050, 0.0600]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    assert linked["linked_allocation_effect"].sum() == pytest.approx(
        0.0765,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert linked["linked_selection_effect"].sum() == pytest.approx(
        0.0885,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert linked["linked_total_effect"].sum() == pytest.approx(
        0.1650,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )


def test_frongello_preserves_the_primary_example_order_dependence() -> None:
    """Reversing the economic periods should reproduce the paper's second result.

    With the 10% portfolio/5% benchmark period first and the 20%/10% period second,
    both source factors are ``1.10``. Allocation therefore becomes
    ``2% * 1.10 + 5% * 1.10 = 7.70%`` and selection becomes
    ``3% * 1.10 + 5% * 1.10 = 8.80%``. The channel allocation changes, while the
    compounded active return remains 16.5%.
    """
    detail = _two_period_detail(
        (0.10, 0.20),
        (0.05, 0.10),
        (0.02, 0.05),
        (0.03, 0.05),
    )

    linked = _link_period_detail(
        detail,
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )

    np.testing.assert_allclose(
        _float_array(linked, "linked_allocation_effect"),
        np.asarray([0.022, 0.055]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    np.testing.assert_allclose(
        _float_array(linked, "linked_selection_effect"),
        np.asarray([0.033, 0.055]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    assert linked["linked_allocation_effect"].sum() == pytest.approx(
        0.077,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert linked["linked_selection_effect"].sum() == pytest.approx(
        0.088,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert linked["linked_total_effect"].sum() == pytest.approx(
        0.165,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )


def test_frongello_one_period_factor_is_identity() -> None:
    """Both empty products are one when no earlier or later period exists."""
    factors = _frongello(
        np.asarray([0.20], dtype=np.float64),
        np.asarray([0.10], dtype=np.float64),
    )

    np.testing.assert_array_equal(factors, np.asarray([1.0]))


def test_frongello_applies_one_factor_to_an_explicit_interaction_channel() -> None:
    """Three-effect linking must use the same factor for every additive component.

    The primary returns imply factors ``[1.05, 1.20]``. Effects of 2% and 1% in the
    explicit interaction channel therefore link to 2.1% and 1.2%. Allocation,
    selection, and interaction still add row by row to the linked total.
    """
    detail = _two_period_detail(
        (0.20, 0.10),
        (0.10, 0.05),
        (0.05, 0.02),
        (0.03, 0.02),
    )
    detail["interaction_effect"] = (0.02, 0.01)
    detail["total_effect"] = (
        detail["total_effect"] + detail["interaction_effect"]
    )

    linked = _link_period_detail(
        detail,
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
        EffectLinkingMethod.FRONGELLO,
    )

    np.testing.assert_allclose(
        _float_array(linked, "linked_interaction_effect"),
        np.asarray([0.021, 0.012]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    component_total = (
        _float_array(linked, "linked_allocation_effect")
        + _float_array(linked, "linked_selection_effect")
        + _float_array(linked, "linked_interaction_effect")
    )
    np.testing.assert_allclose(
        component_total,
        _float_array(linked, "linked_total_effect"),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )


def test_frongello_source_factors_equal_an_independently_stepped_recursion() -> None:
    """Prove the closed-form source allocation against a four-period recursion.

    For portfolio returns ``[20%, 10%, -4%, 3%]`` and benchmark returns
    ``[10%, 5%, 2%, -1%]``, the hand-calculated prefix/suffix factors are
    ``[1.06029, 1.21176, 1.3068, 1.2672]``. Applying them to effects
    ``[5%, 2%, -1%, 0.4%]`` produces a 6.92505% horizon effect.

    Independently stepping ``F[t] = prefix[t] * G[t] + B[t] * C[t-1]`` produces
    cumulative values 5%, 7.65%, 6.483%, and 6.92505%. Equality proves that the
    optimized source-period representation retains the governing recursion without
    using the production factor to construct the recursive expectation.
    """
    portfolio_returns = np.asarray([0.20, 0.10, -0.04, 0.03], dtype=np.float64)
    benchmark_returns = np.asarray([0.10, 0.05, 0.02, -0.01], dtype=np.float64)
    effects = np.asarray([0.05, 0.02, -0.01, 0.004], dtype=np.float64)

    factors = _frongello(portfolio_returns, benchmark_returns)

    np.testing.assert_allclose(
        factors,
        np.asarray([1.06029, 1.21176, 1.3068, 1.2672]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    source_period_total = float(np.sum(effects * factors, dtype=np.float64))

    cumulative_effect = 0.0
    portfolio_prefix = 1.0
    recursive_cumulative = []
    for portfolio_return, benchmark_return, effect in zip(
        portfolio_returns,
        benchmark_returns,
        effects,
        strict=True,
    ):
        increment = (
            portfolio_prefix * effect
            + benchmark_return * cumulative_effect
        )
        cumulative_effect += increment
        recursive_cumulative.append(cumulative_effect)
        portfolio_prefix *= 1.0 + portfolio_return

    np.testing.assert_allclose(
        np.asarray(recursive_cumulative),
        np.asarray([0.05, 0.0765, 0.06483, 0.0692505]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    assert source_period_total == pytest.approx(
        0.0692505,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert source_period_total == pytest.approx(
        cumulative_effect,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )


def test_frongello_rejects_a_nonfinite_factor() -> None:
    """An overflowing intermediate prefix must not become a returned coefficient.

    Two finite ``1e200`` gains overflow the intermediate portfolio prefix. Ten later
    returns immediately above -100% bring the compounded horizon back into the finite
    range, isolating the factor guard from the existing horizon-return guard.
    """
    portfolio_returns = np.asarray(
        [1e200, 1e200, *([-1.0 + 1e-15] * 10)],
        dtype=np.float64,
    )
    benchmark_returns = np.zeros_like(portfolio_returns)

    with pytest.raises(AttributionError, match="linking coefficients must be finite"):
        _calculate_linking_coefficients(
            portfolio_returns,
            benchmark_returns,
            EffectLinkingMethod.FRONGELLO,
        )


def test_frongello_rejects_a_nonfinite_linked_effect() -> None:
    """A finite factor and finite effect must not silently multiply to infinity."""
    detail = _two_period_detail(
        (1e200, 0.0),
        (0.0, 0.0),
        (0.0, 1e200),
        (0.0, 0.0),
    )

    with pytest.raises(
        AttributionError,
        match="linked attribution effects must be finite",
    ):
        _link_period_detail(
            detail,
            effect_linking_method=EffectLinkingMethod.FRONGELLO,
        )
