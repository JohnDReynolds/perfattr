# Hierarchical Result Roll-Up Specification

**Status:** Accepted, implemented, and released in `perfattr==0.9.0a1` on
September 6, 2026.

This document is the governing contract for the deliberately limited additive
hierarchical result roll-up in [roadmap 10][roadmap-10]. It supplements the released
[`specification.md`](specification.md). The user approved this contract and Roadmap 10
on September 6, 2026. The completed implementation followed the roadmap's
dependency-ordered gates.

[roadmap-10]: ../_extras/perfattr_roadmap_10_hierarchical_result_rollup.md

## Methodological identity

Hierarchical result roll-up is a post-calculation aggregation. It answers:

> At which parent classifications did the already calculated leaf values accumulate?

It does not answer:

> What would attribution be if each parent level were independently calculated
> relative to the total portfolio or to its own parent segment?

Those questions can produce different allocation and selection values. This feature
implements only the first. Every reported parent effect is the sum of its descendant
leaf effects; no Brinson formula is run again at a parent.

## User problem

A detailed attribution result may contain industries or securities while a reviewer
also needs sectors, regions, asset classes, or another chain of parent totals. The
released leaf result already contains the authoritative contribution, selected
attribution method, selected effect linker, and reconciled linked effects. Reusing
those results is smaller and more auditable than silently introducing another
level-specific methodology.

## Public API

The package exports this public function from `perfattr.hierarchy` and its root:

```python
def roll_up_attribution(
    result: AttributionResult,
    hierarchy: pd.DataFrame,
    *,
    reconciliation_tolerance: float = 1e-12,
) -> HierarchicalRollupResult:
    ...
```

The package also exports this result type:

```python
@dataclass
class HierarchicalRollupResult:
    period_rollup: pd.DataFrame
    overall_rollup: pd.DataFrame
    hierarchy: pd.DataFrame
    reconciliation: pd.DataFrame
    method: AttributionMethod
    effect_linking_method: EffectLinkingMethod
```

The input must be an `AttributionResult`; a DataFrame or result-shaped object raises
`TypeError`. The hierarchy must be a pandas DataFrame. The tolerance retains the
released finite, positive, non-boolean rule. Invalid result or hierarchy content
raises `AttributionError`.

The function is opt-in and separate from `calculate_attribution`. It neither accepts
raw performance inputs nor invokes preparation or attribution.

## Why a separate result type is required

The five released `AttributionResult` frames have stable meanings and schemas.
Mixing leaves and ancestors into those frames would:

- change released row sets;
- make ordinary sums double count economic values;
- blur calculated leaves with aggregated parents; and
- require full-horizon return values that cannot always be recovered from the released
  result.

`HierarchicalRollupResult` therefore contains parent rows only. The original result
continues to contain the leaves. The normalized hierarchy connects the two without
putting presentation metadata into numerical frames.

## Hierarchy input schema

The hierarchy DataFrame has exactly two columns in this order:

| Column | Dtype | Meaning |
|---|---|---|
| `identifier` | `string[python]` | Child node identifier. |
| `parent_identifier` | `string[python]` | Its one immediate parent. |

Both values are required textual identities. Normalize them under the released
identity policy: trim surrounding whitespace, preserve case and leading zeroes, and
never coerce numbers or other objects to strings. Reject nulls and values that become
blank.

Each row is a directed child-to-parent edge. A parent may itself appear in
`identifier`, creating another edge toward an ancestor. A root is a parent identifier
that never appears as a child. Roots are inferred; the input does not contain a
null-parent terminator row.

For example:

| identifier | parent_identifier |
|---|---|
| `Software` | `Technology` |
| `Hardware` | `Technology` |
| `Technology` | `Equity` |
| `Government` | `Fixed Income` |

This is a valid two-root forest: `Equity` and `Fixed Income` are inferred roots.

## Structural validation

Normalize and validate the entire hierarchy before matching it to the result. Invalid
unused rows must not disappear merely because the selected result does not use them.

The following rules are exact and are not tolerance-based:

- exact normalized duplicate edges collapse harmlessly;
- one child may have only one distinct parent;
- a node may not parent itself;
- the complete graph must contain no directed cycle;
- multiple inferred roots are allowed;
- a parent that has no own edge is an inferred root, not a missing-parent error;
- every identifier in `period_detail` or `overall_detail` must appear as a child;
- every source-result identifier must be a graph leaf and therefore may not also be a
  `parent_identifier`;
- the leaf set represented by `period_detail` and `overall_detail` must agree; and
- additional valid branches not reached by a source-result leaf are allowed.

Complete source-leaf coverage is deliberate. Identity fallback would make an omitted
edge look like an intended root and could conceal a classification error. Multiple
parents are likewise rejected rather than splitting or duplicating one leaf's values.

A valid forest has no arbitrary maximum depth. Detect cycles and resolve paths from
the finite normalized graph rather than stopping at a fixed level count. Resource
limits remain ordinary machine limits; this promise does not require accepting input
that cannot fit in memory.

## Static hierarchy policy

One hierarchy applies to the complete `AttributionResult`. Roadmap 10 does not add
effective dates to hierarchy edges.

The released static or effective-dated classification preparation may still determine
the leaf identifier in each source period before attribution. If one conceptual leaf
must have different parents over time, the host must resolve that ambiguity before
roll-up—for example, by using distinct stable leaf identifiers—or wait for a separately
specified time-aware hierarchy feature. The roll-up function must not infer temporal
assignments.

Portfolio and benchmark already share the equalized identifier boundary in
`period_detail`. The hierarchy is therefore common to both sides; it does not accept
separate portfolio and benchmark trees.

## Source-result validation

`AttributionResult` is deliberately constructible and its frames belong to the caller,
so the roll-up boundary must reject malformed or incompatible instances rather than
assuming every dataclass instance came directly from the calculator.

Before aggregation, require:

- strict `AttributionMethod` and `EffectLinkingMethod` metadata members;
- exact released columns for all five frames under the selected two- or three-effect
  method;
- canonical released dtypes, null placement, `RangeIndex`, and deterministic key
  uniqueness for the frames used by the roll-up;
- nonempty `period_detail` and `overall_detail`;
- consistent period dates, day counts, horizon dates, and identifier sets; and
- non-null, all-true `passed` values in the released reconciliation frame.

All additive source values used by the roll-up must be finite. Return nulls remain
valid only where the released effective-return contract permits them.

This validation protects the new boundary; it is not a second attribution engine. It
must not re-run preparation, linking, Brinson formulas, or every released
reconciliation calculation. A caller needing original-source certification should
retain the calculator and preparation evidence that produced the result.

## Ancestor expansion

Resolve the unique ordered ancestor chain for every active leaf. A leaf contributes
once to its immediate parent, once to that parent's parent, and so on through its
root.

Construct one leaf-to-ancestor relation and reuse it for every numerical column.
Calculate each parent directly from descendant leaf rows rather than recursively from
already aggregated parent rows. This gives the same mathematical sums while avoiding
depth-dependent rounding and repeated traversal.

Unused valid branches remain visible in the normalized `hierarchy` frame but produce
no numerical rows. An active parent is any ancestor of at least one source-result
leaf.

## Period roll-up schema

For a two-effect method, `period_rollup` uses exactly the released two-effect
`period_detail` columns:

```text
from_date
thru_date
quantity_of_days
identifier
portfolio_weight
portfolio_return
portfolio_contribution
benchmark_weight
benchmark_return
benchmark_contribution
active_weight
active_return
active_contribution
allocation_effect
selection_effect
total_effect
linked_portfolio_contribution
linked_benchmark_contribution
linked_active_contribution
linked_allocation_effect
linked_selection_effect
linked_total_effect
```

For a three-effect method, insert `interaction_effect` immediately after
`selection_effect` and `linked_interaction_effect` immediately after
`linked_selection_effect`, matching the released three-effect schema.

Here `identifier` is an active parent identifier. Leaf identifiers are intentionally
absent.

## Period aggregation and return derivation

Within one period and one active parent, strictly sum these descendant-leaf columns:

```text
portfolio_weight
portfolio_contribution
benchmark_weight
benchmark_contribution
allocation_effect
selection_effect
interaction_effect                 # three-effect methods only
total_effect
linked_portfolio_contribution
linked_benchmark_contribution
linked_allocation_effect
linked_selection_effect
linked_interaction_effect          # three-effect methods only
linked_total_effect
```

Derive:

```text
active_weight = portfolio_weight - benchmark_weight

active_contribution =
    portfolio_contribution - benchmark_contribution

linked_active_contribution =
    linked_portfolio_contribution - linked_benchmark_contribution
```

For the portfolio and benchmark separately, derive the parent effective return from
the summed weight `w` and contribution `c`:

```text
r = c / w    when w != 0
r = 0        when w == 0 and c == 0
r = null     when w == 0 and c != 0
```

Then:

```text
active_return = portfolio_return - benchmark_return
```

when both returns are defined, and null otherwise. This is the released
effective-return convention applied to the aggregated parent facts. It is not a
time-series or independently calculated parent return.

`from_date`, `thru_date`, and `quantity_of_days` are the unchanged source-period
values. Rows sort by `thru_date`, `from_date`, and `identifier` using stable ordering
and have a zero-based `RangeIndex`.

## Effect policy: sum, never recalculate

For leaf `g`, ancestor `a`, effect channel `c`, and period `t`, let `g -> a` mean that
`a` occurs anywhere in `g`'s unique ancestor chain. Then:

```text
parent_effect[a, c, t] = sum(effect[g, c, t] for every g -> a)
```

The same identity applies to linked effects. Channel `c` is allocation, selection,
interaction when present, or total.

Do not calculate allocation or selection again from the parent weights and returns.
For example, a Brinson-Fachler parent allocation formed with a parent benchmark return
may differ from the sum of child allocations because it answers a different
level-relative question. Roadmap 10 preserves the leaf calculation and reports its
additive accumulation.

## Horizon roll-up schema

For a two-effect method, `overall_rollup` uses exactly:

```text
from_date
thru_date
identifier
portfolio_weight
linked_portfolio_contribution
benchmark_weight
linked_benchmark_contribution
active_weight
linked_active_contribution
linked_allocation_effect
linked_selection_effect
linked_total_effect
```

For a three-effect method, insert `linked_interaction_effect` immediately after
`linked_selection_effect`.

The horizon dates are copied from `overall_detail`. Rows sort by `identifier` using
stable ordering and have a zero-based `RangeIndex`.

## Why horizon returns are omitted

The released `overall_detail` return for a leaf is compounded from that leaf's
source-period input-return path. A parent horizon return would therefore require all
of its descendant source-period return paths and an explicit aggregation methodology.
`AttributionResult` does not preserve every fact needed to reconstruct that value,
especially where contribution is authoritative or exposure changes over time.

Summing leaf horizon returns would be financially wrong, while taking linked
contribution divided by average weight would introduce a new methodology. The first
version does neither. It exposes only horizon values that are valid strict sums or
differences of strict sums.

The same reasoning excludes a parent `cumulative` frame. A future feature may add
parent return measurement or cumulative presentation after its inputs and financial
identity are independently specified; it must not be smuggled into this additive
roll-up.

## Horizon aggregation

Within one active parent, strictly sum these descendant-leaf `overall_detail` columns:

```text
portfolio_weight
linked_portfolio_contribution
benchmark_weight
linked_benchmark_contribution
linked_allocation_effect
linked_selection_effect
linked_interaction_effect          # three-effect methods only
linked_total_effect
```

Derive:

```text
active_weight = portfolio_weight - benchmark_weight

linked_active_contribution =
    linked_portfolio_contribution - linked_benchmark_contribution
```

No horizon return or unlinked effect is inferred.

## Normalized hierarchy output

`HierarchicalRollupResult.hierarchy` contains the complete normalized edge list,
including valid unused branches, with exactly:

```text
identifier
parent_identifier
```

Rows sort by `identifier`, then `parent_identifier`, and use a zero-based `RangeIndex`.
Both columns use `string[python]`. The returned frame is independently owned.

No `level`, `is_leaf`, label, or display-order column is added. Leaf status is known
from the supplied result; roots and levels are deterministically derivable from the
edges. Presentation systems may create their own traversal metadata without changing
the numerical contract.

## Reconciliation schema

The hierarchy reconciliation frame uses exactly:

```text
scope
from_date
thru_date
identifier
check
actual
expected
residual
tolerance
passed
```

`scope`, `identifier`, and `check` use `string[python]`; `identifier` is null only for
forest-wide root checks. Dates use `datetime64[ns]`, numerical evidence uses
`float64`, and `passed` uses `bool`.

Scopes are:

- `period_parent`: one active parent's period value versus its immediate active
  children;
- `period_roots`: the sum of active roots versus the original source leaves for one
  period;
- `overall_parent`: one active parent's horizon value versus its immediate active
  children; and
- `overall_roots`: the sum of active roots versus the original source leaves for the
  horizon.

An immediate active child is either an original source leaf or an active internal
node. Inactive unused branches contribute no numerical value.

## Reconciliation checks

For period parent and root scopes, check every additive period column:

```text
portfolio_weight
portfolio_contribution
benchmark_weight
benchmark_contribution
active_weight
active_contribution
allocation_effect
selection_effect
interaction_effect                 # three-effect methods only
total_effect
linked_portfolio_contribution
linked_benchmark_contribution
linked_active_contribution
linked_allocation_effect
linked_selection_effect
linked_interaction_effect          # three-effect methods only
linked_total_effect
```

For horizon parent and root scopes, check every `overall_rollup` numerical column.

For each active parent, also check the applicable derived identities:

```text
active_weight_identity
active_contribution_identity       # period only
linked_active_contribution_identity
effect_components                  # two effects, period only
three_effect_components            # three effects, period only
linked_effect_components           # two effects
linked_three_effect_components     # three effects
```

For an additive parent or root check, `actual` is the returned parent value or sum of
active roots, and `expected` is the sum of immediate active children or original
leaves. For an identity check, `actual` is the derived or total column and `expected`
is the relevant difference or component sum. `residual = actual - expected`.

Return columns are not additive and receive no child-sum check. Their exact zero/null/
division behavior is covered directly by financial tests.

Require both relative and absolute agreement at `reconciliation_tolerance`, default
`1e-12`. Emit only passing evidence. Any failure or non-finite reconciliation value
raises `AttributionError`; it must not be returned as a failed row or hidden in a
residual. Rows follow the exact scope, date, identifier, and check order established
by the implementation tests.

## Methods and linking policies

Roll-up accepts every released combination:

- Brinson-Fachler two effect;
- Brinson-Fachler three effect;
- Brinson-Hood-Beebower two effect;
- Brinson-Hood-Beebower three effect;
- Carino effect linking;
- Frongello effect linking; and
- Menchero effect linking.

`method` and `effect_linking_method` are copied to the new result and remain strict
enum members. The roll-up does not dispatch on financial formulas beyond selecting
the correct two- or three-effect schema. It applies no linking coefficient; linked
values are already final leaf values and are simply summed.

## Cash, fees, financing, and signed exposure

Identifiers receive no semantic special treatment.

- Cash rolls into its declared ancestors like any other leaf.
- A zero-weight authoritative fee or financing contribution is preserved in each
  contribution sum. A zero-weight, nonzero-contribution parent return is null.
- Financing or derivatives with signed exposure retain ordinary signed weights and
  finite values supplied through the released attribution result.
- Identifier text never selects a formula, fallback parent, or residual bucket.

These cases require focused independent tests because they exercise the reason parent
returns must be derived from authoritative contribution rather than averaged from
child returns.

## Numerical behavior

All additive source values, ancestor-expanded values, parent sums, differences,
effects, and reconciliation evidence must remain finite. A non-finite intermediate or
result raises `AttributionError`; it must not be clipped, replaced with zero, or
silently excluded.

Exact zero determines the released parent-return null rule. Reconciliation tolerance
does not decide whether a parent weight is zero and does not select a different
formula. Finite positive or negative weights, contributions, returns, and effects are
permitted where the released result contract permits them.

Direct descendant-leaf aggregation minimizes, but cannot eliminate, ordinary
floating-point summation sensitivity. Use deterministic ordering and stable vectorized
aggregation. Do not promise bit-for-bit equivalence under arbitrary edge or caller row
permutations; require unchanged `1e-12` numerical parity and identical null placement,
schemas, and deterministic output ordering.

## Ownership and mutation

The function must not mutate the supplied result frames or hierarchy DataFrame.
Every returned frame belongs to the caller and is independently mutable. No returned
frame may share writable backing storage with an input or another returned frame.

Direct construction of `HierarchicalRollupResult` remains ordinary dataclass
construction; it does not imply immutable or automatically validated frames.

## Compatibility and `ppar`

This feature changes no released `AttributionResult` schema, result row, method,
linker, default, or calculation. Existing calls that do not invoke
`roll_up_attribution` remain unchanged.

`ppar` does not adopt this boundary in Roadmap 10. Its adapter, numerical schema,
audit evidence, reports, and presentation remain unchanged. Because the package adds
a public type and function, the complete `ppar` release-candidate workflow and 500x
gate still verify that installation of the candidate wheel causes no regression.

## Test requirements

Tests must use independently hand-calculated expectations and extensive docstrings or
comments for every nontrivial aggregation, null rule, and identity. At minimum, prove:

- exact public exports, function signature, dataclass fields, and two-/three-effect
  schemas;
- exact identity normalization, duplicate collapse, and deterministic hierarchy
  output;
- a one-parent tree, multiple levels, multiple roots, shared parents, unused valid
  branches, and a deep valid chain without an arbitrary cap;
- rejection of every schema, identity, coverage, parent-conflict, leaf/internal-node,
  self-edge, and cycle violation;
- direct-from-leaf results equal immediate-child sums at every active level;
- all four attribution methods preserve their component identities;
- all three effect linkers preserve their already linked values without relinking;
- positive, negative, zero, signed, and authoritative contributions and weights;
- portfolio-only, benchmark-only, disappearing, cash, fee, and financing-style leaves;
- exact parent return division, zero, and null behavior;
- deliberate absence of horizon return and cumulative fields;
- parent, forest-root, active-value, and component reconciliation evidence;
- malformed or failed source results are rejected without re-running attribution;
- input nonmutation, independent ownership, canonical dtypes, `RangeIndex`, finite
  guards, and deterministic output; and
- unchanged output from existing public attribution and preparation calls.

Randomized valid forests can supplement structural and conservation coverage. They
must not replace literal fixtures whose expected period, horizon, and reconciliation
values are shown independently by hand.

## Performance contract

Correctness and simplicity come first. Let `E` be normalized hierarchy edges, `R` the
source numerical rows, and `A` the number of active leaf-to-ancestor relationships.
The intended design constructs the graph and ancestor relation once, then performs
aggregation proportional to the expanded relationships and selected numerical
columns. It must not repeatedly walk every chain for every column.

Avoid:

- row-wise pandas callbacks;
- dense leaf-by-node matrices;
- recursive aggregation from already rounded parents;
- a fixed hierarchy-depth loop;
- a second attribution or linking calculation; and
- another runtime dependency.

Measure elapsed time and peak memory for realistic selected-result sizes and depths
across all methods and linkers. Establish no new threshold until a correct prototype
produces repeatable evidence. Every existing direct-core and `ppar` threshold remains
unchanged.

## Comparative `pybrinson` review

`gghez/pybrinson` was reviewed at commit
`529b0940937caacec3f2a30609b9ce6b86316a7b`. Its hierarchy implementation reinforced
four useful ideas: explicit parent relationships, cached ancestor chains, cycle
detection, and strict additive parent effects.

This specification makes independent choices suited to `perfattr`'s released pandas
and multi-period result boundary:

- hierarchy is post-calculation rather than embedded in a single-period method;
- leaf and parent numerical rows remain separate;
- weights, authoritative contributions, and linked effects roll up alongside effects;
- graph traversal has no fixed 32-level cap;
- valid unused taxonomy branches are retained; and
- unrecoverable horizon returns are omitted rather than fabricated.

The reviewed source is MIT-licensed, but no code, test value, fixture, or documentation
text is copied. Primary financial references and independent project fixtures govern
the implementation.

## References and provenance

Methodological context:

- Bacon, Carl R. *Practical Portfolio Performance Measurement and Attribution*, 2nd
  ed. Wiley, 2008, ch. 5. [Chapter DOI](https://doi.org/10.1002/9781119206309.ch5).
- CFA Institute Research Foundation. *Performance Attribution: History and Progress*.
  2019. [Research Foundation brief][cfa-history].

Comparative product behavior:

- Eagle Performance, *Create Brinson and Fachler Options – Multicurrency Analysis*.
  Its single-level option rolls selected-level results upward, while its all-level
  options recalculate relative to a total or segment. [Hierarchy-option
  documentation][eagle-hierarchy].

[cfa-history]: https://rpc.cfainstitute.org/research/foundation/2019/performance-attribution
[eagle-hierarchy]: https://eagledocs.atlassian.net/wiki/spaces/Performance2017/pages/856720063

All implementation, tests, fixtures, and prose must be original project work under
the existing MIT license. Fixture provenance must record literal source facts and
independent arithmetic; production output, `ppar`, `pybrinson`, and other
implementations may not supply expected values.
