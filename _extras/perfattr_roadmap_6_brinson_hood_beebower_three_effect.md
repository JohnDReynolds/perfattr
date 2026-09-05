# perfattr Roadmap 6: Brinson-Hood-Beebower Three-Effect Attribution

**Status:** Accepted September 5, 2026. Steps 1–7 are complete; implementation is
authorized in the documented sequence.

This roadmap promotes the Brinson-Hood-Beebower (BHB) three-effect candidate from
roadmap 3 as one narrow calculation policy. Its proposed governing contract is
[`docs/brinson_hood_beebower_three_effect_specification.md`][bhb-spec].

[bhb-spec]: ../docs/brinson_hood_beebower_three_effect_specification.md

## Objective

Add an opt-in BHB calculation that reports allocation, benchmark-weighted selection,
and interaction while preserving every released Brinson-Fachler (BF) method and the
default two-effect behavior.

BHB is the smallest useful next feature because it can reuse the released prepared
inputs, explicit-interaction schemas, Carino linking, reconciliation structure, and
result ownership rules. It requires a distinct single-period financial policy, not a
second calculation engine.

## Scope boundary

Roadmap 6 owns only:

- one additional public `AttributionMethod` value;
- method-specific BHB allocation and total-effect calculations;
- reuse of the released three-effect schemas, linking, and reconciliation checks;
- BHB/BF cross-method invariants and independent hand-calculated fixtures;
- public documentation and direct-core performance evidence; and
- verification that `ppar` remains compatible through its unchanged default path.

Roadmap 6 does not add:

- a BHB two-effect method;
- hierarchy or parent-child roll-up;
- another linking method;
- currency or external-flow attribution;
- new input or result-frame columns;
- a formula registry, plugin system, or general method framework; or
- automatic `ppar` exposure of BHB.

## Proposed compatibility plan

The default remains `BRINSON_FACHLER_TWO_EFFECT`. The released
`BRINSON_FACHLER_THREE_EFFECT` method also remains unchanged. Callers opt into BHB
explicitly:

```python
calculate_attribution(
    portfolio,
    benchmark,
    method=AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
)
```

The BHB method uses the released three-effect column names, positions, dtypes,
ordering, null placement, and reconciliation check names. `AttributionResult.method`
distinguishes the financial meaning. No schema change is needed because the existing
columns already describe allocation, selection, interaction, and total without
embedding a method name.

`total_effect` is method-specific at identifier level. For BHB it is unadjusted active
contribution; for both BF methods it retains the released benchmark-adjusted
definition. Period and linked full-horizon totals reconcile to the same active return,
but callers must not compare BHB and BF identifier-level allocation or total columns
as if their meanings were identical.

Approval of this roadmap constitutes approval of this compatibility plan. Any broader
API or schema change requires separate approval.

## Financial policy

For identifier `g` and period `t`, let `wP`, `wB`, `rP`, and `rB` be portfolio and
benchmark weights and normalized effective returns. Let `cP` and `cB` be authoritative
contributions, `AW = wP - wB`, and `AR = rP - rB` when both returns are defined.

The ordinary BHB three effects are:

```text
allocation  = AW * rB
selection   = wB * AR
interaction = AW * AR
```

The BHB identifier-level total is:

```text
total = cP - cB
```

For defined effective returns, the implementation calculates interaction directly
and selection as the exact reconciliation residual:

```text
interaction = AW * AR
selection = total - allocation - interaction
```

This residual is algebraically equal to benchmark-weighted selection while preserving
authoritative contributions and minimizing an independent floating-point path.

If `rB` is undefined, allocation is zero. If either effective return is undefined,
interaction is zero. Selection retains the remaining authoritative total. These are
disclosed boundary conventions; the core never invents a return or a fourth residual
effect.

For rows with defined benchmark returns:

```text
BHB allocation - BF allocation = AW * total_benchmark_return
BHB total      - BF total      = AW * total_benchmark_return
```

Selection and interaction are therefore equal between BHB and three-effect BF for
ordinary defined-return rows. With exactly normalized portfolio and benchmark
weights, the allocation and total differences sum to zero across a period, so both
methods produce the same period totals while assigning them differently by
identifier.

## Implementation sequence

### 1. Approve the contract

**Status:** Complete September 5, 2026.

- Review and approve this roadmap and the proposed specification.
- Confirm the public enum value, method-specific `total_effect` meaning, schema reuse,
  undefined-return policy, and BHB/BF cross-method identities.
- Confirm that `ppar` exposure remains outside this roadmap.

**Gate:** Passed. The user explicitly approved this roadmap and its governing
specification on September 5, 2026.

### 2. Extend method identity without changing schemas

**Status:** Complete September 5, 2026.

- Add `BRINSON_HOOD_BEEBOWER_THREE_EFFECT` to `AttributionMethod`.
- Identify the two explicit-interaction methods with one small private predicate or
  constant rather than duplicating conditionals throughout the calculation.
- Reuse the released three-effect schema tuples and reconciliation check names.
- Keep strict enum validation and both released methods unchanged.

**Gate:** Method selection and schema tests pass before BHB calculation is enabled.

**Implementation evidence:** `AttributionMethod` now exposes the approved BHB
three-effect identity. One package-internal predicate classifies both three-effect
methods for the released explicit-interaction schemas, aggregation, linking, and
reconciliation paths while leaving the default BF two-effect method outside that
classification. The public calculation boundary temporarily raises
`NotImplementedError` for BHB so the new identity cannot return mislabeled BF values
before Step 3 supplies its allocation and total-effect formulas. Existing invariant
tests continue to cover both released methods explicitly, and focused tests cover the
new enum value, shared schema policy, and temporary guard.

**Gate:** Passed. All 271 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages; and `git diff --check` reports no whitespace
errors. No BHB financial calculation is enabled in this step.

### 3. Calculate BHB period effects

**Status:** Complete September 5, 2026.

- Calculate BHB allocation from active weight and the benchmark effective return.
- Calculate BHB total as authoritative active contribution.
- Calculate interaction only from defined effective returns.
- Calculate selection as the exact residual.
- Preserve the released BF branches rather than routing them through changed formulas.

**Gate:** Independent single-period fixtures prove BHB values, reconciliation, and the
documented differences from BF at `1e-12` relative and absolute tolerance.

**Implementation evidence:** The isolated period-detail calculation now gives BHB its
own allocation and total-effect branch while leaving both released BF expressions
unchanged. BHB allocation uses active weight times the benchmark effective return,
BHB total is a copy of authoritative active contribution, interaction is calculated
only from defined effective returns, and selection is the exact residual. Two original
expectation tables independently cover derived and authoritative contributions,
positive and negative allocation, positive and negative interaction, BHB/BF
identifier differences, and equal period totals. A focused zero-weight fee case proves
that an undefined active return produces zero interaction and retains the complete
authoritative charge in selection. The public BHB guard remains in place until Step 4
verifies linking, aggregation, and reconciliation.

**Gate:** Passed. All 274 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages; and `git diff --check` reports no whitespace
errors. Hand-calculated values reconcile at the unchanged `1e-12` tolerance, and no
BHB result is yet exposed through the public calculator.

### 4. Reuse linking, aggregation, and reconciliation

**Status:** Complete September 5, 2026.

- Apply the released Carino active coefficient independently to every BHB effect.
- Carry BHB through period summary, overall detail, and cumulative output using the
  existing three-effect schemas.
- Reuse the `three_effect_components` and `linked_three_effect_components` checks.
- Preserve every released BF result and reconciliation row unchanged.

**Gate:** Multi-period hand calculations reconcile each component and the linked total
at `1e-12`, including the released linking limits.

**Implementation evidence:** The temporary public guard is removed, so callers can
now select BHB through `calculate_attribution`. The existing explicit-interaction
path carries BHB allocation, selection, interaction, and total through Carino linking,
period summary, overall detail, cumulative results, and the two released three-effect
reconciliation checks without a new schema or calculation engine. An original
two-period fixture records every unlinked and linked BHB effect independently; its
linked allocation, selection, interaction, and total are `0.001258451699584109`,
`-0.0052749105549335295`, `0.0013664588552694257`, and `-0.00265`. Public-result tests
also prove BHB schema ordering, deterministic behavior, nonmutation, identical-input
invariants, and reconciliation at the released regular and near-limit Carino cases.

**Gate:** Passed. All 279 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages; and `git diff --check` reports no whitespace
errors. Every BHB linked component and additive identity passes at the unchanged
`1e-12` relative and absolute tolerance, while the released BF paths remain covered
by their unchanged tests.

### 5. Complete independent tests and documentation

**Status:** Complete September 5, 2026.

- Add a hand-calculated fixture that makes BHB and BF identifier allocations and
  totals visibly different while their period totals agree.
- Cover authoritative contribution, undefined effective returns, missing sides,
  signed weights, row ordering, nonmutation, and independent result ownership.
- Document the absolute-return allocation interpretation and why its signs can differ
  from BF.
- Use extensive financial docstrings and comments for every nontrivial case.

**Gate:** Fixtures and expected values are independent of production output,
`pybrinson`, `ppar`, and other implementations.

**Implementation evidence:** Original single-period expectation tables make the BHB
and BF identifier allocations and totals visibly different while proving equal period
totals. The independent multi-period table records every unlinked and Carino-linked
BHB effect. Public tests now exercise BHB with authoritative contributions, an
undefined zero-weight fee return, identifiers present on only one side, signed and
zero weights, deterministic input permutations, caller-input nonmutation, separately
owned result frames and calculations, and randomized inputs used only for financial
invariants. The fixture provenance explains the hand calculations and confirms that
no expected value came from production output, `pybrinson`, `ppar`, or another
implementation.

The README now presents both opt-in three-effect choices, their formulas, BHB's
absolute-return allocation interpretation, the reason a BHB allocation sign can
differ from BF, and the method-specific identifier-level `total_effect` meaning. The
base specification links the BHB supplement and no longer lists implemented BHB as a
deferred capability. Nontrivial tests retain financial formulas and literal expected
values in their docstrings or fixture provenance.

**Gate:** Passed. All 282 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages; and `git diff --check` reports no whitespace
errors. No production tolerance, warning, invariant, or test gate changed.

### 6. Verify quality and performance

**Status:** Complete September 5, 2026.

- Run all tests, Pylint, Pyright, build, Twine, and clean-wheel smoke checks.
- Compare both released BF methods against `perfattr==0.4.0a1` over all five result
  frames.
- Benchmark all three methods on the established direct-core workloads, measuring
  elapsed time and peak memory.
- Establish no new threshold without repeatable evidence and explicit approval.

**Gate:** All quality and packaging checks pass; released BF artifacts remain
compatible at `1e-12`; no gate or tolerance is weakened.

**Implementation evidence:** The complete 282-test suite passes, Pyright reports no
errors or warnings, Pylint reports 10.00/10 with no messages across `src`, `tests`,
and `scripts`, and `git diff --check` is clean. Hatchling builds both the source
distribution and wheel, Twine accepts both artifacts, and a fresh Python 3.11
environment installs the wheel and completes a public BHB calculation with every
reconciliation row passing. The artifacts intentionally retain version `0.4.0a1`;
the approved `0.5.0a1` version change belongs to the later release step.

The published PyPI `perfattr==0.4.0a1` wheel and the local candidate wheel were
installed in separate clean environments with the same Python 3.11.9, pandas 3.0.5,
and NumPy 2.4.6 versions. Four representative fixtures cover derived and
authoritative contributions, regular multi-period linking, and linking boundaries.
Both released BF methods match across all five result frames: 40 frame comparisons
preserve schemas, dtypes, indexes, ordering, null placement, reconciliation evidence,
and values at `1e-12` relative and absolute tolerance.

The direct-core benchmark now accepts `--method bhb-three-effect`. Five-sample
medians and peak traced allocation were recorded for all three methods over the four
established workloads in `docs/performance.md`. BHB medians ranged from 0.2% lower to
1.2% higher than BF three-effect, and peak traced allocations were equal at reported
precision. These remain observations; no performance threshold, dependency, formula,
test, warning, or tolerance changed.

**Gate:** Passed. Packaging, clean-wheel smoke, released-method compatibility,
quality, and performance verification are complete without weakening a gate.

### 7. Verify the `ppar` boundary

**Status:** Complete September 5, 2026.

- Install the candidate wheel into the adjacent `ppar` development environment.
- Keep `ppar` on its unchanged default BF two-effect calculation and output schema.
- Run the complete `ppar` release-candidate workflow and unchanged 500x gate.

**Gate:** The downstream product passes without a BHB adapter option or presentation
change.

**Implementation evidence:** The local candidate wheel was installed into `ppar`'s
Python 3.12.1 development environment. Inspection confirmed that the unchanged adapter
does not import `AttributionMethod` or pass a method argument, so `ppar` continues to
receive the default BF two-effect result and does not expose BHB in its API, schema,
or presentation.

The complete `ppar` release-candidate command passed 305 tests and 477 subtests,
MyPy, Pyright with no errors or warnings, both Pylint gates, documentation and image
checks, wheel construction and Twine validation, package checks, and installed generic
and Axys/APX demonstration workflows. The unchanged 500x workflow retained large-site
equivalence and passed all three scale scenarios. Its observed large-site,
selected-input, and long-history time ratios were 1.050x, 2.101x, and 1.568x. The
long-history result remained below the established 1.58x warning and 1.65x failure
boundaries. No `ppar` source, dependency metadata, adapter behavior, test, tolerance,
or performance threshold changed.

**Gate:** Passed. The downstream product remains compatible through its unchanged
default boundary, and the complete release-candidate and 500x gates pass without host
expansion.

### 8. Release the feature

- Review public documentation, license, fixture provenance, and compatibility.
- Release first as `perfattr==0.5.0a1` because the package gains a public method with
  distinct identifier-level financial semantics.
- Build and verify distributions from the clean release commit.
- Publish by annotated tag and GitHub prerelease through trusted PyPI publishing.
- Verify a no-cache public-index installation and BHB smoke calculation.

**Gate:** Publication requires explicit user approval after all prepublication
evidence is recorded.

## Required verification matrix

At minimum, tests must cover:

- unchanged BF two-effect and three-effect schemas and values;
- public BHB enum behavior and invalid-method rejection;
- independent positive, negative, and zero BHB allocation values;
- allocation plus selection plus interaction equaling BHB total per row and period;
- BHB total equaling active contribution per period;
- BHB/BF identifier differences of `AW * total_benchmark_return` when defined;
- equal BHB/BF period total-effect sums under exactly normalized weights;
- equal BHB/BF component totals when benchmark effective returns are all defined;
- authoritative contributions with effective returns distinct from supplied returns;
- zero-weight nonzero-contribution rows and undefined-return boundaries;
- identifiers present on only one side and signed weights;
- single and multiple periods, including Carino limits near `-1`;
- deterministic schemas, rows, null placement, and reconciliation names;
- caller-input nonmutation and independent result ownership;
- elapsed-time and peak-memory observations; and
- unchanged `ppar` product and 500x integration gates.

## References and provenance

The governing primary reference is:

- Brinson, Gary P., L. Randolph Hood, and Gilbert L. Beebower. “Determinants of
  Portfolio Performance.” *Financial Analysts Journal* 42, no. 4 (July–August 1986):
  39–44. [doi:10.2469/faj.v42.n4.39](https://doi.org/10.2469/faj.v42.n4.39).

The publisher metadata and the paper's 1995 CFA/AIMR reprint were reviewed on
September 5, 2026. Tables 1–3 define policy return, timing, security selection, and the
cross-product term from which the BHB formulas in the proposed specification are
derived.

The requested comparative review of
[`gghez/pybrinson`](https://github.com/gghez/pybrinson/) used commit
`529b0940937caacec3f2a30609b9ce6b86316a7b`. Its separate BHB entry point, shared
three-effect result shape, explicit identity checks, and BHB/BF cross-method tests
support keeping method identity explicit and common mechanics shared. `perfattr` will
retain its enum-based API and authoritative-contribution policy. No source code,
fixtures, expected values, or documentation text will be copied.

## Completion criteria

Roadmap 6 is complete only when:

- the roadmap and specification are approved;
- every implementation step and required test is complete;
- all released BF behavior remains compatible;
- BHB is explicit, reconciled, documented, and independently verified;
- `ppar` compatibility and scale gates pass without host expansion; and
- the approved prerelease is published and verified from the public PyPI index.
