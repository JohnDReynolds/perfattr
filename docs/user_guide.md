# perfattr User Guide

`perfattr` is a source-neutral pandas calculation engine. It accepts performance facts
that have already been produced by a portfolio accounting system; it does not derive
weights or returns from holdings, transactions, prices, or external flows.

## Install the current release

Python 3.11 or later is required. The complete current API is the `0.12.0a1`
prerelease:

```bash
python -m pip install --pre --upgrade perfattr
```

Plain `python -m pip install perfattr` currently selects the older stable `0.3.0`
release. This distinction will disappear when the current feature set receives its
next stable release.

## The ordinary workflow

Most domestic attribution follows this sequence:

```text
portfolio and benchmark performance
    -> optional portfolio-code selection
    -> optional independent classification mappings
    -> period alignment and reporting-frequency consolidation
    -> arithmetic or geometric attribution
    -> optional hierarchical result roll-up
```

Currency attribution is a separate calculation family because it requires distinct
market and net-currency-exposure facts.

### 1. Supply source-period performance

Portfolio and benchmark are separate pandas DataFrames or CSV files. Each row describes
one attributable identifier in one inclusive source period.

Required columns:

| Column | Meaning |
| --- | --- |
| `from_date` | Inclusive source-period start |
| `thru_date` | Inclusive source-period end |
| `identifier` | Source-neutral attributable identifier |
| `weight` | Period exposure weight |
| `return` | Decimal compoundable return; nullable only when undefined |

Optional columns:

| Column | Meaning |
| --- | --- |
| `contribution` | Fully populated authoritative additive contribution |
| `portfolio_code` | Stream identity used by `select_portfolio` |
| `name` | Display metadata ignored by numerical preparation |

Weights must sum to one on each side and source period. Returns and contributions are
decimals, so `0.01` means one percent. When contribution is absent, `perfattr` derives
it as weight multiplied by return. When present, contribution is authoritative and
must be populated on every row.

A canonical performance CSV has a header. Load and validate it with:

```python
from perfattr import read_performance_csv

portfolio = read_performance_csv("portfolio.csv")
benchmark = read_performance_csv("benchmark.csv")
```

The reader accepts local UTF-8 CSV files only. Vendor schemas, URLs, databases, and
portfolio accounting belong in a host adapter.

### 2. Select a portfolio code when necessary

If a loaded frame contains multiple `portfolio_code` streams, select each requested
stream before preparation:

```python
from perfattr import select_portfolio

portfolio = select_portfolio(portfolio, "PORTFOLIO_1")
benchmark = select_portfolio(benchmark, "BENCHMARK_1")
```

Selection is exact and case-sensitive after surrounding whitespace is removed.
`read_performance_csv` validates every stream before selection; an invalid unselected
stream is not silently ignored.

### 3. Load optional mappings

Portfolio and benchmark mappings are independent. Static mapping files are headerless:

```text
SECURITY_1,Equity
SECURITY_2,Fixed Income
```

Effective-dated files are also headerless and use inclusive dates:

```text
2024-01-01,2024-06-30,SECURITY_1,Equity
2024-07-01,2024-12-31,SECURITY_1,Fixed Income
```

Load them with `read_mapping_csv`. A source identifier absent from a supplied mapping
falls back to itself. Partial mappings can therefore produce a mixture of original
identifiers and classification buckets. If complete classification is required, check
mapping coverage before calling preparation.

For a static mapping, a simple completeness check is:

```python
unmapped = set(portfolio["identifier"]) - set(portfolio_mapping["identifier"])
if unmapped:
    raise ValueError(f"unmapped portfolio identifiers: {sorted(unmapped)}")
```

Apply the same policy independently to the benchmark. Effective-dated completeness
also requires every source period to be contained in an assignment, so rely on
`prepare_attribution` for its interval validation.

Classification files are separate, headerless
`classification_identifier,classification_name` display metadata. Their names do not
enter preparation or appear in numerical results; a host joins them for presentation.

### 4. Prepare aligned reporting periods

Use explicit enum members for policies; strings such as `"Quarterly"` are rejected:

```python
import datetime as dt

from perfattr import Frequency, prepare_attribution, read_mapping_csv

portfolio_mapping = read_mapping_csv("portfolio_mapping.csv")
benchmark_mapping = read_mapping_csv("benchmark_mapping.csv")

prepared = prepare_attribution(
    portfolio,
    benchmark,
    frequency=Frequency.QUARTERLY,
    holidays={dt.date(2024, 3, 29)},
    from_date="2024-01-01",
    thru_date="2024-12-31",
    portfolio_mapping=portfolio_mapping,
    benchmark_mapping=benchmark_mapping,
)
```

Preparation validates and filters each side, aligns their coverage, maps them
independently, and consolidates source periods. It derives inclusive
`quantity_of_days`; callers using `prepare_attribution` do not supply that column.
Holidays are caller-selected dates, not a built-in market calendar.

Date-window bounds select whole source rows by `thru_date`; they do not clip or prorate
a period.

#### Verify accepted coverage

Fixed-frequency preparation returns only complete common reporting buckets. When both
sides end with the same incomplete final bucket, that bucket is intentionally omitted
without a warning. An incomplete interior bucket emits `PreparationWarning` and stops
that bucket and all later output.

Always inspect the accepted coverage when incomplete current-period data may exist:

```python
accepted_thru_date = prepared.portfolio["thru_date"].max()
print("prepared through", accepted_thru_date.date())
```

Preparation reconciliation retains source checks, but it does not add a dedicated row
announcing an omitted final bucket.

### 5. Calculate attribution

The default is compact two-effect Brinson-Fachler with Carino effect linking:

```python
from perfattr import calculate_attribution

result = calculate_attribution(prepared.portfolio, prepared.benchmark)
```

Select other released policies with enums:

```python
from perfattr import AttributionMethod, EffectLinkingMethod

result = calculate_attribution(
    prepared.portfolio,
    prepared.benchmark,
    method=AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    effect_linking_method=EffectLinkingMethod.FRONGELLO,
)
```

Two-effect methods absorb interaction into portfolio-weighted selection. Three-effect
methods report selection and interaction separately. The
[documentation index](README.md) links each governing formula and linking contract.

## Choose the result that answers the question

`AttributionResult` contains five independently owned DataFrames:

| Frame | Use it for |
| --- | --- |
| `period_detail` | Identifier values and effects within each period |
| `period_summary` | Portfolio, benchmark, and effect totals by period |
| `overall_detail` | Identifier values and linked effects for the full horizon |
| `cumulative` | Chronological period values and cumulative prefixes |
| `reconciliation` | Positive evidence for every checked financial identity |

A concise period report usually needs only:

```python
period_report = result.period_summary[
    [
        "from_date",
        "thru_date",
        "portfolio_return",
        "benchmark_return",
        "active_return",
        "allocation_effect",
        "selection_effect",
        "total_effect",
    ]
]
```

Unlinked effects describe their source periods. Each `linked_*_effect` reallocates its
source-period effect to the complete requested horizon under the selected linker.
Intermediate cumulative linked effects are partial sums of those full-horizon
allocations, not independently recalculated as-of attributions.

`overall_detail` compounds identifier returns and uses day-weighted identifier weights.
The final `cumulative` row contains complete-horizon portfolio, benchmark, active, and
effect totals.

All returned financial values are decimals. `perfattr` does not add percent formatting,
classification names, charts, or presentation total rows. A failed calculation or
reconciliation raises before a result is returned; the reconciliation frame is retained
as audit evidence, not as a list of unresolved failures.

## Other public calculations

- `calculate_geometric_attribution` accepts the same prepared portfolio and benchmark
  inputs and measures portfolio wealth relative to benchmark wealth.
- `roll_up_attribution` sums a completed arithmetic result through a static
  child-to-parent hierarchy without recalculating Brinson effects.
- `calculate_currency_attribution` accepts four exact prepared frames: portfolio and
  benchmark market facts plus portfolio and benchmark net currency exposures.
- `roll_up_currency_attribution` adds a completed currency result through time in log
  units.

The README contains minimal examples for each family, and the
[documentation index](README.md) links their exact schemas and reconciliation rules.

### Reconciliation differs by family

Every calculation raises instead of returning failed evidence, but the released
reconciliation frames are family-specific:

| Family | Evidence form |
| --- | --- |
| Preparation | Long rows keyed by stage, side, and check |
| Arithmetic | Long rows keyed by scope and check |
| Hierarchy | Long rows keyed by scope, identifier, and check |
| Geometric | Long rows reporting `difference` and `passed` |
| Currency | One row per period with three `*_reconciled` flags |
| Currency roll-up | Long rows reporting `difference` and `passed` |

Hosts should consume the frame belonging to the calculation they call rather than
assuming one cross-family schema.

## Errors and ownership

- Wrong Python boundary types raise `TypeError`.
- Invalid preparation data raises `PreparationError`.
- Invalid calculation data or a failed calculation invariant raises
  `AttributionError`.
- `PreparationWarning` reports valid preparation that stops at an incomplete interior
  fixed-frequency bucket.

Public operations do not mutate caller-supplied DataFrames. Returned DataFrames belong
to the caller and remain mutable. Result dataclasses are ordinary containers; directly
constructing one does not validate its frames.
