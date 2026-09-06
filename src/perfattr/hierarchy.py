"""Validate and roll leaf attribution results into a static parent hierarchy."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from perfattr._exceptions import AttributionError
from perfattr._hierarchy_source import (
    effective_returns,
    validate_source_result as _validate_source_result,
)
from perfattr._reconciliation import _validate_result_values
from perfattr._schemas import (
    HIERARCHY_COLUMNS,
    HIERARCHY_OVERALL_ROLLUP_COLUMNS,
    HIERARCHY_PERIOD_ROLLUP_COLUMNS,
    HIERARCHY_RECONCILIATION_COLUMNS,
    THREE_EFFECT_HIERARCHY_PERIOD_ROLLUP_COLUMNS,
    THREE_EFFECT_HIERARCHY_OVERALL_ROLLUP_COLUMNS,
)
from perfattr._validation import (
    float_array as _float_array,
    is_close as _is_close,
    normalize_identity_pairs,
    normalize_reconciliation_tolerance,
)
from perfattr.attribution import AttributionResult
from perfattr.method import (
    AttributionMethod,
    EffectLinkingMethod,
    uses_explicit_interaction,
)

_LEAF_ANCESTOR_COLUMNS = (
    "identifier",
    "ancestor_identifier",
    "distance",
)
_PERIOD_GROUP_COLUMNS = (
    "from_date",
    "thru_date",
    "quantity_of_days",
    "ancestor_identifier",
)
_PERIOD_DERIVED_COLUMNS = frozenset(
    {
        "portfolio_return",
        "benchmark_return",
        "active_weight",
        "active_return",
        "active_contribution",
        "linked_active_contribution",
    }
)
_OVERALL_GROUP_COLUMNS = (
    "from_date",
    "thru_date",
    "ancestor_identifier",
)
_OVERALL_DERIVED_COLUMNS = frozenset(
    {
        "active_weight",
        "linked_active_contribution",
    }
)


@dataclass
class _HierarchyPlan:
    """Hold normalized edges and the active ancestor relationships.

    Attributes:
        hierarchy: Complete normalized child-to-parent edge list, including valid
            branches unused by the selected source identifiers.
        leaf_ancestors: One row for every active leaf-to-ancestor relationship, with
            distance one identifying an immediate parent.
        active_parents: Deterministically ordered ancestors of source leaves.
        active_roots: Deterministically ordered roots reached by source leaves.

    Notes:
        Both DataFrames are independently owned and mutable. This internal container
        prevents later numerical steps from rebuilding or reinterpreting the graph.
    """

    hierarchy: pd.DataFrame
    leaf_ancestors: pd.DataFrame
    active_parents: tuple[str, ...]
    active_roots: tuple[str, ...]


@dataclass
class _ReconciliationSlice:
    """Bundle one source/result horizon for hierarchy reconciliation.

    Attributes:
        source: Original leaf detail for the slice.
        rollup: Derived parent detail for the same slice.
        columns: Additive columns reconciled between children and parents.
        period: Whether period-only active and unlinked-effect identities apply.
    """

    source: pd.DataFrame
    rollup: pd.DataFrame
    columns: tuple[str, ...]
    period: bool


@dataclass
class HierarchicalRollupResult:
    """Hold parent-level attribution roll-up frames.

    Attributes:
        period_rollup: Parent values for each source period.
        overall_rollup: Additive parent values for the complete horizon.
        hierarchy: Normalized child-to-parent hierarchy edges.
        reconciliation: Passing parent and root reconciliation evidence.
        method: Attribution effect convention used by the source result.
        effect_linking_method: Multi-period effect-linking policy used by the source
            result.

    Notes:
        Direct construction is ordinary dataclass construction and does not validate
        or copy frames. The roll-up function returns independently owned frames
        without mutating caller inputs.
    """

    period_rollup: pd.DataFrame
    overall_rollup: pd.DataFrame
    hierarchy: pd.DataFrame
    reconciliation: pd.DataFrame
    method: AttributionMethod
    effect_linking_method: EffectLinkingMethod


def _parent_lookup(hierarchy: pd.DataFrame) -> dict[str, str]:
    """Return normalized child-to-parent identities as an ordinary lookup."""
    return {
        str(identifier): str(parent_identifier)
        for identifier, parent_identifier in hierarchy.itertuples(
            index=False,
            name=None,
        )
    }


def _validate_acyclic(parent_by_child: dict[str, str]) -> None:
    """Reject a cycle anywhere in a finite single-parent graph.

    Args:
        parent_by_child: Normalized child-to-parent lookup.

    Raises:
        AttributionError: If following parent edges revisits a node in the current
            path.

    Notes:
        Traversal is iterative and marks completed paths, so it has no recursion or
        arbitrary hierarchy-depth limit. Sorting start nodes makes the reported cycle
        deterministic.
    """
    completed: set[str] = set()
    for start in sorted(parent_by_child):
        if start in completed:
            continue

        path: list[str] = []
        position: dict[str, int] = {}
        current = start
        while current in parent_by_child and current not in completed:
            cycle_start = position.get(current)
            if cycle_start is not None:
                cycle = [*path[cycle_start:], current]
                raise AttributionError(
                    "hierarchy input contains a cycle: " + " -> ".join(cycle)
                )
            position[current] = len(path)
            path.append(current)
            current = parent_by_child[current]
        completed.update(path)


def _normalize_hierarchy_edges(hierarchy: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate a complete single-parent forest.

    Args:
        hierarchy: Candidate child-to-parent edge DataFrame.

    Returns:
        Independently owned, deduplicated edges in deterministic order.

    Raises:
        TypeError: If ``hierarchy`` is not a pandas DataFrame.
        AttributionError: If its schema, identities, single-parent rule, self-edge,
            or acyclic-forest contract is invalid.

    Notes:
        A parent without its own outgoing edge is an inferred root. Every edge is
        validated, including branches that may be unused by a later selected result.
    """
    normalized = normalize_identity_pairs(
        hierarchy,
        HIERARCHY_COLUMNS,
        "hierarchy input",
        AttributionError,
        "maps identifiers to multiple parents",
    )
    self_edges = normalized.loc[
        normalized["identifier"].eq(normalized["parent_identifier"]),
        "identifier",
    ]
    if not self_edges.empty:
        identifiers = sorted(str(value) for value in self_edges.unique())
        raise AttributionError(
            f"hierarchy input contains self-parent identifiers: {identifiers}"
        )

    _validate_acyclic(_parent_lookup(normalized))
    return normalized


def _resolve_active_relationships(
    parent_by_child: dict[str, str],
    source_identifiers: frozenset[str],
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Expand each validated source leaf through its unique ancestor chain.

    Args:
        parent_by_child: Complete normalized acyclic child-to-parent lookup.
        source_identifiers: Covered source identifiers that are not internal parents.

    Returns:
        The deterministic leaf-to-ancestor relation and reached root identifiers.
    """
    relationship_rows: list[tuple[str, str, int]] = []
    active_roots: set[str] = set()
    for identifier in sorted(source_identifiers):
        current = parent_by_child[identifier]
        distance = 1
        while True:
            relationship_rows.append((identifier, current, distance))
            next_parent = parent_by_child.get(current)
            if next_parent is None:
                active_roots.add(current)
                break
            current = next_parent
            distance += 1

    leaf_ancestors = pd.DataFrame(
        relationship_rows,
        columns=_LEAF_ANCESTOR_COLUMNS,
    ).astype(
        {
            "identifier": "string[python]",
            "ancestor_identifier": "string[python]",
            "distance": "int64",
        }
    )
    return leaf_ancestors, tuple(sorted(active_roots))


def _build_hierarchy_plan(
    hierarchy: pd.DataFrame,
    source_identifiers: frozenset[str],
) -> _HierarchyPlan:
    """Resolve a normalized hierarchy for one complete source leaf set.

    Args:
        hierarchy: Candidate child-to-parent edge DataFrame.
        source_identifiers: Complete nonempty identifier set from the source result.

    Returns:
        Independently owned normalized edges and deterministic active relationships.

    Raises:
        AttributionError: If source identifiers are empty, lack hierarchy coverage,
            or appear as internal parent nodes.

    Notes:
        Valid unused hierarchy branches remain in ``hierarchy`` but do not enter
        ``leaf_ancestors`` or either active-identity tuple. Ancestor expansion follows
        every source leaf through its unique chain and therefore takes work
        proportional to the relationships it returns.
    """
    if not source_identifiers:
        raise AttributionError("source result identifiers must not be empty")

    normalized = _normalize_hierarchy_edges(hierarchy)
    parent_by_child = _parent_lookup(normalized)
    children = frozenset(parent_by_child)
    parents = frozenset(parent_by_child.values())

    missing = sorted(source_identifiers - children)
    if missing:
        raise AttributionError(
            f"hierarchy input does not cover source result identifiers: {missing}"
        )

    internal_source_identifiers = sorted(source_identifiers & parents)
    if internal_source_identifiers:
        raise AttributionError(
            "hierarchy input uses source result identifiers as internal parents: "
            f"{internal_source_identifiers}"
        )

    leaf_ancestors, active_roots = _resolve_active_relationships(
        parent_by_child,
        source_identifiers,
    )
    active_parents = tuple(
        sorted(str(value) for value in leaf_ancestors["ancestor_identifier"].unique())
    )
    return _HierarchyPlan(
        hierarchy=normalized,
        leaf_ancestors=leaf_ancestors,
        active_parents=active_parents,
        active_roots=active_roots,
    )


def _period_rollup_schema(method: AttributionMethod) -> tuple[str, ...]:
    """Return the exact parent-period schema for an approved attribution method."""
    if uses_explicit_interaction(method):
        return THREE_EFFECT_HIERARCHY_PERIOD_ROLLUP_COLUMNS
    return HIERARCHY_PERIOD_ROLLUP_COLUMNS


def _period_additive_columns(method: AttributionMethod) -> tuple[str, ...]:
    """Return period columns that are summed directly from descendant leaves."""
    excluded = {
        "from_date",
        "thru_date",
        "quantity_of_days",
        "identifier",
        *_PERIOD_DERIVED_COLUMNS,
    }
    return tuple(
        column for column in _period_rollup_schema(method) if column not in excluded
    )


def _derive_period_values(rollup: pd.DataFrame) -> None:
    """Populate parent return and active columns on one new roll-up frame."""
    portfolio_weights = _float_array(rollup, "portfolio_weight")
    portfolio_contributions = _float_array(rollup, "portfolio_contribution")
    benchmark_weights = _float_array(rollup, "benchmark_weight")
    benchmark_contributions = _float_array(rollup, "benchmark_contribution")
    portfolio_returns = effective_returns(
        portfolio_weights,
        portfolio_contributions,
    )
    benchmark_returns = effective_returns(
        benchmark_weights,
        benchmark_contributions,
    )
    active_returns = np.full(len(rollup), np.nan, dtype=np.float64)
    defined_active_returns = ~np.isnan(portfolio_returns) & ~np.isnan(benchmark_returns)
    np.subtract(
        portfolio_returns,
        benchmark_returns,
        out=active_returns,
        where=defined_active_returns,
    )

    rollup["portfolio_return"] = portfolio_returns
    rollup["benchmark_return"] = benchmark_returns
    rollup["active_weight"] = portfolio_weights - benchmark_weights
    rollup["active_return"] = active_returns
    rollup["active_contribution"] = (
        portfolio_contributions - benchmark_contributions
    )
    rollup["linked_active_contribution"] = (
        _float_array(rollup, "linked_portfolio_contribution")
        - _float_array(rollup, "linked_benchmark_contribution")
    )


def _roll_up_period_detail(
    period_detail: pd.DataFrame,
    plan: _HierarchyPlan,
    method: AttributionMethod,
) -> pd.DataFrame:
    """Aggregate source period-detail rows directly into every active ancestor.

    Args:
        period_detail: Valid released leaf-level period-detail frame.
        plan: Validated hierarchy plan for its complete source identifier set.
        method: Attribution convention that selects the two- or three-effect schema.

    Returns:
        A new parent-only period frame in deterministic released-schema order.

    Raises:
        AttributionError: If aggregation produces a non-finite value outside the
            approved nullable return columns.

    Notes:
        Every additive parent value is calculated from descendant leaves. Parent
        effects are never recursively aggregated or recalculated from parent weights
        and returns. The caller-owned source frame and hierarchy plan are not mutated.
    """
    additive_columns = _period_additive_columns(method)
    source_columns = (
        "from_date",
        "thru_date",
        "quantity_of_days",
        "identifier",
        *additive_columns,
    )
    relationships = plan.leaf_ancestors.loc[
        :, ["identifier", "ancestor_identifier"]
    ]
    expanded = period_detail.loc[:, source_columns].merge(
        relationships,
        on="identifier",
        how="inner",
        sort=False,
        validate="many_to_many",
    )
    expanded = expanded.sort_values(
        ["thru_date", "from_date", "ancestor_identifier", "identifier"],
        kind="stable",
    )
    rollup = expanded.groupby(
        list(_PERIOD_GROUP_COLUMNS),
        as_index=False,
        sort=True,
        observed=True,
    )[list(additive_columns)].sum()
    rollup = rollup.rename(columns={"ancestor_identifier": "identifier"})
    _derive_period_values(rollup)
    rollup["quantity_of_days"] = rollup["quantity_of_days"].astype("int64")
    rollup["identifier"] = rollup["identifier"].astype("string[python]")
    rollup = rollup.loc[:, list(_period_rollup_schema(method))]
    rollup = rollup.sort_values(
        ["thru_date", "from_date", "identifier"],
        kind="stable",
    ).reset_index(drop=True)
    _validate_result_values(
        "period_rollup",
        rollup,
        ("portfolio_return", "benchmark_return", "active_return"),
    )
    return rollup


def _overall_rollup_schema(method: AttributionMethod) -> tuple[str, ...]:
    """Return the exact parent-horizon schema for an approved attribution method."""
    if uses_explicit_interaction(method):
        return THREE_EFFECT_HIERARCHY_OVERALL_ROLLUP_COLUMNS
    return HIERARCHY_OVERALL_ROLLUP_COLUMNS


def _overall_additive_columns(method: AttributionMethod) -> tuple[str, ...]:
    """Return horizon columns that are summed directly from descendant leaves."""
    excluded = {"from_date", "thru_date", "identifier", *_OVERALL_DERIVED_COLUMNS}
    return tuple(
        column for column in _overall_rollup_schema(method) if column not in excluded
    )


def _roll_up_overall_detail(
    overall_detail: pd.DataFrame,
    plan: _HierarchyPlan,
    method: AttributionMethod,
) -> pd.DataFrame:
    """Aggregate additive source horizon values directly into every active ancestor.

    Args:
        overall_detail: Valid released leaf-level overall-detail frame.
        plan: Validated hierarchy plan for its complete source identifier set.
        method: Attribution convention that selects the two- or three-effect schema.

    Returns:
        A new parent-only horizon frame with no invented return columns.

    Raises:
        AttributionError: If aggregation produces a non-finite value.

    Notes:
        Average weights and already-linked contributions and effects are additive
        across descendant leaves. Full-horizon returns are deliberately absent because
        the released source result cannot support their reconstruction in every case.
    """
    additive_columns = _overall_additive_columns(method)
    source_columns = ("from_date", "thru_date", "identifier", *additive_columns)
    relationships = plan.leaf_ancestors.loc[
        :, ["identifier", "ancestor_identifier"]
    ]
    expanded = overall_detail.loc[:, source_columns].merge(
        relationships,
        on="identifier",
        how="inner",
        sort=False,
        validate="many_to_many",
    )
    expanded = expanded.sort_values(
        ["ancestor_identifier", "identifier"],
        kind="stable",
    )
    rollup = expanded.groupby(
        list(_OVERALL_GROUP_COLUMNS),
        as_index=False,
        sort=True,
        observed=True,
    )[list(additive_columns)].sum()
    rollup = rollup.rename(columns={"ancestor_identifier": "identifier"})
    rollup["active_weight"] = (
        _float_array(rollup, "portfolio_weight")
        - _float_array(rollup, "benchmark_weight")
    )
    rollup["linked_active_contribution"] = (
        _float_array(rollup, "linked_portfolio_contribution")
        - _float_array(rollup, "linked_benchmark_contribution")
    )
    rollup["identifier"] = rollup["identifier"].astype("string[python]")
    rollup = rollup.loc[:, list(_overall_rollup_schema(method))]
    rollup = rollup.sort_values("identifier", kind="stable").reset_index(drop=True)
    _validate_result_values("overall_rollup", rollup)
    return rollup


def _period_reconciliation_columns(
    method: AttributionMethod,
) -> tuple[str, ...]:
    """Return additive period columns in their approved reconciliation order."""
    excluded = {
        "from_date",
        "thru_date",
        "quantity_of_days",
        "identifier",
        "portfolio_return",
        "benchmark_return",
        "active_return",
    }
    return tuple(
        column for column in _period_rollup_schema(method) if column not in excluded
    )


def _overall_reconciliation_columns(
    method: AttributionMethod,
) -> tuple[str, ...]:
    """Return every numerical horizon column in approved schema order."""
    return tuple(
        column
        for column in _overall_rollup_schema(method)
        if column not in {"from_date", "thru_date", "identifier"}
    )


def _active_hierarchy_edges(plan: _HierarchyPlan) -> pd.DataFrame:
    """Return immediate edges whose child and parent both have active values."""
    source_identifiers = frozenset(
        str(value) for value in plan.leaf_ancestors["identifier"].unique()
    )
    active_nodes = source_identifiers | frozenset(plan.active_parents)
    active_edges = plan.hierarchy.loc[
        plan.hierarchy["identifier"].isin(list(active_nodes))
        & plan.hierarchy["parent_identifier"].isin(plan.active_parents)
    ].copy(deep=True)
    return active_edges.rename(columns={"identifier": "child_identifier"})


def _immediate_child_sums(
    source: pd.DataFrame,
    rollup: pd.DataFrame,
    plan: _HierarchyPlan,
    keys: tuple[str, ...],
    columns: tuple[str, ...],
) -> pd.DataFrame:
    """Sum immediate active child rows for every returned parent."""
    node_columns = (*keys[:-1], "identifier", *columns)
    nodes = pd.concat(
        [source.loc[:, list(node_columns)], rollup.loc[:, list(node_columns)]],
        ignore_index=True,
    )
    edges = _active_hierarchy_edges(plan)
    expanded = nodes.merge(
        edges,
        left_on="identifier",
        right_on="child_identifier",
        how="inner",
        sort=False,
        validate="many_to_one",
    )
    parent_column = "parent_identifier"
    sort_columns = [*keys[:-1], parent_column, "identifier"]
    expanded = expanded.sort_values(sort_columns, kind="stable")
    expected = expanded.groupby(
        [*keys[:-1], parent_column],
        as_index=False,
        sort=True,
        observed=True,
    )[list(columns)].sum()
    return expected.rename(
        columns={parent_column: "identifier"},
    )


def _root_sums(
    source: pd.DataFrame,
    rollup: pd.DataFrame,
    plan: _HierarchyPlan,
    keys: tuple[str, ...],
    columns: tuple[str, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return active-root actuals and original-leaf expectations by date key."""
    date_keys = keys[:-1]
    root_rows = rollup.loc[rollup["identifier"].isin(plan.active_roots)]
    actual = root_rows.groupby(
        list(date_keys),
        as_index=False,
        sort=True,
        observed=True,
    )[list(columns)].sum()
    source_sorted = source.sort_values([*date_keys, "identifier"], kind="stable")
    expected = source_sorted.groupby(
        list(date_keys),
        as_index=False,
        sort=True,
        observed=True,
    )[list(columns)].sum()
    return actual, expected


def _effect_identity_names(method: AttributionMethod) -> tuple[str, str]:
    """Return unlinked and linked component-identity check names."""
    if uses_explicit_interaction(method):
        return "three_effect_components", "linked_three_effect_components"
    return "effect_components", "linked_effect_components"


def _effect_component_sum(
    rollup: pd.DataFrame,
    method: AttributionMethod,
    *,
    linked: bool,
) -> np.ndarray:
    """Sum approved effect components for each parent row."""
    prefix = "linked_" if linked else ""
    components = (
        _float_array(rollup, f"{prefix}allocation_effect")
        + _float_array(rollup, f"{prefix}selection_effect")
    )
    if uses_explicit_interaction(method):
        components = components + _float_array(
            rollup,
            f"{prefix}interaction_effect",
        )
    return components


def _add_parent_identities(
    actual: pd.DataFrame,
    expected: pd.DataFrame,
    rollup: pd.DataFrame,
    method: AttributionMethod,
    *,
    period: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, tuple[str, ...]]:
    """Append active and component identities to aligned parent comparisons."""
    identity_names = ["active_weight_identity"]
    actual["active_weight_identity"] = _float_array(rollup, "active_weight")
    expected["active_weight_identity"] = (
        _float_array(rollup, "portfolio_weight")
        - _float_array(rollup, "benchmark_weight")
    )
    if period:
        identity_names.append("active_contribution_identity")
        actual["active_contribution_identity"] = _float_array(
            rollup,
            "active_contribution",
        )
        expected["active_contribution_identity"] = (
            _float_array(rollup, "portfolio_contribution")
            - _float_array(rollup, "benchmark_contribution")
        )

    identity_names.append("linked_active_contribution_identity")
    actual["linked_active_contribution_identity"] = _float_array(
        rollup,
        "linked_active_contribution",
    )
    expected["linked_active_contribution_identity"] = (
        _float_array(rollup, "linked_portfolio_contribution")
        - _float_array(rollup, "linked_benchmark_contribution")
    )

    unlinked_name, linked_name = _effect_identity_names(method)
    if period:
        identity_names.append(unlinked_name)
        actual[unlinked_name] = _float_array(rollup, "total_effect")
        expected[unlinked_name] = _effect_component_sum(
            rollup,
            method,
            linked=False,
        )
    identity_names.append(linked_name)
    actual[linked_name] = _float_array(rollup, "linked_total_effect")
    expected[linked_name] = _effect_component_sum(
        rollup,
        method,
        linked=True,
    )
    return actual, expected, tuple(identity_names)


def _comparison_block(
    scope: str,
    actual: pd.DataFrame,
    expected: pd.DataFrame,
    keys: tuple[str, ...],
    checks: tuple[str, ...],
) -> pd.DataFrame:
    """Convert aligned wide reconciliation values into deterministic long rows."""
    expected_columns = {check: f"{check}__expected" for check in checks}
    aligned = actual.loc[:, [*keys, *checks]].merge(
        expected.loc[:, [*keys, *checks]].rename(columns=expected_columns),
        on=list(keys),
        how="inner",
        sort=False,
        validate="one_to_one",
    )
    if len(aligned) != len(actual) or len(aligned) != len(expected):
        raise AttributionError(
            f"hierarchy reconciliation {scope} keys do not match exactly"
        )

    check_count = len(checks)
    row_count = len(aligned)
    actual_values = np.column_stack(
        [_float_array(aligned, check) for check in checks]
    ).ravel()
    expected_values = np.column_stack(
        [_float_array(aligned, expected_columns[check]) for check in checks]
    ).ravel()
    if "identifier" in keys:
        identifiers = pd.array(
            np.repeat(np.asarray(aligned["identifier"], dtype=object), check_count),
            dtype="string[python]",
        )
    else:
        identifiers = pd.array(
            [pd.NA] * (row_count * check_count),
            dtype="string[python]",
        )
    return pd.DataFrame(
        {
            "scope": scope,
            "from_date": np.repeat(
                np.asarray(aligned["from_date"], dtype="datetime64[ns]"),
                check_count,
            ),
            "thru_date": np.repeat(
                np.asarray(aligned["thru_date"], dtype="datetime64[ns]"),
                check_count,
            ),
            "identifier": identifiers,
            "check": np.tile(checks, row_count),
            "actual": actual_values,
            "expected": expected_values,
        }
    )


def _parent_reconciliation_block(
    scope: str,
    data: _ReconciliationSlice,
    plan: _HierarchyPlan,
    method: AttributionMethod,
) -> pd.DataFrame:
    """Build additive and derived-identity evidence for every active parent."""
    keys = ("from_date", "thru_date", "identifier")
    actual = data.rollup.loc[:, [*keys, *data.columns]].copy(deep=True)
    expected = _immediate_child_sums(
        data.source,
        data.rollup,
        plan,
        keys,
        data.columns,
    )
    expected = data.rollup.loc[:, list(keys)].merge(
        expected,
        on=list(keys),
        how="inner",
        sort=False,
        validate="one_to_one",
    )
    if len(expected) != len(data.rollup):
        raise AttributionError(
            f"hierarchy reconciliation {scope} child coverage is incomplete"
        )
    actual, expected, identity_names = _add_parent_identities(
        actual,
        expected,
        data.rollup,
        method,
        period=data.period,
    )
    return _comparison_block(
        scope,
        actual,
        expected,
        keys,
        (*data.columns, *identity_names),
    )


def _root_reconciliation_block(
    scope: str,
    data: _ReconciliationSlice,
    plan: _HierarchyPlan,
) -> pd.DataFrame:
    """Build forest-wide active-root versus original-leaf evidence."""
    keys = ("from_date", "thru_date", "identifier")
    actual, expected = _root_sums(
        data.source,
        data.rollup,
        plan,
        keys,
        data.columns,
    )
    return _comparison_block(scope, actual, expected, keys[:-1], data.columns)


def _build_hierarchy_reconciliation(
    result: AttributionResult,
    period_rollup: pd.DataFrame,
    overall_rollup: pd.DataFrame,
    plan: _HierarchyPlan,
    tolerance: float,
) -> pd.DataFrame:
    """Build passing parent and forest-root hierarchy reconciliation evidence."""
    period_data = _ReconciliationSlice(
        source=result.period_detail,
        rollup=period_rollup,
        columns=_period_reconciliation_columns(result.method),
        period=True,
    )
    overall_data = _ReconciliationSlice(
        source=result.overall_detail,
        rollup=overall_rollup,
        columns=_overall_reconciliation_columns(result.method),
        period=False,
    )
    blocks = [
        _parent_reconciliation_block(
            "period_parent",
            period_data,
            plan,
            result.method,
        ),
        _root_reconciliation_block(
            "period_roots",
            period_data,
            plan,
        ),
        _parent_reconciliation_block(
            "overall_parent",
            overall_data,
            plan,
            result.method,
        ),
        _root_reconciliation_block(
            "overall_roots",
            overall_data,
            plan,
        ),
    ]
    reconciliation = pd.concat(blocks, ignore_index=True)
    reconciliation["residual"] = (
        reconciliation["actual"] - reconciliation["expected"]
    )
    reconciliation["tolerance"] = tolerance
    finite = np.isfinite(
        reconciliation[["actual", "expected", "residual", "tolerance"]].to_numpy(
            dtype=np.float64
        )
    ).all(axis=1)
    reconciliation["passed"] = finite & _is_close(
        _float_array(reconciliation, "actual"),
        _float_array(reconciliation, "expected"),
        tolerance,
    )
    reconciliation = reconciliation.loc[:, list(HIERARCHY_RECONCILIATION_COLUMNS)]
    reconciliation["scope"] = reconciliation["scope"].astype("string[python]")
    reconciliation["identifier"] = reconciliation["identifier"].astype(
        "string[python]"
    )
    reconciliation["check"] = reconciliation["check"].astype("string[python]")
    reconciliation["passed"] = reconciliation["passed"].astype("bool")
    passed = np.asarray(reconciliation["passed"], dtype=np.bool_)
    if not passed.all():
        failed = reconciliation.loc[~reconciliation["passed"]].iloc[0]
        identifier = failed["identifier"]
        identity = "roots" if pd.isna(identifier) else str(identifier)
        raise AttributionError(
            "hierarchy reconciliation failed for "
            f"{failed['scope']} {identity} {failed['check']}"
        )
    _validate_result_values("hierarchy reconciliation", reconciliation)
    return reconciliation.reset_index(drop=True)


def roll_up_attribution(
    result: AttributionResult,
    hierarchy: pd.DataFrame,
    *,
    reconciliation_tolerance: float = 1e-12,
) -> HierarchicalRollupResult:
    """Roll an attribution result into a static parent hierarchy.

    Args:
        result: Reconciled leaf-level attribution result.
        hierarchy: DataFrame containing exact ``identifier`` and
            ``parent_identifier`` child-to-parent columns.
        reconciliation_tolerance: Positive finite relative and absolute tolerance for
            future parent and root reconciliation checks.

    Returns:
        Parent-period and horizon roll-ups with normalized hierarchy and passing
        reconciliation evidence.

    Raises:
        TypeError: If ``result`` is not an :class:`AttributionResult`, ``hierarchy``
            is not a pandas DataFrame, or ``reconciliation_tolerance`` is not a
            non-boolean real number.
        AttributionError: If the tolerance, source result, hierarchy, rolled values,
            or reconciliation evidence violates the governing contract.

    Notes:
        Parent effects are strict sums of descendant leaf effects; no Brinson formula
        or linking policy is recalculated at a parent. Full-horizon returns and a
        parent cumulative frame are deliberately outside this result-only boundary.
    """
    if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        result,
        AttributionResult,
    ):
        raise TypeError("result must be an AttributionResult")
    if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        hierarchy,
        pd.DataFrame,
    ):
        raise TypeError("hierarchy must be a pandas DataFrame")
    tolerance = normalize_reconciliation_tolerance(
        reconciliation_tolerance,
        AttributionError,
    )
    source_identifiers = _validate_source_result(result, tolerance)
    plan = _build_hierarchy_plan(hierarchy, source_identifiers)
    period_rollup = _roll_up_period_detail(
        result.period_detail,
        plan,
        result.method,
    )
    overall_rollup = _roll_up_overall_detail(
        result.overall_detail,
        plan,
        result.method,
    )
    reconciliation = _build_hierarchy_reconciliation(
        result,
        period_rollup,
        overall_rollup,
        plan,
        tolerance,
    )
    return HierarchicalRollupResult(
        period_rollup=period_rollup,
        overall_rollup=overall_rollup,
        hierarchy=plan.hierarchy,
        reconciliation=reconciliation,
        method=result.method,
        effect_linking_method=result.effect_linking_method,
    )


__all__ = ["HierarchicalRollupResult", "roll_up_attribution"]
