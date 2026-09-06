# perfattr Roadmap 10: Hierarchical Result Roll-Up

**Status:** Complete September 6, 2026. Released in `perfattr==0.9.0a1`.

This roadmap promotes the additive hierarchical result-roll-up candidate from roadmap
3. Its governing contract is
[`docs/hierarchical_result_rollup_specification.md`][hierarchy-spec].

[hierarchy-spec]: ../docs/hierarchical_result_rollup_specification.md

## Objective

Add one deliberately limited post-calculation operation that rolls already calculated
leaf-level attribution values into their ancestors. Preserve every released
`AttributionResult` frame and calculation policy, and keep independently recalculated
multi-level attribution as a separate, deferred feature.

The approved release target is `perfattr==0.9.0a1`.

## User problem and smallest design

Users may calculate attribution at a detailed classification and then need the same
additive values summarized at sector, region, asset-class, or other parent levels.
Re-running attribution at every level would introduce materially different financial
policies. It is unnecessary when the immediate question is simply where the released
leaf results accumulate.

The smallest design adds one function, one result dataclass, one exact two-column
hierarchy input, and two numerical roll-up frames. It sums descendant leaf values and
derives only the period returns that remain mathematically recoverable from released
weight and contribution. It does not add hierarchy to the attribution calculator,
modify the five released frames, or create a general graph or reporting framework.

## Scope boundary

Roadmap 10 owns only:

- a public `roll_up_attribution` function accepting an `AttributionResult` and a
  static hierarchy DataFrame;
- a separate `HierarchicalRollupResult` boundary;
- exact validation of a finite, single-parent forest;
- deterministic leaf-to-ancestor expansion with no arbitrary depth limit;
- parent-period aggregation for weights, contributions, returns, and effects;
- parent-horizon aggregation for weights and linked contributions and effects;
- explicit parent and root reconciliation evidence;
- independent fixtures, documentation, and direct-core performance evidence; and
- verification that `ppar` remains unchanged.

Roadmap 10 does not add:

- attribution recalculated relative to the total portfolio or a parent segment;
- weight normalization or parent-level Brinson formulas;
- a cumulative parent frame or independently linked parent returns;
- full-horizon parent return fields that cannot be recovered from released results;
- time-varying hierarchy assignments;
- source classification, hierarchy-file loading, or vendor behavior;
- labels, display order, synthetic total identifiers, charts, or presentation rows;
- multiple-parent graphs, allocation of one leaf across multiple parents, or partial
  hierarchy coverage;
- a `ppar` adapter or report change; or
- another runtime dependency.

## Approved public boundary

```python
result = roll_up_attribution(
    attribution_result,
    hierarchy,
    reconciliation_tolerance=1e-12,
)
```

The hierarchy uses exactly:

```text
identifier, parent_identifier
```

Each row is a directed child-to-parent edge. Roots are inferred as parent identifiers
that never appear as children. The source result identifiers must be leaves in the
graph and must all be covered. A valid hierarchy may contain additional unused
branches so one reusable taxonomy can serve multiple selected results.

The approved result owns independent DataFrames:

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

`period_rollup` and `overall_rollup` contain active parent rows only. They deliberately
exclude the original leaves, which remain available in the supplied
`AttributionResult`. Keeping these boundaries separate prevents accidental double
counting and leaves presentation free to combine or traverse them explicitly.

## Approved financial policy

Every active leaf contributes once to every ancestor in its unique chain. Parent
values are calculated directly from descendant leaves, not recursively from rounded
intermediate parents.

Additive columns are strict sums. For each parent period:

```text
parent weight       = sum(descendant leaf weights)
parent contribution = sum(descendant leaf contributions)
parent effect       = sum(descendant leaf effects)
```

Portfolio and benchmark period returns use the released effective-return rule:

```text
contribution / weight     when weight != 0
0                         when weight == 0 and contribution == 0
null                      when weight == 0 and contribution != 0
```

Active values retain their released derivations. No Brinson effect is recalculated at
a parent. In particular, the sum of descendant allocation effects remains the parent
allocation value even when applying the selected Brinson formula to parent weights
and returns would produce another number. That other calculation belongs to the
deferred hierarchical-recalculation feature.

The horizon frame sums the released leaf `overall_detail` weights, linked
contributions, and linked effects. It omits portfolio, benchmark, and active return:
the released result does not retain enough source-period return information to
reconstruct those parent horizon returns faithfully in every authoritative-
contribution case. Roadmap 10 will not invent a return methodology to fill that gap.

## Compatibility plan

- Do not add, remove, rename, reorder, or reinterpret a column in any released
  `AttributionResult` frame.
- Do not change `calculate_attribution`, any `AttributionMethod`, any
  `EffectLinkingMethod`, or their defaults.
- Keep hierarchy output under a separately named result type and exact schemas.
- Preserve source method and effect-linker identities as result metadata.
- Accept all four released attribution methods and all three released effect linkers.
- Retain the unchanged `1e-12` default relative and absolute reconciliation tolerance.
- Keep pandas and NumPy as the only runtime dependencies.
- Require no `ppar` change; a host may adopt this new opt-in function later under a
  separate approved scope.

## Implementation sequence

### 1. Approve the contract

**Status:** Complete September 6, 2026.

- Approve the result-only user problem and the separation from hierarchical
  recalculation.
- Approve the edge-list hierarchy, complete leaf coverage, single-parent forest, and
  static-hierarchy boundary.
- Approve the parent-only numerical frames and separate hierarchy metadata.
- Approve the period-return derivation and deliberate omission of horizon returns.
- Approve exact schemas, reconciliation policy, unchanged `ppar` boundary, and the
  proposed `0.9.0a1` target.

**Gate:** No source, test, fixture, version, or public API implementation begins before
explicit user approval of this roadmap and its governing specification.

**Approval evidence:** On September 6, 2026, the user explicitly approved Roadmap 10
and its governing specification. This approves the result-only boundary, its
separation from hierarchical recalculation, the exact edge-list hierarchy, complete
leaf coverage, single-parent static forest, parent-only numerical frames, separate
hierarchy metadata, period-return derivation, deliberate omission of horizon returns,
exact schemas, reconciliation policy, unchanged `ppar` boundary, and `0.9.0a1`
prerelease target.

**Gate:** Passed. Step 2 is authorized; later steps remain dependency-gated.

### 2. Establish the public identity and schemas

**Status:** Complete September 6, 2026.

- Add and export `HierarchicalRollupResult` and `roll_up_attribution`.
- Establish exact two- and three-effect period schemas, exact two- and three-effect
  horizon schemas, the normalized hierarchy schema, and the hierarchy reconciliation
  schema.
- Add strict type, direct-construction, independent-ownership, and schema tests.
- Temporarily reject otherwise valid roll-up calls until graph normalization and
  financial aggregation are independently verified.

**Gate:** Public identity and exact-schema tests pass, the temporary guard cannot be
bypassed, and no released schema or calculation behavior changes.

**Implementation evidence:** `HierarchicalRollupResult` and `roll_up_attribution` are
exported from `perfattr.hierarchy` and the package root. The dataclass exposes the six
approved fields in exact order, requires explicit source method and effect-linker
metadata, and documents ordinary direct-construction ownership without implying
automatic validation or immutability.

Dedicated constants establish the normalized hierarchy, two- and three-effect period
roll-up, two- and three-effect horizon roll-up, and hierarchy-reconciliation schemas.
The period schemas exactly reuse the released period-detail columns. The horizon
schemas deliberately omit the three unrecoverable return columns, and three-effect
schemas insert only their approved interaction columns.

The staged function rejects result and hierarchy lookalikes, applies the released
strict positive finite tolerance boundary, and then raises the documented temporary
`NotImplementedError`. A real reconciled result and valid-looking hierarchy reach the
guard without any caller-input mutation. No graph normalization, ancestor traversal,
financial aggregation, reconciliation, or partial fallback is reachable.

**Gate:** Passed. All 381 tests pass, including 13 focused hierarchy-boundary cases;
Pyright reports no errors or warnings; Pylint reports 10.00/10 with no messages across
`src`, `tests`, and `scripts`; and `git diff --check` reports no whitespace errors. No
released result schema, calculation, default, version, dependency, tolerance,
threshold, or invariant changed.

### 3. Normalize and validate the hierarchy

**Status:** Complete September 6, 2026.

- Normalize textual identities without coercion and collapse exact duplicate edges.
- Reject missing or extra columns, null or blank identities, self-parent edges,
  conflicting parents, cycles, incomplete source-leaf coverage, and source identifiers
  used as internal parents.
- Infer roots, permit a forest and valid unused branches, and resolve every active
  leaf's complete ancestor chain.
- Use graph traversal rather than an arbitrary maximum-depth constant.
- Prove deterministic ordering, caller nonmutation, and independent returned
  hierarchy ownership.

**Gate:** Independently specified tree, deep-chain, forest, duplicate, unused-branch,
coverage, multi-parent, collision, self-edge, and cycle tests pass.

**Implementation evidence:** A private hierarchy plan now owns the complete normalized
edge list, deterministic active leaf-to-ancestor relationships with immediate-parent
distance one, and explicit active-parent and active-root identities. Later numerical
steps can reuse this single plan without reinterpreting or repeatedly traversing the
graph.

Normalization requires the exact two-column pandas schema, applies the released
textual identity policy without coercion, trims whitespace, preserves case and leading
zeroes, collapses exact normalized duplicates, and returns a deterministic independent
copy. Conflicting parents, self-parent edges, invalid identities, and cycles anywhere
in the complete taxonomy—including unused branches—raise `AttributionError`.

Plan construction requires a nonempty, completely covered source-leaf set and rejects
any source identifier used as an internal parent. Parent identifiers without outgoing
edges are inferred roots; valid forests and unused branches remain supported. Cycle
detection and ancestor expansion are iterative, with no recursion or fixed depth cap.
A 257-ancestor fixture verifies the entire valid chain, well beyond the comparative
implementation's fixed limit.

The public `roll_up_attribution` guard deliberately remains unchanged and still
precedes graph-content validation. Step 3 behavior is private until the financial
integration removes the guard in Step 5 under the roadmap's dependency order, so no
partial hierarchy feature is exposed.

**Gate:** Passed. All 398 tests pass, including 30 focused hierarchy cases; Pyright
reports no errors or warnings; Pylint reports 10.00/10 with no messages across `src`,
`tests`, and `scripts`; and `git diff --check` reports no whitespace errors. No
released schema, calculation, default, version, dependency, tolerance, threshold, or
invariant changed.

### 4. Implement parent-period roll-up

**Status:** Complete September 6, 2026.

- Expand active leaves to ancestors once and aggregate with vectorized pandas or NumPy
  operations.
- Sum every additive period column from descendant leaves.
- Derive portfolio, benchmark, and active period returns under the released null
  contract.
- Support two- and three-effect schemas without recalculating Brinson formulas.
- Emit active parent rows only in deterministic period and identifier order.

**Gate:** Complete independently hand-calculated period fixtures pass across every
attribution-method family, including authoritative contributions, signed and zero
weights, null returns, missing sides, and multiple hierarchy depths.

**Implementation evidence:** The private period roll-up expands source rows through
the Step 3 leaf-to-ancestor relation once, orders descendant leaves deterministically,
and uses vectorized pandas grouping to calculate every active parent directly from
leaves. It never aggregates from an intermediate parent and never reapplies a Brinson
formula to parent facts.

Weights, authoritative contributions, unlinked effects, linked contributions, and
linked effects are strict descendant sums. Portfolio and benchmark period returns are
derived from their summed contribution and weight under the released rule: division
for nonzero weight, zero for zero weight and zero contribution, and null for zero
weight with nonzero contribution. Active weight and contribution are differences;
active return is a difference only when both side returns are defined. Output retains
the exact method-specific schema, `datetime64[ns]` dates, `int64` day count,
`string[python]` identifier, `float64` numerical values, deterministic period and
identifier order, and zero-based `RangeIndex`.

The complete independent fixture begins from literal prepared facts and documents all
parent arithmetic. It covers signed exposure, both missing-side directions, a
zero-weight authoritative fee, null and zero returns, two hierarchy levels, all four
attribution methods, and all three effect linkers. Because the fixture has one period,
each linker is independently known to be the identity. A separate two-period BHB
three-effect Menchero test verifies nontrivial already-linked values and chronological
parent output.

Focused tests prove the central methodological boundary numerically. Sector 1's
summed Brinson-Fachler allocation is `-0.0003`, while recalculation from parent facts
would produce `0.002325`; its summed BHB allocation is `0.018`, while parent
recalculation would produce `0.020625`. Only the summed leaf values are returned.
Additional tests protect finite aggregation, source and hierarchy nonmutation,
independent output ownership, caller-row-order determinism, and the unchanged public
guard.

**Gate:** Passed. All 416 tests pass, including 18 focused parent-period cases;
Pyright reports no errors or warnings; Pylint reports 10.00/10 with no messages across
`src`, `tests`, and `scripts`; and `git diff --check` reports no whitespace errors. No
released schema, calculation, default, version, dependency, tolerance, threshold, or
invariant changed.

### 5. Implement horizon roll-up and reconciliation

**Status:** Complete September 6, 2026.

- Sum parent horizon weights, linked contributions, and linked effects directly from
  descendant leaf `overall_detail` rows.
- Keep unrecoverable horizon return columns absent.
- Reconcile each active parent to its immediate active children and active roots to
  the original leaves for every additive column.
- Verify active-weight, active-contribution, and effect-component identities.
- Remove the temporary public guard only after every financial and structural test
  passes.

**Gate:** Period, horizon, parent, root, component, method, linker, schema, null,
ordering, and finite-value contracts pass at the unchanged tolerance.

**Implementation evidence:** The public operation now validates the complete mutable
`AttributionResult` boundary before using it. Exact released schemas, column order,
dtypes, zero-based indexes, unique and deterministic keys, period/day/horizon
structure, identifier agreement, return derivations, finite values, and canonical
source reconciliation evidence are required. Invalid or caller-modified source
results fail explicitly rather than producing hierarchy output.

The horizon roll-up sums weights, linked contributions, and linked effects directly
from descendant `overall_detail` leaf rows. It derives only active weight and linked
active contribution, retains the exact method-specific schema and deterministic
ordering, and does not expose horizon returns or cumulative parent values.

Reconciliation covers every additive field for each active parent against its
immediate active children. Separate forest-wide checks compare the sum of active
roots with the original source leaves. Parent evidence additionally verifies active
weight, period active contribution, linked active contribution, unlinked period
effect components, and linked effect components, including explicit interaction for
three-effect methods. Every row must be finite and pass the unchanged relative and
absolute tolerance; a failure raises `AttributionError` rather than returning a
partially trusted result.

Complete independently calculated expectations exercise all four attribution
methods and all three linkers. Focused cases also cover a multi-root forest, tampered
parent evidence, strict source-result corruption, exact schemas and dtypes, null and
ordering contracts, caller nonmutation, and independent result ownership. With those
checks passing, the temporary public guard was removed and the complete result-only
vertical slice became usable.

**Gate:** Passed. All 445 tests pass, including 77 focused hierarchy cases; Pyright
reports no errors or warnings; Pylint reports 10.00/10 with no messages across `src`
and `tests`; and `git diff --check` and the 99-character line-length check report no
errors. No released result schema, calculation, default, version, dependency,
tolerance, threshold, or invariant changed.

### 6. Complete fixtures, documentation, quality, and direct performance

**Status:** Complete September 6, 2026.

- Record complete independently hand-calculated period, horizon, hierarchy, and
  reconciliation expectations.
- Explain every nontrivial calculation and edge case in test docstrings, comments, or
  fixture provenance.
- Document the result-only boundary, return limitation, public use, and distinction
  from hierarchical recalculation in README and the portable specification.
- Run the complete test, Pyright, Pylint, formatting, build, metadata, and clean-wheel
  gates on every supported Python version.
- Measure elapsed time and peak memory across realistic row counts, hierarchy depths,
  all four attribution methods, and all three effect linkers.
- Establish no new performance threshold without correct, repeatable evidence.

**Gate:** All established gates pass without weakening a schema, invariant, warning,
tolerance, threshold, or dependency boundary.

**Implementation evidence:** `README.md` now lists hierarchical result roll-up among
the main distinguishing features and contains a complete public example. It explains
the static forest, parent-only result boundary, direct summation of already calculated
effects, derived period returns, deliberate horizon-return and cumulative omissions,
and explicit reconciliation evidence. The portable calculation specification links
the implemented supplement and now distinguishes this operation from deferred
level-relative hierarchical recalculation. The governing hierarchy specification is
marked implemented.

The central fixture-provenance record documents the original literal source facts,
independent parent arithmetic, fee/null behavior, effect sums, parent-recalculation
counterexamples, one-period linker identity, horizon omissions, and reconciliation
expectations in the hierarchy financial tests. No fixture or expected value came from
production output, `ppar`, `pybrinson`, or another implementation.

The new repeatable direct benchmark constructs source results and hierarchies before
measurement, then measures the complete public roll-up boundary. Its 48-case matrix
crossed all four attribution methods and all three effect linkers over 6,063 to
121,260 source-result rows, 60 to 300 periods, 101 to 1,011 leaves, and depths two to
eight. Median elapsed ranges were 0.0404–0.0511 seconds for the normal workload,
0.1470–0.1687 seconds for selected 10x, 0.3426–0.3760 seconds for 121,260 monthly
rows, and 0.1273–0.1390 seconds for 25-year history. Incremental traced allocation
ranged from 5.2 to 222.6 MiB. These observations retain the simple implementation and
establish no threshold.

Python 3.11, 3.12, 3.13, and 3.14 each pass all 445 tests in isolated environments.
Pyright reports no errors or warnings, and Pylint reports 10.00/10 with no messages
across `src`, `tests`, and `scripts`. A fresh source distribution and universal wheel
build successfully from the source tree; Twine validates both artifacts; archive
inspection confirms the hierarchy modules, tests, benchmark, documentation, license,
and project metadata are present as applicable. Clean wheel installations under all
four supported Python versions successfully import the package, calculate a source
result, perform public hierarchy roll-up, and return passing reconciliation evidence.
`git diff --check` reports no whitespace errors, and all changed Python code conforms
to the established 99-character line limit.

**Gate:** Passed. No released result schema, calculation, default, version,
dependency, tolerance, threshold, warning, or invariant changed.

### 7. Verify the unchanged `ppar` boundary

**Status:** Complete September 6, 2026.

- Install the candidate wheel into `ppar`'s release-candidate environment.
- Confirm `ppar` neither imports nor calls the new opt-in hierarchy boundary.
- Run the complete `ppar` test, analysis, packaging, demo, and unchanged 500x gates.
- Do not edit `ppar` unless an actual defect requires separate approval.

**Gate:** Existing `ppar` values, schemas, reports, and scale behavior remain unchanged
at every established tolerance and threshold.

**Implementation evidence:** Inspection confirmed that `ppar` neither imports nor
calls `roll_up_attribution` or `HierarchicalRollupResult`. Its sole numerical adapter
continues to call `calculate_attribution` without selecting a method or linker, so the
host remains on its established Brinson-Fachler two-effect and Carino defaults. The
adapter retains its `5e-9` compatibility tolerance, exact Polars/pandas translation,
and unchanged host result schemas.

The locally built `perfattr==0.8.0a1` verification wheel was installed into `ppar`'s
Python 3.12.1 release-candidate environment. The complete established command passed
305 tests and 477 subtests, Mypy, Pyright with no errors or warnings, both Pylint
checks, documentation-link validation, README image drift checks, universal-wheel
construction and inspection, Twine validation, package metadata, and clean installed
generic and Axys/APX workflows. Each installed demonstration produced its expected 11
artifacts.

The unchanged 500x workflow retained large-site financial and artifact equivalence
while processing 12,126 and 6,063,000 rows. Observed time was 1.48 and 1.57 seconds, a
1.060x ratio with no performance threshold. The 10x selected-input case took 0.42 and
0.84 seconds, a 2.018x observational ratio. The 5x long-history case took 1.48 and
2.25 seconds, a 1.521x ratio below the unchanged 1.58x warning and 1.65x failure
boundaries.

The `ppar` worktree contained pre-existing user changes before verification. Its
tracked status, changed-file list, and line-change counts were identical afterward;
no `ppar` source, test, documentation, image, configuration, schema, dependency,
tolerance, warning, threshold, or presentation behavior was changed by Roadmap 10.

**Gate:** Passed. The new hierarchy boundary remains an isolated, opt-in `perfattr`
feature and existing `ppar` behavior remains unchanged.

### 8. Release `perfattr==0.9.0a1`

**Status:** Complete September 6, 2026.

- Update version and release-facing documentation only after every prior gate passes.
- Build and validate fresh source and wheel distributions.
- Obtain explicit approval before committing, tagging, pushing, creating a GitHub
  prerelease, or publishing to PyPI.
- Verify the public artifact in clean environments on every supported Python version.

**Gate:** The tagged commit, GitHub prerelease, PyPI files, installed version, public
imports, and supported-version smoke tests agree.

**Prepublication evidence:** The package and its public version test identify
`perfattr==0.9.0a1`, and release-facing documentation identifies hierarchical result
roll-up as the release candidate. The source-tree suite passes all 445 tests; Pyright
reports no errors or warnings; Pylint reports 10.00/10 with no messages across `src`,
`tests`, and `scripts`; and `git diff --check` is clean.

An isolated Hatchling build produced `perfattr-0.9.0a1.tar.gz` and the universal
`perfattr-0.9.0a1-py3-none-any.whl`. Twine accepted both artifacts. The wheel SHA-256
is `af962ecbce7f0ace9a3aea2157a33b622fbba37295da135e0bedfa2ad1c71564`; the
source-distribution SHA-256 is
`b6a8b39f03cd606cdf09057e13995edf47d49075a62aa0aab40c368800a4c85b`.
Archive inspection confirmed version and Python metadata, the unchanged two-runtime-
dependency contract, and inclusion of the hierarchy source, benchmark, governing
specification, tests, and independently documented fixture provenance.

The complete 445-test suite passes against the installed candidate wheel from
`site-packages` on Python 3.11.9, 3.12.1, 3.13.1, and 3.14.7; `pip check` passes in
all four environments. No tolerance, warning, threshold, runtime dependency,
invariant, or release gate was changed.

At this checkpoint, GitHub authentication is active for `JohnDReynolds`; neither tag
nor release `v0.9.0a1` exists. The public PyPI index lists `0.8.0a1` as the latest
prerelease and does not contain `0.9.0a1`. The user explicitly approved Step 8 after
Steps 1–7 and the hierarchy typing cleanup passed the complete project gates.

**Release evidence:** The user explicitly approved creating the GitHub prerelease and
the resulting irreversible PyPI publication. Clean release commit
`75cc0e633c8d9d4f0ac8204ef1380f7d11452593` was pushed to `main`. GitHub Actions CI
run `34050384123` passed the complete suite on Python 3.11, 3.12, 3.13, and 3.14 and
independently built, validated, installed, and imported the distributions.

The release commit was tagged with annotated tag `v0.9.0a1` and published as a
[GitHub prerelease](https://github.com/JohnDReynolds/perfattr/releases/tag/v0.9.0a1).
Trusted-publisher run `34050551681` built the tagged source and wheel distributions,
verified that their metadata matched the tag, and published both artifacts to PyPI.
The public PyPI hashes exactly match the locally validated hashes above.

After public-index propagation, clean no-cache Python 3.11.9, 3.12.1, 3.13.1, and
3.14.7 environments installed `perfattr==0.9.0a1` from
`https://pypi.org/simple`. Every module resolved from its environment's
`site-packages`; `pip check` passed; and the complete 445-test suite passed in all
four environments.

**Gate:** Passed. The approved prerelease is published on GitHub and PyPI and is
independently installable and usable across every supported Python version.

## Test matrix

At minimum, combine:

- all four released attribution methods and all three released effect linkers;
- one and multiple periods, two and three effects, and one through many hierarchy
  levels;
- one root and multiple roots, shared parents, exact duplicate edges, and unused valid
  branches;
- every invalid graph condition named in Step 3;
- positive, negative, zero, signed, and authoritative values;
- zero-weight zero-contribution and zero-weight nonzero-contribution parents;
- cash, fee, financing, disappearing-identifier, and missing-side representations;
- parent-versus-child and root-versus-leaf reconciliation;
- caller nonmutation, independent result ownership, deterministic ordering, exact
  schemas, dtypes, null placement, and finite guards; and
- a sufficiently deep valid chain to prove there is no arbitrary depth cap.

Randomized valid forests may supplement but never replace literal independently
hand-calculated fixtures.

## Performance and dependency constraints

- Preserve pandas and NumPy as the only runtime dependencies.
- Target work proportional to normalized edges plus active leaf-to-ancestor
  relationships; do not scan all paths repeatedly for every numerical column.
- Calculate parents directly from leaves so depth does not create recursive rounding
  or repeated aggregation work.
- Avoid row-wise pandas callbacks, dense leaf-by-node matrices, and speculative caches.
- Measure before optimizing and preserve all existing direct-core and `ppar` gates.

## Comparative review and provenance

Eagle Performance documentation distinguishes a single-level higher-level roll-up
from all-level attribution recalculated relative to a total or a segment. That product
distinction supports keeping Roadmap 10 separate from the deferred recalculation
candidate; Eagle is comparative product evidence, not calculation authority.

`gghez/pybrinson` was reviewed at commit
`529b0940937caacec3f2a30609b9ce6b86316a7b` as Roadmap 3 requests. Its implementation
reinforced explicit child-to-parent edges, ancestor-chain aggregation, cycle tests,
and additive parent effects. Roadmap 10 independently chooses a pandas result-only
boundary, no fixed depth limit, separate leaf and parent frames, multi-period linked
values, and no fabricated horizon returns.

The reviewed `pybrinson` source is MIT-licensed. No source, fixture, expected value,
or documentation text is copied. All implementation and tests must be original
project work, and expected values must be independently calculated and documented.

## References

Methodological context:

- Bacon, Carl R. *Practical Portfolio Performance Measurement and Attribution*, 2nd
  ed. Wiley, 2008, ch. 5. [Chapter DOI](https://doi.org/10.1002/9781119206309.ch5).
- CFA Institute Research Foundation. *Performance Attribution: History and Progress*.
  2019. [Research Foundation brief][cfa-history].

Comparative product behavior:

- Eagle Performance, *Create Brinson and Fachler Options – Multicurrency Analysis*.
  [Hierarchy-option documentation][eagle-hierarchy].

[cfa-history]: https://rpc.cfainstitute.org/research/foundation/2019/performance-attribution
[eagle-hierarchy]: https://eagledocs.atlassian.net/wiki/spaces/Performance2017/pages/856720063

## Completion criterion

Roadmap 10 is complete only when:

- the roadmap and governing specification are explicitly approved;
- every implementation, independent-test, quality, performance, and `ppar` step is
  complete;
- parent values are demonstrably additive result roll-ups rather than recalculated
  attribution;
- every returned parent and root reconciles at the unchanged tolerance;
- no released schema, calculation, default, tolerance, threshold, dependency, or
  invariant is weakened; and
- `perfattr==0.9.0a1` is published and verified from the public PyPI index.
