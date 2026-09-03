# perfattr Roadmap

## First-step implementation plan

### Objective

The first implementation should create a small, independent attribution calculator
using pandas, NumPy, and the Python standard library. It should reproduce `ppar`'s
current attribution calculations and numerical results without importing `ppar` or
Polars. `ppar` should then expose this calculator as a separate, explicitly selected
path alongside its existing Polars calculation path.

The first implementation is a calculation core, not a replacement for all of
`ppar.Analytics`. Source loading, Axys/APX reconciliation, portfolio-code selection,
calendar and holiday rules, classification-file loading, report generation, and
presentation remain outside the reusable core.

### Initial boundary

For the first integration, `ppar` should continue to use its existing Polars code to:

- load generic or Axys/APX inputs;
- perform source-specific validation and reconciliation;
- filter the requested portfolio and benchmark;
- align portfolio and benchmark periods;
- consolidate source periods to the requested reporting frequency; and
- map both sides to the requested classification.

The calculation path should fork after those steps, immediately before the current
`Attribution` class equalizes the portfolio and benchmark universes and calculates
contribution, attribution, linking, cumulative, and overall results.

The Polars and pandas paths should rejoin at a common numerical-result boundary before
sorting, total-row presentation, HTML, PNG, and CSV generation. Both paths will
therefore use the same `ppar` presentation code and produce the same user-facing
reports.

Conceptually:

```text
Generic or Axys/APX inputs
          |
          v
Existing ppar/Polars preparation
- source-specific loading and reconciliation
- date filtering and period alignment
- frequency consolidation
- classification mapping
          |
          v
Canonical prepared attribution frames
          |
          +---- engine="polars" ---- existing Polars calculator ----+
          |                                                         |
          +---- engine="pandas" ---- reusable pandas core ----------+
                                                                    |
                                                                    v
                                                   Common numerical result
                                                                    |
                                                                    v
                                               Existing ppar presentation
                                               Polars / HTML / PNG / CSV
```

A possible `ppar` API is:

```python
polars_result = analytics.attribution(
    "Economic Sector",
    engine="polars",
)

pandas_result = analytics.attribution(
    "Economic Sector",
    engine="pandas",
)
```

The existing Polars engine should remain the default during implementation and
evaluation.

### Prepared input contract

The reusable core should accept two ordinary pandas DataFrames: one portfolio and one
benchmark. Each row represents one attribution unit during one already-aligned
reporting period.

| Field | Meaning |
|---|---|
| `from_date` | Inclusive reporting-period start |
| `thru_date` | Inclusive reporting-period end |
| `identifier` | Security or already-resolved classification identifier |
| `weight` | Period exposure weight |
| `return` | Compoundable holding or group return; nullable when mathematically undefined |
| `contribution` | Optional authoritative additive contribution |
| `quantity_of_days` | Observed period days used when calculating overall weights |

Contribution should be a first-class optional input. When its column is absent, the
core should derive every row as weight multiplied by return; a zero-weight row with a
null return derives zero contribution. When the column is present, every value must be
non-null and finite and must be treated as authoritative. Portfolio and benchmark may
independently use either form. Partial contribution columns are invalid.

The optional authoritative form is required to preserve linked contributions after
frequency consolidation, zero-net-weight groups with nonzero contribution, and future
fee, financing, cash, or derivative treatments.

Where the group weight is nonzero, the effective return used for attribution is
contribution divided by weight. When weight and contribution are both zero, the
effective return is zero. When weight is zero and contribution is nonzero, the return
is mathematically undefined and remains null while the valid contribution is
preserved.

Portfolio and benchmark names, classification display names, currency symbols, and
report labels are metadata rather than numerical input fields. File readers and
vendor-specific column translators belong in host-product adapters.

### Result contract

The core should return a small result object containing ordinary pandas DataFrames:

```python
@dataclass
class AttributionResult:
    period_detail: pd.DataFrame
    period_summary: pd.DataFrame
    overall_detail: pd.DataFrame
    cumulative: pd.DataFrame
    reconciliation: pd.DataFrame
```

The result frames should use stable, neutral `snake_case` column names. A thin `ppar`
adapter should translate these names to `ppar`'s existing output schema. Presentation
total rows should remain a `ppar` responsibility rather than being embedded in the
portable calculation result.

A frozen dataclass should not be described as making pandas DataFrames immutable;
freezing prevents attribute reassignment but does not prevent mutation of the frames.
The simpler initial contract is an ordinary dataclass with documented caller
ownership and no mutation of caller-supplied inputs.

### Responsibilities of the first core

The reusable core should own:

- portfolio and benchmark universe equalization;
- effective group-return calculation;
- simple portfolio, benchmark, and active contribution;
- Brinson-Fachler allocation effect;
- portfolio-weighted selection effect, including interaction under `ppar`'s current
  convention;
- total attribution effect;
- logarithmic contribution linking;
- Carino active-effect linking;
- cumulative results;
- overall results; and
- financial reconciliation checks.

The first core should not own CSV or Parquet access, URLs, databases, vendor schemas,
portfolio accounting, holiday calendars, charts, templates, CLI behavior, or report
file management. Optional source-period consolidation and time-aware classification
helpers can be considered later, after the calculation boundary is proven.

### Provisions for additional capabilities

The first implementation need not calculate the proposed additional effects, but its
contracts should avoid blocking them:

- **Interaction effect:** record explicitly that the initial convention absorbs
  interaction into portfolio-weighted selection. A later calculation policy can
  request a separate interaction effect.
- **Time-varying classifications:** treat the classification identifier as a
  period-specific row value rather than assuming one permanent mapping. Host adapters
  can resolve effective-dated assignments before calling the first core.
- **Cash:** represent cash as an explicit attributable identifier rather than hiding
  it in a residual.
- **Fees and financing:** permit authoritative contribution with zero weight and an
  undefined return.
- **Derivatives:** require the host adapter to provide the chosen exposure basis; the
  core must not infer whether market value, notional, delta-adjusted exposure, or
  another convention is intended.
- **External flows:** keep flow-adjusted return measurement in the host accounting
  layer. A later reconciliation input can disclose flow components without silently
  treating them as attribution effects.
- **Currency attribution:** preserve room for a distinct future calculation using
  local, currency, and base-currency returns. Do not add speculative currency columns
  before the methodology and input requirements are defined.

No plugin framework is needed initially. Explicit functions, schemas, and calculation
policies should be added only when a second implemented methodology demonstrates the
need.

### Numerical parity contract

Cross-engine parity should mean:

- identical rows, columns, null placement, dates, and deterministic ordering after
  the `ppar` adapter;
- numerical equality within `ppar`'s established `1e-12` relative and absolute
  comparison tolerance;
- identical financial reconciliation outcomes;
- identical displayed and serialized values at `ppar`'s supported precision; and
- identical HTML and PNG artifacts when values are equal at presentation precision.

The standalone core retains a default reconciliation tolerance of `1e-12`. The
initial `ppar` adapter may explicitly request `5e-9` to match `ppar`'s established
eight-decimal weight-sum validation. This compatibility tolerance affects only input
acceptance and reconciliation evidence; calculation formulas are unchanged, and
cross-engine output parity remains `1e-12`.

Bit-for-bit floating-point identity is not a suitable cross-engine requirement because
pandas/NumPy and parallel Polars reductions can add the same values in different
orders. The pandas core must not call the Polars implementation. The two engines
should share the written specification and independent fixtures, not calculation
code, so differential testing remains meaningful.

### Performance plan

The current 500x `ppar` workload expands the Axys/APX source from 12,126
security-performance rows to approximately 6,063,000 rows while continuing to select
the same two accounts. Most of that scaling measures source scanning and account
filtering, not attribution calculation. Because the first pandas fork occurs after
the existing Polars preparation, the pandas path will continue to use the current
fast large-source selection and should remain close to the current end-to-end 500x
time if its fixed calculation cost remains modest.

The pandas calculator should also have direct benchmarks that exercise genuinely
larger selected inputs:

- the normal 6,063-row-per-side Axys workload;
- the existing 10x selected-security workload;
- the 121,260-row-per-side monthly workload;
- the genuine 25-year history workload; and
- peak memory as well as elapsed time.

The initial implementation should normalize dtypes once, sort once, use validated
merges, use `groupby(..., sort=False, observed=True)`, and avoid `apply`, `iterrows`,
and Python row loops. Linking coefficients and conditional division should use NumPy
arrays. If profiling shows grouping to be material, composite keys can be factorized
once and reduced with NumPy. Numba, Polars, PyArrow, and additional acceleration
dependencies remain out of scope for the portable core.

Performance thresholds should not be selected before a correct prototype establishes
repeatable evidence. Absolute elapsed time and memory matter alongside ratios;
pandas may have a larger relative cost on an already-fast small calculation while
adding only a few tens of milliseconds to a normal user workflow.

### Implementation sequence

1. **Write the portable specification.** Lock the prepared input semantics, result
   frames, effect convention, linking formulas, undefined-return behavior, ordering,
   and tolerances. Decide the outbound license and fixture provenance before code is
   reused or distributed.
2. **Create the standalone project and publishing path.** Create the `perfattr`
   repository and package metadata, and configure a pending PyPI Trusted Publisher.
   A pending publisher simplifies the first release but does not reserve the project
   name until a release is actually published.
3. **Create independent hand-calculated fixtures.** Cover single and multiple
   periods, missing identifiers, signed and zero weights, zero-weight nonzero
   contribution, linking limits, and returns close to -100%.
4. **Implement the first functional vertical slice.** Using only pandas, NumPy, and
   the standard library, implement documented input validation and a genuine,
   independently tested single-period Brinson-Fachler calculation. Do not import
   `ppar` or Polars and do not mutate caller-owned frames.
5. **Publish `perfattr==0.1.0a1` as early as possible.** Publish immediately after
   the first functional slice passes its build, metadata, installation, and
   calculation tests. This establishes the PyPI project with a legitimate prerelease
   rather than an empty or nonfunctional name-squatting placeholder.
6. **Complete the standalone pandas core.** Add the remaining current `ppar`
   contribution, linking, cumulative, overall, result, and reconciliation behavior
   against the independent fixtures.
7. **Separate calculation from presentation inside `ppar`.** Preserve the current
   Polars behavior while introducing one common numerical-result boundary.
8. **Add the pandas adapter as a non-default backend.** Convert prepared Polars rows to
   pandas once, invoke the core, translate the result back to `ppar`'s existing Polars
   schema once, and reuse all existing presentation code.
9. **Run comprehensive differential tests.** Compare every attribution view, generic
   and Axys/APX demonstrations, randomized valid inputs, metamorphic invariants,
   serialized output, and the required 500x workflow.
10. **Profile before optimizing.** Apply only measured, simple pandas/NumPy
   improvements and preserve every financial invariant.
11. **Reassess permanent dual-engine support.** Both paths should be supported during
   development and evaluation. After parity and performance are established, decide
   whether maintaining two financial calculators continues to earn its additional
   correctness and maintenance cost.

### Agreed design decisions

The initial design adopts these decisions:

- consume prepared, reporting-period attribution data rather than reproducing all of
  `ppar`'s source, calendar, and mapping preparation;
- develop the reusable core as a standalone package or repository so `ppar`-specific
  assumptions cannot leak into it;
- define parity as `1e-12` numerical equivalence plus identical presentation output,
  not bitwise floating-point identity;
- retain both engines during development and evaluation, then reassess permanent dual
  maintenance;
- publish the first genuinely functional prerelease as `perfattr==0.1.0a1` as early
  as possible so the PyPI name is established without publishing an empty shell; and
- decide a suitable outbound license before implementation if the core may be
  contributed to open-source projects.
