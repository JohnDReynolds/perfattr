# perfattr Portable Preparation Specification

## Status

**Status:** Accepted September 4, 2026.

This document is the normative preparation contract for roadmap 2. The words **must**,
**must not**, **should**, and **may** have their ordinary technical meanings.

`docs/specification.md` continues to govern the calculation core. This specification
governs only the upstream preparation that produces the core's existing input frames.
The accepted effective-dated classification extension is governed by
`docs/effective_dated_classification_specification.md` and roadmap 4. Until its
implementation steps are complete, the released preparation API supports only the
static mapping contract documented here.

## Design principles

- Keep one portable preparation path.
- Make weights-and-returns input the ordinary case.
- Preserve authoritative contribution when it is supplied.
- Reject ambiguous data instead of inferring accounting intent.
- Keep vendor and portfolio-accounting policy in host adapters.
- Return pandas data, not presentation.
- Prefer explicit functions and schemas over a framework.

## Scope

The preparation layer accepts source-period portfolio and benchmark performance,
optionally maps each side to a requested classification, aligns their periods, and
consolidates them to a reporting frequency. It returns the two prepared pandas frames
accepted by `calculate_attribution` plus preparation reconciliation evidence.

The preparation layer owns:

- normalized, source-neutral performance validation;
- selection from an already-loaded multi-portfolio frame;
- inclusive date-window filtering;
- calendar buckets and period alignment;
- static classification mapping and roll-up;
- reporting-frequency consolidation;
- canonical local CSV loading; and
- preparation conservation checks.

It does not own vendor schemas, account discovery, composite portfolios, portfolio
accounting, inferred weights, external-flow measurement, security-identity
construction, market-calendar discovery, URLs, databases, Parquet, Excel, reports, or
presentation.

The only direct runtime dependencies remain pandas and NumPy. CSV and calendar support
use pandas and the Python standard library; roadmap 2 adds no dependency.

## Public API

The public preparation entry point is:

```python
def prepare_attribution(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    frequency: Frequency = Frequency.AS_OFTEN_AS_POSSIBLE,
    holidays: Collection[dt.date] = (),
    from_date: str | dt.date | None = None,
    thru_date: str | dt.date | None = None,
    portfolio_mapping: pd.DataFrame | None = None,
    benchmark_mapping: pd.DataFrame | None = None,
    reconciliation_tolerance: float = 1e-12,
) -> PreparationResult:
    ...
```

Supporting public entry points are:

```python
def select_portfolio(
    performance: pd.DataFrame,
    portfolio_code: str,
) -> pd.DataFrame:
    ...

def read_performance_csv(
    path: str | os.PathLike[str],
    *,
    reconciliation_tolerance: float = 1e-12,
) -> pd.DataFrame:
    ...

def read_mapping_csv(path: str | os.PathLike[str]) -> pd.DataFrame:
    ...

def read_classification_csv(path: str | os.PathLike[str]) -> pd.DataFrame:
    ...

def normalize_mapping(mapping: pd.DataFrame) -> pd.DataFrame:
    ...

def normalize_classification(classification: pd.DataFrame) -> pd.DataFrame:
    ...
```

The root package exports these functions along with `Frequency`, `PreparationError`,
`PreparationResult`, and `PreparationWarning`.

`PreparationError` is a `ValueError` subclass used for invalid preparation data or a
failed preparation invariant. Passing a non-DataFrame object where a DataFrame is
required raises `TypeError`. `PreparationWarning` is a `RuntimeWarning` subclass used
only for valid input whose fixed-frequency output must stop before an incomplete
interior bucket.

### Result container

The result is an ordinary dataclass:

```python
@dataclass
class PreparationResult:
    portfolio: pd.DataFrame
    benchmark: pd.DataFrame
    reconciliation: pd.DataFrame
```

`portfolio` and `benchmark` conform exactly to the existing prepared input contract.
The preparation layer owns the returned frames. Mutating them cannot mutate any
caller-supplied frame, although the returned frames themselves are not immutable.

## Source-period performance contract

Each source-period row represents one attributable identifier during one inclusive
period. Both portfolio and benchmark frames require these columns:

| Column | Meaning |
|---|---|
| `from_date` | Inclusive source-period start |
| `thru_date` | Inclusive source-period end |
| `identifier` | Source-neutral attributable identifier |
| `weight` | Period exposure weight |
| `return` | Compoundable identifier return; nullable only when undefined |

These columns are optional:

| Column | Meaning |
|---|---|
| `contribution` | Fully populated authoritative additive contribution |
| `portfolio_code` | Portfolio identifier used by `select_portfolio` |
| `name` | Display metadata ignored by numerical preparation |

The input index has no meaning. Additional columns are ignored. Duplicate column
labels are invalid. Preparation output never propagates `portfolio_code`, `name`, or
another extra source column.

### Normalization

- Dates are normalized to timezone-naive `datetime64[ns]` values at midnight.
- Strings and `datetime.date` values are accepted for dates; timezone-aware values are
  invalid rather than silently converted.
- Surrounding whitespace is removed from identifiers and portfolio codes. Internal
  whitespace and leading zeroes are preserved.
- Identifiers and portfolio codes must be non-null, nonempty strings after trimming.
  Non-string identity values are not coerced.
- DataFrame numeric strings and booleans are rejected as financial numbers.
- CSV readers parse financial fields as numbers and reject unparseable values.
- Financial columns use `float64` after normalization.
- Caller-supplied frames are never mutated.

### Row and period rules

- Neither selected input may be empty.
- A `(from_date, thru_date, identifier)` key must be unique within one portfolio.
- Each `thru_date` identifies exactly one `(from_date, thru_date)` source period.
- `from_date` must not exceed `thru_date`.
- Source periods must not overlap. Gaps are allowed at native frequency but may make a
  fixed-frequency bucket incomplete.
- `quantity_of_days` is derived as `(thru_date - from_date) + 1` for each source period.
- Weight and every non-null return must be finite.
- Every non-null identifier return must be greater than `-1.0` because returns are
  compoundable.
- Weights must sum to `1.0` within the reconciliation tolerance for each side and source
  period. Negative weights and weights greater than `1.0` are allowed.
- A nonzero weight requires a non-null return.

Portfolio and benchmark may independently use returns-only or authoritative-
contribution input.

When `contribution` is absent, preparation derives it as weight multiplied by return.
A zero-weight row with a null return derives zero contribution.

When `contribution` is present, every value must be finite and non-null and is treated
as authoritative. A zero-weight, nonzero-contribution row requires a null return. A
supplied contribution must not be replaced or rejected merely because it differs from
weight multiplied by return.

For either input form, the source-period total return is the sum of contributions. It
must be finite and greater than `-1.0` when logarithmic consolidation is required.

### Cash, fees, and financing

Cash is prepared as an ordinary identifier. Preparation neither detects nor creates
cash, and an optional classification mapping may roll a source identifier such as
`CASH_USD` into a Cash classification using the same rules as any other mapping.
Positive, negative, and zero cash weights receive no special validation or
consolidation behavior beyond the ordinary contracts above. Preparation can preserve
a supplied compoundable return when no roll-up requires deriving a new one; at the
calculation boundary, exact zero cash weight and zero contribution produce the same
defined effective period return of zero as any other zero-exposure row.

A fee or financing charge without attributable exposure requires the authoritative-
contribution form: weight is zero, contribution contains the signed charge, and return
is null because contribution divided by weight is undefined. The row is preserved
through alignment and consolidation. If it remains its own mapped group, its effective
return remains null; if it is mapped into a group with nonzero net exposure, the
group's ordinary effective return is total authoritative contribution divided by total
weight.

Preparation does not recognize special identifier names, calculate charges, choose
gross or net performance, or determine which portfolio or benchmark should contain a
charge. Those are host accounting responsibilities. Financing associated with an
explicit exposure and return may instead use the ordinary weighted-return form.

### Date-window filtering

`from_date` and `thru_date` are optional inclusive bounds on source-period `thru_date`,
matching the established `ppar` contract. They do not clip or prorate a source period.
An invalid bound or `from_date > thru_date` is an error. If filtering leaves either side
without data, preparation fails.

## Portfolio selection contract

`select_portfolio` operates only on an in-memory, source-neutral frame. The frame must
contain `portfolio_code`. The requested code is trimmed, must remain nonempty, and is
matched exactly without case conversion or numeric coercion.

The function returns an independent frame containing only matching rows. No match is an
error. It preserves `portfolio_code` so the selected data retains its lineage until
preparation drops non-core columns.

`prepare_attribution` accepts already-selected inputs. If an input contains
`portfolio_code`, all of its retained rows must contain one identical code; multiple
codes are an error directing the caller to select first.

Hosts remain responsible for discovering portfolio codes, expanding composites, and
filtering vendor sources before converting large data sets to pandas.

## Static classification contracts

Portfolio and benchmark mappings are independent. Each optional mapping DataFrame must
contain exactly these two columns:

```text
identifier
classification_identifier
```

Both fields must be non-null, nonempty strings after trimming. Exact duplicate pairs
collapse to one row. One source identifier mapped to multiple classification
identifiers is invalid. All mapping identities are validated before unused rows are
filtered so an invalid row cannot silently disappear.

A source identifier absent from its mapping maps to itself. Mapping collisions are
intentional: rows whose source identifiers resolve to the same classification
identifier are aggregated.

For each side, source period, and mapped identifier:

```text
mapped_weight       = sum(constituent weights)
mapped_contribution = sum(constituent contributions)

mapped_return = mapped_contribution / mapped_weight
                when mapped_weight != 0
mapped_return = 0
                when mapped_weight == 0 and mapped_contribution == 0
mapped_return = null
                when mapped_weight == 0 and mapped_contribution != 0
```

Exact zero selects these branches. A numerical tolerance does not turn a small weight
into zero. Mapping must preserve each side's source-period weight and contribution
totals.

Classification assignments are resolved before reporting-frequency consolidation.
Weight and contribution aggregation commute with static mapping, so the implementation
must preserve the result of mapping those two values after consolidation. The final
mapped return is derived from consolidated mapped contribution and weight as described
below. This leaves the pipeline order valid for a future effective-dated assignment
without changing the established static result.

### Classification metadata

Classification metadata is not a numerical input. Its canonical frame contains exactly
these columns:

```text
classification_identifier
classification_name
```

Both fields are non-null, nonempty strings after trimming. Exact duplicate pairs
collapse. Conflicting names for one identifier are invalid. The preparation and
calculation results do not propagate display names; a host may join this metadata for
presentation.

Roadmap 2 did not implement effective-dated mappings. The user approved that extension
on September 4, 2026; its additional normative contract is in
`docs/effective_dated_classification_specification.md`, and implementation is governed
by `_extras/perfattr_roadmap_4_effective_dated_classification.md`.

## Frequency and holiday contract

`Frequency` has these members:

```text
AS_OFTEN_AS_POSSIBLE = "Periodic"
MONTHLY = "Monthly"
QUARTERLY = "Quarterly"
YEARLY = "Yearly"
```

`AS_OFTEN_AS_POSSIBLE` preserves validated native periods and requires exact common
period boundaries. Fixed frequencies use calendar month, quarter, or year buckets.

`holidays` is a collection of `datetime.date` values treated as nonbusiness days.
Duplicate dates are harmless. A `datetime.datetime`, string, null, or another type is
invalid. `perfattr` does not discover holidays or interpret a market calendar.

A fixed-frequency bucket's nominal endpoint is calendar month-end, quarter-end, or
year-end. Its effective endpoint rolls backward over Saturdays, Sundays, and supplied
holidays. A source period may close a bucket on either:

- the nominal endpoint, provided that date is not a supplied holiday; or
- the effective endpoint.

This deliberately accepts a literal weekend month-end when the source contains that
date. Without supplied holidays, it is otherwise a last-weekday rule, not an exchange
calendar.

## Period alignment

Date-window filtering and source validation occur before alignment.

### Native frequency

Portfolio and benchmark reporting periods are the sorted intersection of their exact
`(from_date, thru_date)` pairs. Once the first and last common period establish the
comparison window, either side having an unmatched period that intersects that window
is an error. Unmatched periods wholly outside the common window are excluded.

At least one common period is required.

### Fixed frequency

Portfolio and benchmark may use different source partitions, but each accepted bucket
must cover the same complete inclusive date range on both sides.

For each side:

- every calendar bucket between its first and last observed bucket must have coverage;
- source periods assigned to a bucket must be ordered, nonoverlapping, and gapless;
- the last source `thru_date` must be a valid nominal or effective endpoint;
- a source period must not extend outside its assigned reporting range; and
- after one bucket is accepted, the next bucket must begin immediately after the prior
  actual endpoint or within the calendar days between the prior effective and nominal
  endpoints that the source legitimately represents.

The first accepted bucket must likewise start immediately after a valid nominal or
effective endpoint for the preceding bucket. This prevents a partial first reporting
period from being mislabeled as complete.

Both sides must have the same actual start and actual endpoint for every accepted
bucket. Different endpoints, different starts, an internal gap, or a period crossing a
reporting boundary is an error.

An incomplete final bucket present on both sides is omitted because it is not a
completed reporting period. If that bucket is complete on only one side, preparation
fails. An incomplete interior bucket emits `PreparationWarning` and truncates that
bucket and all later output. This preserves the established `ppar` behavior.

At least one complete common reporting bucket is required.

## Reporting-frequency consolidation

Mapping occurs before consolidation. For one side, let source periods `u` belong to
reporting period `t`; let `D[u]` be inclusive source-period days; let `w[g,u]`,
`r[g,u]`, and `c[g,u]` be mapped identifier weight, return, and contribution; and let
`R[u] = sum_g(c[g,u])`.

The reporting-period total return is:

```text
R[t] = product_u(1 + R[u]) - 1
```

Without classification mapping, the reporting-period identifier return compounds the
identifier's present source rows. An absent source-period row contributes a zero
return. Any explicit null return for the identifier makes its consolidated return
null.

```text
r[g,t] = product_u(1 + r[g,u]) - 1
```

The reporting-period identifier weight is observed-day weighted. An absent row has
zero weight:

```text
w[g,t] = sum_u(D[u] * w[g,u]) / sum_u(D[u])
```

Define the stable logarithmic smoothing function already used by the calculation core:

```text
s(x) = log1p(x) / x    when x != 0
s(0) = 1
```

The source-period contribution coefficient is:

```text
L[u,t] = s(R[u]) / s(R[t])
```

The consolidated identifier contribution is:

```text
c[g,t] = sum_u(c[g,u] * L[u,t])
```

This must preserve authoritative contributions and make `sum_g(c[g,t]) == R[t]`
within tolerance. It must not replace consolidated contribution with
`w[g,t] * r[g,t]`.

When a classification mapping is supplied, the reporting-period mapped return is the
effective return of the final mapped group:

```text
mapped_return[g,t] = c[g,t] / w[g,t]
                     when w[g,t] != 0
mapped_return[g,t] = 0
                     when w[g,t] == 0 and c[g,t] == 0
mapped_return[g,t] = null
                     when w[g,t] == 0 and c[g,t] != 0
```

The implementation must not compound intermediate mapped effective returns. Deriving
the final mapped return after weight and contribution consolidation preserves `ppar`'s
static mapping behavior while allowing assignments to be resolved at source-period
granularity.

The reporting period uses the actual common coverage start and endpoint. Its
`quantity_of_days` is their inclusive calendar-day difference. When a source period
already equals its reporting period exactly, preparation preserves its normalized
return, weight, and contribution rather than unnecessarily relinking it.

## Prepared outputs

`PreparationResult.portfolio` and `.benchmark` have exactly these columns:

```text
from_date
thru_date
identifier
weight
return
contribution
quantity_of_days
```

Rows are ordered by `thru_date`, then `identifier`, with a zero-based `RangeIndex`.
Dates, strings, financial numbers, and day counts use the dtypes required by the
calculation specification.

Both prepared frames contain identical ordered period keys and the same
`quantity_of_days` for each period. Their identifier universes need not match; the
calculation core continues to own universe equalization.

The output always includes authoritative `contribution`, including when source input
was returns-only. This gives the calculation core one unambiguous downstream form.

## Preparation reconciliation

`PreparationResult.reconciliation` has this stable column order:

```text
stage
side
from_date
thru_date
check
actual
expected
residual
tolerance
passed
```

`stage` is `source`, `mapped`, or `reporting`; `side` is `portfolio` or `benchmark`.
Rows appear in stage order, side order, chronological period order, and check order.

The checks are:

- `weight_sum` for every source and reporting period;
- `derived_contribution` for returns-only source rows;
- `mapped_weight` and `mapped_contribution` conservation when mapping is applied; and
- `linked_contribution` reconciliation to compounded return when consolidation occurs.

`residual` is `actual - expected`. Comparisons use the requested relative and absolute
`reconciliation_tolerance`. It must be finite and greater than zero. A successful
result contains only passing rows. A failed check raises `PreparationError` before a
result is returned.

Structural checks such as key uniqueness and period alignment raise directly because
they do not have a meaningful scalar residual.

## CSV contracts

All readers accept only a path to an existing local regular file. Blank paths,
directories, URLs, buffers, and file-like objects are invalid. Files are UTF-8 CSV.

### Performance CSV

The performance CSV has a header row using the source-period performance column names.
Required and optional fields, normalization, and validation are identical to in-memory
input. Identity columns are read as strings so leading zeroes are preserved.

### Mapping CSV

The mapping CSV is headerless. Every nonblank row in one file must use exactly one of
the two supported forms. The static form contains these columns:

```text
identifier,classification_identifier
```

The effective-dated form contains these columns and uses closed, inclusive dates:

```text
from_date,thru_date,identifier,classification_identifier
```

Headers, mixed two- and four-column records, and every other record width are invalid.
The normalized result uses the schema selected by the file width.

### Classification CSV

The classification metadata CSV is headerless and contains exactly two columns:

```text
classification_identifier,classification_name
```

Blank rows may be ignored. A nonblank row with the wrong column count is invalid.
Readers return independent normalized pandas frames and do not perform portfolio or
date selection.

These contracts intentionally match the useful generic `ppar` file shapes. Vendor
column translation, header inference, alternative encodings, compressed files, and
other convenience formats remain outside `perfattr`.

## Ownership and deterministic behavior

- No public function mutates a caller-supplied DataFrame or collection.
- Returned frames do not share writable pandas data with inputs.
- Hash iteration, input row order, and input column order must not affect output order.
- File readers close files before returning.
- Errors include the boundary, field or period, and a small deterministic sample of
  affected keys without exposing an entire source file.

## Provenance and licensing

`perfattr` is MIT licensed. `ppar` remains proprietary and is used, with its owner's
authorization, only to inventory the established host behavior and as a temporary
differential oracle during migration.

Do not copy `ppar` source, documentation, or fixtures into `perfattr`. Implement this
written pandas contract directly, construct expected results independently by hand,
and cite primary financial references where a formula requires external authority.
Each migration-ledger entry must record the commits that add the MIT implementation
and remove its proprietary predecessor.

Every implementation of nontrivial mathematics must explain the financial purpose,
formula, assumptions, sign convention, numerical limits, and important edge cases in
its docstring and focused inline comments. Cite the governing primary reference in the
docstring when the formula comes from an external methodology. Comments must explain
why the calculation is correct rather than merely restating its Python operations.

## Verification requirements

Independent fixtures must cover at least:

- returns-only and authoritative-contribution inputs on either side;
- multiple portfolio codes, whitespace, leading zeroes, and no matching code;
- missing identifiers, signed weights, and changing identifier membership;
- zero weight with zero or nonzero contribution;
- exact native alignment and unmatched periods inside the common window;
- different source partitions with identical fixed-frequency coverage;
- gaps, overlaps, crossed bucket boundaries, and unequal endpoints;
- literal and effective month, quarter, and year ends;
- weekends, consecutive supplied holidays, and leap days;
- incomplete final and interior buckets;
- identity mapping, missing mappings, collisions, duplicates, and conflicts;
- a zero-net-weight mapped group with nonzero contribution;
- positive, negative, zero, and near-zero consolidation returns;
- returns approaching but not reaching `-1.0`;
- non-mutation, deterministic row order, and stable dtypes; and
- every preparation reconciliation identity.

Every test case must have a useful docstring stating the financial behavior or
contract it proves. Tests involving nontrivial mathematics must also document the
independent hand calculation, expected identity, and reason the selected values expose
the intended behavior. Supporting comments should make each material intermediate
expected value auditable without consulting the production implementation.

If consolidation would produce a nonzero identifier weight with a null compoundable
return, preparation must fail rather than inventing a return. This can arise when an
identifier combines an undefined zero-weight source row with a defined nonzero-weight
row. Mapped groups avoid that ambiguity by using the documented final effective-return
rule.

`ppar` may be used temporarily for differential testing, but fixtures and expected
values must not be derived from it. Adapter parity remains `1e-12`, together with
identical null placement, ordering, reconciliation outcomes, warnings, and
presentation-precision output.

## Initial examples

The ordinary standalone workflow is deliberately short:

```python
from perfattr import calculate_attribution, prepare_attribution, read_performance_csv

portfolio = read_performance_csv("portfolio.csv")
benchmark = read_performance_csv("benchmark.csv")
prepared = prepare_attribution(portfolio, benchmark)
result = calculate_attribution(prepared.portfolio, prepared.benchmark)
```

A master-file workflow selects before preparation:

```python
from perfattr import prepare_attribution, read_performance_csv, select_portfolio

master = read_performance_csv("performance.csv")
portfolio = select_portfolio(master, "PORTFOLIO")
benchmark = select_portfolio(master, "BENCHMARK")
prepared = prepare_attribution(portfolio, benchmark)
```

Classification mapping remains explicit:

```python
from perfattr import prepare_attribution, read_mapping_csv

mapping = read_mapping_csv("security_to_sector.csv")
prepared = prepare_attribution(
    portfolio,
    benchmark,
    portfolio_mapping=mapping,
    benchmark_mapping=mapping,
)
```

The same workflow accepts an effective-dated mapping file. For example,
`security_to_sector.csv` can contain these headerless records:

```text
2024-01-01,2024-01-31,ASSET,Equity
2024-02-01,2024-12-31,ASSET,Fixed Income
```

Each retained source period for `ASSET` must fit wholly within exactly one assignment.
The mapping is applied before reporting-frequency consolidation; a source period is
never split or prorated across a classification boundary.

No convenience API should combine loading, selection, preparation, calculation, and
presentation until repeated real usage shows that another public entry point is worth
its maintenance cost.
