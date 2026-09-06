# perfattr Roadmap 9: Menchero Optimized Effect Linking

**Status:** Active September 6, 2026. Steps 1–7 and the Step 8 prepublication gate
are complete; commit and publication require explicit approval.

This roadmap promotes the Menchero optimized-linking candidate from roadmap 3. Its
governing contract is
[`docs/menchero_optimized_linking_specification.md`][menchero-spec].

[menchero-spec]: ../docs/menchero_optimized_linking_specification.md

## Objective

Add one opt-in Menchero optimized policy for linking arithmetic attribution effects
across time. Preserve Carino as the default, preserve the released Frongello policy,
preserve logarithmic portfolio and benchmark contribution linking, and record the
selected effect-linking identity in each result.

The approved release target is `perfattr==0.8.0a1`.

## User problem and smallest design

Carino and Frongello do not satisfy a client or comparison that explicitly requires
Menchero's order-independent, minimum-correction distribution of the compounding
residual. Unlike GRAP, Menchero provides a genuinely different numerical policy.

The smallest design adds one member to the released `EffectLinkingMethod` and one
private coefficient helper. It reuses the existing calculator argument, result
metadata, effect columns, aggregation, reconciliation, and strict enum boundary. It
does not add a standalone public linker, plugin system, optimizer API, new result
type, or general method registry.

## Scope boundary

Roadmap 9 owns only:

- `EffectLinkingMethod.MENCHERO = "Menchero"`;
- stable Menchero optimized arithmetic period coefficients;
- Menchero-linked allocation, selection, optional interaction, and total effects;
- unchanged input and result-frame schemas;
- independent primary-source and complete prepared-input fixtures;
- documentation and direct-core performance evidence;
- a repeated patent-status check before implementation merge and publication; and
- verification that `ppar` remains on its unchanged default Carino boundary.

Roadmap 9 does not add:

- a single-period attribution method or effect;
- Menchero linking for portfolio, benchmark, or active contribution columns;
- Menchero geometric attribution or component-level quadratic coefficients;
- as-of cumulative relinking or a new cumulative-result schema;
- GRAP, geometric, hierarchy, currency, or external-flow behavior;
- new prepared-input columns or relaxed return rules;
- a `ppar` selector or presentation change; or
- another runtime dependency.

## Approved compatibility plan

Extend the released enum:

```python
class EffectLinkingMethod(str, Enum):
    CARINO = "Carino"
    FRONGELLO = "Frongello"
    MENCHERO = "Menchero"
```

The existing keyword-only `effect_linking_method` argument and matching result
metadata require no structural change. Carino remains the default. Strings and other
nonmembers remain invalid.

All five result-frame schemas, columns, dtypes, null placement, row ordering,
ownership, and reconciliation check names remain unchanged. The generic linked-effect
columns use the selected policy, and result metadata identifies it.

Omitted and explicit Carino output must remain exactly compatible with
`perfattr==0.7.0a1`. Frongello behavior must remain unchanged. Selecting Menchero may
change only linked and cumulative effect values plus method metadata.

## Approved financial policy

For each source period, calculate active return `d[t] = P[t] - B[t]`. Let `D` be the
difference between the compounded portfolio and benchmark horizon returns and `T` the
period count.

Menchero applies:

```text
M        = continuous common horizon scale
E        = D - M * sum(d[t])
alpha[t] = E * d[t] / sum(d[t] ** 2)
K[t]     = M + alpha[t]
```

When every `d[t]` is zero, the minimum-norm correction is zero. One `K[t]` multiplies
every identifier's allocation, selection, interaction when present, and total effect
in that period.

The common scale must use the stable divided-difference form specified in the
governing document. Do not use a reconciliation-tolerance branch to choose a formula.
Equal compounded horizon returns can still require nonzero corrections when the
period active-return path is not identically zero.

For one period, `K[1] = 1`. Reordering complete economic periods leaves horizon effect
totals unchanged, unlike Frongello's deliberately path-dependent policy.

## Deliberate output interpretation

Each period-detail linked effect remains the source-period effect allocated to the
complete requested horizon. Period summary and overall detail aggregate those rows,
and cumulative output remains the partial sum of complete-horizon allocations.
Intermediate cumulative rows are not independently linked as-of results.

Portfolio and benchmark contributions retain logarithmic linking. Final Menchero
effects and linked active contribution reconcile at the complete horizon, not
necessarily at each intermediate cumulative row.

## Implementation sequence

### 1. Approve the contract

**Status:** Complete September 6, 2026.

- Approve the user problem, narrow method identity, enum name, unchanged default,
  arithmetic period-coefficient formula, and stable divided-difference evaluation.
- Approve the equal-horizon and all-zero-active degeneracy policies.
- Confirm unchanged contribution linking, schemas, cumulative interpretation, and
  `ppar` behavior.
- Approve the `0.8.0a1` prerelease target and the patent recheck gates.

**Gate:** No source, test, fixture, version, or public API implementation begins before
explicit user approval of this roadmap and its governing specification.

**Approval evidence:** On September 6, 2026, the user explicitly approved Roadmap 9
and its governing specification and asked to proceed with Step 1. This approves the
user problem, narrow method identity, enum name, unchanged Carino default, arithmetic
period-coefficient formula, stable divided-difference evaluation, equal-horizon and
zero-active policies, unchanged contribution linking and schemas, cumulative
interpretation, unchanged `ppar` behavior, `0.8.0a1` prerelease target, and patent
recheck gates.

**Gate:** Passed. Step 2 is authorized; later steps remain dependency-gated.

### 2. Extend the public identity

**Status:** Complete September 6, 2026.

- Add and export `EffectLinkingMethod.MENCHERO`.
- Update strict enum and result-metadata tests.
- Temporarily reject Menchero at the calculation boundary until the private financial
  helper and independent tests are complete.
- Preserve exact omitted and explicit Carino output and all Frongello behavior.

**Gate:** Identity, strict-validation, metadata, direct-construction, compatibility,
and temporary-guard tests pass with no result-frame change.

**Implementation evidence:** `EffectLinkingMethod.MENCHERO` is exported through the
existing public enum at both `perfattr.method` and the package root. Directly
constructed `AttributionResult` objects preserve the new metadata identity. Strings,
including `"Menchero"`, remain invalid at the strict enum boundary.

Public Menchero calculation raises the documented temporary `NotImplementedError`
after validating the dedicated enum identity but before tolerance or financial input
normalization. The private dispatcher also cannot fall through to Carino under the new
identity. Existing determinism, caller-nonmutation, and independent-ownership checks
continue to run under the two implemented linkers only; Step 4 will extend them to
Menchero after its numerical policy is verified.

**Gate:** Passed. All 333 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; and
`git diff --check` reports no whitespace errors. No calculation value, frame schema,
default, dependency, tolerance, threshold, or released Carino or Frongello behavior
changed.

### 3. Implement and independently verify the coefficients

**Status:** Complete September 6, 2026.

- Recheck the identified patent records before code is merged.
- Implement the continuous common scale and scaled least-squares correction in
  `float64` without a tolerance-selected formula branch.
- Apply the stable zero-active-vector policy and explicit finite guards.
- Keep coefficient work linear in the period count.
- Add extensively documented independent tests for the six-period primary example,
  equal and near-equal horizons, a nonzero equal-horizon correction, the zero active
  vector, one period, and period permutation.

**Gate:** Literal primary and edge-case values, stable and published forms away from
equality, all reconciliation identities, and randomized checks pass at the unchanged
`1e-12` relative and absolute tolerance.

**Patent recheck evidence:** On September 6, 2026, immediately before implementation,
the public Google Patents records continued to label US 7,249,079 B1, US 7,246,091
B1, and US 7,249,082 B2 `Expired - Lifetime`, with expiration dates of January 26,
2023; December 31, 2022; and February 18, 2024. Each record repeats that the displayed
legal status is an assumption, not a legal conclusion. This engineering review is not
legal advice or a worldwide freedom-to-operate opinion; Roadmap 9 still requires a
fresh recheck before publication.

**Implementation evidence:** The private `_menchero` helper evaluates the common
scale through the continuous difference-of-powers identity in log space, without an
equality tolerance or subtracting horizon roots. Its least-squares correction uses a
scaled active-return norm, treats the exact all-zero vector as the minimum-norm zero
correction, and explicitly rejects non-finite intermediate or final values. Both the
common-scale and correction work are linear in the period count.

Ten independently explained coefficient tests reproduce the literal six-period
primary example, compare the stable common scale with the published quotient away
from equality, exercise exact and near-equal horizons including a required nonzero
equal-horizon correction, cover the zero active vector, prove one-period identity and
period permutation, demonstrate overflow-safe norm scaling and explicit finite
guards, and reconcile 100 deterministically randomized horizons. At the Step 3 gate,
the public Menchero calculation guard remained in place pending Step 4 result-frame
integration.

**Gate:** Passed. All 343 tests pass at the unchanged `1e-12` relative and absolute
tolerance; Pyright reports no errors or warnings; Pylint reports 10.00/10 with no
messages across `src`, `tests`, and `scripts`; and `git diff --check` reports no
whitespace errors. No public calculation behavior, result-frame schema, default,
dependency, tolerance, threshold, or released Carino or Frongello behavior changed.

### 4. Integrate all result frames and attribution methods

**Status:** Complete September 6, 2026.

- Remove the temporary guard only after private numerical verification.
- Reuse the released linker dispatch, vector application, aggregation, cumulative,
  and reconciliation pipeline.
- Cover all four attribution methods and their component and collapse identities.
- Prove contribution linking, unlinked effects, schemas, null placement, and ordering
  remain unchanged across effect-linker selection.

**Gate:** Every public result frame and reconciliation row passes; default Carino and
opt-in Frongello results remain unchanged.

**Implementation evidence:** The temporary public guard is removed. Menchero now uses
the released coefficient dispatch, vectorized period-detail multiplication, period
and identifier aggregation, cumulative construction, and reconciliation pipeline.
No parallel attribution or result-frame path was added.

Parameterized integration tests exercise Brinson-Fachler and
Brinson-Hood-Beebower in both two- and three-effect form. Independently calculated
two-period coefficients are applied to every period-detail effect, after which tests
verify period-summary, overall-detail, cumulative, and final reconciliation values.
Both method families retain their row, period, identifier, and cumulative component
and two-to-three-effect collapse identities.

Exact comparisons against Carino protect every non-linker-sensitive column, including
logarithmically linked contributions, unlinked effects, schemas, dtypes, nulls, and
ordering. Shared one-period tests cover authoritative contribution, null effective
return, signed exposure, and missing-side representations under both Menchero and
Frongello. Determinism, caller nonmutation, and independent frame ownership now cover
all three effect linkers. A deliberate path-sensitive example also proves Menchero
and Frongello remain distinct while reconciling to the same horizon active return.

**Gate:** Passed. All 362 tests pass at the unchanged `1e-12` relative and absolute
tolerance, including every existing Carino and Frongello regression. Pyright reports
no errors or warnings; Pylint reports 10.00/10 with no messages across `src`, `tests`,
and `scripts`; and `git diff --check` reports no whitespace errors. No result-frame
schema, default, dependency, tolerance, threshold, contribution policy, or released
Carino or Frongello behavior changed.

### 5. Complete fixtures and user documentation

**Status:** Complete September 6, 2026.

- Add complete independently hand-calculated expectations for period detail, period
  summary, overall detail, cumulative output, and reconciliation.
- Exercise positive, negative, zero, and authoritative contributions; null effective
  returns; cash; signed weights; missing sides; and disappearing identifiers.
- Explain every nontrivial calculation and expected value in test docstrings or
  fixture provenance.
- Document the Carino default, Menchero opt-in, order independence, source-period
  interpretation, and contribution/effect separation in README and specifications.
- Record that GRAP remains intentionally unimplemented as a separate identity.

**Gate:** Expected values are demonstrably independent of production output, `ppar`,
`pybrinson`, and every other implementation.

**Fixture evidence:** Five `expected_menchero_*.csv` files record complete period
detail, period summary, overall detail, cumulative output, and all 19 reconciliation
rows for the established two-period fixture. The two Menchero coefficients were
derived from literal period and compounded horizon returns with 50-digit decimal
arithmetic. Each effect value is the independently calculated unlinked effect times
its period coefficient; period, identifier, cumulative, and reconciliation values are
independent sums and identities. Non-effect and logarithmic-contribution values retain
the fixture's previously documented independent arithmetic.

`tests/fixtures/README.md` records the common scale, residual, squared active norm,
both coefficients, every linked period-detail effect, period and identifier sums,
cumulative totals, reconciliation, and source provenance. No expected value came from
`perfattr`, `ppar`, `pybrinson`, or another implementation.

**Edge-case evidence:** Shared one-period tests exercise both Menchero and Frongello
across all four attribution methods using the derived and authoritative fixtures.
They cover positive, negative, and zero values; signed and zero weights; identifiers
missing from either side; authoritative contribution; and null effective return.
Dedicated two-period tests independently calculate Menchero values for an ordinary
cash identifier that disappears and a disappearing zero-weight authoritative fee or
financing-style charge. Shared public tests also cover period and horizon returns
close to, but strictly greater than, `-1` under every attribution method. Names select
no special mathematics.

**Documentation evidence:** `README.md` lists all three effect linkers, shows Menchero
selection, distinguishes its order-independent minimum-correction policy from
Frongello's path dependence, explains the source-period cumulative interpretation,
and reiterates contribution/effect separation and ordinary cash, fee, and financing
treatment. It also records why GRAP remains intentionally unimplemented as a
duplicate numerical identity. The portable specification now identifies Menchero at
the shared public boundary and summarizes its governing formula, stable evaluation,
zero-vector policy, and ordering behavior while deferring full detail to the accepted
Menchero specification.

**Gate:** Passed. All 368 tests pass at the unchanged `1e-12` relative and absolute
tolerance. Focused fixture and edge-case tests pass; Pyright reports no errors or
warnings; Pylint reports 10.00/10 with no messages across `src`, `tests`, and
`scripts`; and `git diff --check` reports no whitespace errors. No expected value was
captured from production output, and no schema, dependency, tolerance, threshold,
default, or released Carino or Frongello behavior changed.

### 6. Verify quality, compatibility, and direct performance

**Status:** Complete September 6, 2026.

- Run the complete test, Pyright, Pylint, formatting, build, metadata, and clean-wheel
  gates on every supported Python version.
- Measure elapsed time and peak memory for Carino, Frongello, and Menchero across all
  four attribution methods on established direct-core workloads.
- Confirm only pandas, NumPy, and the standard library remain runtime dependencies.
- Establish no new performance threshold without repeatable evidence.

**Gate:** Every established gate passes without a relaxed tolerance, warning,
threshold, schema, or invariant.

**Quality and supported-version evidence:** The source-tree suite passes all 368
tests. The same 368 tests pass against the installed candidate wheel from
`site-packages` on Python 3.11.9, 3.12.1, 3.13.1, and 3.14.7. Every isolated
environment also passes `pip check`. The Python 3.11 development environment reports
no Pyright errors or warnings and Pylint reports 10.00/10 with no messages across
`src`, `tests`, and `scripts`; `git diff --check` is clean.

An isolated Hatchling build produced the source distribution and universal wheel,
and Twine accepted both artifacts. The source distribution includes the Menchero
specification, independent tests, complete expected fixtures, and final performance
documentation. A clean Python 3.11 environment imported the wheel from
`site-packages` and completed all twelve attribution-method/effect-linker combinations
with passing reconciliation. The candidate deliberately retains version `0.7.0a1`;
the approved `0.8.0a1` change belongs to the release step.

Wheel metadata requires Python 3.11 or newer and lists only NumPy and pandas as
unconditioned runtime dependencies. Build, Pylint, Pyright, pytest, and Twine remain
development extras. No Polars, `ppar`, optimizer, or other runtime dependency was
introduced.

**Performance evidence:** The direct-core benchmark now accepts Menchero while
retaining Carino as its default. Five-sample medians and peak traced allocations are
recorded in `docs/performance.md` for Carino, Frongello, and Menchero across all four
attribution methods and all four established workloads: 48 measured combinations.

Menchero medians ranged from 20.9% below to 4.9% above paired Carino observations;
the large percentage decrease came from one visibly noisy 0.0416-second normal
Carino median. The largest absolute Menchero increase was 0.0093 seconds on the
121,260-row-per-side BHB three-effect case. Compared with Frongello, Menchero ranged
from 6.5% below to 4.7% above, with a largest absolute increase of 0.0074 seconds.
Peak traced allocations were identical at reported precision for every paired method
and workload.

These results are observations, not thresholds. They provide no reason to complicate
the linear coefficient helper, add a dependency, or establish a new performance
gate. No formula, tolerance, warning, threshold, schema, invariant, or existing gate
changed.

**Gate:** Passed. Quality, supported-version, packaging, installed-wheel, dependency,
and direct performance verification are complete without weakening a gate.

### 7. Verify the unchanged `ppar` boundary

**Status:** Complete September 6, 2026.

- Install the candidate wheel into `ppar`'s release-candidate environment.
- Confirm its adapter omits `effect_linking_method` and therefore remains on Carino.
- Run the complete `ppar` test, analysis, packaging, demo, and unchanged 500x gates.
- Do not edit `ppar` unless an actual defect requires separate approval.

**Gate:** Existing `ppar` values, schemas, presentation, and scale behavior remain
unchanged at the established tolerances and thresholds.

**Boundary evidence:** The final Step 6 candidate wheel was installed without its
dependencies into `ppar`'s Python 3.12.1 release-candidate environment, replacing
only the previously installed `perfattr==0.6.0a1`. The import resolved from that
environment's `site-packages`, reported the deliberately unchanged candidate version
`0.7.0a1`, and exposed Carino, Frongello, and Menchero identities.

Inspection confirmed that `ppar`'s sole calculation adapter calls
`calculate_attribution` without `effect_linking_method`. It therefore retains the
public default Carino policy and cannot select Menchero accidentally. No `ppar`
source, test, schema, presentation, dependency, tolerance, or threshold was changed.

**Release-candidate evidence:** The complete `ppar` gate passed 305 tests and 477
subtests; mypy found no issues in 38 source files; Pyright reported no errors or
warnings; both Pylint checks passed, including a 10.00/10 focused check; and README
image and documentation drift checks passed. The isolated universal-wheel build,
Twine validation, metadata and CLI checks, and installed generic and Axys/APX
workflows also passed, each producing the expected 11 report artifacts.

The unchanged 500x scale gate passed. The large-site workload grew from 12,126 to
6,063,000 rows and measured 1.078x elapsed time; the selected workload grew from
12,126 to 121,260 rows and measured 2.126x. Both ratios are observation-only. The
long-history workload grew from 12,246 to 61,230 rows and measured 1.565x, below its
unchanged 1.58x warning and 1.65x failure thresholds. The `ppar` worktree retained
exactly its pre-existing modified-file set and diff summary after the gate.

**Gate:** Passed without editing `ppar` or weakening any established contract.

### 8. Release `perfattr==0.8.0a1`

**Status:** Prepublication gate complete September 6, 2026; commit and publication
require explicit approval.

- Recheck all identified patent records immediately before publication.
- Update version and release-facing documentation only after every prior gate passes.
- Build and validate fresh source and wheel distributions.
- Obtain explicit approval before committing, tagging, pushing, creating a GitHub
  prerelease, or publishing to PyPI.
- Verify the public artifact in a clean environment after publication.

**Gate:** The tagged commit, GitHub prerelease, PyPI files, installed version, public
imports, and supported-version smoke tests agree.

**Publication-time patent recheck:** On September 6, 2026, immediately before release
preparation, the public Google Patents records continued to label US 7,249,079 B1,
US 7,246,091 B1, and US 7,249,082 B2 `Expired - Lifetime`, with expiration dates of
January 26, 2023; December 31, 2022; and February 18, 2024. Each record retains its
disclaimer that the listed legal status is an assumption rather than a legal
conclusion. This targeted engineering check is not legal advice or a worldwide
freedom-to-operate opinion.

**Prepublication evidence:** The package and its public version test now identify
`perfattr==0.8.0a1`, and release-facing documentation identifies Menchero as the
release candidate. The source-tree suite passes all 368 tests; Pyright reports no
errors or warnings; Pylint reports 10.00/10 with no messages across `src`, `tests`,
and `scripts`; and `git diff --check` is clean.

An isolated Hatchling build produced `perfattr-0.8.0a1.tar.gz` and the universal
`perfattr-0.8.0a1-py3-none-any.whl`. Twine accepted both artifacts. The wheel SHA-256
is `ddab2d50cd524dd48194e5c7f8358808f61a47e2ed80c946a98b45763792dc4d`; the
source-distribution SHA-256 is
`aee8f06c787a1697359d74da5a1d91fb47ace58b42651ff2875aeb9f750ec2cb`.
Archive inspection confirmed version and Python metadata, the two-runtime-dependency
contract, and inclusion of the Menchero source, specification, tests, and independent
fixtures.

The complete 368-test suite passes against the installed candidate wheel from
`site-packages` on Python 3.11.9, 3.12.1, 3.13.1, and 3.14.7; `pip check` passes in
all four environments. A separate no-cache Python 3.11.9 installation resolved the
wheel with current NumPy 2.4.6 and pandas 3.0.5, imported version `0.8.0a1` from its
isolated `site-packages`, and passed all twelve combinations of the four attribution
methods and three effect linkers with complete reconciliation.

No tolerance, warning, threshold, schema, dependency, invariant, or release gate was
changed. No commit, tag, push, GitHub release, or PyPI upload has been performed.
GitHub authentication is active for `JohnDReynolds`; neither tag nor release
`v0.8.0a1` exists. The public PyPI index lists `0.7.0a1` as the latest prerelease and
does not list `0.8.0a1`. The exact validated candidate is ready for the required
explicit approval.

## Test matrix

At minimum, combine:

- all four released `AttributionMethod` members;
- default and explicit Carino, Frongello, and Menchero;
- one, two, six, and longer period horizons;
- exact equal, near-equal, positive, negative, mixed, and zero active-return paths;
- original and permuted economic chronology;
- derived and authoritative contributions;
- explicit cash, zero-weight charges, signed weights, null effective returns,
  missing-side identifiers, and identifiers that disappear;
- ordinary, near-`-1`, large finite, and deliberate non-finite intermediate cases; and
- direct construction, invalid enum input, caller nonmutation, deterministic order,
  ownership, schema, and reconciliation contracts.

Randomized identity checks supplement but never replace literal primary and
hand-calculated fixtures.

## Performance and dependency constraints

- Preserve pandas and NumPy as the only runtime dependencies.
- Keep coefficient work `O(T)` and effect application linear in existing rows.
- Do not add row-wise pandas callbacks, quadratic period work, expanded identifier
  grids, a second calculation engine, or speculative caching.
- Measure elapsed time and peak memory before considering optimization.
- Preserve all existing direct-core and `ppar` release thresholds.

## Comparative review

`gghez/pybrinson` was reviewed at commit
`529b0940937caacec3f2a30609b9ce6b86316a7b` as Roadmap 3 requests. It reinforced
explicit linker identity, patent verification, a shared coefficient per period, and
cross-linker reconciliation tests.

Roadmap 9 does not adopt its single-period rejection or near-zero horizon shortcut.
The governing specification independently proves the one-period identity and the need
for nonzero corrections in some equal-horizon paths. No source, fixture, expected
value, or documentation text is copied.

## References and intellectual-property review

Primary methodology:

- Menchero, José G. “An Optimized Approach to Linking Attribution Effects over Time.”
  *The Journal of Performance Measurement* 5, no. 1 (Fall 2000): 36–42.
- Menchero, José G. “Multiperiod Arithmetic Attribution.” *Financial Analysts
  Journal* 60, no. 4 (2004): 76–91.
  [DOI](https://doi.org/10.2469/faj.v60.n4.2638).

Primary patent disclosures and public status records:

- [US 7,249,079 B1](https://patents.google.com/patent/US7249079B1/en)
- [US 7,246,091 B1](https://patents.google.com/patent/US7246091B1/en)
- [US 7,249,082 B2](https://patents.google.com/patent/US7249082B2/en)

As reviewed September 6, 2026, each record is labeled `Expired - Lifetime`; the last
listed family expiration is February 18, 2024. The status provider expressly disclaims
a legal conclusion. This targeted review is not legal advice or a worldwide
freedom-to-operate opinion. Steps 3 and 8 require fresh checks, and unclear or changed
status blocks implementation or publication.

All implementation, tests, fixtures, and prose must be original project work derived
from disclosed facts and formulas under the MIT license.

## Completion criterion

Roadmap 9 is complete only when:

- the roadmap and governing specification are explicitly approved;
- every implementation, independent-test, quality, performance, and `ppar` step is
  complete;
- Carino remains the exact default and Frongello remains unchanged;
- Menchero is explicit, stable, reconciled, documented, and independently verified;
- no schema, tolerance, threshold, dependency, or invariant was weakened; and
- `perfattr==0.8.0a1` is published and verified from the public PyPI index.
