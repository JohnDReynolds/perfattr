"""Independent tests for Menchero optimized effect-linking coefficients."""

from __future__ import annotations

from decimal import Decimal, DefaultContext, Inexact, ROUND_DOWN, localcontext
import math
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


def _decimal_coefficients(
    portfolio_returns: npt.NDArray[np.float64],
    benchmark_returns: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Independently evaluate source wealth and the published optimization.

    Args:
        portfolio_returns: Literal portfolio period returns for the fixture.
        benchmark_returns: Corresponding benchmark returns with nonzero activity.

    Returns:
        Independently optimized coefficients from the admitted binary floats.

    Notes:
        The 1100-digit context retains subnormal differences next to unit wealth
        and products near 1e308. Direct powers, unscaled squares and the unprojected residual
        independently evaluate the published formula at higher precision. All inputs
        are original project fixtures, derived from the owning specification.
    """
    with localcontext() as context:
        context.prec = 1100
        portfolio = [Decimal.from_float(float(value)) for value in portfolio_returns]
        benchmark = [Decimal.from_float(float(value)) for value in benchmark_returns]
        portfolio_wealth = math.prod((1 + value for value in portfolio), start=Decimal(1))
        benchmark_wealth = math.prod((1 + value for value in benchmark), start=Decimal(1))
        count = len(portfolio)
        portfolio_root = context.power(portfolio_wealth, Decimal(1) / count)
        benchmark_root = context.power(benchmark_wealth, Decimal(1) / count)
        common_scale = sum(
            (
                context.power(portfolio_root, count - 1 - index)
                * context.power(benchmark_root, index)
                for index in range(count)
            ),
            start=Decimal(0),
        ) / count
        active = [left - right for left, right in zip(portfolio, benchmark)]
        residual = (
            portfolio_wealth - benchmark_wealth
            - common_scale * sum(active, start=Decimal(0))
        )
        squared_norm = sum((value * value for value in active), start=Decimal(0))
        return np.asarray(
            [float(common_scale + residual * value / squared_norm) for value in active],
            dtype=np.float64,
        )


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


@pytest.mark.parametrize("direction", [-np.inf, np.inf])
def test_adjacent_period_returns_retain_the_telescoping_coefficient(direction: float) -> None:
    """A single tiny active difference requires the other period's wealth factor.

    With only January active, D=dJanuary*(1+.03), so KJanuary=1.03 on either
    side of equality. Subtracting separately rounded horizon returns loses D
    entirely and formerly made the first coefficient zero.
    """
    portfolio = np.asarray([np.nextafter(.02, direction), .03])
    benchmark = np.asarray([.02, .03])

    coefficients = _coefficients(portfolio, benchmark)

    assert coefficients[0] == pytest.approx(1.03, rel=_TOLERANCE, abs=_TOLERANCE)


@pytest.mark.parametrize(
    ("portfolio_values", "benchmark_values"),
    [
        ([1e-20, -2e-20, .03], [0., 0., .03]),
        ([np.nextafter(0., 1.), .03], [0., .03]),
        ([np.nextafter(1e30, np.inf), -1. + 2. ** -40],
         [1e30, -1. + 2. ** -40]),
        ([1e16, -1. + 2. ** -51], [2e16, -1. + 2. ** -52]),
        ([2. ** 51, -1. + 2. ** -51], [2. ** 52, -1. + 2. ** -52]),
        ([2. ** 1000, -1. + 2. ** -51] + [-1. + 2. ** -50] * 19,
         [2. ** 1001, -1. + 2. ** -52] + [-1. + 2. ** -50] * 19),
    ],
)
def test_source_wealth_residual_matches_independent_decimal_optimization(
    portfolio_values: list[float], benchmark_values: list[float],
) -> None:
    """Retain small and subnormal activity, including a tiny finite coefficient.

    Two active periods expose the same residual loss as the single-active case:
    D is approximately -1.03e-20 and K=[1.0178815725481376,
    1.0239407862740688,1.0199013104567813]. The other cases require Kfirst=1.03
    and Kfirst=2**-40 respectively by telescoping wealth. Dividing by the
    independent coefficient before comparison prevents an absolute tolerance from
    accepting zero instead of a meaningful small coefficient. The huge-return case has
    D=2**-52 even though separately rounded log-ratio terms cancel exactly;
    its required first coefficient is 2.4587941139679918e-32.
    The adjacent-to-one wealth case requires 1.6421466378806457e-47;
    rounding its common scale before assembly previously erased it.
    The 21-period huge/near-loss path has a subnormal first coefficient
    of 1.070901e-317; normalization must retain that value too.
    """
    portfolio = np.asarray(portfolio_values, dtype=np.float64)
    benchmark = np.asarray(benchmark_values, dtype=np.float64)
    expected = _decimal_coefficients(portfolio, benchmark)

    actual = _coefficients(portfolio, benchmark)

    np.testing.assert_allclose(actual / expected, np.ones_like(expected),
                               rtol=_TOLERANCE, atol=_TOLERANCE)


def test_near_loss_activity_survives_extreme_dynamic_range() -> None:
    """Retain near-loss activity when dividing its return difference first loses it.

    Doubling the last positive growth base offsets halving the first huge growth
    base. Twenty tiny bases keep both horizons finite and above -1. The remaining
    source wealth difference is below 1e-12. Scaling the last active difference
    before its large log slope underflows it and invents a material wealth loss.
    The coefficient comparison alone would miss that error near zero, so the
    linked active total is also checked against independently multiplied wealth.
    """
    portfolio = np.asarray([5e307] + [-1. + 2. ** -52] * 20)
    benchmark = portfolio.copy()
    benchmark[0], benchmark[-1] = 1e308, -1. + 2. ** -53
    expected = _decimal_coefficients(portfolio, benchmark)

    actual = _coefficients(portfolio, benchmark)

    np.testing.assert_allclose(actual, expected, rtol=_TOLERANCE, atol=_TOLERANCE)
    assert float(np.dot(actual, portfolio - benchmark)) == pytest.approx(
        0., rel=_TOLERANCE, abs=_TOLERANCE,
    )


def test_zero_active_common_scale_uses_source_growth_near_total_loss() -> None:
    """The equal-path scale is sqrt(source wealth), not a rounded horizon base.

    Both paths grow by 1.1 then 2**-52. Reconstructing wealth from their horizon
    simple return loses ten percent of the tiny wealth base. Its independently
    multiplied square root remains the required continuous common scale.
    """
    returns = np.asarray([.1, -1. + 2. ** -52])
    expected = math.sqrt(1.1 * 2. ** -52)

    actual = _coefficients(returns, returns.copy())

    np.testing.assert_allclose(actual / expected, np.ones(2),
                               rtol=_TOLERANCE, atol=_TOLERANCE)


@pytest.mark.parametrize("method", _METHODS)
def test_public_tiny_active_return_preserves_material_component_effects(
    method: AttributionMethod,
) -> None:
    """Retain January's 41.2bp allocation even when aggregate audits round to zero.

    The admitted January totals are .019999999999999997 and .02; February's
    common return is .03. Therefore KJanuary=1.03 and allocation=.004*1.03=.00412.
    The whole four-method result uses independently optimized source-period
    coefficients; unchanged columns match Carino exactly. Caller frames retain
    their original contents.
    """
    columns = ["from_date", "thru_date", "identifier", "weight", "return",
               "quantity_of_days"]
    portfolio = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "A", .6, .06, 31),
         ("2024-01-01", "2024-01-31", "B", .4, -.04, 31),
         ("2024-02-01", "2024-02-29", "A", .6, .09, 29),
         ("2024-02-01", "2024-02-29", "B", .4, -.06, 29)], columns=columns,
    )
    benchmark = portfolio.copy(deep=True)
    benchmark["weight"] = .5
    benchmark["return"] = [.04, 0., .06, 0.]
    portfolio_before, benchmark_before = portfolio.copy(deep=True), benchmark.copy(deep=True)
    carino = calculate_attribution(portfolio, benchmark, method=method)

    result = calculate_attribution(portfolio, benchmark, method=method,
                                   effect_linking_method=EffectLinkingMethod.MENCHERO)

    summary = result.period_summary
    coefficients = _decimal_coefficients(
        np.asarray(summary["portfolio_return"], dtype=np.float64),
        np.asarray(summary["benchmark_return"], dtype=np.float64),
    )
    assert summary["linked_allocation_effect"].iloc[0] == pytest.approx(
        .00412, rel=_TOLERANCE, abs=_TOLERANCE,
    )
    period_codes = np.asarray(result.period_detail.groupby(
        ["from_date", "thru_date"], sort=False, observed=True,
    ).ngroup(), dtype=np.int64)
    for column in _linked_effect_columns(result.period_detail):
        np.testing.assert_allclose(result.period_detail[column],
                                   result.period_detail[column.removeprefix("linked_")]
                                   * coefficients[period_codes],
                                   rtol=_TOLERANCE, atol=_TOLERANCE)
    for name in ("period_detail", "period_summary", "overall_detail", "cumulative"):
        actual_frame, control_frame = getattr(result, name), getattr(carino, name)
        pd.testing.assert_frame_equal(
            actual_frame.drop(columns=_linked_effect_columns(actual_frame)),
            control_frame.drop(columns=_linked_effect_columns(control_frame)), check_exact=True,
        )
    assert bool(result.reconciliation["passed"].all())
    pd.testing.assert_frame_equal(portfolio, portfolio_before)
    pd.testing.assert_frame_equal(benchmark, benchmark_before)


def test_extreme_source_wealth_retains_the_existing_strict_audit() -> None:
    """Correct source coefficients cannot bypass an inconsistent rounded audit.

    Original unit-weight monthly facts have finite wealth near 1e308. Independent
    Decimal products give D=1.5354928451211952e306. Separately rounded log-compounded
    horizons differ by 1.5354928451153587e306, outside the unchanged 1e-12 gate.
    The source-correct effect must match Decimal, while the public call must raise
    under the existing failed-financial-reconciliation rule. No new input guard,
    output adjustment, or wider tolerance is permitted to manufacture success.
    """
    benchmark_returns = np.full(1000, math.expm1(math.log(1e308) / 1000))
    portfolio_returns = benchmark_returns + .00003
    portfolio_returns[0] = benchmark_returns[0] + .001
    with localcontext() as context:
        context.prec = 440
        portfolio_wealth = math.prod(
            1 + Decimal.from_float(float(value)) for value in portfolio_returns
        )
        benchmark_wealth = math.prod(
            1 + Decimal.from_float(float(value)) for value in benchmark_returns
        )
        expected = float(portfolio_wealth - benchmark_wealth)
    coefficients = _coefficients(portfolio_returns, benchmark_returns)
    actual = float(np.dot(coefficients, portfolio_returns - benchmark_returns))
    assert actual == pytest.approx(expected, rel=_TOLERANCE, abs=_TOLERANCE)
    starts = pd.date_range("2000-01-01", periods=1000, freq="MS")
    ends = starts + pd.offsets.MonthEnd()
    portfolio = pd.DataFrame({
        "from_date": starts, "thru_date": ends, "identifier": "A", "weight": 1.,
        "return": portfolio_returns, "quantity_of_days": (ends - starts).days + 1,
    })
    benchmark = portfolio.copy(deep=True)
    benchmark["return"] = benchmark_returns

    with pytest.raises(
        AttributionError, match="calculation reconciliation failed: linked_total_effect",
    ):
        calculate_attribution(portfolio, benchmark,
                              effect_linking_method=EffectLinkingMethod.MENCHERO)


@pytest.mark.parametrize("method", _METHODS)
@pytest.mark.parametrize(
    ("portfolio_values", "benchmark_values", "charge", "include_neutral_row"),
    [
        ([1e30, -1. + 2. ** -51, -1. + 2. ** -52],
         [2e30, -1. + 2. ** -52, -1. + 2. ** -52], 1e100, True),
        ([1e16, -1. + 2. ** -51], [2e16, -1. + 2. ** -52], 1e30, True),
        ([2. ** 51, -1. + 2. ** -51], [2. ** 52, -1. + 2. ** -52], 1e45, True),
        ([2. ** 1000, -1. + 2. ** -51] + [-1. + 2. ** -50] * 19,
         [2. ** 1001, -1. + 2. ** -52] + [-1. + 2. ** -50] * 19, 2.0 ** 1000, False),
    ],
)
def test_tiny_projection_preserves_offsetting_authoritative_charges(
    method: AttributionMethod,
    portfolio_values: list[float],
    benchmark_values: list[float],
    charge: float,
    include_neutral_row: bool,
) -> None:
    """A tiny optimized coefficient must retain material zero-weight charges.

    Halving the first huge growth and doubling the second tiny growth nearly
    cancel. Direct Decimal products give D=2**-104, while independent optimization
    gives Kfirst=4.739296245227224e-47. Opposite authoritative charges of 1e100
    therefore link to +/-4.739296245227224e53, despite cancelling in every audit.
    Rounding the dimensionless projection before multiplying by M formerly erased
    both charges. The two-period case instead has D=2**-52 and requires
    Kfirst=2.4587941139679918e-32, linking opposite 1e30 charges to
    +/-0.02458794113967992. Rounding individual wealth factors or log ratios
    formerly made those components 90.3% too large while every audit passed.
    When source wealth instead lies at 1+2**-51 and 1+2**-52,
    square-root averaging gives M=1.000000000000000166533453693773... .
    Complete optimization then gives Kfirst=1.6421466378806457e-47
    and linked 1e45 charges of +/-0.016421466378806458. Rounding M
    or the cancelling projected terms first erases those charges.
    The 21-period case instead retains a subnormal coefficient
    1.070901e-317, whose 2**1000 charges link to +/-1.147479768810137e-16.
    Matching the first portfolio exposure keeps the separate logarithmic
    contribution reconciliation well-conditioned. Normalizing the direct and
    public effect comparisons prevents an absolute tolerance from accepting zero.
    """
    portfolio_returns = np.asarray(portfolio_values, dtype=np.float64)
    benchmark_returns = np.asarray(benchmark_values, dtype=np.float64)
    expected = _decimal_coefficients(portfolio_returns, benchmark_returns)[0] * charge
    starts = pd.date_range("2000-01-01", periods=len(portfolio_returns), freq="MS")
    ends = starts + pd.offsets.MonthEnd()
    portfolio = pd.DataFrame({
        "from_date": starts, "thru_date": ends, "identifier": "C", "weight": 1.,
        "return": portfolio_returns, "contribution": portfolio_returns,
        "quantity_of_days": (ends - starts).days + 1,
    })
    benchmark = portfolio.copy(deep=True)
    benchmark["return"] = benchmark_returns
    benchmark["contribution"] = benchmark_returns
    charges = pd.concat([portfolio.iloc[[0]], portfolio.iloc[[0]]], ignore_index=True)
    charges["identifier"], charges["weight"], charges["return"] = ["A", "B"], 0., np.nan
    charges["contribution"] = [charge, -charge]
    portfolio = pd.concat([portfolio, charges], ignore_index=True)
    if include_neutral_row:
        # A leading zero retains the small source return when grouped sums reduce
        # the much larger offsetting charges. Keep the subnormal case's original
        # row geometry, which already preserves its contribution reconciliation.
        neutral = portfolio.iloc[[0]].copy(deep=True)
        neutral["identifier"] = "0"
        neutral[["weight", "return", "contribution"]] = 0.
        portfolio = pd.concat([portfolio, neutral], ignore_index=True)

    result = calculate_attribution(
        portfolio, benchmark, method=method,
        effect_linking_method=EffectLinkingMethod.MENCHERO,
    )

    np.testing.assert_array_equal(result.period_summary["portfolio_return"], portfolio_returns)
    np.testing.assert_array_equal(result.period_summary["benchmark_return"], benchmark_returns)
    charges = result.period_detail.loc[result.period_detail["identifier"].isin(["A", "B"])]
    assert bool(charges["portfolio_return"].isna().all())
    np.testing.assert_allclose(
        charges["linked_total_effect"].to_numpy() / np.asarray([expected, -expected]),
        np.ones(2), rtol=_TOLERANCE, atol=0.0,
    )
    assert bool(result.reconciliation["passed"].all())


def test_menchero_preserves_the_callers_decimal_context() -> None:
    """Local high precision must preserve caller rounding, traps and flags.

    The adjacent-to-one source wealth case needs a coefficient far below its
    cancelling terms. A caller using seven digits, directed rounding and an Inexact
    trap must get the independently derived coefficient without changing its own
    context, even though root evaluation necessarily rounds internally.
    """
    portfolio = np.asarray([2. ** 51, -1. + 2. ** -51])
    benchmark = np.asarray([2. ** 52, -1. + 2. ** -52])
    with localcontext() as context:
        context.prec, context.rounding = 7, ROUND_DOWN
        context.traps[Inexact] = True
        context.clear_flags()
        before = context.copy()

        actual = _coefficients(portfolio, benchmark)

        assert actual[0] / 1.6421466378806457e-47 == pytest.approx(
            1., rel=_TOLERANCE, abs=_TOLERANCE,
        )
        assert context.prec == before.prec
        assert context.rounding == before.rounding
        assert context.traps == before.traps
        assert context.flags == before.flags


@pytest.mark.parametrize("method", _METHODS)
def test_public_menchero_is_independent_of_decimal_defaults(
    method: AttributionMethod, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Customized Decimal defaults must not reject ordinary finite attribution.

    For two periods, M=(sqrt(Wp)+sqrt(Wb))/2, D=Wp-Wb and
    K=M+(D-M*sum(d))*d/sum(d**2). Independent evaluation of the admitted binary
    floats gives K=[1.0032560244412194,1.056880020367683], hence linked totals
    [0.01003256024441219,-0.012682560244412196]. Both roots require rounding.
    Enabling process-default traps must not turn that rounding into an input
    error. All process-default and caller-local settings and flags are preserved;
    the monkeypatch context restores the process defaults even if the call fails.
    """
    columns = ["from_date", "thru_date", "identifier", "weight", "return",
               "quantity_of_days"]
    portfolio = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "A", 1., .06, 31),
         ("2024-02-01", "2024-02-29", "A", 1., -.005, 29)], columns=columns,
    )
    benchmark = portfolio.copy(deep=True)
    benchmark["return"] = [.05, .007]
    inputs_before = (portfolio.copy(deep=True), benchmark.copy(deep=True))
    expected = _decimal_coefficients(np.asarray([.06, -.005]), np.asarray([.05, .007]))
    settings = ("prec", "rounding", "Emin", "Emax", "capitals", "clamp", "traps", "flags")
    contexts_before = {"original_defaults": DefaultContext.copy()}

    with monkeypatch.context() as defaults, localcontext() as caller:
        caller.prec, caller.rounding = 7, ROUND_DOWN
        caller.traps[Inexact] = True
        caller.flags[Inexact] = True
        contexts_before["caller"] = caller.copy()
        for name, value in {
            "prec": 5, "rounding": ROUND_DOWN, "Emin": -5, "Emax": 5,
            "capitals": 0, "clamp": 1,
        }.items():
            defaults.setattr(DefaultContext, name, value)
        for signal in DefaultContext.traps:
            defaults.setitem(DefaultContext.traps, signal, True)
            defaults.setitem(DefaultContext.flags, signal, True)
        contexts_before["defaults"] = DefaultContext.copy()

        result = calculate_attribution(portfolio, benchmark, method=method,
                                       effect_linking_method=EffectLinkingMethod.MENCHERO)

        np.testing.assert_allclose(
            result.period_detail["linked_total_effect"], expected * np.asarray([.01, -.012]),
            rtol=_TOLERANCE, atol=_TOLERANCE,
        )
        assert bool(result.reconciliation["passed"].all())
        for name in settings:
            assert getattr(DefaultContext, name) == getattr(contexts_before["defaults"], name)
            assert getattr(caller, name) == getattr(contexts_before["caller"], name)

    for name in settings:
        assert getattr(DefaultContext, name) == getattr(contexts_before["original_defaults"], name)
    pd.testing.assert_frame_equal(portfolio, inputs_before[0])
    pd.testing.assert_frame_equal(benchmark, inputs_before[1])
