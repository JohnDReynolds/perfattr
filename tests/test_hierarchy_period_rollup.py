"""Independent financial tests for parent-period hierarchical result roll-up."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest

from perfattr import (
    AttributionError,
    AttributionMethod,
    AttributionResult,
    EffectLinkingMethod,
    calculate_attribution,
    roll_up_attribution,
)
from perfattr._schemas import (
    HIERARCHY_COLUMNS,
    HIERARCHY_OVERALL_ROLLUP_COLUMNS,
    HIERARCHY_PERIOD_ROLLUP_COLUMNS,
    HIERARCHY_RECONCILIATION_COLUMNS,
    PREPARED_PERFORMANCE_COLUMNS,
    THREE_EFFECT_HIERARCHY_OVERALL_ROLLUP_COLUMNS,
    THREE_EFFECT_HIERARCHY_PERIOD_ROLLUP_COLUMNS,
)
from perfattr.hierarchy import (
    _build_hierarchy_plan,  # pyright: ignore[reportPrivateUsage]
    _build_hierarchy_reconciliation,  # pyright: ignore[reportPrivateUsage]
    _roll_up_period_detail,  # pyright: ignore[reportPrivateUsage]
)
from perfattr.method import uses_explicit_interaction


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_METHODS = tuple(AttributionMethod)
_LINKERS = tuple(EffectLinkingMethod)
_PERIOD = (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31"), 31)
_PARENT_FACT_COLUMNS = (
    "portfolio_weight",
    "portfolio_contribution",
    "portfolio_return",
    "benchmark_weight",
    "benchmark_contribution",
    "benchmark_return",
    "active_weight",
    "active_contribution",
    "active_return",
)


def _float_value(row: pd.Series, column: str) -> float:
    """Return one known-float value from a mixed-dtype expected-results row."""
    return cast(float, row.at[column])


def _authoritative_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return literal prepared facts spanning the important aggregation cases.

    Portfolio weights include a -10% signed exposure and sum to 100%. The FEE leaf
    has zero exposure, null return, and an authoritative -0.1% contribution. The
    benchmark omits C and FEE, while the portfolio omits D, exercising both neutral
    missing-side representations. Contributions are supplied explicitly so every
    parent expectation follows the authoritative accounting facts below.
    """
    from_date, thru_date, days = _PERIOD
    portfolio = pd.DataFrame(
        [
            (from_date, thru_date, "A", 0.6, 0.10, 0.060, days),
            (from_date, thru_date, "B", 0.5, 0.04, 0.020, days),
            (from_date, thru_date, "C", -0.1, 0.20, -0.020, days),
            (from_date, thru_date, "FEE", 0.0, np.nan, -0.001, days),
        ],
        columns=PREPARED_PERFORMANCE_COLUMNS,
    )
    benchmark = pd.DataFrame(
        [
            (from_date, thru_date, "A", 0.5, 0.08, 0.040, days),
            (from_date, thru_date, "B", 0.3, 0.05, 0.015, days),
            (from_date, thru_date, "D", 0.2, 0.03, 0.006, days),
        ],
        columns=PREPARED_PERFORMANCE_COLUMNS,
    )
    return portfolio, benchmark


def _classification_hierarchy() -> pd.DataFrame:
    """Return a two-level tree with an explicit fee parent and common root."""
    return pd.DataFrame(
        {
            "identifier": [
                "A",
                "B",
                "C",
                "D",
                "FEE",
                "Sector 1",
                "Sector 2",
                "Costs",
            ],
            "parent_identifier": [
                "Sector 1",
                "Sector 1",
                "Sector 2",
                "Sector 2",
                "Costs",
                "Total",
                "Total",
                "Total",
            ],
        }
    )


def _calculate_source_result(
    method: AttributionMethod,
    linker: EffectLinkingMethod,
) -> AttributionResult:
    """Calculate the leaf result consumed by the private Step 4 operation."""
    portfolio, benchmark = _authoritative_inputs()
    return calculate_attribution(
        portfolio,
        benchmark,
        method=method,
        effect_linking_method=linker,
    )


def _rollup_source_result(result: AttributionResult) -> pd.DataFrame:
    """Build the accepted plan and roll one valid result into its parents."""
    source_identifiers = frozenset(
        str(value) for value in result.overall_detail["identifier"]
    )
    plan = _build_hierarchy_plan(
        _classification_hierarchy(),
        source_identifiers,
    )
    return _roll_up_period_detail(result.period_detail, plan, result.method)


def _parent_facts() -> dict[str, tuple[float, ...]]:
    """Return independently summed parent weights, contributions, and returns.

    Tuple order is portfolio weight, portfolio contribution, portfolio return,
    benchmark weight, benchmark contribution, benchmark return, active weight,
    active contribution, and active return. Sector 1 demonstrates that returns are
    contribution divided by aggregated weight: 8% / 110% and 5.5% / 80%. Sector 2
    retains signed portfolio exposure. Costs has a null portfolio and active return
    because its zero weight carries a nonzero authoritative contribution; its absent
    benchmark side is the exact zero/zero case and therefore has return zero.
    """
    sector_1_portfolio_return = 0.080 / 1.1
    sector_1_benchmark_return = 0.055 / 0.8
    return {
        "Costs": (0.0, -0.001, np.nan, 0.0, 0.0, 0.0, 0.0, -0.001, np.nan),
        "Sector 1": (
            1.1,
            0.080,
            sector_1_portfolio_return,
            0.8,
            0.055,
            sector_1_benchmark_return,
            0.3,
            0.025,
            sector_1_portfolio_return - sector_1_benchmark_return,
        ),
        "Sector 2": (-0.1, -0.020, 0.20, 0.2, 0.006, 0.03, -0.3, -0.026, 0.17),
        "Total": (1.0, 0.059, 0.059, 1.0, 0.061, 0.061, 0.0, -0.002, -0.002),
    }


def _parent_effects(
    method: AttributionMethod,
) -> dict[str, tuple[float, ...]]:
    """Return effects independently summed from literal leaf calculations.

    For Brinson-Fachler, each leaf allocation is
    ``(wP - wB) * (rB - 0.061)``. For BHB it is
    ``(wP - wB) * rB``. Two-effect selection is portfolio-weighted and absorbs
    interaction. Three-effect selection is benchmark-weighted, while interaction is
    ``(wP - wB) * (rP - rB)`` when both returns exist. The zero-weight FEE has zero
    allocation and interaction, with its -0.1% contribution carried by selection.

    Tuple order is allocation, selection, optional interaction, and total. Values are
    sums of the A, B, C, D, and FEE leaf effects—not formulas recalculated from the
    parent facts. This distinction is visible at Sector 1 and Sector 2.
    """
    if method is AttributionMethod.BRINSON_FACHLER_TWO_EFFECT:
        return {
            "Costs": (0.0, -0.001, -0.001),
            "Sector 1": (-0.0003, 0.007, 0.0067),
            "Sector 2": (0.0123, -0.020, -0.0077),
            "Total": (0.012, -0.014, -0.002),
        }
    if method is AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT:
        return {
            "Costs": (0.0, -0.001, -0.001),
            "Sector 1": (0.018, 0.007, 0.025),
            "Sector 2": (-0.006, -0.020, -0.026),
            "Total": (0.012, -0.014, -0.002),
        }
    if method is AttributionMethod.BRINSON_FACHLER_THREE_EFFECT:
        return {
            "Costs": (0.0, -0.001, 0.0, -0.001),
            "Sector 1": (-0.0003, 0.007, 0.0, 0.0067),
            "Sector 2": (0.0123, -0.006, -0.014, -0.0077),
            "Total": (0.012, 0.0, -0.014, -0.002),
        }
    return {
        "Costs": (0.0, -0.001, 0.0, -0.001),
        "Sector 1": (0.018, 0.007, 0.0, 0.025),
        "Sector 2": (-0.006, -0.006, -0.014, -0.026),
        "Total": (0.012, 0.0, -0.014, -0.002),
    }


def _expected_period_rollup(method: AttributionMethod) -> pd.DataFrame:
    """Build the complete expected parent frame from the documented hand arithmetic."""
    from_date, thru_date, days = _PERIOD
    rows: list[dict[str, object]] = []
    effects_by_parent = _parent_effects(method)
    for identifier, facts in _parent_facts().items():
        effects = effects_by_parent[identifier]
        row: dict[str, object] = dict(
            zip(_PARENT_FACT_COLUMNS, facts, strict=True)
        )
        row.update(
            {
                "from_date": from_date,
                "thru_date": thru_date,
                "quantity_of_days": days,
                "identifier": identifier,
                "allocation_effect": effects[0],
                "selection_effect": effects[1],
                "total_effect": effects[-1],
                "linked_portfolio_contribution": facts[1],
                "linked_benchmark_contribution": facts[4],
                "linked_active_contribution": facts[7],
                "linked_allocation_effect": effects[0],
                "linked_selection_effect": effects[1],
                "linked_total_effect": effects[-1],
            }
        )
        if uses_explicit_interaction(method):
            row["interaction_effect"] = effects[2]
            row["linked_interaction_effect"] = effects[2]
        rows.append(row)

    columns = (
        THREE_EFFECT_HIERARCHY_PERIOD_ROLLUP_COLUMNS
        if uses_explicit_interaction(method)
        else HIERARCHY_PERIOD_ROLLUP_COLUMNS
    )
    expected = pd.DataFrame(rows, columns=columns)
    expected["from_date"] = expected["from_date"].astype("datetime64[ns]")
    expected["thru_date"] = expected["thru_date"].astype("datetime64[ns]")
    expected["identifier"] = expected["identifier"].astype("string[python]")
    return expected


def _expected_overall_rollup(method: AttributionMethod) -> pd.DataFrame:
    """Return the hand-calculated horizon values valid at the result-only boundary."""
    columns = (
        THREE_EFFECT_HIERARCHY_OVERALL_ROLLUP_COLUMNS
        if uses_explicit_interaction(method)
        else HIERARCHY_OVERALL_ROLLUP_COLUMNS
    )
    return _expected_period_rollup(method).loc[:, list(columns)].copy(deep=True)


def _expected_normalized_hierarchy() -> pd.DataFrame:
    """Return the exact independently ordered hierarchy metadata frame."""
    edges = sorted(
        zip(
            _classification_hierarchy()["identifier"],
            _classification_hierarchy()["parent_identifier"],
            strict=True,
        )
    )
    expected = pd.DataFrame(edges, columns=HIERARCHY_COLUMNS)
    for column in HIERARCHY_COLUMNS:
        expected[column] = expected[column].astype("string[python]")
    return expected


def _period_additive_checks(method: AttributionMethod) -> tuple[str, ...]:
    """Return the specification's additive period check order."""
    columns = (
        THREE_EFFECT_HIERARCHY_PERIOD_ROLLUP_COLUMNS
        if uses_explicit_interaction(method)
        else HIERARCHY_PERIOD_ROLLUP_COLUMNS
    )
    # The first four fields are period keys; every remaining return is derived.
    return tuple(
        column for column in columns[4:] if not column.endswith("_return")
    )


def _overall_additive_checks(method: AttributionMethod) -> tuple[str, ...]:
    """Return the specification's horizon check order."""
    columns = (
        THREE_EFFECT_HIERARCHY_OVERALL_ROLLUP_COLUMNS
        if uses_explicit_interaction(method)
        else HIERARCHY_OVERALL_ROLLUP_COLUMNS
    )
    return tuple(
        column
        for column in columns
        if column not in {"from_date", "thru_date", "identifier"}
    )


def _component_value(
    row: pd.Series,
    method: AttributionMethod,
    *,
    linked: bool,
) -> float:
    """Independently sum the applicable effect components in one expected row."""
    prefix = "linked_" if linked else ""
    value = _float_value(row, f"{prefix}allocation_effect") + _float_value(
        row, f"{prefix}selection_effect"
    )
    if uses_explicit_interaction(method):
        value += _float_value(row, f"{prefix}interaction_effect")
    return value


def _identity_expectations(
    row: pd.Series,
    method: AttributionMethod,
    *,
    period: bool,
) -> list[tuple[str, float, float]]:
    """Return independently calculated active and component identity checks."""
    expectations = [
        (
            "active_weight_identity",
            _float_value(row, "active_weight"),
            _float_value(row, "portfolio_weight")
            - _float_value(row, "benchmark_weight"),
        )
    ]
    if period:
        expectations.append(
            (
                "active_contribution_identity",
                _float_value(row, "active_contribution"),
                _float_value(row, "portfolio_contribution")
                - _float_value(row, "benchmark_contribution"),
            )
        )
    expectations.append(
        (
            "linked_active_contribution_identity",
            _float_value(row, "linked_active_contribution"),
            _float_value(row, "linked_portfolio_contribution")
            - _float_value(row, "linked_benchmark_contribution"),
        )
    )
    if period:
        name = (
            "three_effect_components"
            if uses_explicit_interaction(method)
            else "effect_components"
        )
        expectations.append(
            (
                name,
                _float_value(row, "total_effect"),
                _component_value(row, method, linked=False),
            )
        )
    linked_name = (
        "linked_three_effect_components"
        if uses_explicit_interaction(method)
        else "linked_effect_components"
    )
    expectations.append(
        (
            linked_name,
            _float_value(row, "linked_total_effect"),
            _component_value(row, method, linked=True),
        )
    )
    return expectations


def _reconciliation_record(
    scope: str,
    identifier: object,
    check: str,
    values: tuple[float, float],
    tolerance: float,
) -> dict[str, object]:
    """Return one independently structured passing hierarchy check row."""
    from_date, thru_date, _days = _PERIOD
    actual, expected = values
    return {
        "scope": scope,
        "from_date": from_date,
        "thru_date": thru_date,
        "identifier": identifier,
        "check": check,
        "actual": actual,
        "expected": expected,
        "residual": actual - expected,
        "tolerance": tolerance,
        "passed": True,
    }


@dataclass(frozen=True)
class _ExpectedBlock:
    """Describe one independently calculated reconciliation block.

    Attributes:
        scope: Stable public reconciliation scope.
        checks: Additive columns expected in their exact output order.
        tolerance: Expected comparison tolerance.
        period: Whether period-only identities apply.
    """

    scope: str
    checks: tuple[str, ...]
    tolerance: float
    period: bool


def _expected_parent_reconciliation(
    frame: pd.DataFrame,
    method: AttributionMethod,
    block: _ExpectedBlock,
) -> list[dict[str, object]]:
    """Build hand-value parent rows in the specification's exact check order."""
    rows: list[dict[str, object]] = []
    for _, values in frame.iterrows():
        identifier = str(values.at["identifier"])
        rows.extend(
            _reconciliation_record(
                block.scope,
                identifier,
                check,
                (
                    _float_value(values, check),
                    _float_value(values, check),
                ),
                block.tolerance,
            )
            for check in block.checks
        )
        rows.extend(
            _reconciliation_record(
                block.scope,
                identifier,
                check,
                (actual, expected),
                block.tolerance,
            )
            for check, actual, expected in _identity_expectations(
                values,
                method,
                period=block.period,
            )
        )
    return rows


def _expected_root_reconciliation(
    frame: pd.DataFrame,
    scope: str,
    checks: tuple[str, ...],
    tolerance: float,
) -> list[dict[str, object]]:
    """Build forest-wide checks from the hand-calculated single Total root."""
    root = frame.loc[frame["identifier"] == "Total"].iloc[0]
    return [
        _reconciliation_record(
            scope,
            pd.NA,
            check,
            (
                _float_value(root, check),
                _float_value(root, check),
            ),
            tolerance,
        )
        for check in checks
    ]


def _expected_reconciliation(
    method: AttributionMethod,
    tolerance: float,
) -> pd.DataFrame:
    """Return the complete hierarchy evidence from independently derived values."""
    period = _expected_period_rollup(method)
    overall = _expected_overall_rollup(method)
    period_checks = _period_additive_checks(method)
    overall_checks = _overall_additive_checks(method)
    rows = [
        *_expected_parent_reconciliation(
            period,
            method,
            _ExpectedBlock(
                scope="period_parent",
                checks=period_checks,
                tolerance=tolerance,
                period=True,
            ),
        ),
        *_expected_root_reconciliation(
            period,
            "period_roots",
            period_checks,
            tolerance,
        ),
        *_expected_parent_reconciliation(
            overall,
            method,
            _ExpectedBlock(
                scope="overall_parent",
                checks=overall_checks,
                tolerance=tolerance,
                period=False,
            ),
        ),
        *_expected_root_reconciliation(
            overall,
            "overall_roots",
            overall_checks,
            tolerance,
        ),
    ]
    expected = pd.DataFrame(rows, columns=HIERARCHY_RECONCILIATION_COLUMNS)
    expected["scope"] = expected["scope"].astype("string[python]")
    expected["from_date"] = expected["from_date"].astype("datetime64[ns]")
    expected["thru_date"] = expected["thru_date"].astype("datetime64[ns]")
    expected["identifier"] = expected["identifier"].astype("string[python]")
    expected["check"] = expected["check"].astype("string[python]")
    expected["passed"] = expected["passed"].astype("bool")
    return expected


@pytest.mark.parametrize("method", _METHODS)
@pytest.mark.parametrize("linker", _LINKERS)
def test_period_rollup_matches_complete_independent_parent_values(
    method: AttributionMethod,
    linker: EffectLinkingMethod,
) -> None:
    """Every method and linker should match the complete hand-calculated frame.

    The fixture has one period, for which every released linker is the identity. This
    lets one independent expectation cover Carino, Frongello, and Menchero without
    deriving expected values from production output. All parent columns—including
    linked values, signed exposure, missing sides, and null returns—are compared.
    """
    result = _calculate_source_result(method, linker)

    actual = _rollup_source_result(result)

    pd.testing.assert_frame_equal(
        actual,
        _expected_period_rollup(method),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    assert isinstance(actual.index, pd.RangeIndex)
    numeric_values = np.asarray(
        actual.select_dtypes(include="number"),
        dtype=np.float64,
    )
    assert np.isfinite(numeric_values[~np.isnan(numeric_values)]).all()


@pytest.mark.parametrize("method", _METHODS)
@pytest.mark.parametrize("linker", _LINKERS)
def test_public_rollup_matches_independent_horizon_and_reconciliation(
    method: AttributionMethod,
    linker: EffectLinkingMethod,
) -> None:
    """Every public frame should match the complete independent result contract.

    The expected horizon includes only additive average weights and already-linked
    contributions and effects. It deliberately has no return or cumulative columns.
    Reconciliation covers each of four active parents, the single active root versus
    all source leaves, and every active and component identity. All expected values
    descend from the literal prepared facts and hand arithmetic documented above.
    """
    source = _calculate_source_result(method, linker)

    result = roll_up_attribution(
        source,
        _classification_hierarchy(),
        reconciliation_tolerance=5e-9,
    )

    pd.testing.assert_frame_equal(
        result.period_rollup,
        _expected_period_rollup(method),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    pd.testing.assert_frame_equal(
        result.overall_rollup,
        _expected_overall_rollup(method),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    pd.testing.assert_frame_equal(result.hierarchy, _expected_normalized_hierarchy())
    pd.testing.assert_frame_equal(
        result.reconciliation,
        _expected_reconciliation(method, 5e-9),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    assert result.method is method
    assert result.effect_linking_method is linker
    assert "portfolio_return" not in result.overall_rollup
    assert "benchmark_return" not in result.overall_rollup
    assert "active_return" not in result.overall_rollup
    assert not hasattr(result, "cumulative")


@pytest.mark.parametrize(
    ("method", "recalculated_allocation"),
    (
        (AttributionMethod.BRINSON_FACHLER_TWO_EFFECT, 0.3 * (0.06875 - 0.061)),
        (AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT, 0.3 * 0.06875),
    ),
)
def test_parent_allocation_is_summed_from_leaves_not_recalculated(
    method: AttributionMethod,
    recalculated_allocation: float,
) -> None:
    """The central result-roll-up boundary must stay numerically observable.

    Sector 1's rolled BF allocation is -0.03%, whereas applying the BF formula to its
    parent facts would produce +0.2325%. Its rolled BHB allocation is 1.8%, whereas a
    parent-level BHB recalculation would produce 2.0625%. Those recalculated answers
    belong to the deferred hierarchical-attribution feature.
    """
    result = _calculate_source_result(method, EffectLinkingMethod.CARINO)

    rollup = _rollup_source_result(result).set_index("identifier")
    sector = cast(pd.Series, rollup.loc["Sector 1"])
    rolled_allocation = _float_value(sector, "allocation_effect")

    assert rolled_allocation == pytest.approx(
        _parent_effects(method)["Sector 1"][0],
        abs=1e-12,
    )
    assert rolled_allocation != pytest.approx(recalculated_allocation, abs=1e-12)


def test_multiperiod_rollup_preserves_periods_and_nontrivial_linked_values() -> None:
    """Parent periods should remain distinct and retain already linked leaf values.

    The established two-period fixture supplies non-identity Menchero coefficients.
    Bonds and Equity first roll into distinct sleeves and then into Total. For each
    period, Total must equal the source period summary for every common numerical
    column; this supplements, but does not replace, the hand-calculated fixture above.
    """
    case_path = _FIXTURE_ROOT / "multi_period_linking"
    inputs = {
        side: pd.read_csv(case_path / f"{side}.csv")
        for side in ("portfolio", "benchmark")
    }
    result = calculate_attribution(
        inputs["portfolio"],
        inputs["benchmark"],
        method=AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
        effect_linking_method=EffectLinkingMethod.MENCHERO,
    )
    hierarchy = pd.DataFrame(
        {
            "identifier": ["Bonds", "Equity", "Bond Sleeve", "Equity Sleeve"],
            "parent_identifier": [
                "Bond Sleeve",
                "Equity Sleeve",
                "Total",
                "Total",
            ],
        }
    )
    source_identifiers = frozenset(
        str(value) for value in result.overall_detail["identifier"]
    )
    plan = _build_hierarchy_plan(hierarchy, source_identifiers)

    rollup = _roll_up_period_detail(result.period_detail, plan, result.method)

    assert list(rollup["identifier"]) == [
        "Bond Sleeve",
        "Equity Sleeve",
        "Total",
        "Bond Sleeve",
        "Equity Sleeve",
        "Total",
    ]
    total_rows = rollup.loc[rollup["identifier"] == "Total"].reset_index(drop=True)
    common_columns = [
        column
        for column in result.period_summary.columns
        if column in total_rows.columns
    ]
    pd.testing.assert_frame_equal(
        total_rows.loc[:, common_columns],
        result.period_summary.loc[:, common_columns],
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def test_period_rollup_is_deterministic_independent_and_nonmutating() -> None:
    """Caller row order and later output mutation must not affect owned inputs."""
    result = _calculate_source_result(
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
        EffectLinkingMethod.FRONGELLO,
    )
    identifiers = frozenset(str(value) for value in result.overall_detail["identifier"])
    plan = _build_hierarchy_plan(_classification_hierarchy(), identifiers)
    source_before = result.period_detail.copy(deep=True)
    hierarchy_before = plan.hierarchy.copy(deep=True)
    relationships_before = plan.leaf_ancestors.copy(deep=True)

    ordinary = _roll_up_period_detail(result.period_detail, plan, result.method)
    reordered = _roll_up_period_detail(
        result.period_detail.iloc[::-1].reset_index(drop=True),
        plan,
        result.method,
    )

    pd.testing.assert_frame_equal(ordinary, reordered)
    pd.testing.assert_frame_equal(result.period_detail, source_before)
    pd.testing.assert_frame_equal(plan.hierarchy, hierarchy_before)
    pd.testing.assert_frame_equal(plan.leaf_ancestors, relationships_before)
    ordinary.loc[0, "portfolio_weight"] = 999.0
    pd.testing.assert_frame_equal(result.period_detail, source_before)
    pd.testing.assert_frame_equal(plan.leaf_ancestors, relationships_before)


def test_period_rollup_rejects_nonfinite_aggregates() -> None:
    """Finite leaf values must not be allowed to overflow silently at a parent."""
    result = _calculate_source_result(
        AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
        EffectLinkingMethod.CARINO,
    )
    source = result.period_detail.copy(deep=True)
    source.loc[source["identifier"].isin(["A", "B"]), "portfolio_contribution"] = 1e308
    identifiers = frozenset(str(value) for value in result.overall_detail["identifier"])
    plan = _build_hierarchy_plan(_classification_hierarchy(), identifiers)

    with pytest.raises(
        AttributionError,
        match="period_rollup column 'portfolio_return' contains a non-finite value",
    ):
        _roll_up_period_detail(source, plan, result.method)


def test_public_reconciliation_supports_multiple_active_roots() -> None:
    """A forest-wide check should sum all roots without a synthetic total node."""
    source = _calculate_source_result(
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
        EffectLinkingMethod.MENCHERO,
    )
    hierarchy = _classification_hierarchy()
    forest = hierarchy.loc[
        hierarchy["parent_identifier"] != "Total"
    ].reset_index(drop=True)

    result = roll_up_attribution(source, forest)

    assert list(result.overall_rollup["identifier"]) == [
        "Costs",
        "Sector 1",
        "Sector 2",
    ]
    root_checks = result.reconciliation.loc[
        result.reconciliation["scope"].isin(["period_roots", "overall_roots"])
    ]
    assert root_checks["identifier"].isna().all()
    assert bool(root_checks["passed"].to_numpy().all())
    assert root_checks["residual"].abs().max() == pytest.approx(0.0, abs=1e-12)


def test_reconciliation_rejects_a_tampered_parent_value() -> None:
    """Parent evidence must compare with children rather than trusting the roll-up.

    Increasing Sector 1 selection after aggregation breaks both its immediate-child
    sum and its component identity. Reconciliation must raise rather than return a
    failed row or allow the root's still-correct direct-from-leaf value to hide it.
    """
    source = _calculate_source_result(
        AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
        EffectLinkingMethod.CARINO,
    )
    identifiers = frozenset(str(value) for value in source.overall_detail["identifier"])
    plan = _build_hierarchy_plan(_classification_hierarchy(), identifiers)
    public = roll_up_attribution(source, _classification_hierarchy())
    tampered_period = public.period_rollup.copy(deep=True)
    tampered_period.loc[
        tampered_period["identifier"] == "Sector 1",
        "selection_effect",
    ] += 0.01

    with pytest.raises(
        AttributionError,
        match="hierarchy reconciliation failed for period_parent Sector 1",
    ):
        _build_hierarchy_reconciliation(
            source,
            tampered_period,
            public.overall_rollup,
            plan,
            1e-12,
        )


def test_public_rollup_exposes_the_verified_period_implementation() -> None:
    """The completed public result should reuse the independently tested period path."""
    result = _calculate_source_result(
        AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
        EffectLinkingMethod.CARINO,
    )

    public_result = roll_up_attribution(result, _classification_hierarchy())

    pd.testing.assert_frame_equal(
        public_result.period_rollup,
        _expected_period_rollup(result.method),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
