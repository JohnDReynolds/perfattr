"""Integration tests for Frongello across portable attribution result frames."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from perfattr import (
    AttributionMethod,
    EffectLinkingMethod,
    calculate_attribution,
)


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_TOLERANCE = 1e-12
_METHODS = (
    AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
    AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
)


def _read_inputs(case_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read a fixture's two prepared input frames."""
    case_path = _FIXTURE_ROOT / case_name
    return (
        pd.read_csv(case_path / "portfolio.csv"),
        pd.read_csv(case_path / "benchmark.csv"),
    )


def _float_array(frame: pd.DataFrame, column: str) -> np.ndarray:
    """Return one result column as a float64 NumPy array."""
    return np.asarray(frame[column], dtype=np.float64)


def _read_expected_frame(file_name: str) -> pd.DataFrame:
    """Read one independently calculated Frongello result-frame fixture."""
    expected = pd.read_csv(
        _FIXTURE_ROOT / "multi_period_linking" / file_name
    )
    for column in ("from_date", "thru_date"):
        expected[column] = pd.to_datetime(expected[column]).astype(
            "datetime64[ns]"
        )
    for column in ("identifier", "scope", "check"):
        if column in expected:
            expected[column] = expected[column].astype("string[python]")
    return expected


def _linked_effect_columns(frame: pd.DataFrame) -> list[str]:
    """Return columns whose values may differ between effect-linking policies."""
    return [
        column
        for column in frame.columns
        if column.endswith("_effect")
        and (column.startswith("linked_") or column.startswith("cumulative_"))
    ]


def test_public_frongello_matches_independent_values_in_every_result_frame() -> None:
    """Every public frame should match the complete hand-calculated fixture.

    January portfolio and benchmark returns are 6% and 5%; February returns are
    -0.5% and 0.7%. Frongello factors are therefore ``1 + 0.7% = 1.007`` for
    January and ``1 + 6% = 1.06`` for February. Multiplying the fixture's original
    BF effects gives the literal detail values below.

    Summing by period gives linked totals 1.007% and -1.272%; summing by identifier
    gives -0.4293% for Bonds and 0.1643% for Equity. The final -0.265% equals
    ``(1.06 * 0.995 - 1) - (1.05 * 1.007 - 1)``. These expectations were derived
    from the governing formula and original input fixture, not production output.

    The fixture also records the unchanged logarithmic contribution allocations,
    observed-day weights, identifier returns, cumulative rows, and all 19
    reconciliation checks. Comparing complete frames makes an accidental schema,
    ordering, dtype, null, contribution, or non-effect change visible.
    """
    portfolio, benchmark = _read_inputs("multi_period_linking")

    result = calculate_attribution(
        portfolio,
        benchmark,
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )

    assert result.effect_linking_method is EffectLinkingMethod.FRONGELLO
    expected_files = {
        "period_detail": "expected_frongello_period_detail.csv",
        "period_summary": "expected_frongello_period_summary.csv",
        "overall_detail": "expected_frongello_overall_detail.csv",
        "cumulative": "expected_frongello_cumulative.csv",
        "reconciliation": "expected_frongello_reconciliation.csv",
    }
    for frame_name, file_name in expected_files.items():
        pd.testing.assert_frame_equal(
            getattr(result, frame_name),
            _read_expected_frame(file_name),
            check_exact=False,
            rtol=_TOLERANCE,
            atol=_TOLERANCE,
        )

    final = result.cumulative.iloc[-1]
    assert final["cumulative_total_effect"] == pytest.approx(
        final["cumulative_active_return"],
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert final["cumulative_total_effect"] == pytest.approx(
        final["cumulative_active_contribution"],
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert bool(result.reconciliation["passed"].to_numpy().all())


@pytest.mark.parametrize(
    "case_name",
    ("single_period_derived", "single_period_authoritative"),
)
@pytest.mark.parametrize("method", _METHODS)
def test_one_period_frongello_preserves_all_representational_edge_cases(
    case_name: str,
    method: AttributionMethod,
) -> None:
    """One-period identity must preserve the released edge-case representations.

    ``single_period_derived`` contains positive, negative, and zero effects, a short
    position, portfolio-only and benchmark-only identifiers, and an explicit neutral
    row. ``single_period_authoritative`` contains supplied contributions that differ
    from weight times return plus an unexposed charge whose effective return is null.
    With one source period, Frongello's prefix and suffix are both empty products of
    one, so every financial frame must equal the Carino result exactly.
    """
    portfolio, benchmark = _read_inputs(case_name)

    carino = calculate_attribution(portfolio, benchmark, method=method)
    frongello = calculate_attribution(
        portfolio,
        benchmark,
        method=method,
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )

    frongello_frames = (
        frongello.period_detail,
        frongello.period_summary,
        frongello.overall_detail,
        frongello.cumulative,
        frongello.reconciliation,
    )
    carino_frames = (
        carino.period_detail,
        carino.period_summary,
        carino.overall_detail,
        carino.cumulative,
        carino.reconciliation,
    )
    for frongello_frame, carino_frame in zip(
        frongello_frames,
        carino_frames,
        strict=True,
    ):
        pd.testing.assert_frame_equal(
            frongello_frame,
            carino_frame,
            check_exact=True,
        )


def test_disappearing_cash_identifier_keeps_its_effect_on_its_source_row() -> None:
    """A later benchmark return grows an earlier cash effect without inventing a row.

    In January, CASH_USD has portfolio/benchmark weights of 40%/50% and returns of
    10%/4%. The deliberately generic numbers emphasize that a cash label does not
    select special mathematics. The total benchmark return is 2%, so BF allocation is
    ``-10% * (4% - 2%) = -0.2%`` and portfolio-weighted selection is
    ``40% * (10% - 4%) = 2.4%``. CASH_USD disappears completely in February, whose
    benchmark earns 1%. Its January Frongello factor is 1.01, giving linked allocation
    -0.202%, selection 2.424%, and total 2.222% on the January row. No February cash
    row is synthesized merely to record benchmark carry-forward.
    """
    columns = "from_date thru_date identifier weight return quantity_of_days".split()
    portfolio = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "CASH_USD", 0.4, 0.10, 31),
            ("2024-01-01", "2024-01-31", "B", 0.6, 0.00, 31),
            ("2024-02-01", "2024-02-29", "B", 1.0, 0.02, 29),
        ],
        columns=columns,
    )
    benchmark = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "CASH_USD", 0.5, 0.04, 31),
            ("2024-01-01", "2024-01-31", "B", 0.5, 0.00, 31),
            ("2024-02-01", "2024-02-29", "B", 1.0, 0.01, 29),
        ],
        columns=columns,
    )

    result = calculate_attribution(
        portfolio,
        benchmark,
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )
    cash = result.period_detail.loc[
        result.period_detail["identifier"] == "CASH_USD"
    ]

    assert len(cash) == 1
    assert cash.iloc[0]["thru_date"] == pd.Timestamp("2024-01-31")
    np.testing.assert_allclose(
        cash.iloc[0][
            [
                "linked_allocation_effect",
                "linked_selection_effect",
                "linked_total_effect",
            ]
        ].to_numpy(dtype=np.float64),
        np.asarray([-0.00202, 0.02424, 0.02222]),
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    assert result.cumulative.iloc[-1]["cumulative_total_effect"] == pytest.approx(
        0.0306,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )


def test_unexposed_authoritative_charge_uses_the_ordinary_source_factor() -> None:
    """An undefined-return charge is a normal finite selection effect.

    January portfolio contribution is 1.9%: a 2% Core contribution and a -0.1%
    zero-weight Fee contribution whose return is undefined. The Fee has zero active
    weight, hence zero allocation, while its total and residual selection are -0.1%.
    February's benchmark return is 2%, so the January source factor is 1.02 and the
    Fee's linked selection and total are both ``-0.1% * 1.02 = -0.102%``. Its later
    absence creates no row and does not erase the authoritative charge.
    """
    columns = (
        "from_date thru_date identifier weight return contribution quantity_of_days"
    ).split()
    portfolio = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "Core", 1.0, 0.02, 0.02, 31),
            ("2024-01-01", "2024-01-31", "Fee", 0.0, np.nan, -0.001, 31),
            ("2024-02-01", "2024-02-29", "Core", 1.0, 0.03, 0.03, 29),
        ],
        columns=columns,
    )
    benchmark = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "Core", 1.0, 0.01, 0.01, 31),
            ("2024-02-01", "2024-02-29", "Core", 1.0, 0.02, 0.02, 29),
        ],
        columns=columns,
    )

    result = calculate_attribution(
        portfolio,
        benchmark,
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )
    fee = result.period_detail.loc[result.period_detail["identifier"] == "Fee"]

    assert len(fee) == 1
    assert pd.isna(fee.iloc[0]["portfolio_return"])
    assert fee.iloc[0]["linked_allocation_effect"] == 0.0
    assert fee.iloc[0]["linked_selection_effect"] == pytest.approx(
        -0.00102,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert fee.iloc[0]["linked_total_effect"] == pytest.approx(
        -0.00102,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert result.cumulative.iloc[-1]["cumulative_total_effect"] == pytest.approx(
        0.01937,
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )


@pytest.mark.parametrize("method", _METHODS)
def test_frongello_changes_only_linked_effect_values_and_metadata(
    method: AttributionMethod,
) -> None:
    """All methods must retain schemas, contributions, and unlinked calculations.

    Effect linking occurs after each selected Brinson policy calculates its period
    effects. Switching from Carino to Frongello may therefore change only linked and
    cumulative effect values plus the explicit result metadata. Exact comparisons of
    every other frame column protect contribution linking, input normalization,
    returns, unlinked effects, null placement, dtypes, ordering, and ownership shape.
    """
    portfolio, benchmark = _read_inputs("multi_period_linking")
    carino = calculate_attribution(portfolio, benchmark, method=method)
    frongello = calculate_attribution(
        portfolio,
        benchmark,
        method=method,
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )

    assert carino.effect_linking_method is EffectLinkingMethod.CARINO
    assert frongello.effect_linking_method is EffectLinkingMethod.FRONGELLO
    paired_financial_frames = (
        (carino.period_detail, frongello.period_detail),
        (carino.period_summary, frongello.period_summary),
        (carino.overall_detail, frongello.overall_detail),
        (carino.cumulative, frongello.cumulative),
    )
    for carino_frame, frongello_frame in paired_financial_frames:
        assert tuple(frongello_frame.columns) == tuple(carino_frame.columns)
        effect_columns = _linked_effect_columns(carino_frame)
        pd.testing.assert_frame_equal(
            carino_frame.drop(columns=effect_columns),
            frongello_frame.drop(columns=effect_columns),
            check_exact=True,
        )
    assert tuple(frongello.reconciliation.columns) == tuple(
        carino.reconciliation.columns
    )
    assert list(frongello.reconciliation["check"]) == list(
        carino.reconciliation["check"]
    )
    assert bool(frongello.reconciliation["passed"].to_numpy().all())


@pytest.mark.parametrize(
    ("compact_method", "explicit_method"),
    (
        (
            AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
            AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
        ),
        (
            AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
            AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
        ),
    ),
)
def test_frongello_preserves_two_to_three_effect_collapse_in_every_frame(
    compact_method: AttributionMethod,
    explicit_method: AttributionMethod,
) -> None:
    """Linearity must preserve each method family's interaction-collapse identity."""
    portfolio, benchmark = _read_inputs("multi_period_linking")
    compact = calculate_attribution(
        portfolio,
        benchmark,
        method=compact_method,
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )
    explicit = calculate_attribution(
        portfolio,
        benchmark,
        method=explicit_method,
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )
    frame_pairs = (
        (compact.period_detail, explicit.period_detail, ("", "linked_")),
        (compact.period_summary, explicit.period_summary, ("", "linked_")),
        (compact.overall_detail, explicit.overall_detail, ("linked_",)),
        (compact.cumulative, explicit.cumulative, ("linked_", "cumulative_")),
    )
    for compact_frame, explicit_frame, prefixes in frame_pairs:
        for prefix in prefixes:
            np.testing.assert_allclose(
                compact_frame[f"{prefix}allocation_effect"],
                explicit_frame[f"{prefix}allocation_effect"],
                rtol=_TOLERANCE,
                atol=_TOLERANCE,
            )
            np.testing.assert_allclose(
                compact_frame[f"{prefix}selection_effect"],
                explicit_frame[f"{prefix}selection_effect"]
                + explicit_frame[f"{prefix}interaction_effect"],
                rtol=_TOLERANCE,
                atol=_TOLERANCE,
            )
            np.testing.assert_allclose(
                compact_frame[f"{prefix}total_effect"],
                explicit_frame[f"{prefix}total_effect"],
                rtol=_TOLERANCE,
                atol=_TOLERANCE,
            )


@pytest.mark.parametrize("method", _METHODS)
def test_frongello_near_minus_one_boundary_reconciles(
    method: AttributionMethod,
) -> None:
    """The released near-wipeout inputs must remain finite under every method.

    The fixture contains period and compounded returns close to, but strictly above,
    -100%. Frongello uses multiplication rather than Carino's active log ratio, while
    contribution linking still uses logarithms. Every linked effect must remain finite
    and reconcile to the same compounded active return at the unchanged tolerance.
    """
    portfolio, benchmark = _read_inputs("linking_boundaries")

    result = calculate_attribution(
        portfolio,
        benchmark,
        method=method,
        effect_linking_method=EffectLinkingMethod.FRONGELLO,
    )

    effect_columns = _linked_effect_columns(result.cumulative)
    assert np.isfinite(result.cumulative[effect_columns].to_numpy()).all()
    final = result.cumulative.iloc[-1]
    assert final["cumulative_total_effect"] == pytest.approx(
        final["cumulative_active_return"],
        rel=_TOLERANCE,
        abs=_TOLERANCE,
    )
    assert bool(result.reconciliation["passed"].to_numpy().all())
