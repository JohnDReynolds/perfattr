# perfattr Roadmap 5: Brinson-Fachler Three-Effect Attribution

**Status:** Completed September 5, 2026. Released as `perfattr==0.4.0a1`.

This roadmap promotes the separate-interaction and Brinson-Fachler three-effect
candidates from roadmap 3 as one deliberately narrow feature. Its governing contract
is
[`docs/brinson_fachler_three_effect_specification.md`][three-effect-spec].

[three-effect-spec]: ../docs/brinson_fachler_three_effect_specification.md

## Objective

Add an explicit opt-in Brinson-Fachler three-effect calculation that reports
allocation, benchmark-weighted selection, and interaction separately while preserving
the released portfolio-weighted-selection calculation and every existing default
result-frame schema.

The new calculation must:

- use the released Brinson-Fachler allocation formula unchanged;
- separate interaction only when the caller explicitly selects the new method;
- preserve authoritative contributions, including zero-weight charges with undefined
  effective returns;
- link all three effects with the released Carino active-effect coefficient;
- reconcile allocation plus selection plus interaction to total effect at period and
  full-horizon levels; and
- leave `ppar` behavior and output schemas unchanged unless a later, separately
  approved host-exposure step requests the new method.

## Scope boundary

Roadmap 5 owns only:

- one public calculation-method enum;
- an optional `method` argument on `calculate_attribution()`;
- explicit method metadata on `AttributionResult`;
- one opt-in three-effect result-schema variant;
- Brinson-Fachler interaction calculation and Carino linking;
- three-effect reconciliation, fixtures, documentation, and performance evidence; and
- verification that `ppar`'s existing default path remains compatible.

Roadmap 5 does not add:

- Brinson-Hood-Beebower attribution;
- classification hierarchy or parent-child roll-up;
- another multi-period linking method;
- currency, external-flow, derivative, cash, fee, or financing policy;
- a plugin framework or generic formula registry;
- presentation, charts, HTML, or report formatting; or
- automatic `ppar` exposure of the new method.

## Approved compatibility plan

The released two-effect behavior remains the default and returns exactly the released
DataFrame columns, order, null placement, values, and reconciliation check names.

The caller opts into a distinct three-effect schema with:

```python
calculate_attribution(
    portfolio,
    benchmark,
    method=AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
)
```

`AttributionResult.method` identifies the selected method. The new three-effect frame
variant adds only these columns at the documented effect positions:

- `interaction_effect` and `linked_interaction_effect` in period detail and summary;
- `linked_interaction_effect` in overall detail; and
- `linked_interaction_effect` and `cumulative_interaction_effect` in cumulative output.

Three-effect reconciliation uses `three_effect_components` and
`linked_three_effect_components` check names. The reconciliation frame's columns do
not change. Because the default schemas remain byte-for-byte compatible, current
`ppar` translation continues to request and consume only the two-effect result.

This is an intentional opt-in schema addition for a new method, not a reinterpretation
of any released column. Approval of this roadmap constitutes approval of this
compatibility plan; implementation must not broaden it without further approval.

## Financial policy

For group `g` and period `t`, let `wP`, `wB`, `rP`, and `rB` be the portfolio and
benchmark weights and effective returns, and let `B` be the total benchmark return.
The three ordinary Brinson-Fachler effects are:

```text
allocation  = (wP - wB) * (rB - B)
selection   = wB * (rP - rB)
interaction = (wP - wB) * (rP - rB)
```

The released total-effect definition remains authoritative:

```text
total = portfolio_contribution - benchmark_contribution - (wP - wB) * B
```

When both effective returns are defined, the implementation calculates interaction
directly and calculates selection as the exact reconciliation residual:

```text
interaction = (wP - wB) * (rP - rB)
selection = total - allocation - interaction
```

Because a defined effective return is contribution divided by nonzero weight, this
residual is algebraically equal to benchmark-weighted selection while minimizing an
additional floating-point reconciliation path.

When either effective return is undefined, there is no defensible return difference
from which to calculate interaction. The implementation sets interaction to zero and
leaves the authoritative residual in selection. It does not invent a return or create
a fourth residual effect. This preserves the released treatment of zero-weight fees
and financing while keeping all three reported effects finite and reconciled.

The released two-effect selection must equal three-effect selection plus interaction
within the approved numerical tolerance for every valid input.

## Implementation sequence

### 1. Approve the contract

**Status:** Complete September 5, 2026.

- Review and approve this roadmap and the proposed specification.
- Confirm the public method names, default compatibility, result metadata, opt-in
  schema additions, and undefined-return policy.
- Confirm that `ppar` exposure remains outside this roadmap unless separately approved.

**Gate:** Passed. The user approved the roadmap and governing specification on
September 5, 2026.

### 2. Add method selection and schema variants

**Status:** Complete September 5, 2026.

- Add and export `AttributionMethod` with only the released two-effect and proposed
  three-effect Brinson-Fachler values.
- Add the keyword-only `method` argument with the two-effect value as its default.
- Add method metadata to `AttributionResult` without breaking existing five-argument
  construction.
- Define separate, deterministic internal column tuples for two- and three-effect
  frames rather than mutating one global schema at runtime.
- Reject invalid method values at the public boundary with a clear exception.

**Implementation evidence:** `AttributionMethod` is exported with the two approved
values. `calculate_attribution()` accepts and strictly validates the keyword-only
method, `AttributionResult` carries defaulted method metadata without breaking its
released five-argument construction, and independent three-effect schema tuples add
only the approved interaction columns and reconciliation names. Until Step 3 supplies
the financial decomposition, an explicit temporary guard prevents the selected
three-effect method from returning misleading two-effect values.

**Gate:** Passed. All 258 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages; and existing default schema and method behavior
remain unchanged.

### 3. Calculate the third effect

**Status:** Complete September 5, 2026.

- Preserve allocation and total-effect calculation exactly.
- Calculate interaction only from defined effective returns.
- Calculate three-effect selection as the reconciliation residual.
- Preserve current two-effect selection without routing it through a new numerical
  formula.
- Keep null effective-return placement and finite effect output unchanged.

**Implementation evidence:** The period-detail calculation now selects the approved
three-effect schema internally, calculates interaction only where both effective
returns are defined, and assigns zero interaction at the disclosed undefined-return
boundary. Three-effect selection is the exact residual after unchanged allocation and
total effect, while the released two-effect branch retains its previous expression.
Independent tests cover the specification's positive-interaction table, a negative-
interaction case driven by authoritative contributions, and a zero-weight fee with a
null effective return. An exact frame comparison also proves that explicitly selecting
the two-effect method produces the same five public frames as the default path. The
public three-effect method remains guarded until Step 4 carries interaction through
linking, aggregation, and reconciliation.

**Gate:** Passed. Independent single-period values prove each effect, the three-effect
identity, and collapse back to released two-effect selection at `1e-12`. All 262 tests
pass; Pyright reports no errors or warnings; Pylint reports 10.00/10 with no messages;
and `git diff --check` reports no whitespace errors.

### 4. Link, aggregate, and reconcile

**Status:** Complete September 5, 2026.

- Apply the existing Carino active coefficient to interaction.
- Carry interaction through period summary, overall detail, and cumulative output.
- Sum three components in period and overall reconciliation.
- Retain every existing two-effect reconciliation row and value unchanged.
- Validate all numerical result columns under the released finite/null policy.

**Implementation evidence:** The public three-effect method now carries interaction
through period detail and summary, overall identifier detail, and cumulative output
using the same Carino active coefficient as allocation, selection, and total effect.
Method-aware reconciliation sums all three components and uses the approved explicit
check names, while the two-effect schemas, checks, and calculation branches remain
unchanged. Reconciliation construction was separated into a focused internal module
to keep the calculation path within the established static-quality limits; the public
`AttributionError` export and behavior remain unchanged. Independent two-period values
verify linked selection and interaction for every identifier-period, aggregation by
period and identifier, cumulative totals, and collapse to linked two-effect selection.
The near-minus-one and equal-return linking fixture also passes every three-effect
identity.

**Gate:** Passed. Multi-period hand calculations and linking-limit cases reconcile at
`1e-12` without changing the established tolerance. All 265 tests pass; Pyright
reports no errors or warnings; Pylint reports 10.00/10 with no messages; and
`git diff --check` reports no whitespace errors.

### 5. Complete independent tests and documentation

**Status:** Complete September 5, 2026.

- Add hand-calculated fixtures that distinguish selection from interaction and expose
  positive and negative interaction.
- Cover authoritative contribution, zero-weight nonzero-contribution, missing-side,
  signed-weight, row-order, and caller-nonmutation behavior.
- Cover equal and near-equal Carino returns and returns near the greater-than-minus-one
  linking boundary.
- Document formulas, sign conventions, null behavior, column order, and examples.
- Give every nontrivial test and calculation the detailed financial comments and
  Google-style docstrings required by `AGENTS.md`.

**Implementation evidence:** Two original single-period fixture sets now record
independently calculated positive and negative interaction values, including an
authoritative-contribution case whose supplied returns deliberately differ from its
effective returns. End-to-end tests cover an unexposed accounting charge, explicit
zero-weight and missing-side identifiers, signed weights, both method schemas,
deterministic input permutations, caller nonmutation, independent result-frame
ownership, regular and near-boundary Carino linking, and reproducible randomized
inputs used only to test financial identities. The fixture provenance explains the
hand calculations and confirms that no expected value came from `ppar`, `pybrinson`,
or production output. The README now gives a working method-selection example and
documents formulas, sign interpretation, authoritative and null-return behavior,
column insertion order, and method metadata. The default calculation specification
now identifies the three-effect supplement and accurately distinguishes released
behavior from still-deferred capabilities.

**Gate:** Passed. Expected values are constructed independently rather than copied
from `ppar`, `pybrinson`, or the production implementation. All 269 tests pass;
Pyright reports no errors or warnings; Pylint reports 10.00/10 with no messages; and
`git diff --check` reports no whitespace errors.

### 6. Verify quality and performance

**Status:** Complete September 5, 2026.

- Run all `perfattr` tests, Pylint, Pyright, build, Twine, and clean-wheel smoke gates.
- Benchmark both methods on the established realistic core workload, measuring elapsed
  time and peak memory.
- Compare default two-effect artifacts with the stable `0.3.0` release.
- Establish no new threshold until correct repeatable measurements justify one.

**Implementation evidence:** The candidate version is `0.4.0a1`. Isolated Hatchling
builds produced its source distribution and universal wheel, and Twine accepted both
artifacts. A clean Python 3.11 environment installed the wheel with only its declared
dependencies and successfully ran public-import, default two-effect, opt-in
three-effect, interaction-value, and reconciliation smoke checks. The candidate
wheel's default results were compared with the published `perfattr==0.3.0` wheel over
the four established attribution fixtures and all five result frames. Columns,
dtypes, index shape, dates, identifiers, null placement, ordering, check names, and
booleans matched exactly; every number matched at `1e-12` relative and absolute
tolerance.

The direct-core benchmark now accepts `--method` while retaining two-effect as its
default. Five-sample measurements covered all four established workloads for both
methods on Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. Three-effect elapsed medians
ranged from 0.3% lower to 2.5% higher; incremental peak traced allocation increased
by 0.2 to 5.0 MiB. The complete observations are recorded in
`docs/performance.md`. They do not justify a new threshold, optimization, or
dependency.

**Gate:** Passed. All 269 tests pass; Pyright reports no errors or warnings; Pylint
reports 10.00/10 with no messages; build, Twine, clean-wheel, and both-method smoke
checks pass; and `git diff --check` reports no whitespace errors. No suppression or
threshold changed, and the default result artifacts remain identical within the
released compatibility contract.

### 7. Verify the `ppar` boundary without expanding it

**Status:** Complete September 5, 2026.

- Install the candidate `perfattr` wheel into the adjacent `ppar` development
  environment without changing the released adapter call or output schema.
- Run the complete `ppar` product gate and unchanged 500x scale check.
- Do not raise `ppar`'s dependency floor or add a host method option unless the user
  separately approves that product change.

**Implementation evidence:** The verified `perfattr==0.4.0a1` wheel was installed in
the adjacent `ppar` Python 3.12.1 development environment. The user approved removing
`ppar`'s speculative `<0.4` upper bound after PEP 440 correctly rejected the candidate;
the existing `>=0.3.0a1` floor and `0.3.0a1` CI constraint remain unchanged. No adapter,
calculation call, host method option, output schema, or presentation behavior changed.
The dependency edit changed the source fingerprint deliberately embedded in `ppar`'s
README images, so the established renderer refreshed that metadata; an independent
pixel comparison against `ppar` HEAD found no visual differences.

The complete `ppar` release-candidate command passed 305 tests and 477 subtests,
Mypy, Pyright, Pylint, documentation and image checks, universal-wheel build, Twine,
installed-wheel metadata and CLI checks, both generic and Axys/APX installed demos,
and the unchanged 500x workflow. The final scale run retained byte-identical
large-site artifacts and observed 1.070x large-site, 2.025x selected-input, and 1.490x
long-history time ratios. An earlier long-history observation of 1.582x crossed only
the unchanged 1.58x warning; immediate repeat and final complete-gate values were
1.537x and 1.490x, both below the warning and 1.65x failure thresholds. No gate or
threshold changed.

**Gate:** Passed. Existing `ppar` output, null placement, ordering, presentation
precision, errors, warnings, and performance gates remain unchanged. The complete
release-candidate command ended with `ppar release-candidate gate passed.`

### 8. Release the feature

**Status:** Complete September 5, 2026.

- Review public documentation, license, fixture provenance, and the compatibility
  plan.
- Release first as `perfattr==0.4.0a1` because the package gains a public method and an
  opt-in result-schema variant.
- Build and verify source and wheel distributions from the clean release commit.
- Publish by annotated tag and GitHub prerelease through trusted PyPI publishing.
- Verify a no-cache public-index installation and three-effect smoke calculation.
- Promote to stable `0.4.0` only after approved downstream integration evidence.

**Gate:** Publication requires explicit user approval after all prepublication evidence
is recorded.

**Release evidence:** The user approved publication after every prepublication gate
passed. Clean commit `59d6fa1` produced a verified source distribution and universal
wheel, and an isolated Python 3.11 installation passed the public import and explicit
three-effect smoke calculation with current NumPy and pandas releases. Annotated tag
`v0.4.0a1` and its GitHub prerelease were published from that commit. Trusted
publishing workflow run `33975827124` built, checked, and published both distributions
successfully. A fresh no-cache installation of `perfattr==0.4.0a1` from the public PyPI
index then passed the same version, public-enum, result-method, interaction-schema, and
hand-calculated interaction-total checks.

**Gate:** Passed. The prerelease is published and independently usable from the public
index.

## Required verification matrix

At minimum, tests must cover:

- unchanged default two-effect schemas and values;
- public enum behavior and invalid method rejection;
- independent positive, negative, and zero interaction values;
- three-effect selection plus interaction equaling released two-effect selection;
- allocation plus selection plus interaction equaling total effect per row and period;
- linked three-effect components equaling linked total effect over the horizon;
- authoritative contribution with nonzero weight;
- zero-weight nonzero-contribution rows with null return and zero interaction;
- zero-weight zero-contribution rows;
- identifiers present on only one side;
- signed weights and returns near `-1`;
- one and multiple reporting periods;
- deterministic row and column ordering;
- caller-input nonmutation and independent result ownership;
- direct elapsed-time and peak-memory observations; and
- unchanged `ppar` product and 500x integration gates.

## References and provenance

The governing primary reference is:

- Brinson, Gary P., and Nimrod Fachler. “Measuring Non-U.S. Equity Portfolio
  Performance.” *The Journal of Portfolio Management* 11, no. 3 (1985): 73–76.
  [doi:10.3905/jpm.1985.409005](https://doi.org/10.3905/jpm.1985.409005).

Crossref metadata was verified on September 5, 2026. The formulas must be documented
against the primary publication, not inferred from another software package.

The requested comparative review of
[`pybrinson`](https://github.com/gghez/pybrinson/) used repository commit
`529b0940937caacec3f2a30609b9ce6b86316a7b`. Its explicit method labeling,
three-effect identity, two-effect collapse, and independent per-effect linking informed
the review. No source code, fixtures, expected values, or documentation text will be
copied. The project is MIT-licensed, but `perfattr` will use self-authored code and
independently hand-calculated fixtures under its existing MIT license.

## Completion criteria

Roadmap 5 is complete only when:

- the roadmap and specification are approved;
- every implementation step and required test is complete;
- the two-effect default remains compatible;
- the three-effect method is explicit, reconciled, documented, and independently
  verified;
- `ppar` compatibility and scale gates pass without an unapproved host change; and
- the approved prerelease is published and verified from the public PyPI index.

All completion criteria were satisfied on September 5, 2026.
