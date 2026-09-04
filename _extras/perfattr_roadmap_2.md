# perfattr Roadmap 2: Portable Preparation Layer

**Status:** Complete and historical as of September 4, 2026.

Roadmap 1 records the completed calculation-core work. This roadmap records the
completed portable-preparation phase. Roadmap 3 remains a noncommitted backlog and
does not authorize further implementation.

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
- The migration ledger below records the completed `ppar` transfer and retirement
  work.
- All nine roadmap steps are complete. Source-period normalization, financial
  validation, exact in-memory portfolio selection, portable calendar rules, and
  portfolio/benchmark period alignment now live in `perfattr`. Static classification
  mapping, source-period roll-up, and reporting-frequency consolidation are also
  implemented behind one public composition API, together with canonical performance,
  mapping, and classification CSV loading. `ppar` now delegates through one adapter,
  and its superseded portable implementations have been retired. `perfattr==0.2.2`
  and `ppar==0.3.1` are published, and the release evidence is recorded under Step 9.

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

**Status:** Complete September 4, 2026.

- Validate canonical source-period performance frames without vendor assumptions.
- Select one portfolio identifier without scanning or interpreting vendor files.
- Preserve returns-only input as the ordinary case and authoritative contribution as
  the optional accounting-integrated case.
- Add independently constructed fixtures for missing identifiers, signed and zero
  weights, and zero-weight nonzero contribution.

### 3. Add calendar rules and period alignment

**Status:** Complete September 4, 2026.

- Implement frequency buckets using explicit caller-supplied holidays.
- Support exact common source periods and documented fixed-frequency alignment.
- Detect gaps, overlaps, unmatched coverage, and incomplete terminal buckets.
- Cover weekends, supplied holidays, leap days, month ends, and year ends.

### 4. Add classification mapping

**Status:** Complete September 4, 2026.

- Map portfolio and benchmark independently at source-period granularity.
- Specify behavior for missing mappings and already-classified identifiers.
- Preserve neutral identifiers in the prepared output; presentation names remain host
  metadata.
- Keep the implementation simple while avoiding an assumption that one identifier has
  one permanent classification for all time.

### 5. Add reporting-frequency consolidation

**Status:** Complete September 4, 2026.

- Consolidate only after period alignment and classification mapping.
- Compound returns and calculate observed-day-weighted exposures.
- Link authoritative contributions without reconstructing them as weight times return.
- Preserve undefined effective returns for zero-weight, nonzero-contribution groups.
- Reconcile source-period and consolidated totals with independently calculated
  expected values.

### 6. Add one composition API

**Status:** Complete September 4, 2026.

- Return a small preparation result containing the two frames accepted by
  `calculate_attribution` and useful reconciliation evidence.
- Keep the lower-level preparation functions available only where they provide a
  clear, testable responsibility.
- Consider a convenience prepare-and-calculate function only after the preparation
  result contract is stable.

### 7. Add canonical CSV loading

**Status:** Complete September 4, 2026.

- Add thin performance, mapping, and classification CSV readers for the documented
  canonical schemas.
- Keep column translation, file discovery, URL access, vendor conventions, and holiday
  file loading in host adapters.
- Do not add another runtime dependency.

### 8. Integrate through `ppar`

**Status:** Complete September 4, 2026.

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

**Status:** Complete September 4, 2026.

- Update user documentation with a minimal weights-and-returns example starting from
  source periods.
- Build and validate the source distribution and wheel, install them in a clean
  environment, and run public-import smoke tests.
- Publish only after all standalone and `ppar` integration gates pass.
- Record release commits, tags, versions, and measured performance before marking this
  roadmap complete.

The portable preparation release is `perfattr==0.2.2`, tag `v0.2.2`, at commit
`1fb21d4`. GitHub CI run `33895731983` passed the Python 3.11 through 3.14 matrix and
distribution checks; trusted-publisher run `33895888126` published the release. A
clean, no-cache installation from the public PyPI index confirmed the version and
public preparation API.

The integrated host release is `ppar==0.3.1`, tag `v0.3.1`, at commit `9a5887f`.
Compatibility run `33896623834` passed Python 3.11.9, 3.12.1, 3.13, and 3.14. Release
run `33897191588` passed the complete product and 500x gates before publishing its
validated universal wheel. On that Linux runner, the 500x large-source observation
was 2.46 to 3.11 seconds with byte-identical artifacts, and the 5x long-history gate
was 2.46 to 3.98 seconds, or 1.619x, below the unchanged 1.65x failure boundary. A
clean public-index installation confirmed `ppar==0.3.1`, `perfattr==0.2.2`, CLI
version reporting, and a consistent dependency set.

## `ppar` migration ledger

The status values are **pending**, **implemented**, **delegated**, and **retired**. An
item is not complete until it reaches **retired**: `perfattr` is tested, `ppar`
delegates to it, and the superseded `ppar` implementation and implementation-only
tests are deleted. Every Step 8 migration item below has reached that state.

### Normalized performance validation — retired

`perfattr` replacement:

- source-period normalization and validation;
- contribution derivation and authoritative-contribution preservation; and
- source-period weight and contribution-total validation.

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

`ppar` now delegates canonical loading, date-window filtering, normalization, and
financial validation through its sole adapter. `Performance` remains only as a
Polars-facing host container with translated-output checks.

### Portfolio-code selection — retired (no duplicate implementation)

`perfattr` replacement:

- exact selection from a normalized in-memory multi-portfolio frame.

There is no general in-memory selector to retire from the current `ppar` calculation
path. Axys/APX code discovery, partitioning, composite expansion, and lazy predicate
pushdown remain in `ppar` because they are source-specific and avoid materializing
unselected vendor rows.

### Calendar arithmetic and period alignment — retired

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

`ppar.frequency.Frequency` is now an algorithm-free re-export. Holiday-file loading
and risk-period counts remain host responsibilities; all portable calendar and
alignment helpers were deleted.

### Static mapping validation — retired

`perfattr` replacement:

- normalized pair validation, deterministic deduplication, and conflict detection; and
- identity fallback for an unmapped source identifier.

Superseded `ppar` implementation to retire or reduce to delegation:

- `src/ppar/mapping.py`: the `Mapping` algorithm and generic validation; and
- `src/ppar/utilities.py`: `_deduplicate_identifier_pairs` for normalized portable
  pairs.

Axys/APX callers of `_deduplicate_identifier_pairs` must either delegate after
translation or use validation narrowly tied to the vendor source. A shared generic
Polars copy must not remain.

Permitted `ppar` remainder:

- Axys/APX classification extraction and security-identity construction; and
- source-specific validation before normalization.

The unsupported direct `ppar.mapping` module and shared generic Polars pair validator
were deleted. Host mapping sources and Axys/APX extracted pairs now cross the same
portable normalization boundary.

### Canonical CSV loading — retired

`perfattr` replacement:

- canonical performance, mapping, and classification CSV loading; and
- normalized classification-name metadata validation.

Superseded `ppar` implementation to retire or reduce to delegation:

- `src/ppar/mapping.py`: generic file loading;
- `src/ppar/classification.py`: generic classification-file loading; and
- `src/ppar/utilities.py`: `load_datasource` once no generic caller remains.

Permitted `ppar` remainder:

- classification display metadata and host-facing compatibility containers; and
- source-specific file translation before canonical loading.

The three portable readers and classification metadata validation are used through
the adapter. The superseded generic `ppar.utilities.load_datasource` implementation
was deleted.

### Classification roll-up — retired

`perfattr` replacement:

- independent portfolio and benchmark mapping at source-period granularity;
- aggregation of mapped weights and authoritative contributions; and
- defined, zero, or null mapped effective returns.

Superseded `ppar` implementation to retire:

- `src/ppar/core.py`: `Analytics._map_performance`.

Permitted `ppar` remainder:

- mapping-source selection and translation in the host adapter; and
- joining classification display names for presentation.

`Analytics` delegates both portfolio and benchmark mapping through `perfattr`;
`Analytics._map_performance` was deleted.

### Reporting-frequency consolidation — retired

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

The portable consolidation implementation is the only remaining implementation.
`ppar`'s consolidation methods, state flag, and local logarithmic-linking helpers were
deleted.

### Composition and final retirement — retired

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

`PreparationResult` and `prepare_attribution` compose the portable stages and return
stable prepared and reconciliation frames. `ppar` delegates through
`src/ppar/_perfattr_adapter.py`; no source-neutral fallback remains.

Step 8 is recorded by `perfattr` commit `2c260cf` and `ppar` commit `4456b89`. Step 9
published the required preparation release, raised `ppar`'s dependency floor to
`perfattr>=0.2.2,<0.3`, and published the integrated host release.

Final repository review confirmed that every retired symbol is absent or replaced by
an algorithm-free compatibility facade. The commits above record the `perfattr`
support and `ppar` retirement work.

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
