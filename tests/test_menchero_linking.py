"""Independent tests for Menchero optimized effect-linking coefficients."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest

from perfattr import (
    AttributionError,
    AttributionMethod,
    AttributionResult,
    EffectLinkingMethod,
    calculate_attribution,
)
from perfattr._linking import _menchero
from perfattr.attribution import _calculate_linking_coefficients


_TOLERANCE = 1e-12
_FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_METHODS = tuple(AttributionMethod)
_THREE_EFFECT_METHODS = (
    AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
)


def _coefficients(
    portfolio_returns: npt.NDArray[np.float64],
    benchmark_returns: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Return Menchero coefficients through the private production dispatcher."""
    return _calculate_linking_coefficients(
        portfolio_returns,
        benchmark_returns,
        EffectLinkingMethod.MENCHERO,
    )[2]


def _read_inputs(case_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read both prepared-input frames for an established fixture."""
    case_path = _FIXTURE_ROOT / case_name
    return (
        pd.read_csv(case_path / "portfolio.csv"),
        pd.read_csv(case_path / "benchmark.csv"),
    )


def _linked_effect_columns(frame: pd.DataFrame) -> list[str]:
    """Return only effect columns whose values depend on the selected linker."""
    return frame.filter(regex=r"^(linked|cumulative)_.*_effect$").columns.tolist()


def _read_expected_menchero_frame(file_name: str) -> pd.DataFrame:
    """Read one independently calculated complete-result fixture frame."""
    expected = pd.read_csv(_FIXTURE_ROOT / "multi_period_linking" / file_name)
    for column in ("from_date", "thru_date"):
        expected[column] = pd.to_datetime(expected[column]).astype("datetime64[ns]")
    for column in ("identifier", "scope", "check"):
        if column in expected:
            expected[column] = expected[column].astype("string[python]")
    return expected


def _assert_complete_menchero_fixture(result: AttributionResult) -> None:
    """Compare all five public frames with independently derived literals."""
    expected_files = {
        "period_detail": "expected_menchero_period_detail.csv",
        "period_summary": "expected_menchero_period_summary.csv",
        "overall_detail": "expected_menchero_overall_detail.csv",
        "cumulative": "expected_menchero_cumulative.csv",
        "reconciliation": "expected_menchero_reconciliation.csv",
    }
    for frame_name, file_name in expected_files.items():
        pd.testing.assert_frame_equal(
            getattr(result, frame_name),
            _read_expected_menchero_frame(file_name),
            check_exact=False,
            rtol=_TOLERANCE,
            atol=_TOLERANCE,
        )


def test_menchero_matches_the_six_period_primary_example() -> None:
    """Reproduce the disclosed six-period example from literal source values.

    Decimal multiplication independently gives portfolio and benchmark horizon
    returns of 0.643709375 and 0.393068600. Menchero's common-scale and least-squares
    formulas then give the six expected coefficients recorded below. Applying one
    coefficient per period links issue and sector selection to 0.125249475909329 and
    0.125391299090671, whose sum is the 0.250640775 horizon active return.
    """
    portfolio_returns = np.asarray(
        [0.10, 0.25, 0.10, -0.10, 0.05, 0.15],
        dtype=np.float64,
    )
    benchmark_returns = np.asarray(
        [0.05, 0.15, 0.20, 0.10, -0.08, -0.05],
        dtype=np.float64,
    )
    issue_selection = np.asarray(
        [0.02, 0.09, -0.02, -0.13, 0.03, 0.10],
        dtype=np.float64,
    )
    sector_selection = np.asarray(
        [0.03, 0.01, -0.08, -0.07, 0.10, 0.10],
        dtype=np.float64,
    )

    coefficients = _coefficients(portfolio_returns, benchmark_returns)

    np.testing.assert_allclose(
        coefficients,
        np.asarray(
            [
                1.4122180419446309,
                1.4106064148839273,
                1.4170529231267417,
                1.4202761772481490,
                1.4096394386475051,
                1.4073831607625201,
            ]
        ),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    assert float(np.dot(coefficients, issue_selection)) == pytest.approx(
        0.1252494759093290,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert float(np.dot(coefficients, sector_selection)) == pytest.approx(
        0.1253912990906710,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert float(np.dot(coefficients, portfolio_returns - benchmark_returns)) == (
        pytest.approx(0.250640775, rel=_TOLERANCE, abs=_TOLERANCE)
    )


def test_stable_common_scale_matches_the_published_quotient() -> None:
    """Compare the stable identity with Menchero's quotient away from equality.

    The second period has zero active return, so its correction is zero and its
    coefficient exposes the common scale directly. The expected value independently
    evaluates ``(D / T) / (P_root - B_root)`` from comfortably separated roots.
    """
    portfolio_returns = np.asarray([0.20, -0.05, 0.08], dtype=np.float64)
    benchmark_returns = np.asarray([0.10, -0.05, -0.04], dtype=np.float64)
    portfolio_horizon = float(np.prod(1.0 + portfolio_returns) - 1.0)
    benchmark_horizon = float(np.prod(1.0 + benchmark_returns) - 1.0)
    period_count = portfolio_returns.size
    published_scale = (
        (portfolio_horizon - benchmark_horizon) / period_count
    ) / (
        (1.0 + portfolio_horizon) ** (1.0 / period_count)
        - (1.0 + benchmark_horizon) ** (1.0 / period_count)
    )

    coefficients = _coefficients(portfolio_returns, benchmark_returns)

    assert coefficients[1] == pytest.approx(
        published_scale,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )


def test_equal_horizons_can_require_nonzero_period_corrections() -> None:
    """Preserve corrections when two different paths both compound to 8%.

    Portfolio returns 20% then -10%; benchmark returns 0% then 8%. Both growth paths
    equal 1.08, while their period active returns sum to 2%. The common scale is
    ``sqrt(1.08)`` but cannot itself reconcile a zero horizon difference. The stated
    nonzero corrections are therefore financially necessary, not rounding residue.
    """
    portfolio_returns = np.asarray([0.20, -0.10], dtype=np.float64)
    benchmark_returns = np.asarray([0.00, 0.08], dtype=np.float64)

    coefficients = _menchero(
        portfolio_returns,
        benchmark_returns,
        0.08,
        0.08,
    )

    np.testing.assert_allclose(
        coefficients,
        np.asarray([0.9818144356716398, 1.0909049285240443]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    assert float(np.dot(coefficients, portfolio_returns - benchmark_returns)) == (
        pytest.approx(0.0, rel=_TOLERANCE, abs=_TOLERANCE)
    )


def test_near_equal_horizons_remain_continuous_and_finite() -> None:
    """Avoid cancellation in a quotient of nearly equal horizon roots.

    The two one-billionth-scale horizon returns differ by only ``1e-15``. The stable
    divided-difference identity remains finite and converges toward one; direct root
    subtraction would discard much of the available precision. The second period's
    zero active return exposes the common scale ``(sqrt(P_growth) +
    sqrt(B_growth)) / 2`` directly.
    """
    portfolio_returns = np.asarray([1e-9, 0.0], dtype=np.float64)
    benchmark_returns = np.asarray([1e-9 - 1e-15, 0.0], dtype=np.float64)

    portfolio_horizon = portfolio_returns[0]
    benchmark_horizon = benchmark_returns[0]
    coefficients = _menchero(
        portfolio_returns,
        benchmark_returns,
        portfolio_horizon,
        benchmark_horizon,
    )
    expected = np.asarray(
        [
            (portfolio_horizon - benchmark_horizon)
            / (portfolio_returns[0] - benchmark_returns[0]),
            (
                np.sqrt(1.0 + portfolio_horizon)
                + np.sqrt(1.0 + benchmark_horizon)
            )
            / 2.0,
        ]
    )

    assert np.isfinite(coefficients).all()
    np.testing.assert_allclose(
        coefficients,
        expected,
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )


def test_zero_active_vector_uses_the_minimum_norm_zero_correction() -> None:
    """Use only the continuous common scale when every active return is zero.

    Identical 20%, -10%, and 5% paths have a 13.4% horizon return. Since ``Q=0``,
    dividing by the squared active norm would be undefined; the optimized solution is
    uniquely zero correction and a common coefficient of ``1.134 ** (2 / 3)``.
    Opposite allocation and selection effects additionally show that nonzero
    components may offset within each zero-active period without changing the policy.
    """
    returns = np.asarray([0.20, -0.10, 0.05], dtype=np.float64)
    expected_scale = 1.134 ** (2.0 / 3.0)

    coefficients = _coefficients(returns, returns.copy())

    np.testing.assert_allclose(
        coefficients,
        np.full(3, expected_scale),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    allocation_effects = np.asarray([0.02, -0.01, 0.03], dtype=np.float64)
    selection_effects = -allocation_effects
    np.testing.assert_allclose(
        coefficients * allocation_effects + coefficients * selection_effects,
        np.zeros(3, dtype=np.float64),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )


def test_one_period_coefficient_is_the_identity() -> None:
    """A one-period horizon has common scale one and no compounding residual."""
    coefficients = _coefficients(
        np.asarray([0.20], dtype=np.float64),
        np.asarray([-0.10], dtype=np.float64),
    )

    np.testing.assert_allclose(
        coefficients,
        np.asarray([1.0]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )


def test_one_period_identity_ignores_horizon_reconstruction_noise() -> None:
    """Preserve exact identity when equivalent horizon reconstruction moves one ULP.

    A one-period horizon has no compounding to allocate, so its coefficient is exactly
    one. Platform math libraries may place ``expm1(log1p(return))`` one representable
    float above or below the source return. That numerical artifact must not become a
    least-squares correction to the period's effects.
    """
    portfolio_returns = np.asarray([0.028], dtype=np.float64)
    benchmark_returns = np.asarray([0.0225], dtype=np.float64)
    reconstructed_portfolio_return = float(
        np.nextafter(portfolio_returns[0], -np.inf)
    )

    coefficients = _menchero(
        portfolio_returns,
        benchmark_returns,
        reconstructed_portfolio_return,
        float(benchmark_returns[0]),
    )

    np.testing.assert_array_equal(coefficients, np.asarray([1.0], dtype=np.float64))


def test_scaled_active_norm_avoids_overflow_from_squaring() -> None:
    """Keep a finite coefficient when a naive active-return square overflows.

    A one-period active return of ``1e200`` is finite, but its direct square is not
    representable in float64. Scaling by the largest absolute active return makes the
    squared norm exactly one and retains the required one-period coefficient of one.
    """
    coefficients = _coefficients(
        np.asarray([1e200], dtype=np.float64),
        np.asarray([0.0], dtype=np.float64),
    )

    np.testing.assert_allclose(
        coefficients,
        np.asarray([1.0]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )


def test_nonfinite_intermediate_value_is_rejected_explicitly() -> None:
    """Reject overflow in active subtraction instead of returning a coefficient.

    This private-helper test deliberately bypasses released return validation to
    isolate its defensive arithmetic guard. Both inputs are finite float64 values,
    but subtracting opposite ``1e308`` values overflows the active return.
    """
    with np.errstate(over="ignore", invalid="ignore"):
        with pytest.raises(
            AttributionError,
            match="Menchero linking values must be finite",
        ):
            _menchero(
                np.asarray([1e308], dtype=np.float64),
                np.asarray([-1e308], dtype=np.float64),
                0.0,
                0.0,
            )


def test_coefficients_follow_their_periods_under_permutation() -> None:
    """Menchero's complete-horizon coefficient assignment is order independent.

    Compounding, the active-return sum, and its squared norm are commutative. Moving
    each complete economic period therefore moves its coefficient to the same new
    position without changing the coefficient's value.
    """
    portfolio_returns = np.asarray([0.12, -0.03, 0.07, 0.01], dtype=np.float64)
    benchmark_returns = np.asarray([0.04, 0.02, -0.01, 0.03], dtype=np.float64)
    permutation = np.asarray([2, 0, 3, 1])

    coefficients = _coefficients(portfolio_returns, benchmark_returns)
    permuted_coefficients = _coefficients(
        portfolio_returns[permutation],
        benchmark_returns[permutation],
    )

    np.testing.assert_allclose(
        permuted_coefficients,
        coefficients[permutation],
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )


def test_menchero_differs_from_frongello_on_a_path_sensitive_example() -> None:
    """Distinguish two policies that reconcile but allocate periods differently.

    Portfolio returns of 20% then 10% and benchmark returns of 10% then 5% compound
    to a 16.5% active horizon return. Frongello's chronological factors are 1.05 and
    1.20. Menchero instead minimizes coefficient dispersion without using chronology;
    both coefficient dot products reconcile to 16.5%, but the vectors must differ.
    """
    portfolio_returns = np.asarray([0.20, 0.10], dtype=np.float64)
    benchmark_returns = np.asarray([0.10, 0.05], dtype=np.float64)
    menchero = _coefficients(portfolio_returns, benchmark_returns)
    frongello = _calculate_linking_coefficients(
        portfolio_returns,
        benchmark_returns,
        EffectLinkingMethod.FRONGELLO,
    )[2]
    active_returns = portfolio_returns - benchmark_returns

    assert not np.allclose(
        menchero,
        frongello,
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    np.testing.assert_allclose(
        np.asarray(
            [np.dot(menchero, active_returns), np.dot(frongello, active_returns)]
        ),
        np.asarray([0.165, 0.165]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )


def test_randomized_coefficients_reconcile_to_compounded_active_return() -> None:
    """Supplement literal cases with deterministic reconciliation checks.

    The seeded inputs cover 100 horizons containing two through twelve periods and
    returns from -35% through 45%. For each valid path, the coefficient dot product
    with arithmetic period active return must equal the independently compounded
    horizon-return difference at the unchanged project tolerance.
    """
    generator = np.random.default_rng(20260906)
    for _ in range(100):
        period_count = int(generator.integers(2, 13))
        portfolio_returns = generator.uniform(-0.35, 0.45, period_count)
        benchmark_returns = generator.uniform(-0.35, 0.45, period_count)

        coefficients = _coefficients(portfolio_returns, benchmark_returns)
        linked_active_return = float(
            np.dot(coefficients, portfolio_returns - benchmark_returns)
        )
        expected_active_return = float(
            np.prod(1.0 + portfolio_returns)
            - np.prod(1.0 + benchmark_returns)
        )

        assert linked_active_return == pytest.approx(
            expected_active_return,
            rel=_TOLERANCE,
            abs=_TOLERANCE,
        )


@pytest.mark.parametrize("method", _METHODS)
def test_public_menchero_integrates_every_result_frame(
    method: AttributionMethod,
) -> None:
    """Apply verified coefficients through every frame for all four methods.

    Independent decimal arithmetic for the established two-period fixture gives
    Menchero coefficients ``1.0032560244412194`` and ``1.0568800203676828``.
    Period-detail effects must equal their unlinked values times those coefficients.
    Period summary, overall detail, and cumulative values must then be plain sums of
    those linked source rows, ending at the -0.265% compounded active return.

    Comparing every non-linker-sensitive column exactly with Carino also protects the
    released schemas, dtypes, null placement, ordering, logarithmic contributions,
    unlinked effects, and input-derived values.
    """
    portfolio, benchmark = _read_inputs("multi_period_linking")
    carino = calculate_attribution(portfolio, benchmark, method=method)
    menchero = calculate_attribution(
        portfolio,
        benchmark,
        method=method,
        effect_linking_method=EffectLinkingMethod.MENCHERO,
    )

    assert menchero.effect_linking_method is EffectLinkingMethod.MENCHERO
    expected_coefficients = np.asarray(
        [1.0032560244412194, 1.0568800203676828],
        dtype=np.float64,
    )
    period_codes = np.asarray(
        menchero.period_detail.groupby(
            ["from_date", "thru_date"], sort=False, observed=True
        ).ngroup(),
        dtype=np.int64,
    )
    effect_names = ["allocation", "selection", "total"]
    if method in _THREE_EFFECT_METHODS:
        effect_names.insert(2, "interaction")
    for effect_name in effect_names:
        np.testing.assert_allclose(
            menchero.period_detail[f"linked_{effect_name}_effect"],
            menchero.period_detail[f"{effect_name}_effect"]
            * expected_coefficients[period_codes],
            rtol=_TOLERANCE,
            atol=_TOLERANCE,
        )

    for carino_frame, menchero_frame in (
        (carino.period_detail, menchero.period_detail),
        (carino.period_summary, menchero.period_summary),
        (carino.overall_detail, menchero.overall_detail),
        (carino.cumulative, menchero.cumulative),
    ):
        assert tuple(menchero_frame.columns) == tuple(carino_frame.columns)
        pd.testing.assert_frame_equal(
            menchero_frame.drop(columns=_linked_effect_columns(menchero_frame)),
            carino_frame.drop(columns=_linked_effect_columns(carino_frame)),
            check_exact=True,
        )

    for effect_name in effect_names:
        linked_column = f"linked_{effect_name}_effect"
        expected_period = np.asarray(
            menchero.period_detail.groupby(
                ["from_date", "thru_date"], sort=False, observed=True
            )[linked_column].sum(),
            dtype=np.float64,
        )
        np.testing.assert_allclose(
            menchero.period_summary[linked_column],
            expected_period,
            rtol=_TOLERANCE,
            atol=_TOLERANCE,
        )
        expected_identifier = np.asarray(
            menchero.period_detail.groupby(
                "identifier", sort=True, observed=True
            )[linked_column].sum(),
            dtype=np.float64,
        )
        np.testing.assert_allclose(
            menchero.overall_detail[linked_column],
            expected_identifier,
            rtol=_TOLERANCE,
            atol=_TOLERANCE,
        )
        np.testing.assert_allclose(
            menchero.cumulative[linked_column],
            menchero.period_summary[linked_column],
            rtol=_TOLERANCE,
            atol=_TOLERANCE,
        )
        np.testing.assert_allclose(
            menchero.cumulative[f"cumulative_{effect_name}_effect"],
            np.cumsum(np.asarray(menchero.period_summary[linked_column])),
            rtol=_TOLERANCE,
            atol=_TOLERANCE,
        )

    final = menchero.cumulative.iloc[-1]
    np.testing.assert_allclose(
        np.asarray(
            [
                final["cumulative_total_effect"],
                final["cumulative_active_contribution"],
            ],
            dtype=np.float64,
        ),
        np.asarray([-0.00265, -0.00265]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    assert tuple(menchero.reconciliation.columns) == tuple(
        carino.reconciliation.columns
    )
    assert list(menchero.reconciliation["check"]) == list(
        carino.reconciliation["check"]
    )
    assert bool(menchero.reconciliation["passed"].to_numpy().all())
    if method is AttributionMethod.BRINSON_FACHLER_TWO_EFFECT:
        _assert_complete_menchero_fixture(menchero)
