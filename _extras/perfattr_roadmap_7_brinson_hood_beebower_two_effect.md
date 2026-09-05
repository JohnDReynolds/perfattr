# perfattr Roadmap 7: Brinson-Hood-Beebower Two-Effect Reporting

**Status:** Accepted September 5, 2026. Steps 1–7 are complete; implementation is
authorized in the documented sequence.

This roadmap promotes the Brinson-Hood-Beebower (BHB) two-effect reporting candidate
from roadmap 3. Its governing contract is
[`docs/brinson_hood_beebower_two_effect_specification.md`][bhb-two-spec].

[bhb-two-spec]: ../docs/brinson_hood_beebower_two_effect_specification.md

## Objective

Add an opt-in compact BHB result that reports allocation and portfolio-weighted
selection, with interaction absorbed into selection. Preserve the default
Brinson-Fachler (BF) two-effect method and both released three-effect methods.

This is a reporting convention derived from the released BHB three-effect method. It
does not claim that Brinson, Hood, and Beebower originally defined a two-effect model.

## User value and smallest design

Callers can already derive compact BHB selection by adding the released BHB selection
and interaction columns. A native method is useful only when callers need:

- the stable two-effect schemas without post-processing;
- one authoritative method identity in `AttributionResult`;
- linking and reconciliation performed directly on the combined selection channel; or
- a compact BHB boundary analogous to the default compact BF boundary.

The implementation should remain one policy branch in the existing engine. It does
not justify another schema, calculation engine, abstraction registry, or dependency.

## Scope boundary

Roadmap 7 owns only:

- one additional public `AttributionMethod` value;
- shared identification of BHB allocation policy across its two reporting forms;
- reuse of the released two-effect schemas and reconciliation checks;
- independent BHB two-effect fixtures and cross-method invariants;
- public documentation and direct-core performance evidence; and
- verification that `ppar` remains on its unchanged default BF two-effect boundary.

Roadmap 7 does not add:

- a new financial effect or input column;
- a separate interaction column to two-effect results;
- hierarchy, currency, external-flow effects, or another linking method;
- automatic `ppar` exposure of the new method; or
- a formula registry, plugin system, or second calculation engine.

## Approved compatibility plan

Add the explicit enum member:

```python
AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT
```

The default remains `BRINSON_FACHLER_TWO_EFFECT`. Every released method retains its
formulas, schemas, values, ordering, null placement, and reconciliation names.

BHB two-effect reuses the default two-effect schemas exactly. `AttributionResult.method`
distinguishes its financial policy. Because the schema is shared, downstream code
must retain method metadata whenever the allocation convention matters.

Approval of this roadmap approves that compatibility plan. Any schema change or
default-method change requires separate approval.

## Financial policy

For identifier `g` and period `t`, let `wP`, `wB`, `rP`, and `rB` be normalized
portfolio and benchmark weights and effective returns. Let `cP` and `cB` be
authoritative contributions, `AW = wP - wB`, and `AR = rP - rB` when defined.

```text
allocation = AW * rB
total      = cP - cB
selection  = total - allocation
```

For defined effective returns, selection is algebraically:

```text
selection = wP * AR
```

If `rB` is undefined, allocation is zero. Selection retains the complete residual.
The two-effect method does not calculate or expose an interaction channel merely to
combine it later.

Relative to released BHB three-effect:

```text
A_two = A_three
T_two = T_three
S_two = S_three + I_three
```

The same collapse identity must survive Carino linking, summaries, overall detail,
and cumulative output at `1e-12` relative and absolute tolerance.

## Implementation sequence

### 1. Approve the contract

**Status:** Complete September 5, 2026.

- Confirm that native compact output provides enough value to justify another public
  method rather than requiring callers to combine two columns.
- Approve the enum name, two-effect schema reuse, residual behavior, historical
  labeling, cross-method identities, and approved `0.6.0a1` prerelease.
- Confirm that `ppar` exposure remains outside this roadmap.

**Gate:** No implementation begins before explicit user approval.

**Approval evidence:** The user explicitly approved Roadmap 7 and its governing
specification on September 5, 2026, including the compact reporting value, enum and
schema compatibility plan, historical labeling, financial identities, unchanged
`ppar` boundary, and ordered implementation gates.

**Gate:** Passed.

### 2. Extend method identity and policy classification

**Status:** Complete September 5, 2026.

- Add `BRINSON_HOOD_BEEBOWER_TWO_EFFECT` to `AttributionMethod`.
- Introduce one small package-internal BHB-allocation predicate covering both BHB
  methods while retaining the explicit-interaction predicate for only three-effect
  methods.
- Reuse every released two-effect schema tuple and reconciliation check name.
- Temporarily reject the new method at the public calculation boundary until its
  period policy is verified.

**Gate:** Enum, classification, strict-validation, schema, and temporary-guard tests
pass without changing a released method.

**Implementation evidence:** `AttributionMethod` now exposes the approved BHB
two-effect identity. One package-internal predicate identifies both BHB allocation
methods independently of the existing explicit-interaction predicate, which continues
to classify only the two three-effect methods. The new identity therefore selects the
released compact schema policy without changing a schema tuple or reconciliation
name. Strict enum validation remains unchanged, and the public calculation boundary
temporarily raises `NotImplementedError` for BHB two-effect so it cannot fall through
the current BF compact calculation before Step 3 implements its financial policy.

**Gate:** Passed. All 284 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; and
`git diff --check` reports no whitespace errors. No BHB two-effect financial result is
enabled in this step, and every released method remains covered by the existing
calculation invariants.

### 3. Calculate BHB two-effect period results

**Status:** Complete September 5, 2026.

- Route both BHB methods through the released BHB allocation and total policy.
- For BHB two-effect, calculate selection directly as `total - allocation`.
- Do not calculate an unused interaction array in the two-effect branch.
- Preserve every released BF and BHB three-effect expression.

**Gate:** Independent single-period values and BHB two/three collapse identities pass
at `1e-12`, including authoritative and undefined-return cases.

**Implementation evidence:** The period-detail calculation now routes both BHB
methods through the one approved absolute-return allocation and unadjusted-total
policy. Because BHB two-effect remains outside the explicit-interaction predicate, its
existing compact branch calculates selection directly as `total - allocation` and
does not allocate or return an interaction channel. Both released BF expressions and
the released BHB three-effect interaction branch remain unchanged.

Two original expectation tables independently record compact BHB allocation,
selection, and total for derived and authoritative inputs. They prove positive,
negative, and zero values; contribution-implied returns distinct from supplied
returns; equal BHB two/three allocation and total; selection collapse; and the
ordinary BF/BHB compact-selection identity. A separate zero-weight fee case proves
that undefined effective return produces no invented interaction and retains the full
authoritative charge in selection. After those isolated period tests passed, the
temporary guard was removed and a public single-period calculation confirmed method
identity, compact schema behavior, expected values, and reconciliation.

**Gate:** Passed. All 287 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; and
`git diff --check` reports no whitespace errors. Independent values and cross-method
identities pass at the unchanged `1e-12` relative and absolute tolerance.

### 4. Reuse linking, aggregation, and reconciliation

**Status:** Complete September 5, 2026.

- Apply the released Carino coefficient to allocation, combined selection, and total.
- Reuse period summary, overall detail, cumulative output, and two-effect schemas.
- Reuse `effect_components` and `linked_effect_components` reconciliation checks.

**Gate:** Independent multi-period and linking-boundary values reconcile at `1e-12`.

**Implementation evidence:** No new production linking or aggregation branch was
needed. BHB two-effect uses the released compact schema path, which applies the same
Carino active coefficient directly to allocation, combined selection, and total,
then reuses the released period-summary, overall-detail, cumulative, and two-effect
reconciliation builders.

Original expectation tables now record unlinked and linked compact BHB effects for
both the regular two-period fixture and the analytic Carino boundary fixture near a
-100% compounded return. Tests compare those literal values directly, independently
sum allocation and selection to total, and verify passing reconciliation evidence.
Additional cross-method tests prove equal BHB two/three allocation and total and the
selection-plus-interaction collapse in period detail, period summary, overall detail,
and cumulative output. They also confirm exact reuse of every compact schema tuple
and the `effect_components` and `linked_effect_components` check ordering.

**Gate:** Passed. All 290 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; and
`git diff --check` reports no whitespace errors. Independent regular and linking-limit
values and every cross-method identity pass at the unchanged `1e-12` relative and
absolute tolerance.

### 5. Complete tests and documentation

**Status:** Complete September 5, 2026.

- Cover positive, negative, and zero effects; missing sides; signed weights;
  authoritative contributions; undefined returns; deterministic ordering;
  nonmutation; and independent result ownership.
- Prove the BHB two/three collapse in every applicable result frame.
- Document that this is a derived compact presentation and explain the allocation
  difference from BF two-effect.
- Keep nontrivial financial expectations explicit in docstrings and fixture
  provenance.

**Gate:** Expected values remain independent of production output, `ppar`,
`pybrinson`, and other implementations.

**Implementation evidence:** Compact BHB now participates in the shared identical-
input, deterministic-ordering, caller-input-nonmutation, and independent-result-
ownership tests for every implemented attribution method. Focused public tests use
literal hand calculations to cover positive, negative, and zero allocation and
selection; portfolio-only and benchmark-only identifiers; a negative portfolio
weight; an explicit zero row; authoritative contribution; and a zero-weight fee with
undefined effective return. The BHB two/three collapse remains proved in every
applicable result frame, including both unlinked and linked effect channels.

The README now lists all four method identities, shows explicit compact-BHB
selection, labels it as a derived `perfattr` presentation rather than a historical BHB
claim, and explains its identifier-level allocation difference from compact BF. The
base specification links the governing compact-BHB supplement and accurately
describes shared two-effect schemas, selection convention, reconciliation, and
method-policy boundaries. The public calculation docstring likewise distinguishes
the two compact allocation policies from explicit three-effect output. Test docstrings
and fixture provenance retain the arithmetic, sign conventions, linking coefficients,
undefined-return behavior, and independence of all expected values.

**Gate:** Passed. All 294 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; and
`git diff --check` reports no whitespace errors. Expected values remain original
hand calculations and were not obtained from production output, `ppar`, `pybrinson`,
or another implementation. No tolerance or quality gate changed.

### 6. Verify quality, compatibility, and performance

**Status:** Complete September 5, 2026.

- Run all tests, Pylint, Pyright, build, Twine, and clean-wheel smoke checks.
- Compare all three released methods against `perfattr==0.5.0a1` over all five result
  frames.
- Benchmark all four methods on the established direct-core workloads, recording
  elapsed time and peak memory.
- Establish no new threshold without repeatable evidence and explicit approval.

**Gate:** Released artifacts remain compatible at `1e-12`; all quality and packaging
checks pass without weakening a gate.

**Implementation evidence:** The complete 294-test suite passes, Pyright reports no
errors or warnings, Pylint reports 10.00/10 with no messages across `src`, `tests`,
and `scripts`, and `git diff --check` is clean. Hatchling builds the source
distribution and wheel from the current tree, Twine accepts both artifacts, and a
fresh Python 3.11 environment installs the candidate wheel and completes a public
compact-BHB calculation with the approved schema and passing reconciliation. The
candidate intentionally retains version `0.5.0a1`; the approved `0.6.0a1` version
change belongs to the release step.

The actual published PyPI `perfattr==0.5.0a1` wheel and the local candidate wheel were
installed in separate clean environments with identical Python 3.11.9, pandas 3.0.5,
and NumPy 2.4.6 versions. Four representative fixtures cover derived and authoritative
contributions, regular multi-period linking, and analytic linking boundaries. All
three released methods match across all five result frames: 60 comparisons preserve
schemas, dtypes, indexes, ordering, null placement, reconciliation evidence, and
values at `1e-12` relative and absolute tolerance.

The direct-core benchmark now accepts `--method bhb-two-effect`. Five-sample medians
and peak traced allocations were recorded for all four methods over the four
established workloads in `docs/performance.md`. Compact BHB medians were 0.6% to 0.9%
above compact BF, and peak traced allocations were equal at reported precision. The
compact methods also retained the expected lower memory use than the three-effect
methods because they omit interaction columns. These are observations only; no
threshold, dependency, formula, tolerance, warning, or quality gate changed.

**Gate:** Passed. Packaging, clean-wheel smoke, released-method compatibility,
quality, and performance verification are complete without weakening a gate.

### 7. Verify the `ppar` boundary

**Status:** Complete September 5, 2026.

- Install the candidate wheel into the adjacent `ppar` development environment.
- Keep `ppar` on its unchanged default BF two-effect method and schemas.
- Run the complete `ppar` release-candidate workflow and unchanged 500x gate.

**Gate:** The downstream product passes without a BHB selector or presentation change.

**Implementation evidence:** The verified candidate wheel was installed into
`ppar`'s existing Python 3.12.1 development environment without changing host source,
configuration, or dependency metadata. Inspection confirmed that the adapter still
omits the method argument and therefore continues to select the default BF two-effect
calculation and established host schemas.

The complete `ppar` release-candidate workflow passed 305 tests and 477 subtests,
Mypy across 38 source files, Pyright with no errors or warnings, both Pylint checks,
documentation and image verification, universal-wheel construction and Twine
validation, package metadata checks, and installed generic and Axys/APX demonstrations.
The composed script then ran its unchanged 500x scale gate. Large-site artifacts
remained byte-identical, with observed large-site and selected-input ratios of 1.105x
and 2.049x. Long-history measured 1.583x, producing the existing warning above 1.58x
but remaining below the unchanged 1.65x failure boundary; the release-candidate gate
passed. An immediate repeat of the scale command observed ratios of 1.059x, 2.007x,
and 1.563x respectively, with long-history below the warning boundary.

**Gate:** Passed. `ppar` remains on its unchanged default BF two-effect boundary and
passes the complete product and 500x integration gates without a BHB selector,
presentation change, host edit, or weakened threshold.

### 8. Release the feature

- Review documentation, license, fixture provenance, and compatibility.
- Release first as `perfattr==0.6.0a1` because this adds a public method identity with
  distinct identifier-level financial semantics.
- Build from the clean release commit and publish by annotated tag and GitHub
  prerelease through trusted PyPI publishing.
- Verify a no-cache public-index installation and BHB two-effect smoke calculation.

**Gate:** Publication requires explicit user approval after all prepublication
evidence is recorded.

## Required verification matrix

At minimum, tests must cover:

- unchanged schemas and values for all three released methods;
- strict new enum behavior and invalid-method rejection;
- exact reuse of the released two-effect column and reconciliation-name ordering;
- independent positive, negative, and zero allocation and selection values;
- `allocation + selection = total` per row, period, and linked horizon;
- BHB total equaling active contribution per period;
- BHB two-effect selection equaling BHB three-effect selection plus interaction;
- equal BHB two/three allocation and total in every applicable result frame;
- documented BHB/BF two-effect identifier differences and period identities;
- authoritative contributions and undefined effective returns;
- missing-side rows, signed weights, Carino limits near `-1`, deterministic ordering,
  nonmutation, and independent result ownership;
- elapsed-time and peak-memory observations; and
- the unchanged `ppar` product and 500x integration gates.

## References and provenance

The BHB allocation basis is supported by:

- Brinson, Gary P., L. Randolph Hood, and Gilbert L. Beebower. “Determinants of
  Portfolio Performance.” *Financial Analysts Journal* 42, no. 4 (1986): 39–44.
  [doi:10.2469/faj.v42.n4.39](https://doi.org/10.2469/faj.v42.n4.39).

The two-effect collapse is a `perfattr` reporting convention derived algebraically
from the released three-effect result, not a representation attributed to that paper.

The prior review of `gghez/pybrinson` at commit
`529b0940937caacec3f2a30609b9ce6b86316a7b` supports explicit BHB method identity and
shared mechanics, but it does not serve as authority for this compact convention. No
source, fixtures, expected values, or documentation text may be copied.

## Completion criteria

Roadmap 7 is complete only when:

- this roadmap and specification are explicitly approved;
- every implementation and independent-test step is complete;
- all three released methods remain compatible;
- BHB two-effect is explicit, reconciled, documented, and independently verified;
- `ppar` passes without host expansion; and
- the approved prerelease is published and verified from the public PyPI index.
