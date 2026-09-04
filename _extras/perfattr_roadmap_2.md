# perfattr Roadmap 2: Portable Preparation Layer

**Status:** Active and governing as of September 4, 2026.

Roadmap 1 records the completed calculation-core work. This roadmap governs the next
implementation phase. Roadmap 3 is a noncommitted backlog and does not expand this
roadmap's scope.

## Objective

Allow users to start with ordinary source-period weights and returns, or authoritative
contributions when available, without requiring them to align periods, consolidate
frequencies, or resolve classifications before using `perfattr`.

Add a small pandas-based preparation layer that produces the existing prepared input
contract consumed by `calculate_attribution`. Keep the calculation core stable and
keep vendor-specific and accounting behavior in host adapters such as `ppar`.

## Architectural boundary

The package should have three explicit responsibilities:

```text
Canonical files or in-memory source-period frames
                       |
                       v
Optional source-neutral I/O
                       |
                       v
Portable preparation
- normalized validation and portfolio selection
- calendar and period alignment
- classification mapping
- reporting-frequency consolidation
                       |
                       v
Existing prepared attribution frames
                       |
                       v
Existing calculation core
```

The existing `calculate_attribution` entry point and prepared-frame contract remain
valid. Preparation should compose with that API rather than being folded into its
financial calculations.

### Required migration end state

This roadmap moves ownership rather than creating a second permanent implementation.
After each portable responsibility is integrated and its parity gates pass:

- delete the corresponding algorithmic implementation from `ppar`;
- make `ppar` call the `perfattr` implementation through one thin translation boundary;
- remove the temporary `ppar` oracle or fallback for that responsibility; and
- retain no independent Polars version of the same portable algorithm.

An existing `ppar` import path may remain as a compatibility facade or re-export when
removing it would break the supported public API. Such a facade must contain no
financial or preparation algorithm; it may only normalize host arguments, translate
data, delegate to `perfattr`, translate results, or preserve a public symbol.

The migration does not remove vendor and product responsibilities from `ppar`. Those
responsibilities are inputs to or consumers of the portable preparation layer, not
duplicate implementations of it.

### Portable preparation owns

- validation of documented, source-neutral performance and classification schemas;
- selection by portfolio identifier from an already-loaded normalized frame;
- source-period coverage checks and portfolio/benchmark alignment;
- reporting-frequency and calendar arithmetic using caller-supplied holiday dates;
- classification mapping for portfolio and benchmark rows;
- consolidation of source periods to the requested reporting frequency; and
- deterministic prepared pandas frames accepted by the calculation core.

### Host adapters continue to own

- vendor-specific files, schemas, column meanings, and configuration;
- efficient source-level filtering such as Polars predicate pushdown;
- account expansion, composite portfolios, and portfolio accounting;
- security-identity construction and source-specific classification extraction;
- inferred weights, cash-flow treatment, and source-specific reconciliation;
- choosing portfolio and benchmark codes from product metadata;
- downloading data and loading holiday files; and
- reports, charts, HTML, templates, CLI behavior, and presentation rows.

Generic validation may test normalized types, keys, coverage, finiteness, and financial
invariants. It must not reinterpret source accounting, infer missing exposure, or
assume authoritative contribution equals weight multiplied by return.

### `ppar` retirement matrix

- **Canonical CSV loading:** `perfattr` owns performance, mapping, and classification
  loading. `ppar` may retain only an algorithm-free compatibility call into `perfattr`.
- **Normalized validation:** `perfattr` owns source-neutral schema and financial
  validation. `ppar` retains vendor validation before normalization and host-output
  validation.
- **Portfolio selection:** `perfattr` owns selection from a normalized multi-portfolio
  frame. `ppar` retains code discovery, composite expansion, and source-level predicate
  pushdown.
- **Calendar rules:** `perfattr` owns frequency buckets and calendar arithmetic. `ppar`
  retains holiday-file loading and, if compatibility requires it, an algorithm-free
  `Frequency` re-export.
- **Period alignment:** `perfattr` is the sole implementation. `ppar` retains only
  input/result translation and host error presentation.
- **Classification mapping and roll-up:** `perfattr` is the sole implementation. `ppar`
  retains vendor classification extraction and display metadata.
- **Reporting-frequency consolidation:** `perfattr` is the sole implementation. `ppar`
  retains only input/result translation.

The portable implementations above must no longer exist in `ppar` when this roadmap is
complete. Tests of `ppar` behavior may remain, but they must exercise delegation to
`perfattr`, not a locally implemented fallback.

The following cannot be removed from `ppar` under this roadmap because moving them
would put vendor or accounting policy into the portable package:

- Axys/APX and other vendor-specific loaders and column translators;
- lazy source filtering needed to avoid loading unselected portfolios;
- portfolio-code discovery, composite expansion, and product-level portfolio choice;
- security-identity construction and vendor classification extraction;
- inferred weights, cash-flow interpretation, and source-specific reconciliation;
- holiday-file discovery and loading for existing `ppar` workflows;
- Polars/pandas boundary translation; and
- risk, reporting, presentation, and CLI behavior.

## Portability and simplicity rules

- Use pandas, NumPy, and the Python standard library only.
- Do not import `ppar` or Polars into `perfattr`.
- Do not add a plugin framework, abstract adapter hierarchy, or speculative extension
  points.
- Accept in-memory pandas frames first. Add only the three canonical CSV readers
  defined in this roadmap after the in-memory pipeline is stable.
- Accept holiday dates as data. Do not add a market-calendar dependency or embed one
  market's holidays.
- Do not mutate caller-supplied frames.
- Preserve deterministic row and column ordering.
- Keep the existing prepared input and result schemas stable unless the user approves
  an intentional compatibility plan.

## Preparation contracts to specify

Implementation begins with a written portable preparation specification covering:

1. **Source-period performance rows.** Define required dates, portfolio identifier,
   attributable identifier, weight, return, optional authoritative contribution, and
   observed-day fields. Define uniqueness, null, numeric, and interval rules.
2. **Classification rows.** Define a simple identifier-to-classification mapping for
   the first implementation. Apply mappings at source-period granularity so the
   pipeline can later support effective-dated mappings without changing consolidation
   order.
3. **Portfolio selection.** Define selection from normalized in-memory data. Hosts
   remain responsible for discovering codes and optimizing the source scan.
4. **Alignment.** Define exact common-period behavior for the most-frequent mode and
   gapless common coverage for fixed reporting frequencies. Specify incomplete leading
   and trailing bucket behavior rather than silently discarding data.
5. **Calendar policy.** Define frequency buckets, expected endpoints, and the meaning
   of supplied holidays without assuming a particular exchange calendar.
6. **Consolidation.** Define geometric returns, observed-day-weighted exposures, linked
   authoritative contributions, undefined effective returns, and conservation checks.
7. **Prepared output.** Produce one portfolio frame and one benchmark frame conforming
   exactly to the existing calculation-core input contract.
8. **Errors and warnings.** Distinguish invalid data from valid but incomplete coverage
   and make every truncation or exclusion explicit.

The first classification implementation may be static, but classification assignments
must be resolved before consolidation. Weight and contribution aggregation must remain
equivalent to static mapping after consolidation, including its effective-return
semantics. This order also permits a future classification change inside a reporting
bucket to be handled correctly.

## Current status

- The roadmap structure was committed in `02dbc22`.
- `docs/preparation_specification.md` was accepted on September 4, 2026 and is the
  normative preparation contract.
- The migration ledger below inventories the current `ppar` transfer and retirement
  targets.
- Roadmap step 1 is complete. No preparation implementation has begun; normalized
  validation and selection is the next step.

## Implementation sequence

### 1. Write the portable preparation specification

- Record the schemas, policies, formulas, errors, ordering, and ownership rules above.
- Use `docs/preparation_specification.md` as the normative preparation contract after
  it is reviewed and accepted.
- Decide public names only after representative examples make the boundary concrete.
- Inventory related `ppar` behavior and document license and fixture provenance before
  reusing any material in the MIT-licensed package.
- Create a migration ledger that maps every portable `ppar` implementation to its
  `perfattr` replacement and eventual deletion. Record any compatibility facade and
  demonstrate that it contains no duplicated algorithm.

### 2. Add normalized validation and selection

- Validate canonical source-period performance frames without vendor assumptions.
- Select one portfolio identifier without scanning or interpreting vendor files.
- Preserve returns-only input as the ordinary case and authoritative contribution as
  the optional accounting-integrated case.
- Add independently constructed fixtures for missing identifiers, signed and zero
  weights, and zero-weight nonzero contribution.

### 3. Add calendar rules and period alignment

- Implement frequency buckets using explicit caller-supplied holidays.
- Support exact common source periods and documented fixed-frequency alignment.
- Detect gaps, overlaps, unmatched coverage, and incomplete terminal buckets.
- Cover weekends, supplied holidays, leap days, month ends, and year ends.

### 4. Add classification mapping

- Map portfolio and benchmark independently at source-period granularity.
- Specify behavior for missing mappings and already-classified identifiers.
- Preserve neutral identifiers in the prepared output; presentation names remain host
  metadata.
- Keep the implementation simple while avoiding an assumption that one identifier has
  one permanent classification for all time.

### 5. Add reporting-frequency consolidation

- Consolidate only after period alignment and classification mapping.
- Compound returns and calculate observed-day-weighted exposures.
- Link authoritative contributions without reconstructing them as weight times return.
- Preserve undefined effective returns for zero-weight, nonzero-contribution groups.
- Reconcile source-period and consolidated totals with independently calculated
  expected values.

### 6. Add one composition API

- Return a small preparation result containing the two frames accepted by
  `calculate_attribution` and useful reconciliation evidence.
- Keep the lower-level preparation functions available only where they provide a
  clear, testable responsibility.
- Consider a convenience prepare-and-calculate function only after the preparation
  result contract is stable.

### 7. Add canonical CSV loading

- Add thin performance, mapping, and classification CSV readers for the documented
  canonical schemas.
- Keep column translation, file discovery, URL access, vendor conventions, and holiday
  file loading in host adapters.
- Do not add another runtime dependency.

### 8. Integrate through `ppar`

- Update `ppar`'s engineering instructions to identify `perfattr` as the sole authority
  for portable preparation and prohibit a permanent local fallback.
- Place translation at one boundary: Polars to canonical pandas input and portable
  pandas results back to the existing host representation where needed.
- Preserve `ppar`'s public API, output schemas, warnings, presentation, and supported
  precision.
- Use the existing `ppar` preparation path only as a temporary differential oracle.
- As each parity and performance gate passes, delete its superseded portable logic and
  tests that exercise only the retired implementation.
- Complete the migration ledger and verify by code review that no independent portable
  validation, selection, calendar, alignment, mapping, consolidation, or canonical CSV
  implementation remains in `ppar`.
- Retain Axys/APX and other source-specific behavior in `ppar`.

### 9. Release and close the roadmap

- Update user documentation with a minimal weights-and-returns example starting from
  source periods.
- Build and validate the source distribution and wheel, install them in a clean
  environment, and run public-import smoke tests.
- Publish only after all standalone and `ppar` integration gates pass.
- Record release commits, tags, versions, and measured performance before marking this
  roadmap complete.

## `ppar` migration ledger

The status values are **pending**, **implemented**, **delegated**, and **retired**. An
item is not complete until it reaches **retired**: `perfattr` is tested, `ppar`
delegates to it, and the superseded `ppar` implementation and implementation-only
tests are deleted. All items are currently **pending**.

### Normalized performance loading and validation — pending

`perfattr` replacement:

- canonical performance CSV loading;
- source-period normalization and validation;
- contribution derivation and source-period totals;
- date-window filtering; and
- preparation reconciliation evidence.

Superseded `ppar` implementation to retire or reduce to delegation:

- `src/ppar/performance.py`: `Performance._load_data`;
- `Performance._clean_and_validate_columns`;
- `Performance._cast_and_validate_columns`;
- `Performance._clean_and_validate_dates`;
- `Performance._filter_date_range`;
- `Performance._calculate_rows`; and
- the source-neutral portions of `Performance.audit` and
  `Performance.audit_performances`.

Permitted `ppar` remainder:

- an algorithm-free `Performance` compatibility container if still required by risk,
  reporting, or supported imports;
- Polars/pandas translation; and
- validation of host objects after translation.

### Portfolio-code selection — pending

`perfattr` replacement:

- exact selection from a normalized in-memory multi-portfolio frame.

There is no general in-memory selector to retire from the current `ppar` calculation
path. Axys/APX code discovery, partitioning, composite expansion, and lazy predicate
pushdown remain in `ppar` because they are source-specific and avoid materializing
unselected vendor rows.

### Calendar arithmetic and period alignment — pending

`perfattr` replacement:

- `Frequency`;
- nominal and effective bucket endpoints;
- bucket labels and completeness checks;
- gapless coverage validation;
- native-period intersection; and
- fixed-frequency portfolio/benchmark alignment.

Superseded `ppar` implementation to retire:

- `src/ppar/frequency.py`: `date_matches_frequency`;
- `frequency_bucket`;
- `frequency_bucket_end`;
- `frequency_bucket_effective_end`;
- `frequency_bucket_label`;
- `validate_frequency_coverage`;
- `completed_frequency_bucket_ends`;
- `fixed_frequency_coverage_start`;
- `src/ppar/core.py`: `_period_tuples` and `_formatted_periods`; and
- `Analytics._calculate_subperiod_dates`.

Permitted `ppar` remainder:

- `load_holidays` for the existing path-based host API;
- `periods_per_year` for host risk calculations; and
- an algorithm-free `Frequency` re-export for compatibility.

### Classification and mapping loading — pending

`perfattr` replacement:

- canonical mapping and classification CSV loading;
- normalized pair validation, deterministic deduplication, and conflict detection; and
- identity fallback for an unmapped source identifier.

Superseded `ppar` implementation to retire or reduce to delegation:

- `src/ppar/mapping.py`: the `Mapping` algorithm and generic loading;
- `src/ppar/classification.py`: generic classification-file loading; and
- `src/ppar/utilities.py`: `load_datasource` once no generic caller remains.

`utilities._deduplicate_identifier_pairs` is also superseded for normalized portable
pairs. Its Axys/APX callers must either delegate after translation or use validation
narrowly tied to the vendor source. A shared generic Polars copy must not remain.

Permitted `ppar` remainder:

- classification display metadata and host-facing compatibility containers;
- Axys/APX classification extraction and security-identity construction; and
- source-specific validation before normalization.

### Classification roll-up — pending

`perfattr` replacement:

- independent portfolio and benchmark mapping at source-period granularity;
- aggregation of mapped weights and authoritative contributions; and
- defined, zero, or null mapped effective returns.

Superseded `ppar` implementation to retire:

- `src/ppar/core.py`: `Analytics._map_performance`.

Permitted `ppar` remainder:

- mapping-source selection and translation in the host adapter; and
- joining classification display names for presentation.

### Reporting-frequency consolidation — pending

`perfattr` replacement:

- source-to-reporting-period assignment;
- geometric total and identifier returns;
- observed-day-weighted exposures;
- logarithmically linked authoritative contributions; and
- consolidation reconciliation.

Superseded `ppar` implementation to retire:

- `src/ppar/core.py`: `Analytics._consolidate_all_subperiods`;
- `Analytics._source_periods_match_reporting_periods`;
- `Analytics._consolidate_subperiods`;
- consolidation-only uses of `Performance._replace_calculated_rows`;
- `Performance.subperiods_have_been_consolidated`; and
- `Performance.linking_coefficients` plus any overall helper left unused after the
  transfer.

Permitted `ppar` remainder:

- a host container for prepared Polars rows if risk or presentation still needs it;
  and
- conversion to and from the pandas preparation result.

### Composition and final retirement — pending

`perfattr` replacement:

- one public composition API returning prepared portfolio, benchmark, and
  reconciliation frames.

Superseded `ppar` implementation to retire or reduce to delegation:

- preparation orchestration inside `Analytics.__init__`; and
- unit tests that call only a retired Polars algorithm.

Permitted `ppar` remainder:

- `Analytics` as the host-facing coordinator;
- `_perfattr_adapter.py` or its replacement as one thin translation boundary;
- host error translation needed to preserve supported exceptions; and
- end-to-end tests proving the public `ppar` workflow delegates correctly.

At final review, repository search must confirm that every retired symbol is absent or
is an algorithm-free compatibility facade. The ledger must then record the `perfattr`
and `ppar` commits that supplied and retired each responsibility.

## Verification gates

Every implementation step must keep the existing functional, pylint, Pylance, pyright,
build, and import checks clean. New preparation behavior additionally requires:

- independently hand-calculated fixtures rather than expected values derived from
  `ppar`;
- unit coverage of every specified validation, alignment, mapping, and consolidation
  edge case;
- non-mutation tests for all caller inputs;
- financial conservation and explanation-reconciliation checks in normal execution;
- direct `perfattr` elapsed-time and peak-memory benchmarks on realistic selected
  inputs;
- `1e-12` relative and absolute numerical parity at the `ppar` boundary, with identical
  null placement, ordering, reconciliation outcomes, and presentation-precision output;
  and
- the existing 500x `ppar` integration workflow after adapter or cross-cutting changes.

No established tolerance, threshold, invariant, or release gate may be relaxed merely
to make a new implementation pass.

## Completion criteria

This roadmap is complete when a user can load canonical source-period weights and
returns, select portfolio and benchmark data, supply calendar and classification
inputs, prepare aligned reporting-period frames, and calculate attribution without
`ppar`; when `ppar` uses the same portable preparation behavior without public-output
regression; when the migration ledger confirms that every superseded portable
implementation has been deleted from `ppar`; and when vendor-specific and accounting
behavior remains isolated in its host adapter. Algorithm-free compatibility facades do
not violate this condition.
