# perfattr Portable Attribution Specification

## Status

This document defines the released default two-effect calculation contract for
`perfattr`. It is normative for the portable pandas implementation. The project
roadmaps govern sequencing and scope; this specification governs the shared and
default calculation behavior.

Roadmap 2's upstream preparation contract is defined separately in
`docs/preparation_specification.md`. That layer produces the prepared frames consumed
by this calculation contract without changing the calculation core's responsibility.
The opt-in Brinson-Fachler three-effect extension is defined in
`docs/brinson_fachler_three_effect_specification.md`; that document changes only the
method, additional interaction channels, and related reconciliation names it states
explicitly.
The opt-in Brinson-Hood-Beebower three-effect extension is defined in
`docs/brinson_hood_beebower_three_effect_specification.md`; it reuses those explicit
interaction schemas while defining its distinct allocation and total-effect policy.
The opt-in compact Brinson-Hood-Beebower extension is defined in
`docs/brinson_hood_beebower_two_effect_specification.md`; it reuses the two-effect
schemas while retaining the Brinson-Hood-Beebower allocation and total-effect policy.
The opt-in Frongello extension is defined in
`docs/frongello_recursive_linking_specification.md`; it changes only active-effect
linking and its explicit result metadata while retaining logarithmic contribution
linking and every result-frame schema.
The opt-in Menchero extension is defined in
`docs/menchero_optimized_linking_specification.md`; it adds order-independent
optimized active-effect linking through the same unchanged public boundary.
The post-calculation hierarchical result-roll-up supplement is defined in
`docs/hierarchical_result_rollup_specification.md`; it aggregates already calculated
leaf values into static ancestors without changing any `AttributionResult` frame or
recalculating attribution at parent levels.
The separate geometric excess-return calculation is defined in
`docs/geometric_attribution_specification.md`; it uses a distinct result type and
multiplicative wealth-ratio identity without changing this arithmetic calculation,
its method enums, or its effect linkers.
The separate single-period currency calculation is defined in
`docs/currency_attribution_specification.md`; it accepts side-separated market and
currency frames and reports reconciled effects in log-return units.
The multi-period currency roll-up is defined in
`docs/multi_period_currency_rollup_specification.md`; it sums those period log returns
and effects into cumulative prefixes and a full horizon.

The words **must**, **must not**, **should**, and **may** describe requirements with
their ordinary technical meanings.

## Design principles

- Keep one explicit calculation path.
- Prefer auditable formulas over abstraction.
- Derive contribution for common inputs and preserve it when supplied.
- Reject ambiguous financial inputs instead of guessing.
- Return data, not presentation.
- Establish correctness before optimizing.

## Scope

The core accepts prepared portfolio and benchmark attribution rows and returns
single-period and linked multi-period Brinson results.

The core owns:

- input validation and normalization;
- portfolio and benchmark universe equalization;
- contribution and method-specific Brinson effects;
- logarithmic contribution linking;
- selectable Carino, Frongello, or Menchero active-effect linking, with Carino as the
  default;
- cumulative and overall results; and
- reconciliation evidence.

The core does not own source loading, files, URLs, vendor schemas, portfolio
accounting, external-flow measurement, frequency conversion, classification mapping,
calendars, currencies, charts, reports, or presentation total rows.

## Public API

The public calculation entry point for this arithmetic contract is:

```python
def calculate_attribution(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    method: AttributionMethod = AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
    effect_linking_method: EffectLinkingMethod = EffectLinkingMethod.CARINO,
    reconciliation_tolerance: float = 1e-12,
) -> AttributionResult:
    ...
```

The root package exports `AttributionError`, `AttributionMethod`,
`EffectLinkingMethod`, `AttributionResult`, and `calculate_attribution`; callers do
not need to import an internal module.

The result container is an ordinary dataclass:

```python
@dataclass
class AttributionResult:
    period_detail: pd.DataFrame
    period_summary: pd.DataFrame
    overall_detail: pd.DataFrame
    cumulative: pd.DataFrame
    reconciliation: pd.DataFrame
    method: AttributionMethod = AttributionMethod.BRINSON_FACHLER_TWO_EFFECT
    effect_linking_method: EffectLinkingMethod = EffectLinkingMethod.CARINO
```

`AttributionError`, a subclass of `ValueError`, reports invalid financial data or a
failed calculation invariant. Passing an object other than a pandas `DataFrame`
raises `TypeError`.

The method enum is the calculation policy boundary. Both two-effect methods absorb
interaction into portfolio-weighted selection, while the two three-effect methods
expose it separately. Their allocation and identifier-total policies are defined by
this specification and the applicable supplemental specification. The numerical
tolerance remains fixed by this specification.
The runtime dependencies are limited to pandas, NumPy, and the Python standard
library.

## Prepared inputs

The function accepts one portfolio DataFrame and one benchmark DataFrame. Each row is
one already-classified attribution unit in one already-aligned reporting period.

Both frames require these columns in this order-independent input schema:

| Column | Required value |
|---|---|
| `from_date` | Inclusive, timezone-naive reporting-period start |
| `thru_date` | Inclusive, timezone-naive reporting-period end |
| `identifier` | Nonempty string identifying the period-specific attribution unit |
| `weight` | Finite period exposure weight |
| `return` | Compoundable unit return, nullable only when undefined |
| `quantity_of_days` | Positive integer observed-day count for the period |

Each frame may also include this optional column:

| Column | Optional value |
|---|---|
| `contribution` | Fully populated, finite authoritative additive contribution |

Portfolio and benchmark inputs independently may include or omit `contribution`.
When the column is absent, the core derives it for every row. When the column is
present, every value must be non-null and finite; partial population is invalid.

The index has no meaning. Additional columns are ignored and never propagated to a
result. Duplicate column labels are invalid.

### Input normalization

- Dates are normalized to timezone-naive `datetime64[ns]` values at midnight.
- Surrounding whitespace is removed from identifiers. Identifiers are not otherwise
  changed or coerced, so leading zeroes are preserved.
- Identifier, scope, and check columns use `string[python]` values. Financial numeric
  output uses `float64`; day counts use `int64`; pass flags use `bool`.
- Numeric strings are rejected rather than silently converted.
- Boolean values are not accepted as numbers.
- Complex values are not accepted as real-valued financial numbers.
- Caller-owned DataFrames are never mutated.

### Row and period rules

- Neither input may be empty.
- A `(from_date, thru_date, identifier)` key must be unique within each frame.
- Each `thru_date` identifies exactly one `(from_date, thru_date)` period.
- `from_date` must not exceed `thru_date`.
- Periods must not overlap. Gaps are allowed.
- Portfolio and benchmark period keys must match exactly.
- `quantity_of_days` must be a positive integer representable as `int64`, constant
  within a period, and equal across both inputs. It is authoritative observed coverage
  and is not recalculated from the dates.
- Portfolio and benchmark weights must each sum to `1.0` within tolerance in every
  period. Negative weights and weights greater than `1.0` are allowed.
- An input `return` must be finite and greater than `-1.0` when it is present.
- A nonzero weight requires a non-null `return`.
- A supplied zero weight with nonzero contribution requires a null `return`.
- Every calculated non-null effective return must be finite.

An identifier need not occur on both sides. For each period, the core forms the union
of portfolio and benchmark identifiers and adds missing rows to the other side with
zero weight, return, and contribution. Absence in a different period likewise means
zero exposure, zero return, and zero contribution for overall calculations.

The core does not aggregate duplicate identifiers. Classification mapping and any
aggregation needed to create one row per period and identifier belong to the host
adapter.

## Return and contribution semantics

All weights, returns, contributions, and effects are decimal values. For example,
`0.01` means one percent.

The normalized contribution for each row is:

```text
contribution = supplied contribution    when the column is present
contribution = weight * return           when the column is absent and return is defined
contribution = 0                         when the column is absent, weight is 0,
                                         and return is null
```

A supplied contribution is authoritative. The core must not replace it with weight
multiplied by return or reject it merely because those values differ.

The input `return` remains required because it is the compoundable value used to
calculate an identifier's overall return. It is not used directly in period
attribution when contribution is supplied. This distinction preserves inputs whose
contributions have already been linked during frequency consolidation.

For each side, identifier `g`, and period `t`, the effective period return is:

```text
effective_return = contribution / weight    when weight != 0
effective_return = 0                        when weight == 0 and contribution == 0
effective_return = null                     when weight == 0 and contribution != 0
```

Exact zero determines which branch applies; numerical tolerance does not convert a
small exposure into zero.

### Cash, fees, financing, and other prepared cases

Cash receives no special numerical treatment. It is an ordinary explicit identifier
with caller-supplied weight, return, and optional authoritative contribution. It may
also be mapped into a Cash classification like any other identifier. Positive,
negative, and zero cash weights follow the same validation, attribution, linking, and
reconciliation rules as all other rows. The core does not identify or synthesize cash,
calculate a distinct cash-drag effect, or use cash as a hidden residual; those choices
belong to the host accounting adapter. In particular, exact zero cash weight and zero
contribution produce the ordinary defined effective return of zero under the
effective-return branch above.

A fee or financing charge without attributable exposure is represented by zero
weight, authoritative nonzero contribution, and null return. Its effective and active
returns are null, but its contribution remains part of the portfolio or benchmark
total and is linked normally. Because its active weight is zero, its allocation effect
is zero. Under the released portfolio-weighted-selection convention, its active
contribution is carried by selection so that the effect components reconcile. The
core does not infer fee or financing semantics from identifier text or calculate the
charge. Financing with an attributable exposure and return may instead be supplied as
an ordinary identifier using those facts.

Semantic labels, gross-to-net policy, accrual calculations, and decisions about
whether a charge belongs to the portfolio, benchmark, or both remain host accounting
responsibilities. Mapping a zero-weight charge into a classification with nonzero
exposure combines its authoritative contribution with that classification under the
ordinary mapping rules.

A derivatives adapter must supply its chosen exposure basis as weight; the core never
infers market value, notional, or delta-adjusted exposure. Classification identifiers
are period-specific and may change between periods. External-flow adjustment belongs
to the host accounting layer.

## Notation

For identifier `g` and period `t`:

- `wP[g,t]`, `wB[g,t]`: portfolio and benchmark weights;
- `rP[g,t]`, `rB[g,t]`: effective period returns;
- `cP[g,t]`, `cB[g,t]`: normalized supplied or derived contributions;
- `P[t]`, `B[t]`: total portfolio and benchmark returns; and
- `D[t]`: quantity of observed days.

Portfolio and benchmark period returns are additive contribution totals:

```text
P[t] = sum_g(cP[g,t])
B[t] = sum_g(cB[g,t])
```

The period active return is the arithmetic difference `P[t] - B[t]`, not the relative
return `(1 + P[t]) / (1 + B[t]) - 1`.

## Single-period calculation

For each equalized identifier row:

```text
active_weight       = wP[g,t] - wB[g,t]
active_return       = rP[g,t] - rB[g,t]  when both returns are defined; else null
active_contribution = cP[g,t] - cB[g,t]
```

Brinson-Fachler allocation is:

```text
allocation_effect = (wP[g,t] - wB[g,t]) * (rB[g,t] - B[t])
```

If `rB[g,t]` is undefined, allocation is zero. This leaves an undefined-return
residual in selection rather than inventing a benchmark group return.

Total effect is calculated directly from contributions:

```text
total_effect = cP[g,t] - cB[g,t] - (wP[g,t] - wB[g,t]) * B[t]
```

Selection is the residual:

```text
selection_effect = total_effect - allocation_effect
```

When both effective returns are defined, this selection convention is equivalent to:

```text
selection_effect = wP[g,t] * (rP[g,t] - rB[g,t])
```

It therefore combines conventional benchmark-weighted selection and interaction.
This remains the default. The explicit three-effect method and its undefined-return
boundary are specified in `docs/brinson_fachler_three_effect_specification.md`. The
Brinson-Hood-Beebower alternatives are specified separately in
`docs/brinson_hood_beebower_three_effect_specification.md` and
`docs/brinson_hood_beebower_two_effect_specification.md`.

## Multi-period linking

Every portfolio and benchmark period return must be greater than `-1.0`. Define the
full-horizon returns:

```text
P = product_t(1 + P[t]) - 1
B = product_t(1 + B[t]) - 1
```

### Contribution linking

Define the logarithmic smoothing function:

```text
s(x) = log1p(x) / x    when x != 0
s(0) = 1
```

The portfolio and benchmark contribution coefficients are:

```text
LP[t] = s(P[t]) / s(P)
LB[t] = s(B[t]) / s(B)
```

Linked contributions are:

```text
linked_portfolio_contribution = cP[g,t] * LP[t]
linked_benchmark_contribution = cB[g,t] * LB[t]
linked_active_contribution = (
    linked_portfolio_contribution - linked_benchmark_contribution
)
```

### Active-effect linking

`EffectLinkingMethod.CARINO` is the default and preserves the original released
behavior. Its coefficient is defined as follows.

Define the Carino coefficient:

```text
k(p, b) = (log1p(p) - log1p(b)) / (p - b)    when p != b
k(p, p) = 1 / (1 + p)
```

The implementation must evaluate the formula stably for near-equal returns. The
active-effect coefficient is:

```text
LA[t] = k(P[t], B[t]) / k(P, B)
```

Linked effects are each simple effect multiplied by `LA[t]`:

```text
linked_allocation_effect = allocation_effect * LA[t]
linked_selection_effect = selection_effect * LA[t]
linked_total_effect = total_effect * LA[t]
```

The opt-in three-effect methods apply the selected effect-linking policy to
interaction as well. `EffectLinkingMethod.FRONGELLO` instead uses the source-period
factor:

```text
LF[t] = product_s<t(1 + P[s]) * product_s>t(1 + B[s])
```

Every simple effect originating in period `t` is multiplied by `LF[t]`. The final
sum is equivalent to Frongello's forward recursion and reconciles to `P - B` over the
complete horizon.

`EffectLinkingMethod.MENCHERO` instead defines period active return `d[t] = P[t] -
B[t]`, a continuous common horizon scale `M`, residual `E`, and coefficient `LM[t]`:

```text
E     = (P - B) - M * sum_t(d[t])
LM[t] = M + E * d[t] / sum_t(d[t] ** 2)
```

The exact zero active vector uses zero correction. The implementation evaluates `M`
with the stable difference-of-powers identity rather than subtracting nearly equal
horizon roots; its complete formula and equal-horizon limit are defined in
`docs/menchero_optimized_linking_specification.md`. Applying one `LM[t]` to every
effect in period `t` minimizes the squared period corrections and reconciles to
`P - B`. Unlike Frongello, moving complete economic periods leaves complete-horizon
effect totals unchanged.

Contribution linking remains logarithmic under every effect policy. Period-detail
and intermediate cumulative values retain the full-horizon source-allocation
interpretation described in the applicable supplemental linking specification;
intermediate cumulative rows are not independently relinked as-of results.

Linked active contribution and linked total effect are distinct allocation paths.
Their period and identifier values need not match, but both reconcile to `P - B` over
the full horizon.

## Overall and cumulative calculations

An identifier's overall return compounds its supplied input `return` values. An
absent period contributes a zero return. If any explicit return for that identifier
is null, its overall return is null.

The overall weight is observed-day weighted across the complete horizon:

```text
overall_weight[g] = sum_t(weight[g,t] * D[t]) / sum_t(D[t])
```

An absent period contributes zero weight. Overall contributions and effects are sums
of their linked period-detail values.

Overall active weight is portfolio weight minus benchmark weight. Overall active
return is portfolio return minus benchmark return when both are defined; otherwise it
is null. Overall linked active contribution is linked portfolio contribution minus
linked benchmark contribution.

Cumulative portfolio and benchmark returns compound chronologically through each
period. Cumulative active return is their arithmetic difference. Other cumulative
values are chronological sums of the linked values.

Linking coefficients are calculated once for the complete requested horizon.
Consequently, an intermediate cumulative linked value is a contribution toward the
full-horizon result; it is not a separately relinked as-of calculation. All linked
identities must reconcile in the final cumulative row.

## Result schemas

Every result has a zero-based `RangeIndex`. Columns appear exactly in the order below.
The portable core does not add display names or total rows.

The schemas below are the stable compact two-effect schemas, reused by both
Brinson-Fachler and Brinson-Hood-Beebower. Both three-effect specifications reuse the
same exact insertion positions for their additional interaction columns without
reinterpreting any column listed here.

In `period_detail`, portfolio and benchmark return columns contain effective period
returns. In `period_summary`, they contain period totals. In `overall_detail`, they
contain compounded supplied returns.

### `period_detail`

```text
from_date
thru_date
quantity_of_days
identifier
portfolio_weight
portfolio_return
portfolio_contribution
benchmark_weight
benchmark_return
benchmark_contribution
active_weight
active_return
active_contribution
allocation_effect
selection_effect
total_effect
linked_portfolio_contribution
linked_benchmark_contribution
linked_active_contribution
linked_allocation_effect
linked_selection_effect
linked_total_effect
```

Rows are ordered by `thru_date`, then `identifier`.

### `period_summary`

```text
from_date
thru_date
quantity_of_days
portfolio_return
benchmark_return
active_return
portfolio_contribution
benchmark_contribution
active_contribution
allocation_effect
selection_effect
total_effect
linked_portfolio_contribution
linked_benchmark_contribution
linked_active_contribution
linked_allocation_effect
linked_selection_effect
linked_total_effect
```

Rows are ordered by `thru_date`.

Contribution and effect columns are sums of `period_detail` values for the period.

### `overall_detail`

```text
from_date
thru_date
identifier
portfolio_weight
portfolio_return
linked_portfolio_contribution
benchmark_weight
benchmark_return
linked_benchmark_contribution
active_weight
active_return
linked_active_contribution
linked_allocation_effect
linked_selection_effect
linked_total_effect
```

The dates are the first `from_date` and last `thru_date`. Rows are ordered by
`identifier`.

### `cumulative`

```text
from_date
thru_date
portfolio_return
benchmark_return
active_return
cumulative_portfolio_return
cumulative_benchmark_return
cumulative_active_return
linked_portfolio_contribution
linked_benchmark_contribution
linked_active_contribution
cumulative_portfolio_contribution
cumulative_benchmark_contribution
cumulative_active_contribution
linked_allocation_effect
linked_selection_effect
linked_total_effect
cumulative_allocation_effect
cumulative_selection_effect
cumulative_total_effect
```

Rows are ordered by `thru_date`.

### `reconciliation`

```text
scope
from_date
thru_date
check
actual
expected
residual
tolerance
passed
```

`scope` is `period` or `overall`. `residual` is `actual - expected`. Period checks
appear in chronological order using these stable `check` values:

```text
portfolio_weight
benchmark_weight
portfolio_contribution
benchmark_contribution
active_contribution
effect_components
total_effect
```

Overall checks follow the period checks using these stable values:

```text
linked_portfolio_contribution
linked_benchmark_contribution
linked_active_contribution
linked_effect_components
linked_total_effect
```

Weight checks compare each net weight sum with `1.0`. Contribution and total-effect
checks compare detail sums with their corresponding period or overall return.
Two-effect component checks compare allocation plus selection with total effect. A
three-effect method compares allocation plus selection plus interaction and uses the
explicit check names defined in its supplemental specification.

A successful result contains only passing reconciliation rows. Any failed financial
reconciliation raises `AttributionError` before a result is returned. The frame is
retained as positive audit evidence rather than as a warning channel.
The calculation emits no warnings and never returns a partial result.

## Numerical contract

By default, all financial comparisons use:

```python
math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
```

Null placement, dates, identifiers, row ordering, column ordering, and boolean values
must match exactly. Numerical calculations must be equal within the tolerance above.
Bit-for-bit floating-point identity is not required.

`calculate_attribution()` also accepts an explicit keyword-only
`reconciliation_tolerance`. It must be finite and greater than zero and controls input
weight-sum validation and the tolerance recorded and enforced by the reconciliation
frame. Its default remains `1e-12`. A host with an established, less precise input
contract may deliberately request a wider compatibility tolerance; doing so changes
only validation and reconciliation acceptance, never calculation formulas or result
values. Cross-engine result comparison remains subject to the host's separate parity
tolerance.

Except for undefined return fields, result numeric columns must be finite. The core
must use numerically stable `log1p`-based calculations and explicit zero-return limits.

## Ownership and determinism

The calculation must not mutate either input frame. Each result frame is caller-owned
and may be mutated without changing another result frame or later calculation.

Given equivalent normalized inputs, results must be deterministic regardless of
input row order or pandas grouping defaults.

## Reference fixtures and parity

Expected values must originate in independently hand-calculated fixtures. Fixtures
must cover:

- equivalent calculations from derived and explicitly supplied contributions;
- one and multiple periods;
- portfolio-only and benchmark-only identifiers;
- identifiers that disappear before the horizon ends;
- signed, leveraged, and zero weights;
- zero weight with nonzero contribution;
- equal and near-equal Carino and Menchero returns;
- zero total return;
- returns close to, equal to, and below `-1.0`;
- period gaps and overlaps; and
- cases where unlinked effects do not reconcile across time but linked effects do.

`ppar` may be used temporarily as a differential oracle after independent expected
values are locked. It must not be imported by `perfattr`, required by distributed
tests, or used as the source of fixture expectations.

At the `ppar` adapter boundary, parity requires matching rows, columns, nulls, dates,
ordering, reconciliation outcomes, and values within the numerical tolerance. The
adapter is responsible for translating neutral names to the existing `ppar` schema.
Integration tests separately require identical displayed and serialized values at
`ppar` presentation precision when the underlying values are equivalent.

## Deferred capabilities

Current deferred calculation candidates include independently recalculated
hierarchical attribution, identifier-level geometric horizon attribution, additional
nonduplicative multi-period linking methods, modeled-to-accounting currency
reconciliation, separate currency interaction effects, and hierarchical currency
attribution. External-flow measurement, derivative exposure inference, and
presentation or report generation remain outside the portable calculation boundary.
The released static additive hierarchy operation is a post-calculation result roll-up,
not the deferred level-relative calculation. Add a policy or abstraction only when an
approved implemented use case requires it.
