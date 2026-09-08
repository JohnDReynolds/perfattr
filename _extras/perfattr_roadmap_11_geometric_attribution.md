# perfattr Roadmap 11: Geometric Excess-Return Attribution

**Status:** Active. Steps 1–7 and the Step 8 prepublication gate are complete
September 7, 2026; commit and publication are explicitly approved and in progress.

This roadmap promotes the geometric-attribution candidate from roadmap 3. Its accepted
governing contract is
[`docs/geometric_attribution_specification.md`][geometric-spec].

[geometric-spec]: ../docs/geometric_attribution_specification.md

## Objective

Add one opt-in Bacon/Burnie top-down geometric attribution calculation whose effects
compound naturally across periods. Keep it separate from the released arithmetic
Brinson calculator and its Carino, Frongello, and Menchero effect linkers.

The approved prerelease target is `perfattr==0.10.0a1`.

## User problem and corrected feature identity

Users comparing relative wealth rather than arithmetic return difference may want
attribution whose total is:

```text
(1 + portfolio return) / (1 + benchmark return) - 1
```

The Roadmap 3 label "geometric linking" was too narrow. Research for this roadmap
confirmed that the feature changes the single-period effect formulas, excess-return
definition, and effect-combination identity. It is therefore a separate geometric
attribution family, not another `EffectLinkingMethod` for existing arithmetic effects.

The smallest useful design provides allocation and portfolio-weighted selection,
with interaction absorbed into selection. It exposes period identifier effects,
period channel totals, compounded prefix results, and explicit multiplicative
reconciliation. It does not invent a per-identifier horizon linker or force geometric
values into the five stable `AttributionResult` frames.

## Scope boundary

Roadmap 11 owns only:

- a public `calculate_geometric_attribution` function using the released prepared
  performance inputs;
- one Bacon/Burnie top-down, two-channel geometric methodology;
- a separate `GeometricAttributionResult` with exact new schemas;
- Brinson-Fachler-style geometric allocation and portfolio-weighted geometric
  selection;
- an explicit accounting-residual extension that preserves authoritative supplied
  contributions;
- period channel totals and direct compounding of allocation and selection through
  time;
- multiplicative period and cumulative reconciliation evidence;
- independently hand-calculated fixtures, documentation, and direct-core performance
  evidence; and
- verification that the existing arithmetic calculator and `ppar` remain unchanged.

Roadmap 11 does not add:

- a member of `AttributionMethod` or `EffectLinkingMethod`;
- Carino, Frongello, Menchero, GRAP, or logarithmic smoothing of geometric effects;
- a separate interaction channel;
- per-identifier horizon effects or a geometric `overall_detail` frame;
- hierarchy roll-up or independently recalculated hierarchy;
- geometric Brinson-Hood-Beebower, currency, derivatives, or external-flow policy;
- Menchero's fully geometric methodology;
- a generic method registry, plugin framework, or user-supplied formula callback;
- a `ppar` adapter or presentation change; or
- another runtime dependency.

## Approved public boundary

```python
result = calculate_geometric_attribution(
    portfolio,
    benchmark,
    reconciliation_tolerance=1e-12,
)
```

The approved result owns four independent pandas DataFrames:

```python
@dataclass
class GeometricAttributionResult:
    period_detail: pd.DataFrame
    period_summary: pd.DataFrame
    cumulative: pd.DataFrame
    reconciliation: pd.DataFrame
```

Do not add a methodology enum until a second approved geometric methodology creates a
real selection problem. The function and result type establish the method identity
without a speculative abstraction.

## Approved financial policy

For period `t`, let `P[t]` and `B[t]` be the authoritative portfolio and benchmark
contribution totals. Form the semi-notional return `N[t]` by applying portfolio
weights to benchmark identifier returns. Then:

```text
geometric excess E[t] = (1 + P[t]) / (1 + B[t]) - 1
allocation A[t]       = (1 + N[t]) / (1 + B[t]) - 1
selection S[t]        = (1 + P[t]) / (1 + N[t]) - 1

1 + E[t] = (1 + A[t]) * (1 + S[t])
```

Identifier allocation uses the published geometric Brinson-Fachler expression when
benchmark contribution equals benchmark weight times return. An explicit benchmark
accounting-residual term extends it when supplied contribution is authoritative.
Identifier selection likewise uses authoritative portfolio contribution rather than
silently reconstructing it. The governing specification defines these formulas and
their null boundary exactly.

Across periods, compound portfolio, benchmark, semi-notional, allocation, and
selection returns independently. No smoothing coefficient is required:

```text
1 + E[H] = product_t(1 + E[t])
         = product_t(1 + A[t]) * product_t(1 + S[t])
```

The allocation and selection channel totals compound naturally, but individual
identifier effects do not have a unique compounded allocation without another
policy. Roadmap 11 therefore omits per-identifier horizon values instead of silently
assigning cross-period or cross-channel terms.

## Compatibility plan

- Do not add, remove, rename, reorder, or reinterpret any released
  `AttributionResult` column.
- Do not change `calculate_attribution`, `AttributionMethod`, `EffectLinkingMethod`,
  their defaults, or their arithmetic active-return identity.
- Keep the new geometric frames under a separate result type and exact schemas.
- Reuse input normalization only where its existing meaning is unchanged.
- Preserve supplied contribution as authoritative in both calculation families.
- Retain the unchanged `1e-12` default relative and absolute reconciliation tolerance.
- Keep pandas and NumPy as the only runtime dependencies.
- Require no `ppar` change; later host adoption needs separately approved scope.

## Implementation sequence

### 1. Approve the contract

**Status:** Complete September 7, 2026.

- Approve the corrected geometric-attribution identity and separate result family.
- Approve the one-method, two-channel Bacon/Burnie boundary.
- Approve the authoritative-contribution residual formulas and undefined
  semi-notional-return rejection.
- Approve the four exact schemas and deliberate omission of per-identifier horizon
  output.
- Approve unchanged arithmetic behavior, unchanged `ppar`, and the approved
  `0.10.0a1` target.

**Gate:** No source, test, fixture, version, or public API implementation begins before
explicit user approval of this roadmap and its governing specification.

**Approval evidence:** On September 7, 2026, the user explicitly approved Roadmap 11
and its governing specification and asked to proceed with Step 1 while using GPT-5.6
Sol High. This approves the separate geometric-attribution identity; the one-method,
two-channel Bacon/Burnie boundary; the authoritative-contribution residual formulas;
the undefined semi-notional-return rejection; the four exact schemas; the deliberate
omission of per-identifier horizon output; unchanged arithmetic and `ppar` behavior;
and the `0.10.0a1` prerelease target.

**Gate:** Passed. Step 2 is authorized; later steps remain dependency-gated.

### 2. Establish the public identity and exact schemas

**Status:** Complete September 7, 2026.

- Add and export `GeometricAttributionResult` and
  `calculate_geometric_attribution`.
- Establish exact period-detail, period-summary, cumulative, and reconciliation
  schemas, dtypes, ordering, and ownership tests.
- Add strict argument and direct-construction tests.
- Temporarily reject otherwise valid calculations until the financial helper and
  independent fixtures pass.

**Gate:** Identity and exact-schema tests pass, the temporary guard cannot be bypassed,
and no released API or schema changes.

**Implementation evidence:** `GeometricAttributionResult` and
`calculate_geometric_attribution` are exported from `perfattr.geometric` and the
package root. The result has exactly the four approved DataFrame fields in order and
is deliberately separate from `AttributionResult`; no methodology enum, arithmetic
method, or effect-linker member was added.

Dedicated immutable schema tuples establish the exact period-detail, period-summary,
cumulative, and reconciliation columns. Tests record their canonical date, day-count,
identity, numerical, and boolean dtypes; zero-based indexes; ordinary direct-
construction ownership; the deliberate absence of identifier `total_effect`; and the
deliberate absence of an `overall_detail` result field.

The staged function strictly requires pandas inputs and the released positive finite,
non-boolean tolerance. Every otherwise valid call reaches an unconditional
`NotImplementedError` before input-content normalization or financial calculation,
without mutating either input. No empty or partial geometric result can escape the
guard.

**Gate:** Passed. All 461 tests pass, including 15 focused geometric-boundary tests
and one package-root export test. Pyright reports no errors or warnings; Pylint reports
10.00/10 with no messages across `src`, `tests`, and `scripts`; the complete Python
line-length check and `git diff --check` report no errors. No released calculation,
result schema, enum, default, version, dependency, tolerance, threshold, or invariant
changed.

Step 3 is authorized; later steps remain dependency-gated.

### 3. Implement and independently verify single-period mathematics

**Status:** Complete September 7, 2026.

- Normalize and equalize prepared inputs under the released contract.
- Construct the semi-notional return without treating a null return as zero when its
  portfolio exposure is nonzero.
- Implement identifier allocation and selection, including authoritative-contribution
  residuals.
- Add literal hand calculations that reduce to the published weights-and-returns
  formulas and separate accounting-integrated cases.
- Cover signed weights, missing sides, cash, unexposed fees, null effective returns,
  and invalid semi-notional denominators.

**Gate:** Identifier sums, the two successive-notional ratios, and the complete
multiplicative identity pass at the unchanged tolerance for independently calculated
fixtures and randomized checks.

**Implementation evidence:** A private geometric period vertical slice reuses the
released prepared-input normalization, period matching, weight-total validation, and
identifier-universe equalization without changing their behavior. It returns the
approved canonical period-detail and period-summary frames while the public function
remains unconditionally guarded.

The calculation applies portfolio weights to benchmark effective returns to form the
semi-notional contribution. It rejects a null benchmark effective return whenever
the corresponding portfolio weight is nonzero, preserves zero only when that weight
is exactly zero, and requires every semi-notional period return to be finite and
greater than `-1.0`. Allocation implements the geometric Brinson-Fachler numerator
and subtracts the explicit authoritative benchmark accounting residual. Selection
uses authoritative portfolio contribution directly and absorbs interaction. Every
non-null calculated value is required to be finite.

Ten independently explained financial tests reproduce the governing two-identifier
example from literal numerators; demonstrate supplied returns that differ from
authoritative contributions; preserve portfolio and benchmark zero-weight charges;
reject an unknowable semi-notional leg and a nonpositive semi-notional wealth base;
cover missing sides, ordinary cash, signed exposure, exact zero effects, and caller
row-order determinism; and verify 160 identifier-period effects across 20 randomized
periods against independently calculated dot products and wealth ratios. No expected
value came from production output, `ppar`, `pybrinson`, or another implementation.

**Gate:** Passed. All 471 tests pass, including 10 focused single-period geometric
tests and the 15 staged-boundary tests. Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; the complete
Python line-length check and `git diff --check` report no errors. The public guard
remains active, and no released arithmetic calculation, result schema, enum, default,
version, dependency, tolerance, threshold, or invariant changed.

Step 4 is authorized; later steps remain dependency-gated.

### 4. Add cumulative compounding and reconciliation

**Status:** Complete September 7, 2026.

- Compound portfolio, benchmark, semi-notional, allocation, and selection values for
  every chronological prefix.
- Populate period and cumulative reconciliation evidence.
- Prove the final geometric excess equals both the portfolio-to-benchmark wealth
  ratio and the compounded channel product.
- Remove the temporary public guard only after complete period and cumulative tests
  pass.

**Gate:** Every period and prefix reconciles; one-period identity, period-order
invariance, long history, near-total-loss, and explicit invalid-domain cases pass.

**Implementation evidence:** The public `calculate_geometric_attribution` operation
now runs the independently verified period calculation, compounds every chronological
portfolio, benchmark, semi-notional, allocation, and selection prefix with stable
`log1p`/`expm1` arithmetic, derives geometric excess directly from compounded
portfolio and benchmark wealth, and returns all four approved frames. The temporary
guard is removed; no partial result path remains.

Each period produces six ordered checks: identifier allocation and selection sums,
both successive-notional ratios, portfolio-to-benchmark geometric excess, and the
multiplicative channel identity. Each cumulative prefix produces nine ordered checks:
direct compounding of all five legs, geometric excess, both successive-notional
ratios, and the multiplicative channel identity. Stable logarithmic cumulative values
are cross-checked against direct prefix products. Every check must pass before the
result is returned, and non-finite evidence is rejected.

The governing specification's tolerance display was corrected to match the existing
project helper's unchanged symmetric rule: difference must not exceed the greater of
the absolute tolerance and relative tolerance times the larger magnitude. The earlier
prose had called the rule unchanged while displaying a different additive expression.
No implementation tolerance or gate was widened or otherwise changed.

Seven focused cumulative tests independently multiply a two-period example, verify
the exact six-plus-nine reconciliation inventory, prove one-period identity and final
period-order invariance, exercise 1,000 chronological periods and 15,000 passing
checks, retain finite near-total-loss behavior, and demonstrate that tampered period
totals raise before a result can escape. The previously specified undefined and
nonpositive semi-notional domain failures now also execute through the public
boundary.

**Gate:** Passed. All 478 tests pass, including 32 focused geometric tests. Pyright
reports no errors or warnings; Pylint reports 10.00/10 with no messages across `src`,
`tests`, and `scripts`; the complete Python line-length check and `git diff --check`
report no errors. No released arithmetic calculation, result schema, enum, default,
version, dependency, tolerance, threshold, or invariant changed.

Step 5 is authorized; later steps remain dependency-gated.

### 5. Complete behavioral coverage and documentation

**Status:** Complete September 7, 2026.

- Prove caller nonmutation, independent result ownership, deterministic sorting, and
  strict schema/dtype/null behavior.
- Prove every existing arithmetic result remains unchanged.
- Document when geometric attribution is appropriate and why it is separate from
  arithmetic effect linking.
- Explain every nontrivial fixture calculation and accounting residual in test
  docstrings, comments, or fixture-provenance notes.
- Record the exact `pybrinson` comparative review and confirm no copied code, fixture,
  expected value, or prose.

**Gate:** Documentation, provenance, compatibility, and complete functional coverage
pass without weakening a tolerance, invariant, warning, threshold, or dependency
boundary.

**Implementation evidence:** Seven public-behavior tests now require exact schemas,
canonical `datetime64[ns]`, `int64`, `float64`, `bool`, and Python-backed pandas string
dtypes, zero-based indexes, and the approved effective-return null placement for
opposing portfolio and benchmark unexposed charges. Reversing caller rows preserves
every result frame exactly. Mutating any returned frame leaves its peers and a later
calculation unchanged, while both caller inputs remain unmodified.

A focused compatibility test runs the geometric family between two arithmetic
calculations and requires bit-for-bit equality across all five arithmetic result
frames. It also preserves the hand-calculated distinction between 0.2% arithmetic BF
allocation and that numerator divided by 1.06 under geometric attribution. The
complete pre-existing arithmetic suite continues to pass without an enum, default,
formula, linker, schema, dtype, null, ordering, or reconciliation change.

The README now lists geometric excess-return attribution among the main features,
links its roadmap and specification, provides a public example, and explains when to
choose wealth-relative geometric output rather than additive arithmetic output. It
documents the semi-notional bridge, multiplicative channel identity, absence of
arithmetic smoothing, deliberate omission of identifier-level horizon output, and
authoritative cash and charge behavior. The portable arithmetic specification links
the separate geometric supplement without changing its own contract and records
identifier-level geometric horizon attribution as deferred.

The governing geometric specification records the exact `pybrinson` commit reviewed
and the independent provenance of the period, cumulative, reconciliation, behavior,
and compatibility tests. No source, prose, fixture, or expected value was copied from
`pybrinson`, `ppar`, production output, or another implementation.

**Gate:** Passed. All 485 tests pass, including 39 focused geometric tests. Pyright
reports no errors or warnings; Pylint reports 10.00/10 with no messages across `src`,
`tests`, and `scripts`; documentation line checks, the complete Python line-length
check, and `git diff --check` report no errors. No released calculation, result
schema, enum, default, version, dependency, tolerance, threshold, or invariant
changed.

Step 6 is authorized; later steps remain dependency-gated.

### 6. Complete quality, performance, and package gates

**Status:** Complete September 7, 2026.

- Run the complete test suite on every supported Python version.
- Run Pyright with no errors or warnings and Pylint with no messages.
- Run formatting, line-length, build, metadata, archive-inspection, and clean-wheel
  import/calculation checks.
- Benchmark elapsed time and peak memory for realistic derived and authoritative
  inputs across period counts and identifier counts.
- Establish no new performance threshold without correct, repeatable evidence.

The complete suite passes all 485 tests in isolated Python 3.11.9, 3.12.1, 3.13.1,
and 3.14.7 environments. Pyright reports no errors or warnings, and Pylint reports
10.00/10 with no messages across `src`, `tests`, and `scripts`. `git diff --check`,
the complete Python line-length check, and documentation line checks report no
errors.

The repeatable direct benchmark uses the four established workload shapes and the
same deterministic prepared-input builder as the arithmetic benchmark. Its eight-case
matrix covers both derived and authoritative inputs across 6,063 to 121,260 rows per
side and 60 to 300 periods. Median elapsed time ranged from 0.0260 to 0.1707 seconds;
incremental Python-traced allocation ranged from 3.5 to 66.0 MiB. Prepared inputs and
returned frames are reported separately. The results retain the simple direct
implementation and establish no threshold.

A fresh source distribution and universal wheel build successfully from the source
tree at the unchanged pre-release version `0.9.0a1`; Twine validates both artifacts.
Archive inspection confirms the geometric module, tests, benchmark, specification,
license, README, and project metadata are present as applicable. Clean wheel
installations under all four supported Python versions pass dependency checks, import
from `site-packages`, report the built version, complete a public geometric
calculation, and return passing reconciliation evidence.

**Gate:** Passed. No released schema, calculation, default, version, dependency,
tolerance, threshold, warning, or invariant changed.

Step 7 is authorized; later steps remain dependency-gated.

### 7. Verify the unchanged `ppar` boundary

**Status:** Complete September 7, 2026.

- Install the candidate wheel into `ppar`'s release-candidate environment.
- Confirm `ppar` neither imports nor calls the new geometric boundary.
- Run the complete established `ppar` release-candidate workflow, including its
  unchanged 500x scale check.
- Do not edit `ppar` unless an actual defect requires separate approval.

Inspection confirms that `ppar` neither imports nor calls
`calculate_geometric_attribution` or `GeometricAttributionResult`. Its adapter keeps
calling the established arithmetic `calculate_attribution` boundary without a method
or schema change. The Roadmap 11 candidate wheel was installed without dependencies
into `ppar`'s Python 3.12.1 release-candidate environment; `pip check` passes and the
installed package reports `perfattr==0.9.0a1` from `site-packages`.

The complete established `ppar` release-candidate command passes 305 tests and 477
subtests, Mypy across 38 source files, Pyright with no errors or warnings, both Pylint
checks, documentation and image validation, universal-wheel construction, Twine,
package metadata, and installed generic and Axys/APX demonstrations producing all 11
expected artifacts each.

The unchanged 500x gate retains large-site equivalence and observes a
1.065x elapsed-time ratio. The selected-input workload observes 2.016x at 10x rows;
neither case has a machine-specific threshold. Long history observes 1.552x at 5x
history, below the unchanged 1.58x warning and 1.65x failure boundaries.

**Gate:** Passed. No `ppar` source, schema, report, dependency declaration, version,
calculation, tolerance, threshold, warning, or presentation behavior changed. The
pre-existing user worktree changes remained untouched.

Step 8 is authorized.

### 8. Release `perfattr==0.10.0a1`

**Status:** Prepublication gate complete September 7, 2026; commit and publication
are explicitly approved and in progress.

- Update version and release-facing documentation only after every prior gate passes.
- Build and validate fresh source and wheel distributions.
- Obtain explicit approval before committing, tagging, pushing, creating a GitHub
  prerelease, or publishing to PyPI.
- Verify the public artifact in clean environments on every supported Python version.

**Gate:** The tagged commit, GitHub prerelease, PyPI files, installed version, public
imports, and supported-version smoke tests agree.

**Prepublication evidence:** The package and its public version test identify
`perfattr==0.10.0a1`. The README and governing specification identify geometric
excess-return attribution as the release candidate. The source-tree suite passes all
485 tests; Pyright reports no errors or warnings; Pylint reports 10.00/10 with no
messages across `src`, `tests`, and `scripts`; and whitespace, Python line-length, and
documentation line checks are clean.

An isolated Hatchling build produced `perfattr-0.10.0a1.tar.gz` and the universal
`perfattr-0.10.0a1-py3-none-any.whl`. Twine accepts both artifacts. The wheel SHA-256
is `574bc2785cdca8bfcdc733626ccf517462fa8836854beaff3c1f33a43ac7e496`; the source-
distribution SHA-256 is
`0a1ccca7ff66e25f58e2000697612f269584d8509500698b90bc1bad36b3a811`.
Archive inspection confirms version and Python metadata, the unchanged two-runtime-
dependency contract, and inclusion of the geometric source, benchmark, governing
specification, tests, and independently documented fixture provenance.

Clean installations of the candidate wheel under Python 3.11.9, 3.12.1, 3.13.1, and
3.14.7 import from `site-packages`, report the expected version, pass dependency
checks, complete a public geometric calculation with passing reconciliation, and pass
all 485 tests in each environment.

At this checkpoint, GitHub authentication is active for `JohnDReynolds`; neither the
remote tag nor GitHub release `v0.10.0a1` exists. The public PyPI index lists
`0.9.0a1` as the latest prerelease and does not contain `0.10.0a1`. No commit, tag,
push, GitHub release, or PyPI publication has been performed without the required
explicit approval.

The user explicitly approved committing and pushing, tagging `v0.10.0a1`, creating
the GitHub prerelease, publishing to PyPI, and verifying the public package after all
prepublication evidence above passed.

## Comparative review and provenance

`gghez/pybrinson` was reviewed at commit
`529b0940937caacec3f2a30609b9ce6b86316a7b` as Roadmap 3 requests. Its geometric
module reinforced three useful boundaries: calculate through a semi-notional
portfolio, absorb interaction into selection, and compound channel totals without an
arithmetic smoothing coefficient.

Roadmap 11 makes independent choices suited to `perfattr`: a separate geometric
result, explicit period detail, cumulative prefixes, authoritative-contribution
support, and no identifier-level horizon allocation. `pybrinson` returns aggregate
channel totals and derives them from an arithmetic result; `perfattr` will calculate
its geometric identifier effects directly from prepared facts.

The reviewed source is MIT-licensed. No source, fixture, expected value, or prose is
copied. All implementation and tests must be original project work, with expected
values calculated independently and documented.

## References

Methodological authority and context:

- Bacon, Carl R. *Practical Portfolio Performance Measurement and Attribution*, 2nd
  ed. Wiley, 2008, ch. 6.
  [Chapter DOI](https://doi.org/10.1002/9781119206309.ch6).
- Bacon, Carl R. *Practical Portfolio Performance Measurement and Attribution*, 3rd
  ed. Wiley, 2022, ch. 6.
  [Chapter page](https://onlinelibrary.wiley.com/doi/10.1002/9781119831976.ch6).
- CFA Institute Research Foundation. *Performance Attribution: History and Progress*.
  2019. [Research Foundation brief][cfa-history].

Comparative product behavior:

- Eagle Performance, *Geometric Attribution Method*.
  [Method overview][eagle-overview].
- Eagle Performance, *Brinson-Fachler Effects for the Geometric Attribution Method*.
  [Effect formulas][eagle-effects].

[cfa-history]: https://rpc.cfainstitute.org/research/foundation/2019/performance-attribution
[eagle-overview]: https://eagledocs.atlassian.net/wiki/spaces/Performance2017/pages/856719916
[eagle-effects]: https://eagledocs.atlassian.net/wiki/spaces/Performance2017/pages/856719436

## Completion criterion

Roadmap 11 is complete only when:

- the roadmap and governing specification are explicitly approved;
- every implementation, independent-test, quality, performance, and `ppar` step is
  complete;
- every period and cumulative prefix satisfies the successive-notional and complete
  multiplicative identities at the unchanged tolerance;
- authoritative contributions remain authoritative and all undefined-return cases
  follow the approved boundary;
- the existing arithmetic calculator and all released schemas remain unchanged;
- no tolerance, warning, threshold, dependency, or invariant is weakened; and
- `perfattr==0.10.0a1` is published and verified from the public PyPI index.
