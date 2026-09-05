# perfattr Roadmap 8: Frongello Recursive Effect Linking

**Status:** Complete September 5, 2026. Released in `perfattr==0.7.0a1`.

This roadmap promotes the Frongello recursive-linking candidate from roadmap 3. Its
governing contract is
[`docs/frongello_recursive_linking_specification.md`][frongello-spec].

[frongello-spec]: ../docs/frongello_recursive_linking_specification.md

## Objective

Add one opt-in Frongello policy for linking arithmetic attribution effects across
time. Preserve Carino as the default effect linker, preserve logarithmic portfolio
and benchmark contribution linking, and make the selected effect-linking policy
explicit in each result.

## User problem and smallest design

The released engine always uses Carino for active-effect linking. That is insufficient
when a client, comparison, or established reporting process requires Frongello's
path-dependent treatment of arithmetic effects.

The smallest useful design is one public enum and one keyword on the existing
calculator. The same calculation, aggregation, schema, and reconciliation pipeline
will remain in place. Roadmap 8 does not justify standalone linker functions, a
plugin framework, a second result type, or a general linking registry.

The public name must be **effect linking**, not merely linking, because portfolio and
benchmark contributions continue to use their released logarithmic linker.

## Scope boundary

Roadmap 8 owns only:

- an explicit `EffectLinkingMethod` with released Carino and new Frongello members;
- one keyword-only `effect_linking_method` calculation argument;
- result metadata recording the selected effect linker;
- Frongello-linked allocation, selection, optional interaction, and total effects;
- independent primary-source and full-input fixtures;
- unchanged result-frame schemas and reconciliation names;
- documentation and direct-core performance evidence; and
- verification that `ppar` remains on its unchanged default Carino boundary.

Roadmap 8 does not add:

- another single-period attribution method or effect;
- Frongello linking for portfolio, benchmark, or active contribution columns;
- as-of cumulative relinking or a new cumulative-result schema;
- GRAP, geometric, or Menchero linking;
- new prepared-input columns or relaxed return rules;
- hierarchy, currency, or external-flow behavior;
- a `ppar` selector or presentation change; or
- another runtime dependency.

## Proposed compatibility plan

Add this public string enum:

```python
class EffectLinkingMethod(str, Enum):
    CARINO = "Carino"
    FRONGELLO = "Frongello"
```

Extend the existing keyword-only boundary:

```python
def calculate_attribution(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    method: AttributionMethod = AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
    effect_linking_method: EffectLinkingMethod = EffectLinkingMethod.CARINO,
    reconciliation_tolerance: float = 1e-12,
) -> AttributionResult:
    ...
```

Append matching metadata to `AttributionResult` after its released `method` field,
with the same Carino default. Existing callers that omit the new argument must receive
the exact `perfattr==0.6.0a1` values, frames, ordering, dtypes, null placement, and
errors. Existing direct construction of `AttributionResult` remains valid because the
new field has a default.

All five result-frame schemas and all reconciliation check names remain unchanged.
The generic `linked_*_effect` names already describe either policy; callers use result
metadata to identify which policy produced them.

The argument accepts only an `EffectLinkingMethod` member. Strings, members of other
enums, and arbitrary objects raise `TypeError`. No compatibility sentinel or implicit
string coercion is added.

Approval of this roadmap approves this API and schema plan. A different name, default,
schema, contribution-linking rule, or cumulative interpretation requires separate
approval.

## Financial policy

For source period `t`, let `P[t]` and `B[t]` be the released portfolio and benchmark
period returns. For any identifier and effect channel, let `G[t]` be its unlinked
single-period effect. The Frongello full-horizon factor for that source period is:

```text
prefix_portfolio[t] = product(1 + P[s]) for s < t
suffix_benchmark[t] = product(1 + B[s]) for s > t
factor[t]           = prefix_portfolio[t] * suffix_benchmark[t]
linked_effect[t]    = G[t] * factor[t]
```

This is the closed form obtained by unrolling Frongello's forward recursion:

```text
increment[t] = prefix_portfolio[t] * G[t]
               + B[t] * cumulative_linked_effect_before_t
```

The closed form preserves each existing source-period row and assigns later benchmark
growth back to the effect's originating period. It produces the same full-horizon
effect as the recursion without synthesizing rows for identifiers absent in a later
period. This is especially important because `period_detail` is a source-period table,
not a ledger of recursive carry-forward events.

The same factor applies independently to allocation, selection, interaction when the
selected attribution method exposes it, and total. Linearity therefore preserves all
two-effect, three-effect, and BHB collapse identities.

For one period the prefix and suffix products are both one, so linked effects equal
unlinked effects. Period order is chronological and financially significant. Input
row order remains irrelevant because the released normalization produces deterministic
chronological output.

## Deliberate output interpretation

Under both Carino and Frongello, each `linked_*_effect` period-detail value represents
the originating period's allocated share of the selected **complete horizon**. The
`cumulative_*_effect` columns remain cumulative sums of those full-horizon allocations;
intermediate rows are not independently relinked as-of results.

Roadmap 8 deliberately does not expose the alternative display in which benchmark
carry-forward is booked as a new increment in each later period. That display would
require synthetic period/identifier rows when an identifier disappears and would
change the meaning and row population of released result frames. The full-horizon
totals are mathematically identical, but the period presentation is not.

Portfolio and benchmark contributions retain their released logarithmic linking.
Consequently, Frongello effect values and logarithmically linked active contributions
need reconcile at the complete horizon, not necessarily in each intermediate
`cumulative` row.

## Implementation sequence

### 1. Approve the contract

**Status:** Complete September 5, 2026.

- Approve the user problem, public names, strict enum behavior, unchanged default,
  formula, source-period interpretation, and `0.7.0a1` prerelease plan.
- Confirm that only active effects select Frongello and contributions remain
  logarithmically linked.
- Confirm that `ppar` remains on its default Carino path.

**Gate:** No implementation begins before explicit user approval.

**Approval evidence:** The user explicitly approved Roadmap 8 Step 1 on September 5,
2026. This approves the user problem, public names, strict enum behavior, unchanged
Carino default, Frongello formula and source-period interpretation, logarithmic
contribution-linking boundary, unchanged `ppar` behavior, and proposed `0.7.0a1`
prerelease plan.

**Gate:** Passed. Implementation is authorized only in the sequence below.

### 2. Extend effect-linking identity and metadata

**Status:** Complete September 5, 2026.

- Add and export `EffectLinkingMethod`.
- Add strict normalization for the new argument.
- Add the keyword and append result metadata with a Carino default.
- Temporarily reject `FRONGELLO` at the public calculation boundary until its
  numerical policy is independently verified.

**Gate:** Public identity, strict-validation, default-metadata, direct-construction,
and temporary-guard tests pass without changing any released result frame.

**Implementation evidence:** `EffectLinkingMethod` now exposes the approved `CARINO`
and `FRONGELLO` identities from both `perfattr.method` and the root package. The
calculator accepts the new keyword-only policy, validates it without string or
cross-enum coercion, and returns explicit metadata. `AttributionResult` appends the
same metadata with a Carino default, preserving existing direct construction.

Explicit and omitted Carino calls use the released calculation path and produce
exactly equal frames. During Steps 2–3, Frongello raised the documented temporary
`NotImplementedError` before financial input normalization, preventing the new
identity from falling through to mislabeled Carino results. Step 4 removed that guard
only after cross-frame verification. Result construction was simplified without
changing calculation order or any returned frame.

**Gate:** Passed. All 299 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; and
`git diff --check` reports no whitespace errors. No released schema, numerical value,
default, tolerance, reconciliation name, or dependency changed.

### 3. Implement the Frongello factor

**Status:** Complete September 5, 2026.

- Compute chronological portfolio prefixes and benchmark suffixes in linear time.
- Apply one factor vector to each selected effect channel.
- Keep Carino expressions byte-for-byte or structurally unchanged where practical.
- Reject non-finite factors or linked effects with `AttributionError`.
- Do not use row-wise pandas callbacks or an identifier-by-period expansion.

**Gate:** The primary two-period example, its reversed ordering, one-period identity,
and an independently stepped recursion agree within `1e-12` relative and absolute
tolerance.

**Implementation evidence:** A focused numerical helper now calculates the approved
prefix-portfolio, suffix-benchmark Frongello factors with two linear-time cumulative
product passes. The existing private period linker selects that factor vector only
when explicitly requested and otherwise retains the released Carino expression.
Portfolio and benchmark contributions continue to use their unchanged logarithmic
coefficients. One selected effect vector is applied to allocation, selection,
interaction when present, and total without row-wise pandas callbacks or an expanded
identifier grid. Explicit finite guards reject invalid factors and products.

Independent tests reproduce Frongello's primary two-period allocation, selection, and
active totals; reproduce the distinct reversed-order result; prove the one-period
identity; and compare the optimized factors with a separately stepped four-period
recursion and literal intermediate values. A three-effect case proves that interaction
uses the identical factor and retains row-level component reconciliation. Defensive
cases isolate non-finite factor and linked-effect failures. Public Frongello execution
remained behind the Step 2 guard until Step 4 verified every returned frame and
reconciliation identity.

**Gate:** Passed. All 306 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; and
`git diff --check` reports no whitespace errors. Every literal and recursive value
passes at the unchanged `1e-12` relative and absolute tolerance. No released Carino
value, public schema, default, dependency, tolerance, or threshold changed.

### 4. Integrate aggregation and reconciliation

**Status:** Complete September 5, 2026.

- Reuse period detail, period summary, overall detail, cumulative, and reconciliation
  builders without schema branches.
- Prove full-horizon linked effects equal compounded portfolio return minus compounded
  benchmark return.
- Prove component and compact/explicit-interaction identities under all four released
  attribution methods.
- Preserve logarithmic contribution linking exactly.

**Gate:** Every result frame and reconciliation identity passes at the unchanged
`1e-12` tolerance; Carino output remains unchanged.

**Implementation evidence:** The public calculator now passes the validated
`EffectLinkingMethod` into the private linker and returns the selected metadata. The
temporary Frongello guard is removed. Existing period-summary, overall-detail,
cumulative, and reconciliation builders consume the same generic linked-effect
columns, so no schema-specific aggregation branch or duplicate engine was added.

The regular two-period prepared-input fixture has independent literal Frongello
expectations for every linked period-detail effect, period summary, identifier horizon
total, and cumulative effect. Its final linked total equals the independently
compounded active return and logarithmically linked active contribution. Tests across
all four attribution methods prove identical Carino/Frongello schemas, exact equality
of every non-linked-effect frame column, unchanged contribution linking, unchanged
unlinked effects, and passing reconciliation names and rows. Separate BF and BHB
comparisons prove allocation, total, and selection-plus-interaction collapse in period
detail, period summary, overall detail, and cumulative output. All four methods also
remain finite and reconciled on the existing near-minus-one boundary fixture.

**Gate:** Passed. All 317 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; and
`git diff --check` reports no whitespace errors. Every financial comparison uses the
unchanged `1e-12` relative and absolute tolerance. No schema, reconciliation name,
Carino value, contribution value, default, dependency, tolerance, or threshold
changed.

### 5. Complete independent fixtures and documentation

**Status:** Complete September 5, 2026.

- Record the paper's two-period worked example directly from the primary source and
  explain every arithmetic step in test docstrings.
- Add a complete prepared-input fixture with hand-calculated identifier, period,
  overall, cumulative, and reconciliation expectations.
- Cover positive, negative, and zero effects; missing sides; signed weights;
  authoritative contributions; undefined returns; and identifiers that disappear.
- Document period ordering, source-period allocation, Carino default compatibility,
  contribution/effect separation, and Frongello/GRAP horizon equivalence.
- Keep all nontrivial expected values and calculations extensively explained in
  docstrings or fixture provenance as required by the preparation specification and
  `AGENTS.md`.

**Gate:** Expected values are demonstrably independent of production output, `ppar`,
`pybrinson`, and other implementations.

The existing `multi_period_linking` prepared inputs now have complete independent
Frongello expectations for period detail, period summary, overall detail, cumulative
output, and all reconciliation rows. Fixture provenance derives each period return,
source factor, identifier effect, aggregation, observed-day weight, compound return,
logarithmic contribution, and horizon identity from the inputs and written formulas.
The primary paper example and reversed chronology retain their direct arithmetic in
test docstrings. None of these expected values came from production output, `ppar`,
`pybrinson`, or another implementation.

Focused public tests cover positive, negative, and zero effects; missing sides; a
signed weight; explicit cash; authoritative contributions; an undefined-return fee;
and identifiers that disappear. The disappearing-cash and fee cases prove that later
benchmark growth stays on the originating row through its suffix factor without a
synthetic later row. All four attribution methods preserve their one-period edge-case
representations under Frongello's identity factor. Determinism, input nonmutation, and
independent result ownership now run under both effect linkers and every attribution
method.

README and governing-specification documentation now expose the public option,
Carino default, contribution/effect separation, chronological source allocation,
intermediate cumulative interpretation, and the Frongello/GRAP horizon equivalence.

**Gate evidence:** Passed. All 331 tests pass; Pyright reports no errors or warnings;
Pylint reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; and
`git diff --check` reports no whitespace errors. Every financial comparison uses the
unchanged `1e-12` relative and absolute tolerance. No expected value was generated by
the implementation, no schema or dependency changed in this step, and no tolerance,
threshold, warning, or release gate was relaxed.

### 6. Verify quality, compatibility, and performance

**Status:** Complete September 5, 2026.

- Run the complete test, Pyright, Pylint, formatting, build, metadata, and installed-
  wheel gates on supported Python versions.
- Measure elapsed time and peak memory for Carino and Frongello across all four
  attribution methods on the established direct-core workloads.
- Record evidence before considering a new performance threshold.
- Confirm no runtime dependency beyond pandas, NumPy, and the standard library.

**Gate:** All established gates pass without relaxed tolerances, thresholds, warnings,
or static-analysis expectations.

**Implementation evidence:** The source-tree suite passes all 331 tests. The same 331
tests pass against the installed candidate wheel on Python 3.11.9, 3.12.1, 3.13.1,
and 3.14.7. The Python 3.11 development environment reports no Pyright errors or
warnings and Pylint reports 10.00/10 with no messages across `src`, `tests`, and
`scripts`; `git diff --check` is clean.

An isolated Hatchling build produced the source distribution and universal wheel,
Twine accepted both artifacts, and a clean Python 3.11 environment imported the wheel
from `site-packages` and completed all eight attribution-method/effect-linker
combinations with passing reconciliation. The candidate deliberately retains version
`0.6.0a1`; the approved `0.7.0a1` version change belongs to the release step. Wheel
metadata requires Python 3.11 or newer and lists only NumPy and pandas as runtime
dependencies; build, Pylint, Pyright, pytest, and Twine remain development extras.

The direct-core benchmark now accepts `--effect-linking-method` while retaining
Carino as its default. Five-sample medians and peak traced allocations were recorded
for both linkers, all four attribution methods, and all four established workloads in
`docs/performance.md`. Frongello medians ranged from 8.5% below to 6.7% above paired
Carino observations, with a largest absolute increase of 0.0111 seconds. Peak traced
allocations were identical at reported precision for every paired case. These are
observations rather than thresholds; no optimization, dependency, formula, tolerance,
warning, or release gate changed.

**Gate:** Passed. Quality, supported-version, packaging, installed-wheel,
compatibility, dependency, and direct performance verification are complete without
weakening a gate.

### 7. Verify the unchanged `ppar` boundary

**Status:** Complete September 5, 2026.

- Install the candidate wheel into `ppar`'s release-candidate environment.
- Confirm the adapter omits `effect_linking_method` and therefore remains on Carino.
- Run the complete `ppar` product, documentation, packaging, demonstration, and 500x
  integration gates.
- Do not edit `ppar` unless an actual compatibility defect requires a separately
  approved change.

**Gate:** `ppar` output and performance remain compatible at its established
boundaries.

**Implementation evidence:** The verified candidate wheel was installed into
`ppar`'s Python 3.12.1 development environment. Direct inspection confirmed that
`calculate_with_perfattr` still passes only prepared portfolio and benchmark frames
plus `reconciliation_tolerance`; it omits both attribution-policy arguments and
therefore retains default BF two-effect with default Carino linking. No Frongello
selector, metadata, schema, audit field, or presentation behavior was added to the
host.

The unchanged complete release-candidate command passed 305 tests and 477 subtests,
Mypy across 38 source files, Pyright with no errors or warnings, both Pylint gates,
README image and documentation validation, universal-wheel construction, Twine,
installed-package metadata and CLI checks, and both generic and Axys/APX installed
demonstrations. The candidate was imported from `ppar`'s `site-packages`, not the
adjacent source tree.

The required unchanged 500x workflow also passed. Large-site processing retained
byte-identical artifacts while growing from 12,126 to 6,063,000 rows and measuring
1.34 versus 1.50 seconds, a 1.113x observation with no threshold. The 10x selected
workload measured 0.40 versus 0.81 seconds, a 2.019x observation with no threshold.
The 5x long-history workload measured 1.29 versus 2.03 seconds, a 1.573x ratio below
the unchanged 1.58x warning and 1.65x failure boundaries.

`ppar` had pre-existing uncommitted user-facing cleanup changes, all of which were
preserved. Step 7 changed only the installed package in its virtual environment; it
made no `ppar` repository edit and changed no tolerance, warning, threshold, test,
dependency declaration, output, or release gate.

**Gate:** Passed. The unchanged host remains compatible on its established default
calculation and complete product and scale boundaries.

### 8. Release the feature

**Status:** Complete September 5, 2026.

- Review documentation, license, fixture provenance, API compatibility, and all gate
  evidence.
- Release first as `perfattr==0.7.0a1` because this adds a public policy enum, keyword,
  result metadata, and distinct linked-effect values.
- Build from a clean release commit and publish by annotated tag and GitHub prerelease
  through trusted PyPI publishing.
- Verify a no-cache public-index installation and both default-Carino and explicit-
  Frongello smoke calculations.

**Gate:** Publication requires explicit user approval after all prepublication
evidence is recorded.

**Release evidence:** The user explicitly approved commit and publication after all
Steps 1–7 passed. Version `0.7.0a1` then passed all 331 tests, Pyright with no errors
or warnings, Pylint at 10.00/10 with no messages, `git diff --check`, an isolated
Hatchling source and wheel build, Twine, and a clean Python 3.11 installed-wheel
Carino and Frongello smoke test.

Clean release commit `08d3eb1f1ecdc16923aadcbe99aa962726ef3051` was pushed to
`main`. GitHub Actions CI run `33994500066` passed the complete suite on Python 3.11,
3.12, 3.13, and 3.14 and independently verified the distributions. The commit was
tagged with annotated tag `v0.7.0a1` and published as a GitHub prerelease. Trusted-
publisher run `33994566231` successfully built the tagged distributions and published
them to PyPI.

After public-index propagation, a fresh Python 3.11.9 environment installed
`perfattr==0.7.0a1` from `https://pypi.org/simple` with pip caching disabled. The
installed module resolved from that environment's `site-packages`; default Carino and
explicit Frongello calculations both passed reconciliation, and the primary
two-period Frongello horizon produced the expected 16.5% linked total effect.

**Gate:** Passed. The approved prerelease is published on GitHub and PyPI and is
independently installable and usable from the public index.

## Required verification matrix

At minimum, tests must cover:

- exact default-Carino compatibility for all four attribution methods;
- strict new enum behavior and result metadata;
- unchanged schemas, dtypes, null placement, ordering, and reconciliation names;
- the primary two-period example and its reversed chronology;
- one, two, and multiple periods;
- full-horizon Frongello/recursive equivalence;
- additive identities per identifier and effect channel;
- two-effect and three-effect component reconciliation;
- BF and BHB cross-method identities and both interaction-collapse identities;
- missing-side rows, disappearing identifiers, signed weights, cash, and unexposed
  fees or financing;
- authoritative contributions and undefined effective returns;
- returns near but greater than `-1`, finite-value failure behavior, and long horizons;
- deterministic input permutations, caller-input nonmutation, and independent result
  ownership;
- elapsed-time and peak-memory observations; and
- the unchanged `ppar` product and 500x integration gates.

## References, comparative review, and provenance

Primary methodology:

- Frongello, Andrew S. B. “Linking Single Period Attribution Results.” *The Journal
  of Performance Measurement* 6, no. 3 (Spring 2002): 10–22.
  [Author-hosted PDF](https://frongello.com/support/Works/JPMSpring2002.pdf).
- Frongello, Andrew S. B. “Attribution Linking: Proofed and Clarified.” *The Journal
  of Performance Measurement* 7, no. 1 (Fall 2002): 54–67.
  [Author-hosted PDF](https://frongello.com/support/Works/JPMFall2002.pdf).

The Fall paper provides the governing recursive formula, proof, order-dependence
discussion, and worked examples. The Spring paper establishes the original method.
The implementation and test expectations must be derived independently from those
papers.

Comparative design review:

- [`gghez/pybrinson`](https://github.com/gghez/pybrinson/), reviewed at commit
  `529b0940937caacec3f2a30609b9ce6b86316a7b` on September 5, 2026.

The review reinforced explicit linker identity, primary-source fixtures, and the exact
full-horizon equivalence between Frongello recursion and the GRAP prefix/suffix factor.
Its horizon-only result does not answer `perfattr`'s period-detail presentation
question, so the source-period rule above is an independent compatibility decision.
No source, fixture, expected value, or documentation text is copied.

A targeted public search found no Frongello-specific patent claim. That is a project
risk review, not a legal opinion. Roadmap 8 implements independently documented
mathematics under the project's MIT license and reuses no copyrighted implementation
material.

## Completion criteria

Roadmap 8 is complete only when:

- this roadmap and specification are explicitly approved;
- every implementation and independent-test step is complete;
- Carino remains the exact default and all four attribution methods remain compatible;
- Frongello is explicit, reconciled, documented, and independently verified;
- `ppar` passes without host expansion; and
- the approved prerelease is published and verified from the public PyPI index.
