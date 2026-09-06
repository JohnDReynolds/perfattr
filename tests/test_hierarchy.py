"""Tests for the staged hierarchical result-roll-up public boundary."""

from __future__ import annotations

from dataclasses import fields
from typing import cast

import pandas as pd
import pytest

import perfattr
from perfattr import (
    AttributionError,
    AttributionMethod,
    AttributionResult,
    EffectLinkingMethod,
    HierarchicalRollupResult,
    calculate_attribution,
    roll_up_attribution,
)
from perfattr._schemas import (
    HIERARCHY_COLUMNS,
    HIERARCHY_OVERALL_ROLLUP_COLUMNS,
    HIERARCHY_PERIOD_ROLLUP_COLUMNS,
    HIERARCHY_RECONCILIATION_COLUMNS,
    OVERALL_DETAIL_COLUMNS,
    PERIOD_DETAIL_COLUMNS,
    PREPARED_REQUIRED_COLUMNS,
    RECONCILIATION_COLUMNS,
    THREE_EFFECT_HIERARCHY_OVERALL_ROLLUP_COLUMNS,
    THREE_EFFECT_HIERARCHY_PERIOD_ROLLUP_COLUMNS,
)
from perfattr.hierarchy import __all__ as hierarchy_all
from perfattr.hierarchy import (
    _build_hierarchy_plan,  # pyright: ignore[reportPrivateUsage]
    _normalize_hierarchy_edges,  # pyright: ignore[reportPrivateUsage]
)


_TWO_EFFECT_OVERALL_COLUMNS = tuple(
    column
    for column in OVERALL_DETAIL_COLUMNS
    if column not in {"portfolio_return", "benchmark_return", "active_return"}
)
_HIERARCHY_RECONCILIATION_COLUMNS = (
    *RECONCILIATION_COLUMNS[:3],
    "identifier",
    *RECONCILIATION_COLUMNS[3:],
)


def _source_result() -> AttributionResult:
    """Return a small valid result for testing the staged public guard."""
    portfolio = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "Leaf", 1.0, 0.02, 31)],
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    benchmark = pd.DataFrame(
        [("2024-01-01", "2024-01-31", "Leaf", 1.0, 0.01, 31)],
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    return calculate_attribution(portfolio, benchmark)


def _hierarchy() -> pd.DataFrame:
    """Return the smallest valid-looking child-to-parent edge list."""
    return pd.DataFrame(
        {"identifier": ["Leaf"], "parent_identifier": ["Parent"]}
    )


def test_hierarchy_api_is_exported_from_module_and_package_root() -> None:
    """Both approved public identities should be importable without implementation."""
    assert hierarchy_all == ["HierarchicalRollupResult", "roll_up_attribution"]
    assert perfattr.HierarchicalRollupResult is HierarchicalRollupResult
    assert perfattr.roll_up_attribution is roll_up_attribution


def test_hierarchical_result_has_the_exact_approved_field_order() -> None:
    """The new result identity must not alter or masquerade as AttributionResult."""
    assert [field.name for field in fields(HierarchicalRollupResult)] == [
        "period_rollup",
        "overall_rollup",
        "hierarchy",
        "reconciliation",
        "method",
        "effect_linking_method",
    ]
    assert not issubclass(HierarchicalRollupResult, AttributionResult)


def test_hierarchy_schemas_match_the_accepted_two_effect_contract() -> None:
    """Two-effect schemas should expose only the approved parent result values."""
    assert HIERARCHY_COLUMNS == ("identifier", "parent_identifier")
    assert HIERARCHY_PERIOD_ROLLUP_COLUMNS == PERIOD_DETAIL_COLUMNS
    assert HIERARCHY_OVERALL_ROLLUP_COLUMNS == _TWO_EFFECT_OVERALL_COLUMNS
    assert HIERARCHY_RECONCILIATION_COLUMNS == _HIERARCHY_RECONCILIATION_COLUMNS


def test_three_effect_schemas_insert_only_interaction_columns() -> None:
    """Three-effect hierarchy frames should mirror released interaction placement."""
    expected_period: list[str] = list(PERIOD_DETAIL_COLUMNS)
    expected_period.insert(
        expected_period.index("selection_effect") + 1,
        "interaction_effect",
    )
    expected_period.insert(
        expected_period.index("linked_selection_effect") + 1,
        "linked_interaction_effect",
    )
    expected_overall: list[str] = list(_TWO_EFFECT_OVERALL_COLUMNS)
    expected_overall.insert(
        expected_overall.index("linked_selection_effect") + 1,
        "linked_interaction_effect",
    )

    assert THREE_EFFECT_HIERARCHY_PERIOD_ROLLUP_COLUMNS == tuple(expected_period)
    assert THREE_EFFECT_HIERARCHY_OVERALL_ROLLUP_COLUMNS == tuple(expected_overall)


def test_hierarchy_plan_normalizes_a_forest_and_retains_unused_branches() -> None:
    """The private plan should resolve only active chains from one reusable taxonomy.

    Software rolls through Technology to Equity, while Government rolls directly to
    Fixed Income. The unused branch remains visible in normalized metadata but cannot
    create an active parent or numerical expansion row. Reversing caller row order
    must produce the same plan, and exact normalized duplicates collapse.
    """
    hierarchy = pd.DataFrame(
        {
            "identifier": [
                " Software ",
                "Technology",
                "Government",
                "UnusedLeaf",
                "Software",
            ],
            "parent_identifier": [
                " Technology ",
                "Equity",
                "Fixed Income",
                "UnusedRoot",
                "Technology",
            ],
        }
    )
    hierarchy_before = hierarchy.copy(deep=True)
    source_identifiers = frozenset({"Software", "Government"})

    plan = _build_hierarchy_plan(hierarchy, source_identifiers)
    reordered_plan = _build_hierarchy_plan(
        hierarchy.iloc[::-1].reset_index(drop=True),
        source_identifiers,
    )

    expected_hierarchy = pd.DataFrame(
        {
            "identifier": pd.Series(
                ["Government", "Software", "Technology", "UnusedLeaf"],
                dtype="string[python]",
            ),
            "parent_identifier": pd.Series(
                ["Fixed Income", "Technology", "Equity", "UnusedRoot"],
                dtype="string[python]",
            ),
        }
    )
    expected_relationships = pd.DataFrame(
        {
            "identifier": pd.Series(
                ["Government", "Software", "Software"],
                dtype="string[python]",
            ),
            "ancestor_identifier": pd.Series(
                ["Fixed Income", "Technology", "Equity"],
                dtype="string[python]",
            ),
            "distance": pd.Series([1, 1, 2], dtype="int64"),
        }
    )
    pd.testing.assert_frame_equal(plan.hierarchy, expected_hierarchy)
    pd.testing.assert_frame_equal(plan.leaf_ancestors, expected_relationships)
    pd.testing.assert_frame_equal(reordered_plan.hierarchy, expected_hierarchy)
    pd.testing.assert_frame_equal(
        reordered_plan.leaf_ancestors,
        expected_relationships,
    )
    assert plan.active_parents == ("Equity", "Fixed Income", "Technology")
    assert plan.active_roots == ("Equity", "Fixed Income")
    pd.testing.assert_frame_equal(hierarchy, hierarchy_before)

    plan.hierarchy.loc[0, "identifier"] = "Changed"
    plan.leaf_ancestors.loc[0, "ancestor_identifier"] = "Changed"
    pd.testing.assert_frame_equal(hierarchy, hierarchy_before)
    assert plan.hierarchy is not plan.leaf_ancestors


@pytest.mark.parametrize(
    ("hierarchy", "message"),
    (
        (
            pd.DataFrame({"identifier": ["Leaf"]}),
            "missing columns: parent_identifier",
        ),
        (
            pd.DataFrame(
                {
                    "identifier": ["Leaf"],
                    "parent_identifier": ["Parent"],
                    "label": ["Leaf label"],
                }
            ),
            "unexpected columns: label",
        ),
        (
            pd.DataFrame(
                [["Leaf", "Parent", "Duplicate"]],
                columns=["identifier", "parent_identifier", "parent_identifier"],
            ),
            "duplicate column labels",
        ),
    ),
)
def test_hierarchy_normalization_rejects_an_inexact_schema(
    hierarchy: pd.DataFrame,
    message: str,
) -> None:
    """Missing, extra, and duplicate labels must not be guessed or discarded."""
    with pytest.raises(AttributionError, match=message):
        _normalize_hierarchy_edges(hierarchy)


def test_hierarchy_normalization_requires_a_dataframe() -> None:
    """A hierarchy-shaped iterable must not bypass the pandas boundary."""
    with pytest.raises(TypeError, match="hierarchy input must be a pandas DataFrame"):
        _normalize_hierarchy_edges(cast(pd.DataFrame, [("Leaf", "Parent")]))


@pytest.mark.parametrize(
    ("column", "value", "message"),
    (
        ("identifier", None, "must contain non-null strings"),
        ("parent_identifier", 7, "must contain non-null strings"),
        ("identifier", "   ", "contains an empty string"),
        ("parent_identifier", "", "contains an empty string"),
    ),
)
def test_hierarchy_normalization_rejects_invalid_identities(
    column: str,
    value: str | int | None,
    message: str,
) -> None:
    """Hierarchy identities remain textual, non-null, and nonblank without coercion."""
    hierarchy = _hierarchy().astype("object")
    hierarchy.loc[0, column] = value

    with pytest.raises(AttributionError, match=message):
        _normalize_hierarchy_edges(hierarchy)


def test_hierarchy_rejects_conflicting_and_self_parent_edges() -> None:
    """A child has one parent and cannot become its own ancestor after trimming."""
    conflicting = pd.DataFrame(
        {
            "identifier": ["Leaf", " Leaf "],
            "parent_identifier": ["Parent A", "Parent B"],
        }
    )
    self_parent = pd.DataFrame(
        {"identifier": [" Node "], "parent_identifier": ["Node"]}
    )

    with pytest.raises(AttributionError, match="maps identifiers to multiple parents"):
        _normalize_hierarchy_edges(conflicting)
    with pytest.raises(AttributionError, match="self-parent identifiers.*Node"):
        _normalize_hierarchy_edges(self_parent)


@pytest.mark.parametrize(
    "hierarchy",
    (
        pd.DataFrame(
            {
                "identifier": ["A", "B"],
                "parent_identifier": ["B", "A"],
            }
        ),
        pd.DataFrame(
            {
                "identifier": ["Leaf", "Unused A", "Unused B", "Unused C"],
                "parent_identifier": ["Root", "Unused B", "Unused C", "Unused A"],
            }
        ),
    ),
)
def test_hierarchy_rejects_cycles_in_active_or_unused_branches(
    hierarchy: pd.DataFrame,
) -> None:
    """Every edge is validated, so an unused taxonomy cycle cannot disappear."""
    with pytest.raises(AttributionError, match="hierarchy input contains a cycle"):
        _normalize_hierarchy_edges(hierarchy)


def test_hierarchy_plan_requires_complete_leaf_coverage() -> None:
    """An omitted leaf edge must not silently turn that source leaf into a root."""
    with pytest.raises(
        AttributionError,
        match="does not cover source result identifiers.*Missing",
    ):
        _build_hierarchy_plan(_hierarchy(), frozenset({"Leaf", "Missing"}))


def test_hierarchy_plan_rejects_a_source_leaf_used_as_an_internal_parent() -> None:
    """Mixing source leaves with parent roles would make numerical rows ambiguous."""
    hierarchy = pd.DataFrame(
        {
            "identifier": ["Leaf", "Another Leaf", "Parent"],
            "parent_identifier": ["Parent", "Leaf", "Root"],
        }
    )

    with pytest.raises(
        AttributionError,
        match="uses source result identifiers as internal parents.*Leaf",
    ):
        _build_hierarchy_plan(hierarchy, frozenset({"Leaf"}))


def test_hierarchy_plan_requires_a_nonempty_source_leaf_set() -> None:
    """A result-only roll-up has no meaningful active graph without source leaves."""
    with pytest.raises(AttributionError, match="identifiers must not be empty"):
        _build_hierarchy_plan(_hierarchy(), frozenset())


def test_hierarchy_plan_has_no_arbitrary_depth_limit() -> None:
    """A deep finite chain should use iterative traversal rather than a level cap.

    The 257 ancestors are intentionally well beyond the 32-level comparative design
    reviewed during specification. The expected first and final relationships prove
    that every edge is retained in order without relying on recursion.
    """
    internal_nodes = [f"Node {index:03d}" for index in range(256)]
    hierarchy = pd.DataFrame(
        {
            "identifier": ["Leaf", *internal_nodes],
            "parent_identifier": [*internal_nodes, "Root"],
        }
    )

    plan = _build_hierarchy_plan(hierarchy, frozenset({"Leaf"}))

    assert len(plan.leaf_ancestors) == 257
    assert tuple(plan.leaf_ancestors.iloc[0]) == ("Leaf", "Node 000", 1)
    assert tuple(plan.leaf_ancestors.iloc[-1]) == ("Leaf", "Root", 257)
    assert len(plan.active_parents) == 257
    assert plan.active_roots == ("Root",)


def test_direct_result_construction_preserves_explicit_frames_and_metadata() -> None:
    """Direct construction remains an ordinary, non-validating dataclass operation.

    Each frame is deliberately created independently. Mutating one after construction
    demonstrates that the dataclass does not alias distinct caller-owned frames or
    reinterpret their contents before the public roll-up implementation exists.
    """
    period_rollup = pd.DataFrame(columns=HIERARCHY_PERIOD_ROLLUP_COLUMNS)
    overall_rollup = pd.DataFrame(columns=HIERARCHY_OVERALL_ROLLUP_COLUMNS)
    hierarchy = pd.DataFrame(columns=HIERARCHY_COLUMNS)
    reconciliation = pd.DataFrame(columns=HIERARCHY_RECONCILIATION_COLUMNS)

    result = HierarchicalRollupResult(
        period_rollup=period_rollup,
        overall_rollup=overall_rollup,
        hierarchy=hierarchy,
        reconciliation=reconciliation,
        method=AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
        effect_linking_method=EffectLinkingMethod.MENCHERO,
    )

    assert result.period_rollup is period_rollup
    assert result.overall_rollup is overall_rollup
    assert result.hierarchy is hierarchy
    assert result.reconciliation is reconciliation
    assert result.method is AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT
    assert result.effect_linking_method is EffectLinkingMethod.MENCHERO

    result.period_rollup.loc[0, "identifier"] = "Parent"
    assert result.overall_rollup.empty
    assert result.hierarchy.empty
    assert result.reconciliation.empty


def test_rollup_rejects_result_and_hierarchy_lookalikes() -> None:
    """Only the two dedicated pandas and attribution-result types may cross the API."""
    source_result = _source_result()

    with pytest.raises(TypeError, match="result must be an AttributionResult"):
        roll_up_attribution(
            cast(AttributionResult, pd.DataFrame()),
            _hierarchy(),
        )
    with pytest.raises(TypeError, match="hierarchy must be a pandas DataFrame"):
        roll_up_attribution(
            source_result,
            cast(pd.DataFrame, [("Leaf", "Parent")]),
        )


@pytest.mark.parametrize(
    ("tolerance", "error_type"),
    (
        (True, TypeError),
        ("1e-12", TypeError),
        (0.0, AttributionError),
        (-1e-12, AttributionError),
        (float("nan"), AttributionError),
        (float("inf"), AttributionError),
    ),
)
def test_rollup_rejects_an_invalid_reconciliation_tolerance(
    tolerance: object,
    error_type: type[Exception],
) -> None:
    """The staged boundary should retain the released strict tolerance contract."""
    with pytest.raises(error_type, match="reconciliation_tolerance"):
        roll_up_attribution(
            _source_result(),
            _hierarchy(),
            reconciliation_tolerance=cast(float, tolerance),
        )


def test_valid_public_call_returns_independent_frames_without_mutation() -> None:
    """The completed boundary should own its frames and preserve every caller input."""
    source_result = _source_result()
    hierarchy = _hierarchy()
    source_frame_names = tuple(
        field.name for field in fields(AttributionResult)[:5]
    )
    source_frames = {
        name: cast(pd.DataFrame, getattr(source_result, name)).copy(deep=True)
        for name in source_frame_names
    }
    hierarchy_before = hierarchy.copy(deep=True)

    result = roll_up_attribution(
        source_result,
        hierarchy,
        reconciliation_tolerance=5e-9,
    )

    for name, expected in source_frames.items():
        actual = cast(pd.DataFrame, getattr(source_result, name))
        pd.testing.assert_frame_equal(actual, expected)
    pd.testing.assert_frame_equal(hierarchy, hierarchy_before)
    assert isinstance(result, HierarchicalRollupResult)
    assert result.method is source_result.method
    assert result.effect_linking_method is source_result.effect_linking_method
    assert bool(result.reconciliation["passed"].to_numpy().all())
    assert bool(result.reconciliation["tolerance"].eq(5e-9).all())

    result.hierarchy.loc[0, "identifier"] = "Changed"
    result.period_rollup.loc[0, "portfolio_weight"] = 999.0
    pd.testing.assert_frame_equal(hierarchy, hierarchy_before)
    pd.testing.assert_frame_equal(source_result.period_detail, source_frames["period_detail"])


def test_public_call_now_applies_hierarchy_content_validation() -> None:
    """Removing the guard must expose strict graph validation rather than a fallback."""
    malformed_hierarchy = pd.DataFrame({"wrong": ["schema"]})

    with pytest.raises(AttributionError, match="exactly the required columns"):
        roll_up_attribution(_source_result(), malformed_hierarchy)
