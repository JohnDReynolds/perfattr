# perfattr Roadmap 4: Effective-Dated Classification

**Status:** Accepted September 4, 2026. Steps 1–7 are complete; the Step 8
`0.3.0a1` release candidate has passed its prepublication gates.

This is the governing implementation roadmap for the first unresolved feature promoted
from roadmap 3. The user approved this roadmap and
`docs/effective_dated_classification_specification.md` on September 4, 2026.

## Objective

Allow a source identifier to resolve to different classifications during different
inclusive source periods while preserving the released static mapping behavior,
mapping and consolidation mathematics, public preparation signature, and result
schemas.

## Governing contract

The normative contract is `docs/effective_dated_classification_specification.md`. It
supplements `docs/preparation_specification.md`. In a conflict about this feature, the
effective-dated specification governs; all unchanged preparation and calculation
contracts remain in force.

The first implementation is deliberately narrow:

- retain the exact two-column static mapping;
- add one exact four-column effective-dated mapping form;
- use required inclusive dates rather than open-ended intervals;
- require each mapped source period to be fully contained in exactly one assignment;
- retain identity fallback only when an identifier is wholly absent from the mapping;
- map each side before reporting-frequency consolidation; and
- add no output columns, policy framework, hierarchy, dependency, or vendor behavior.

## Architecture and ownership

`perfattr` owns source-neutral mapping validation, temporal assignment, source-period
roll-up, and financial conservation checks.

Host adapters such as `ppar` continue to own vendor classification extraction,
security-identity construction, mapping-snapshot selection, product configuration,
and any accounting decision needed when a classification boundary cuts through an
available performance period.

There must be only one effective-dated assignment algorithm. If `ppar` later exposes
this feature, it must translate host data and delegate to `perfattr`; it must not add a
second resolver or retain a fallback implementation.

## Implementation sequence

### 1. Approve the contract — complete

- The user approved the specification and roadmap decisions on September 4, 2026.
- The approved decisions cover schema, inclusivity, gaps, fallback, boundary cuts,
  compatibility, and implementation gates.
- Both documents, the accepted preparation specification, README, and `AGENTS.md`
  record the governing status.
- No production or fixture code began before approval.

**Gate:** Passed by explicit user approval on September 4, 2026.

### 2. Extend mapping normalization — complete

- Preserved the static normalization path and its existing behavior.
- Added recognition of only the exact static or effective-dated schema.
- Normalized dates and identities without mutating caller data.
- Collapsed exact normalized duplicates and rejected reversed, overlapping, and nested
  intervals.
- Returned stable canonical dtypes, columns, and deterministic row order.
- Used a temporary explicit preparation error so dated rows could not reach the static
  lookup before Step 3 replaced it with source-period assignment.

**Gate:** Passed September 4, 2026. All 39 focused mapping tests and all 229 repository
tests pass. Pyright reports zero errors and warnings, and Pylint reports 10.00/10 with
no messages. No check was suppressed or relaxed.

### 3. Resolve source-period assignments — complete

- Added one package-internal resolver at the existing mapping boundary.
- Applied identity fallback only to identifiers absent from the effective mapping.
- Required complete containment for every retained period of an identifier present in
  the mapping.
- Added distinct deterministic errors for gaps, multiple matches, and a classification
  boundary inside a source period.
- Preserved the existing mapped weight, contribution, and effective-return rules.
- Kept temporal assignment separate from financial roll-up; no source row is split or
  prorated.

**Gate:** Passed September 4, 2026. All 49 focused mapping tests and all 239 repository
tests pass. Independent cases cover exact and wider containment, adjacency, overlap,
gaps, boundary cuts, defensive multiple matches, identity fallback, collisions, and
zero-weight authoritative-contribution semantics. Pyright reports zero errors and
warnings, and Pylint reports 10.00/10 with no messages.

### 4. Compose mapping before consolidation — complete

- Routed both mapping forms through the existing `portfolio_mapping` and
  `benchmark_mapping` arguments.
- Kept portfolio and benchmark classification histories independent.
- Demonstrated different classification-change dates inside one quarterly reporting
  bucket.
- Used the existing source-period mapping conservation and reporting-period
  reconciliation evidence without changing its schema.
- Passed the resulting prepared frames directly into the calculation core without
  translation or schema changes.

**Gate:** Passed September 4, 2026. The in-memory fixture independently documents all
monthly contributions, classification assignments, 91-day weighted class weights,
logarithmic linking coefficients, linked contributions, final effective returns, and
conservation identities. All 24 focused preparation tests and all 240 repository tests
pass at the established `1e-12` tolerance. Pyright reports zero errors and warnings,
and Pylint reports 10.00/10 with no messages.

### 5. Extend canonical mapping CSV input — complete

- Preserved existing headerless two-column mapping files, including the empty-file
  static-mapping behavior.
- Added one uniformly four-column effective-dated form in the specified order.
- Rejected canonical headers, mixed row widths, unsupported widths, and invalid
  mapping values before preparation.
- Preserved string identities, normalized inclusive dates, independently owned
  results, canonical dtypes, and deterministic ordering.
- Updated the public reader docstring and user-facing CSV examples.

**Gate:** Passed September 4, 2026. All 34 focused canonical I/O tests and all 247
repository tests pass. Tests cover both forms, ownership and file closure,
deterministic output, canonical headers, mixed widths, and unsupported widths below,
between, and above the supported forms. Pyright reports zero errors and warnings, and
Pylint reports 10.00/10 with no messages. The source distribution and wheel build,
Twine metadata checks, and a clean Python 3.11 wheel installation and public import
all pass.

### 6. Verify quality and performance — complete

- Ran the complete functional suite in isolated environments under every supported CI
  Python version.
- Kept Pyright, Pylance-relevant typing, and Pylint clean without suppressing a check.
- Added a direct public-boundary preparation benchmark using the four established
  selected-history sizes, independent portfolio and benchmark mappings, quarterly
  consolidation, and a mid-quarter classification change.
- Measured five-sample median elapsed time, source-plus-mapping input memory, and peak
  Python-tracked allocation for both static and effective mappings.
- Preserved the existing core benchmark behavior by sharing only workload definitions
  and generic measurement utilities.
- Documented the environment, method, evidence, and performance interpretation in
  `docs/performance.md`. No new threshold is proposed or established.

**Gate:** Passed September 4, 2026. All 247 tests pass on Python 3.11, 3.12, 3.13, and
3.14. Pyright reports zero errors and warnings, and Pylint reports 10.00/10 with no
messages. On Python 3.11.9 with pandas 3.0.5 and NumPy 2.4.6, the effective-dated
preparation medians range from 0.1227 seconds for 6,063 rows per side to 0.8773 seconds
for 121,260 rows per side. Peak traced allocation at 121,260 rows per side is 30.6 MiB,
versus 30.5 MiB for static mapping. All established correctness and release gates
pass, and the benchmark evidence and environment are documented.

### 7. Decide `ppar` exposure separately — complete

- Confirmed that generic `Analytics.attribution(..., mapping_data_sources=...)` is a
  real existing user workflow accepting CSV paths or Polars frames.
- Kept headerless CSV loading delegated directly to `perfattr` and extended only the
  thin Polars container translation to recognize the same positional two- or
  four-column forms.
- Added no API and no temporal resolver, mapping fallback, or financial algorithm to
  `ppar`.
- Kept Axys/APX classifications static because their configured source is one undated
  security-master snapshot. An authoritative historical source would be required
  before that host workflow could expose effective-dated assignment honestly.
- Documented both the generic capability and the Axys/APX limitation.
- Proved complete output equality between Polars and headerless CSV effective mappings
  and ran the unchanged full `ppar` release-candidate and 500x workflows against the
  adjacent `perfattr` implementation.

**Gate:** Passed September 4, 2026. The focused mapping suite passes 14 tests and 3
subtests. The complete `ppar` suite passes 332 tests and 501 subtests; Mypy and Pyright
are clean, Pylint reports 10.00/10 with no enabled messages, image fingerprints are
current, and wheel and installed-demonstration checks pass. The unchanged 500x gate
passes byte-identical large-site output, 10x selected-workload equivalence, and the 5x
long-history gate at 1.567x, below its 1.58x warning and 1.65x failure boundaries. No
speculative Axys/APX behavior was added.

The `ppar` integration was verified with the locally built `perfattr` wheel because
the feature is not published yet. `ppar`'s released dependency range remains
`perfattr>=0.2.2,<0.3`; it must be raised to the Step 8 minor prerelease before these
host changes are committed for release.

### 8. Release the feature

- Review public documentation, changelog text, fixture provenance, and license notes.
- Build and validate the source distribution and wheel.
- Install the wheel in a clean Python 3.11 environment and run a public-import and
  effective-mapping smoke test.
- Publish under a minor prerelease version because the accepted input capability
  expands while existing schemas remain compatible.

**Prepublication evidence:** Passed September 4, 2026 for `0.3.0a1`. Public
documentation, MIT licensing, and independently constructed fixture provenance were
reviewed. All 247 tests pass; Pyright reports zero errors and warnings; Pylint reports
10.00/10 with no messages; the source distribution and wheel build successfully; and
Twine accepts both artifacts. A clean Python 3.11 environment installed the wheel and
passed a public-import and effective-dated CSV-to-quarterly-preparation smoke test.

**Gate:** Publication was explicitly approved on September 4, 2026. Publish only from
the clean release commit containing this evidence. Record the final tag, GitHub
prerelease, workflow, and PyPI verification after publication.

## Required verification

Every implementation step must preserve:

- existing static mapping results and errors except where newly documented schema
  recognition necessarily changes an unsupported-input error;
- caller-input non-mutation and independently owned outputs;
- deterministic row and column ordering and stable dtypes;
- authoritative-contribution and zero-weight/null-return behavior;
- source-period weight and contribution conservation;
- reporting-period linked-contribution reconciliation;
- stable prepared and reconciliation schemas;
- clean tests, pyright, pylint, build, metadata, and public-import checks; and
- the existing prohibition on relaxing tolerances, warnings, or release gates without
  explicit approval.

Expected results must be independently calculated by hand. Tests containing
nontrivial mapping, linking, or effective-return mathematics must include substantial
docstrings and focused comments explaining the financial meaning, assumptions,
intermediate values, and reconciliations.

## Deferred work

This roadmap does not authorize:

- open-ended or partially null validity ranges;
- endpoint-selection policies for a period crossed by a classification change;
- automatic period splitting or return prorating;
- bitemporal or restatement-version history;
- dated display-name metadata;
- classification hierarchies;
- new attribution methodologies; or
- generalized policy, plugin, or temporal-table frameworks.

These may return to roadmap 3 only after an actual user need and an independently
approved specification justify them.

## Completion criteria

This roadmap is complete when static mappings remain regression-identical; effective
mappings resolve each retained source period deterministically; gaps, overlaps, and
boundary cuts fail explicitly; changes between source periods consolidate and
reconcile correctly; canonical CSV input supports both forms; all quality and release
gates pass; and no duplicate resolver exists in `ppar`.
