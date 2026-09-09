# Geometric Excess-Return Attribution Specification

**Status:** Accepted, implemented, and released in `perfattr==0.10.0a1` on
September 7, 2026.

This document is the governing contract for the deliberately limited geometric
attribution feature in [roadmap 11][roadmap-11]. It supplements the released
arithmetic [`specification.md`](specification.md). The user approved this contract and
Roadmap 11 on September 7, 2026. The implementation completed the roadmap's
dependency-ordered engineering and compatibility gates.

[roadmap-11]: ../_extras/perfattr_roadmap_11_geometric_attribution.md

## Methodological identity

This feature is Bacon/Burnie top-down geometric excess-return attribution. It compares
portfolio wealth with benchmark wealth and decomposes the relative return through a
semi-notional portfolio that holds portfolio weights and earns benchmark identifier
returns.

It is not an arithmetic effect-linking method. The existing calculation reconciles:

```text
arithmetic active return = portfolio return - benchmark return
```

The geometric calculation instead reconciles:

```text
geometric excess return = (1 + portfolio return) / (1 + benchmark return) - 1
```

Its allocation and selection channels combine multiplicatively, not additively.
Adding `GEOMETRIC` to `EffectLinkingMethod` would falsely suggest that the same
single-period effects and five result schemas remain meaningful. A separate function
and result type make the changed financial identity explicit.

The released calculation implements one method only. It does not add an enum merely to hold
one value.

## User problem

Arithmetic attribution is appropriate when the reporting contract measures active
return as a difference and needs additive effects. Geometric attribution is useful
when the reporting contract asks how portfolio ending wealth compares with benchmark
ending wealth. Its effects compound through time without a Carino, Frongello, or
Menchero arithmetic smoothing coefficient.

The two families answer related but different questions. Neither is a more accurate
format for the other, and their effect totals should not be compared as though they
shared one denominator.

## Public API

The package exports this public function from `perfattr.geometric` and its root:

```python
def calculate_geometric_attribution(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    reconciliation_tolerance: float = 1e-12,
) -> GeometricAttributionResult:
    ...
```

The package also exports this result type:

```python
@dataclass
class GeometricAttributionResult:
    period_detail: pd.DataFrame
    period_summary: pd.DataFrame
    cumulative: pd.DataFrame
    reconciliation: pd.DataFrame
```

The result fields are in exactly that order. Returned frames are independent from
caller inputs and from one another. As with `AttributionResult`, ordinary dataclass
construction stores the supplied objects; it does not validate or freeze them.

The tolerance retains the released finite, positive, non-boolean rule. Invalid input
or a failed financial reconciliation raises `AttributionError`. The function neither
invokes preparation nor accepts an arithmetic method or effect-linker argument.

The portfolio and benchmark arguments must be pandas DataFrames; another object
raises `TypeError`. Invalid DataFrame content raises `AttributionError` once financial
normalization is enabled.

## Inputs

The function accepts the two released prepared-input forms unchanged:

```text
from_date, thru_date, identifier, weight, return, quantity_of_days
```

or:

```text
from_date, thru_date, identifier, weight, return, contribution, quantity_of_days
```

All released normalization, identity, date, period, day-count, weight-sum, numeric,
return, contribution, caller-nonmutation, and portfolio/benchmark matching rules
apply. The function forms the same union of identifiers within each period and uses
the same missing-side zero row.

Supplied contribution remains authoritative. When contribution is absent, it is
derived under the released rule. The effective return remains:

```text
contribution / weight     when weight != 0
0                         when weight == 0 and contribution == 0
null                      when weight == 0 and contribution != 0
```

The formulas below use these effective returns, not a separately supplied return that
would contradict authoritative contribution. This preserves consolidated source
periods and accounting-integrated inputs.

Cash remains an ordinary identifier. An unexposed fee or financing charge remains a
zero-weight, nonzero-contribution, null-return row. The geometric method adds no
semantic detection or special cash, fee, financing, derivative, flow, or currency
effect.

## Notation

For identifier `g` and chronological period `t`:

- `wP[g,t]`, `wB[g,t]` are portfolio and benchmark weights;
- `rP[g,t]`, `rB[g,t]` are effective returns;
- `cP[g,t]`, `cB[g,t]` are authoritative normalized contributions;
- `P[t] = sum_g(cP[g,t])` is the portfolio period return;
- `B[t] = sum_g(cB[g,t])` is the benchmark period return;
- `n[g,t]` is the identifier's semi-notional contribution;
- `N[t] = sum_g(n[g,t])` is the semi-notional period return;
- `a[g,t]`, `s[g,t]` are geometric allocation and selection; and
- `A[t]`, `S[t]`, `E[t]` are their period totals and geometric excess return.

All values are decimals. Exact zero, not a tolerance, selects zero-weight and null
branches.

## Semi-notional portfolio

The semi-notional portfolio holds portfolio weights and earns benchmark effective
returns:

```text
n[g,t] = wP[g,t] * rB[g,t]    when rB[g,t] is defined
n[g,t] = 0                    when wP[g,t] is zero and rB[g,t] is null

N[t] = sum_g(n[g,t])
```

A nonzero portfolio weight with a null benchmark effective return makes the
semi-notional return unknowable and raises `AttributionError`. The implementation
must not replace that null with zero. This case can arise when the benchmark has an
unexposed authoritative contribution for an identifier to which the portfolio has
exposure.

A null benchmark return with zero portfolio weight contributes zero to the
semi-notional portfolio. Its benchmark contribution is still authoritative and is
handled by the allocation accounting residual below.

Require all three successive wealth bases to be strictly positive:

```text
1 + P[t] > 0
1 + B[t] > 0
1 + N[t] > 0
```

The released input validation already enforces the first two period-total bounds. The
third is new because signed or leveraged portfolio weights can make `N[t] <= -1` even
when each defined source return is greater than `-1`. Do not use reconciliation
tolerance to turn a nonpositive wealth base into a valid denominator.

## Identifier allocation

First define the benchmark modeled contribution and accounting residual:

```text
mB[g,t] = wB[g,t] * rB[g,t]    when rB[g,t] is defined
mB[g,t] = 0                    when wB[g,t] is zero and rB[g,t] is null

uB[g,t] = cB[g,t] - mB[g,t]
```

Under the released effective-return contract, `uB` is zero for a nonzero benchmark
weight. It can be nonzero for an unexposed authoritative benchmark contribution.

Define the ordinary geometric Brinson-Fachler allocation numerator:

```text
x[g,t] = (wP[g,t] - wB[g,t]) * (rB[g,t] - B[t])
          when rB[g,t] is defined
x[g,t] = 0
          when both weights are zero and rB[g,t] is null
```

Then the accounting-integrated identifier allocation is:

```text
a[g,t] = (x[g,t] - uB[g,t]) / (1 + B[t])
```

When every contribution is weight times return, `uB` is zero and this is the
published geometric Brinson-Fachler expression:

```text
a[g,t] = (wP[g,t] - wB[g,t])
         * ((1 + rB[g,t]) / (1 + B[t]) - 1)
```

The accounting residual is not a new effect. It prevents an authoritative benchmark
charge from disappearing merely because its weight and effective return are both
zero or null. Its sign follows the benchmark-relative allocation leg.

Summing identifier allocation gives the first successive-notional ratio:

```text
A[t] = sum_g(a[g,t])
     = (1 + N[t]) / (1 + B[t]) - 1
```

## Identifier selection

Portfolio-weighted geometric selection is:

```text
s[g,t] = (cP[g,t] - n[g,t]) / (1 + N[t])
```

When portfolio contribution is weight times return, this reduces to:

```text
s[g,t] = wP[g,t] * (rP[g,t] - rB[g,t]) / (1 + N[t])
```

Selection therefore absorbs interaction, consistent with the released two-effect
reporting convention. A zero-weight authoritative portfolio fee or financing charge
is preserved in selection through `cP`; no return is fabricated for it.

Summing identifier selection gives the second successive-notional ratio:

```text
S[t] = sum_g(s[g,t])
     = (1 + P[t]) / (1 + N[t]) - 1
```

## Period total and the deliberate absence of identifier total effect

The period geometric excess return is:

```text
E[t] = (1 + P[t]) / (1 + B[t]) - 1
```

The two channels reconcile multiplicatively:

```text
1 + E[t] = (1 + A[t]) * (1 + S[t])
E[t]     = A[t] + S[t] + A[t] * S[t]
```

The product term belongs to the relationship between whole allocation and selection
channels. There is no unique method-free way to distribute it among identifiers.
`period_detail` therefore contains identifier allocation and selection but no
`total_effect` column. `period_summary` contains the channel totals and the period
`total_effect`, which equals `geometric_excess_return`.

Do not create an interaction column only to hold the channel product. That value is
not the conventional identifier-level Brinson interaction that selection already
absorbs.

## Multi-period compounding

For every chronological prefix ending at period `k`, compound each wealth leg and
effect channel directly:

```text
P[1:k] = product_t<=k(1 + P[t]) - 1
B[1:k] = product_t<=k(1 + B[t]) - 1
N[1:k] = product_t<=k(1 + N[t]) - 1
A[1:k] = product_t<=k(1 + A[t]) - 1
S[1:k] = product_t<=k(1 + S[t]) - 1
E[1:k] = (1 + P[1:k]) / (1 + B[1:k]) - 1
```

The period identities imply:

```text
1 + A[1:k] = (1 + N[1:k]) / (1 + B[1:k])
1 + S[1:k] = (1 + P[1:k]) / (1 + N[1:k])
1 + E[1:k] = (1 + A[1:k]) * (1 + S[1:k])
```

No arithmetic smoothing coefficient is calculated. Final horizon results are
invariant to reordering complete economic periods; intermediate prefix rows naturally
follow chronological order.

Roadmap 11 does not return an identifier horizon frame. Compounding identifier values
separately would introduce cross-period terms, and allocating those terms requires an
additional policy. Omitting the frame is more accurate than labeling a simple sum or
product as a governed identifier-level result.

## Exact result schemas

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
semi_notional_contribution
benchmark_accounting_residual
allocation_effect
selection_effect
```

Dates use `datetime64[ns]`; `quantity_of_days` uses `int64`; `identifier` uses
`string[python]`; every numerical value uses `float64`. Portfolio, benchmark, and
active facts retain their released meanings. `portfolio_return`, `benchmark_return`,
and `active_return` follow the released effective-return null contract.

Rows are sorted by `thru_date`, `from_date`, and `identifier` using stable ordering
and have a zero-based `RangeIndex`.

### `period_summary`

```text
from_date
thru_date
quantity_of_days
portfolio_return
benchmark_return
semi_notional_return
geometric_excess_return
allocation_effect
selection_effect
total_effect
```

Each period has one row. `total_effect` equals `geometric_excess_return` and is kept as
an explicit effect reconciliation field, not as a third additive effect. Rows use
chronological order and a zero-based `RangeIndex`.

### `cumulative`

```text
from_date
thru_date
quantity_of_days
portfolio_return
benchmark_return
semi_notional_return
geometric_excess_return
allocation_effect
selection_effect
total_effect
```

Each source period contributes one cumulative-prefix row. `from_date` is the first
source date, `thru_date` is the current prefix end, and `quantity_of_days` is the sum
through that prefix. Numerical columns are the compounded prefix values defined
above. `total_effect` equals `geometric_excess_return`.

### `reconciliation`

```text
scope
from_date
thru_date
check
actual
expected
difference
tolerance
passed
```

`scope` and `check` use `string[python]`; dates use `datetime64[ns]`; `actual`,
`expected`, `difference`, and `tolerance` use `float64`; and `passed` uses `bool`.

For every period, record at least:

- identifier allocation sum versus period allocation;
- identifier selection sum versus period selection;
- allocation successive-notional ratio;
- selection successive-notional ratio;
- portfolio-to-benchmark geometric excess; and
- allocation-times-selection total identity.

For every cumulative prefix, record at least:

- compounded portfolio, benchmark, and semi-notional values;
- compounded allocation and selection values;
- cumulative portfolio-to-benchmark geometric excess;
- cumulative allocation and selection successive-notional ratios; and
- cumulative allocation-times-selection total identity.

Every check must pass before returning a result. Reconciliation failure raises
`AttributionError`; the function does not return a partially trusted result with
`passed=False` rows.

## Numerical behavior

Use `float64` throughout and favor `log1p`/`expm1` or stable product helpers where
they materially improve compounding without changing the formulas. Do not branch on
reconciliation tolerance to select a financial formula.

A comparison passes only under the unchanged symmetric relative and absolute rule:

```text
abs(actual - expected)
    <= max(
           reconciliation_tolerance,
           reconciliation_tolerance * max(abs(actual), abs(expected)),
       )
```

Require every non-null returned numeric value and every intermediate ratio to be
finite. Preserve signed zero only incidentally; no schema promise distinguishes it
from zero.

Input returns may approach `-1` from above. Period portfolio, benchmark, and
semi-notional wealth must nevertheless remain strictly positive. Exact `-1`, a value
below `-1`, a non-finite value, or overflow raises `AttributionError` rather than
producing an infinite or complex result.

## Independent fixture requirements

Expected results must be calculated from literal inputs by hand or an independently
documented derivation. Production output, `ppar`, `pybrinson`, and other
implementations may not supply expected values.

The basic fixture should include two identifiers whose allocation and selection have
opposing signs. One useful independent case is:

| Identifier | `wP` | `rP` | `wB` | `rB` |
|---|---:|---:|---:|---:|
| A | `0.60` | `0.12` | `0.50` | `0.08` |
| B | `0.40` | `0.03` | `0.50` | `0.04` |

It gives:

```text
P = 0.084
B = 0.060
N = 0.064
A = 1.064 / 1.060 - 1
S = 1.084 / 1.064 - 1
E = 1.084 / 1.060 - 1
```

Tests must document each identifier numerator and prove both channel sums. Separate
fixtures must cover:

- authoritative contribution differing from the supplied return at nonzero weight;
- portfolio and benchmark zero-weight charges, separately and together;
- a null benchmark effective return with zero portfolio weight;
- rejection of a null benchmark effective return with nonzero portfolio weight;
- missing portfolio and benchmark identifiers;
- cash as an ordinary identifier;
- long, short, leveraged, and zero weights whose side totals remain one;
- exact zero effects and identical portfolio, semi-notional, and benchmark returns;
- one period and multiple periods with gains and losses;
- near-total-loss returns and every nonpositive-wealth rejection;
- deterministic period and identifier reordering;
- complete-horizon period-order invariance; and
- randomized identity checks against formulas written independently in tests.

Nontrivial test cases and formulas require substantive docstrings, comments, or
fixture-provenance notes explaining the financial intent and arithmetic. Merely
restating production code is not independent evidence.

## Compatibility and deliberately deferred behavior

This feature must not change:

- `calculate_attribution` or `AttributionResult`;
- any released `AttributionMethod` or `EffectLinkingMethod` member or default;
- logarithmic contribution linking or arithmetic effect linking;
- any released result-frame schema, value, dtype, null, ordering, or ownership rule;
- hierarchy roll-up; or
- the `ppar` adapter and host presentation schemas.

The following require separate future specifications:

- identifier-level geometric horizon attribution;
- geometric hierarchy roll-up or recalculation;
- a separate geometric interaction effect;
- geometric BHB or another allocation convention;
- Menchero fully geometric attribution;
- currency attribution; and
- direct `ppar` integration.

Do not expose placeholders, enums, columns, or callback hooks for those possibilities.

## Comparative review and provenance

`gghez/pybrinson` was reviewed at commit
`529b0940937caacec3f2a30609b9ce6b86316a7b`. Its geometric module reconstructs a
semi-notional return from an arithmetic result, absorbs interaction into selection,
compounds aggregate allocation and selection channels, and rejects nonpositive
wealth bases. Those ideas are useful confirmation of the method boundary.

This specification independently chooses direct prepared inputs, identifier-level
period effects, cumulative-prefix evidence, and explicit authoritative-contribution
behavior. It deliberately omits identifier-level horizon output rather than treating
aggregate channel compounding as an allocation policy.

The reviewed project is MIT-licensed, but no source, test value, fixture, or prose may
be copied. Primary financial references and independently constructed project
fixtures govern implementation.

Roadmap 11's implementation tests were constructed independently in this repository.
`tests/test_geometric_period.py` starts from literal weights, returns, and
authoritative contributions and documents every nontrivial semi-notional, allocation,
selection, charge, and domain calculation. `tests/test_geometric_cumulative.py`
multiplies literal period wealth independently, cross-checks logarithmic prefixes
against direct products, and deliberately corrupts a period total to prove the public
reconciliation gate. `tests/test_geometric_behavior.py` verifies public schemas,
dtypes, nulls, ordering, ownership, and unchanged arithmetic results. Production
output was never captured as an expectation, and neither `ppar`, `pybrinson`, nor
another package supplied a test value.

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

Comparative implementation and product behavior:

- Eagle Performance, *Geometric Attribution Method*.
  [Method overview][eagle-overview].
- Eagle Performance, *Brinson-Fachler Effects for the Geometric Attribution Method*.
  [Effect formulas][eagle-effects].
- `gghez/pybrinson`, commit
  `529b0940937caacec3f2a30609b9ce6b86316a7b`, reviewed September 6, 2026.

[cfa-history]: https://rpc.cfainstitute.org/research/foundation/2019/performance-attribution
[eagle-overview]: https://eagledocs.atlassian.net/wiki/spaces/Performance2017/pages/856719916
[eagle-effects]: https://eagledocs.atlassian.net/wiki/spaces/Performance2017/pages/856719436
