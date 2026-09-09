# Project-Wide KISS Cleanup Review

**Status:** Complete September 9, 2026.

**Reviewed revision:** `485880d` (`main` and `origin/main` before this report was
added).

## Conclusion

The project is already disciplined. No confirmed dead production function, abandoned
stub, skipped test, xfail, live fallback engine, or compatibility shim was found. The
public calculation families are implemented, tested, and explicit about what they do
not support. The two runtime dependencies are appropriate, and there is no evidence
for adding another dependency or a general plugin or strategy framework.

The best cleanup is contained rather than sweeping:

1. Correct stale completion-era prose in current-facing source and documentation.
2. Exercise the declared minimum NumPy and pandas versions in CI and close the small
   gap between the written release gate and the publish workflow.
3. Put repeated weight/return/contribution rules behind one small internal invariant
   helper so preparation and calculation cannot drift.
4. Move the prepared-input boundary shared by arithmetic and geometric attribution
   out of `attribution.py` when that area is next changed.

Only the first item is an immediate no-risk edit. Items 2–4 should be implemented as
separate, reviewable changes with all existing gates unchanged. A broad rewrite,
generic attribution engine, compatibility purge, or mass module split would create
more complexity than it removes.

## Implementation disposition

The approved cleanup sequence was completed September 9, 2026:

| Finding | Disposition |
| --- | --- |
| CLN-001 | Completed in Phase 1 |
| CLN-002 | Completed in Phase 2 |
| CLN-003 | Completed in Phase 3 |
| CLN-004 | Completed in Phase 4 |
| CLN-005 | Its recommended attribution and test seams were completed in Phase 4 |
| CLN-007 | Completed conservatively across Phases 1 and 5 |
| CLN-008 | Completed in Phase 1 |

CLN-006 remains optional and deliberately unimplemented because renaming technically
importable predicates requires a separate compatibility decision. Currency, hierarchy,
and preparation files were not split merely for line count; CLN-005 recommends waiting
for a cohesive seam exposed by future work.

## Review scope and method

The review covered all tracked source, tests, fixtures, scripts, workflows, package
metadata, current documentation, specifications, and roadmaps. It used:

- an inventory of the 141 tracked files and every package-level definition;
- AST and repository-reference scans for unreferenced definitions;
- searches for deprecations, aliases, legacy branches, `NotImplementedError`, skips,
  xfails, suppressions, and transitional language;
- import-layer and public-export inspection;
- exact-hash comparison of test fixtures;
- local-link validation across README, specifications, and roadmaps;
- focused inspection of repeated validation, normalization, reconciliation, and
  aggregation paths; and
- the complete functional and static-analysis gates.

The tracked project contains approximately:

| Area | Lines |
|---|---:|
| `src/perfattr` | 9,610 |
| `tests` and fixtures | 13,662 |
| `scripts` | 1,288 |
| `docs` | 6,458 |
| `_extras` before this report | 7,611 |

The test-to-source ratio is reasonable for financial software with several stable
result schemas. The documentation volume is useful audit history, but current guidance
and historical evidence are beginning to blur together.

## Findings and recommendations

### CLN-001: remove stale implementation-state prose

**Priority:** Do first  
**Risk:** Very low; documentation and docstrings only  
**Payoff:** High relative to effort

Several current-facing statements still describe completed features as guarded,
pending, or deferred:

- `src/perfattr/geometric.py` lines 1–4 says the released geometric calculation
  remains guarded.
- The same module's `_calculate_geometric_period_frames` docstring, around lines
  315–317, says the public function remains guarded pending cumulative
  reconciliation.
- `src/perfattr/consolidation.py` lines 3–5 still says the public preparation API is
  awaiting a Roadmap 2 step-six decision.
- `docs/hierarchical_result_rollup_specification.md` lines 9–10 says implementation is
  authorized only in roadmap order even though the status immediately above says it
  is implemented and released.
- `docs/specification.md` lines 673–676 still lists currency attribution as deferred,
  despite the released Roadmap 12 calculation and Roadmap 13 roll-up. Its opening
  supplement list stops at geometric attribution and should point to the two currency
  specifications.
- `_extras/perfattr_roadmap_3.md` lines 43–45 says compact BHB is the next candidate
  after Roadmap 6 even though Roadmaps 7–13 are complete.
- The README's benchmark command list omits the existing
  `scripts/benchmark_geometric.py` command.

Replace these with timeless descriptions of current behavior. Also change phrases
such as “the first public entry point” and “the first release emits” in the normative
arithmetic specification when nearby prose is edited; “the public entry point” and
“the calculation emits” convey the same contract without preserving obsolete phase
language.

This is the clearest KISS win: it deletes misleading state without changing a single
contract or calculation.

### CLN-002: test the dependency floor and enforce the publication boundary

**Priority:** Do soon  
**Risk:** Low  
**Payoff:** High assurance for little workflow code

`pyproject.toml` declares `numpy>=1.26` and `pandas>=2.2`, but the CI matrix installs
unconstrained current versions. The reviewed environment used NumPy 2.4.6 and pandas
3.0.5. Python 3.11 through 3.14 are exercised, but the claimed dependency floor is
not.

Add one Python 3.11 minimum-dependency job that installs the oldest supported NumPy
1.26 and pandas 2.2 lines and runs the functional suite. Do not multiply this into a
large cross-product matrix; one lower-bound lane is the 80/20 check.

The publish workflow verifies tag/version agreement, builds both distributions, and
runs Twine, but it does not itself run functional tests or install and import the
built wheel. The ordinary CI package job does both, yet a published GitHub release can
trigger the PyPI workflow independently of the status of that commit's CI run. The
simplest robust options are either:

- make the publish build reuse the already defined package/test gate; or
- add the functional test and clean-wheel smoke steps directly before artifact upload.

There is no reason to add timing thresholds to hosted CI. Existing performance
observations are deliberately machine-specific, while production reconciliation and
functional invariants already fail loudly.

### CLN-003: share only the repeated performance-row invariants

**Priority:** Do after the documentation cleanup  
**Risk:** Moderate because financial boundary behavior is involved  
**Payoff:** Moderate-to-high maintainability

The same consequential row rules are implemented in both
`attribution._normalize_input` and `preparation._normalize_contributions`:

- a defined return must be greater than `-1`;
- a nonzero weight requires a return;
- supplied contribution is authoritative;
- zero weight plus nonzero contribution requires a null return;
- absent contribution is weight times return; and
- effective return is contribution divided by weight, with the documented zero-weight
  branches.

The final preparation-to-calculation compoundability check in
`prepare._validate_calculation_domain` then restates another subset of the downstream
calculation domain. The recent correctness review demonstrated that these two public
boundaries can drift even when each path is individually well tested.

Extract only these proven shared invariants into one small private helper, parameterized
by context and domain error type. It can return the contribution provenance,
normalized contributions, and effective returns needed by its callers. Keep source
schema selection, day-count derivation, period alignment, mapping, and calculation
normalization in their existing layers.

Do not build a generic validation framework. Two callers with the same financial rule
justify a helper; superficially similar period validators with different contracts do
not.

### CLN-004: give arithmetic and geometric attribution a neutral input seam

**Priority:** Do when either calculation is next modified  
**Risk:** Low-to-moderate if behavior-preserving  
**Payoff:** Moderate structural simplification

`geometric.py` currently imports `_normalize_input`, `_validate_matched_periods`, and
`_equalize_universe` from the public sibling module `attribution.py`. These functions
are genuinely shared prepared-input infrastructure, not Brinson arithmetic formulas.
They and their direct helpers occupy roughly the first 260 lines of an
`attribution.py` file that is now 974 lines long.

Move that cohesive boundary to a private module such as `_prepared_input.py`, leaving
both arithmetic and geometric calculations as consumers. Keep the functions private,
preserve their exact errors and ordering, and verify exact public-frame parity under
both calculation families.

This is a better seam than splitting files merely to satisfy a line count: it removes
a sibling's dependency on another feature module's internals and makes the shared
contract visible. It does not justify merging arithmetic and geometric mathematics or
creating a common calculation class.

### CLN-005: files at the line ceiling need selective, not automatic, splitting

**Priority:** Opportunistic  
**Risk:** Low for test-only moves; moderate for production moves

Current physical line counts include:

| File | Lines |
|---|---:|
| `src/perfattr/currency.py` | 1,000 |
| `tests/test_attribution.py` | 1,000 |
| `src/perfattr/hierarchy.py` | 981 |
| `src/perfattr/attribution.py` | 974 |
| `src/perfattr/preparation.py` | 932 |

These are not evidence of incorrect design by themselves, and the configured Pylint
limit must not be raised merely to accommodate growth. Use only clear seams:

- CLN-004 naturally reduces `attribution.py`.
- Move the input-validation/error cases at the end of `test_attribution.py` into a
  focused `test_attribution_validation.py`; do not delete or combine assertions.
- If currency attribution changes again, its input normalization and cross-frame
  validation form a plausible private `_currency_input.py` seam.
- Leave hierarchy and preparation alone until a real change exposes a comparably
  cohesive seam. They already separate source-result validation and composition where
  it matters.

A mass split would increase navigation cost and private interfaces without reducing
conceptual complexity.

### CLN-006: resolve one small public/private naming ambiguity

**Priority:** Low  
**Risk:** Low internally, but potentially compatibility-sensitive

`method.py` defines `uses_explicit_interaction` and `uses_bhb_allocation` without
leading underscores, while omitting them from `__all__`. They are implementation
predicates used by package modules and tests, not documented root APIs. This conflicts
with the project's convention that internal module-level names use an underscore.

If they are intentionally internal, rename them to `_uses_explicit_interaction` and
`_uses_bhb_allocation` in one mechanical change. Do not add deprecated aliases solely
to preserve undocumented names; that would turn a tiny cleanup into permanent
surface area. Because direct imports are technically possible, obtain explicit
compatibility approval before the rename. If external use is discovered, the other
coherent choice is to document and export them—not to leave the status ambiguous.

### CLN-007: make current documentation shorter than its audit history

**Priority:** Low-to-moderate  
**Risk:** Documentation only  
**Payoff:** Better navigation and less future drift

The 535-line README, 559-line performance document, and 404-line Roadmap 3 mix current
usage, current policy, historical release evidence, and completed candidate history.
The detailed records are valuable and should not be deleted, but they make it harder
to answer simple questions such as “what is supported now?” and “what remains?”

Apply a conservative separation:

- Keep the README's distinguishing-feature list, minimal domestic example, minimal
  currency example, development commands, and links. Move or remove repeated method
  exposition already governed by specifications.
- Put a compact “remaining candidates” table near the top of Roadmap 3 and keep its
  detailed decision records below it. Do not rewrite completed roadmap files.
- Keep benchmark methodology and the latest comparable observations in
  `docs/performance.md`; move the append-only historical `ppar` release chronology to
  `_extras` if it no longer helps a current developer run or interpret a benchmark.

Avoid creating a documentation generator or metadata registry. A short hand-maintained
index is sufficient.

### CLN-008: finish the highest-value mathematical docstrings

**Priority:** Low; combine with CLN-003 or CLN-004  
**Risk:** None to runtime behavior

All test functions and all module-level source definitions have docstrings, and the
financial tests are unusually well explained. The small remaining inconsistency with
`AGENTS.md` is that `_compound_returns`, `_smoothing`, and `_carino` in `_linking.py`
have only one-line docstrings despite implementing nontrivial financial formulas and
limits.

Add concise `Args`, `Returns`, `Notes`, and the governing reference where applicable.
Do not repeat entire specifications in source. A formula, its zero/equal-return limit,
and a specification or primary-reference pointer are enough.

## Dead code and compatibility assessment

### No confirmed dead production code

Every module-level source definition either participates in a production call path or
is a deliberate public boundary. A scan based only on call counts initially makes
many one-caller helpers look suspicious, but inspection shows that they form explicit
normalization, calculation, aggregation, and reconciliation stages.

In particular, retain:

- the scalar effective-dated mapping resolver: the optimized valid path uses
  `merge_asof`, while the scalar path preserves exact gap-versus-boundary diagnostics
  for the first invalid row;
- downstream source-result validation for hierarchy and currency roll-up: public
  result dataclasses contain mutable DataFrames, so callers can alter them after a
  valid calculation;
- production reconciliation builders: they are positive audit evidence and enforce
  financial identities before results are returned; and
- the classification reader and normalizer: names do not enter numerical calculation,
  but the source-neutral metadata boundary is intentionally consumed by host
  presentation adapters.

Two reconciliation fixture files for Frongello and Menchero are byte-identical. Keep
them. Each completes a policy-specific five-frame expected-result set, and the tiny
duplication makes fixture provenance and complete-result review clearer than an alias,
symlink, or conditional fixture loader would.

### No active compatibility layer to purge

No deprecated alias, warning-based migration path, fallback implementation, legacy
keyword parser, or duplicate `ppar` engine exists in this repository. The following
may look historical but are released contracts rather than obviously unnecessary
compatibility:

- `Frequency.AS_OFTEN_AS_POSSIBLE.value == "Periodic"`;
- stable result columns and enum string values;
- root exports and direct construction of ordinary result dataclasses; and
- compatibility tolerances explicitly selected by a host.

Changing any of those requires an intentional API decision. Removing them under the
label of cleanup would be riskier than leaving them alone.

## Supported and deliberately unsupported scope

There are no implementation placeholders for advertised features. Current deliberate
exclusions are consistently enforced rather than half implemented:

- vendor schemas, URLs, account discovery, portfolio accounting, holiday-file loading,
  exposure inference, hedge pricing, presentation, and reports remain host concerns;
- GRAP is not a separate selector because its full-horizon allocation duplicates the
  released Frongello result at this boundary;
- external-flow reconciliation is not pursued without a complete upstream accounting
  contract;
- independently recalculated hierarchical attribution remains distinct from released
  additive result roll-up;
- geometric identifier-level horizon attribution remains unimplemented because it
  requires another allocation policy; and
- modeled-to-accounting currency reconciliation, separate currency interaction
  columns, and hierarchical currency attribution remain deferred.

The only support claim lacking direct automated evidence is the minimum NumPy/pandas
dependency floor described in CLN-002. The stale currency entry in
`docs/specification.md` is a documentation defect, not a missing calculation.

## Local generated artifacts

The ignored local `dist/` directory contains only `perfattr-0.5.0a1` artifacts while
the source version is `0.12.0a1`. Ignored bytecode caches also contain files from
several Python versions. Neither affects Git, CI, or the built wheel, and neither was
removed during this read-only review.

Before a future manual local release, empty or replace the stale `dist/` contents so a
broad command such as `twine upload dist/*` cannot select old artifacts. This is local
hygiene, not a repository-source change.

## Verification evidence

The complete current gate passed:

```text
pytest:  647 passed in 12.57s
pyright: 0 errors, 0 warnings, 0 informations
pylint:  10.00/10
```

Additional checks found:

- zero skipped or expected-failure tests;
- zero live `NotImplementedError` branches;
- zero missing local Markdown link targets across the README, specifications, and
  roadmaps;
- no `ppar`, Polars, or unapproved third-party import in `src/perfattr`; and
- no tracked generated distribution or bytecode artifact.

Only this report and its directory index were added. Production source, tests,
fixtures, workflows, package metadata, specifications, schemas, thresholds, and
released behavior were not changed.

## Suggested sequence

If the findings are approved, keep the cleanup in small commits:

1. Fix CLN-001 and the README benchmark omission.
2. Add the single minimum-dependency lane and harden the publish gate in CLN-002.
3. Implement CLN-003 with focused differential tests and the complete release gate.
4. Combine CLN-004, the attribution-test split, and the linking docstrings only when
   calculation input code is next touched.
5. Treat CLN-006 and CLN-007 as optional polish, not blockers.

Do not combine these with a financial feature release. Keeping documentation, CI,
shared-invariant, and module-boundary changes separate makes regressions easier to
attribute and review.
