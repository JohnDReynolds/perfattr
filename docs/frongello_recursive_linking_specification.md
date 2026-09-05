# Frongello Recursive Effect-Linking Specification

**Status:** Accepted September 5, 2026. Public calculation and independent fixture
coverage are implemented.

This document specifies the opt-in Frongello effect-linking contract for
[roadmap 8][roadmap-8]. It supplements the released default
[`specification.md`](specification.md). Every released input, attribution-method,
schema, ownership, validation, and reconciliation rule remains unchanged unless this
document explicitly defines behavior for Frongello effect linking.

[roadmap-8]: ../_extras/perfattr_roadmap_8_frongello_recursive_linking.md

## Methodological identity

Frongello linking converts additive single-period attribution effects into additive
full-horizon effects that reconcile to the arithmetic difference between compounded
portfolio and benchmark returns. It accounts for the path of the portfolio base before
an effect occurs and for subsequent benchmark growth after that effect occurs.

The selected effect linker is independent of the selected single-period
`AttributionMethod`. All four released attribution methods may use either Carino or
Frongello without changing their unlinked period effects.

## Public API

The root package exports this string enum:

```python
class EffectLinkingMethod(str, Enum):
    CARINO = "Carino"
    FRONGELLO = "Frongello"
```

The public calculator becomes:

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

`AttributionResult` appends matching metadata after its released fields:

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

The new argument is keyword-only and accepts only an `EffectLinkingMethod` member.
Passing a string, another enum member, or any other object raises `TypeError` with no
calculation. The default and direct-construction default are Carino.

## Why the policy is specifically effect linking

The released engine has two different linking responsibilities:

- portfolio and benchmark contributions use logarithmic linking; and
- allocation, selection, optional interaction, and total use active-effect linking.

`effect_linking_method` selects only the second responsibility. Portfolio and
benchmark contribution columns continue to use their released logarithmic
coefficients. `linked_active_contribution` remains linked portfolio contribution minus
linked benchmark contribution.

This separation avoids silently changing the meaning of contribution columns and
makes the narrow public policy truthful.

## Inputs and single-period effects

Frongello adds no input column and changes no normalization rule. The released
prepared frames, contribution authority, effective-return behavior, period matching,
universe equalization, weight validation, return limits, and deterministic sorting all
apply unchanged.

The selected `AttributionMethod` first produces the released unlinked allocation,
selection, optional interaction, and total effects. Frongello operates only on those
calculated effects and on total portfolio and benchmark period returns. It does not
reinterpret cash, fees, financing, derivatives, identifiers, or classifications.

Undefined identifier returns remain null only in their released return fields. Their
already-calculated finite effects are linked normally. No return is invented during
linking.

## Notation

For chronological source periods `t = 1, ..., T`:

- `P[t]` is the released total portfolio return in period `t`;
- `B[t]` is the released total benchmark return in period `t`;
- `G[g,c,t]` is the unlinked effect for identifier `g`, channel `c`, and period `t`;
- `c` is allocation, selection, interaction when present, or total; and
- `L[g,c,t]` is the source-period row's full-horizon linked effect.

Period returns and effects are decimal values. Chronology is the deterministic order
already established by normalized `thru_date` and `from_date`.

## Governing Frongello recursion

For one effect series `G[t]`, define the portfolio growth before period `t`:

```text
Q[t] = product(1 + P[s]) for s < t
```

The empty product for the first period is one. Frongello's forward recursion defines
an adjusted increment `F[t]` and a running cumulative linked effect `C[t]`:

```text
C[0] = 0
F[t] = Q[t] * G[t] + B[t] * C[t - 1]
C[t] = C[t - 1] + F[t]
```

The first term places the current effect on the portfolio base accumulated before the
period. The second carries the already-linked effect through the current benchmark
return. The horizon effect is `C[T]`, equivalently `sum(F[t])`.

This formula is applied to each additive effect channel. Summing the channels before
or after recursion gives the same answer because the recurrence is linear.

## Equivalent source-period factor

Unrolling the recursion and grouping the result by the originating `G[t]` gives:

```text
Q[t] = product(1 + P[s]) for s < t
V[t] = product(1 + B[s]) for s > t
K[t] = Q[t] * V[t]

L[g,c,t] = G[g,c,t] * K[t]
```

`V[T]` is the empty product one. This prefix-portfolio, suffix-benchmark factor is
mathematically identical to the complete Frongello recursion:

```text
sum_t(L[g,c,t]) = C[g,c,T]
```

The implementation should calculate the prefix and suffix vectors in linear time and
apply them to the effect arrays. It must not implement an avoidable quadratic loop.

### Why result rows use the equivalent factor

The released `period_detail` frame has one row per source period and identifier, and
its linked columns allocate the selected complete horizon back to those originating
rows. The equivalent factor preserves that meaning.

Displaying `F[t]` instead would book growth of an earlier effect as a new linked amount
in a later period. If an identifier were absent in that later period, the engine would
have to invent a row merely to hold the carry-forward. Roadmap 8 does not change the
row population or turn period detail into a recursive-event ledger.

Thus:

- `period_detail.linked_*_effect` is `L[g,c,t]`, not `F[g,c,t]`;
- `period_summary.linked_*_effect` sums `L[g,c,t]` across identifiers;
- `overall_detail.linked_*_effect` sums `L[g,c,t]` across periods for each identifier;
- `cumulative.cumulative_*_effect` cumulatively sums the source-period `L` values; and
- the final cumulative values equal the full Frongello horizon result.

Intermediate cumulative rows remain partial sums of full-horizon allocations. They
are not independent Frongello calculations ending on each row's date and need not
equal the compounded active return through that intermediate date. This is the same
released cumulative interpretation already used for Carino.

## Full-horizon identity

For the total-effect series summed across identifiers, the released single-period
identity is:

```text
sum_g(G[g,total,t]) = P[t] - B[t]
```

The Frongello factor telescopes, so:

```text
sum_t sum_g(L[g,total,t])
    = product_t(1 + P[t]) - product_t(1 + B[t])
    = compounded_portfolio_return - compounded_benchmark_return
```

The subtraction of one in each compounded return cancels. The same identity must hold
for the sum of the component channels because each channel uses the same `K[t]`.

For two-effect output:

```text
linked_allocation_effect + linked_selection_effect = linked_total_effect
```

For three-effect output:

```text
linked_allocation_effect
    + linked_selection_effect
    + linked_interaction_effect
    = linked_total_effect
```

These identities apply per source row, period summary, identifier horizon, and final
cumulative result subject to the released `1e-12` relative and absolute tolerance.

Because Frongello is linear, the released BF and BHB three-to-two collapse identities
also remain true after linking.

## One-period and ordering behavior

For one period, both empty products equal one:

```text
K[1] = 1
linked effect = unlinked effect
```

Unlike an API that accepts already-separated period-attribution objects, `perfattr`
does not reject a one-period calculation merely because linking is unnecessary.

Frongello effect allocation is order-dependent. Reversing the economic sequence can
change linked allocation, selection, and interaction even though compounded portfolio
and benchmark returns are individually order-independent. Merely permuting caller
rows without changing their dates must not change output; changing which economic
period occurs on which dates can.

## Independent primary-source example

Frongello's two-period example supplies:

| Period | `P` | `B` | Allocation | Selection |
|---|---:|---:|---:|---:|
| 1 | 0.20 | 0.10 | 0.05 | 0.05 |
| 2 | 0.10 | 0.05 | 0.02 | 0.03 |

The factors are:

```text
K[1] = 1.00 * (1 + 0.05) = 1.05
K[2] = (1 + 0.20) * 1.00 = 1.20
```

Therefore the originating-period linked values are:

| Period | Linked allocation | Linked selection | Linked total |
|---|---:|---:|---:|
| 1 | `0.05 * 1.05 = 0.0525` | `0.05 * 1.05 = 0.0525` | `0.1050` |
| 2 | `0.02 * 1.20 = 0.0240` | `0.03 * 1.20 = 0.0360` | `0.0600` |
| Horizon | `0.0765` | `0.0885` | `0.1650` |

The compounded returns are:

```text
portfolio = (1.20 * 1.10) - 1 = 0.3200
benchmark = (1.10 * 1.05) - 1 = 0.1550
active    = 0.3200 - 0.1550   = 0.1650
```

The forward recursion reaches the same allocation total:

```text
F[1] = 1.00 * 0.05 + 0.10 * 0.00   = 0.0500
F[2] = 1.20 * 0.02 + 0.05 * 0.0500 = 0.0265
C[2] = 0.0500 + 0.0265              = 0.0765
```

Its displayed increments differ from the source-period allocations `0.0525` and
`0.0240`, but their horizon sum is identical by construction.

When the two economic periods are reversed, linked allocation is `0.0770` and linked
selection is `0.0880`, while total active return remains `0.1650`. Tests must explain
this arithmetic explicitly rather than obtain expected values from production code.

## Complete prepared-input fixture

The primary example verifies the linker independently of a Brinson calculation. A
second fixture must enter through public `calculate_attribution` with valid prepared
portfolio and benchmark rows, then hand-calculate:

- every unlinked identifier effect from the selected attribution formula;
- each `P[t]`, `B[t]`, prefix, suffix, and `K[t]`;
- every linked identifier effect;
- period summaries, identifier horizon totals, cumulative values, and reconciliation;
- unchanged logarithmically linked contribution values; and
- method and effect-linking metadata.

The completed `tests/fixtures/multi_period_linking/expected_frongello_*.csv` set covers
all five public result frames. `tests/fixtures/README.md` derives the source-period
factors, identifier effects, period and identifier aggregates, cumulative results,
logarithmic contributions, observed-day weights, compounded returns, and
reconciliation expectations. The expectations were written independently of
`perfattr`, `ppar`, `pybrinson`, and every other implementation.

## Authoritative contributions and null behavior

Supplied contributions remain authoritative before effects are calculated. Frongello
does not attempt to reconstruct them as weight multiplied by return.

A zero-weight, nonzero-contribution row retains its released null effective return and
finite effect values. Those effects are multiplied by the ordinary finite `K[t]`.
Frongello creates no new null linked values. Cash and exposed financing likewise use
ordinary effect values and ordinary factors.

An identifier absent from a source period retains the released row behavior. It does
not receive a synthetic row for benchmark carry-forward. Any effect originating in an
earlier period receives subsequent benchmark growth through that earlier row's
suffix factor.

## Numerical and error behavior

Roadmap 8 preserves the released requirement that every period and compounded horizon
return be finite and greater than `-1`. Frongello's multiplication does not justify
relaxing that shared input contract because contribution linking still uses logarithms.

Prefix, suffix, factor, linked-effect, aggregation, and reconciliation values must be
finite. A non-finite value raises `AttributionError`; it must not be replaced by zero,
clipped, or hidden as a residual.

Products should be accumulated in chronological `float64` operations consistent with
the existing NumPy engine. Numerical comparisons use the unchanged `1e-12` relative
and absolute tolerance. No test tolerance may be widened to accommodate an
implementation defect.

## Schemas, ownership, and compatibility

No result-frame column is added, removed, renamed, reordered, or reinterpreted beyond
the selected meaning already conveyed by the generic `linked_*_effect` names. All
released dtypes, null placement, deterministic row ordering, zero-based `RangeIndex`,
and independent ownership guarantees remain in force.

Default calls must be exactly compatible with `perfattr==0.6.0a1`. This includes
unlinked and linked numerical values, errors, all five frames, method metadata, and
reconciliation evidence. The only additional observable state is
`result.effect_linking_method == EffectLinkingMethod.CARINO`.

Changing from Carino to Frongello may change linked effect values by row, period,
identifier, and component. It must not change inputs, unlinked effects, contribution
columns, compounded returns, schemas, or final active-return reconciliation.

## `ppar` compatibility

`ppar` does not pass `effect_linking_method`, so it remains on default Carino. Roadmap
8 adds no `ppar` option, schema, audit field, report label, or presentation behavior.
The complete `ppar` release-candidate and unchanged 500x gates are nevertheless
required because the shared result object and calculation signature change.

## Test requirements

In addition to the roadmap matrix, tests must prove:

- the primary values above and the recurrence/factor equivalence;
- the exact source-period rather than recursive-increment display convention;
- a disappearing identifier receives no invented row but retains later benchmark
  growth in its originating row's linked value;
- one-period identity and chronological order dependence;
- unchanged logarithmic contribution columns under both effect linkers;
- identical final cumulative active contribution and linked total effect, within
  tolerance, despite possibly different intermediate cumulative values;
- all four attribution methods work with both enum members;
- Carino is the default at the function and result-construction boundaries;
- invalid enum inputs fail before any financial calculation;
- finite guards cover long positive paths and returns near but above `-1`; and
- randomized valid inputs supplement but never replace hand-calculated expectations.

Test modules, fixture provenance, and non-obvious helper docstrings must explain the
formula, expected arithmetic, financial interpretation, ordering, and edge cases.

## Performance contract

Correctness comes first. The implementation should require two `O(T)` factor passes
and vector multiplication over the existing effect rows. It must not add a row-wise
pandas callback, quadratic period loop, second attribution engine, expanded
period/identifier grid, or runtime dependency.

Measure elapsed time and peak memory for both effect linkers across all four
attribution methods on the established realistic direct-core workloads. Establish no
new threshold until correct, repeatable evidence exists. All existing gates remain
unchanged.

## Relationship to GRAP

Unrolling Frongello's recursion produces the same prefix-portfolio,
suffix-benchmark full-horizon factor commonly associated with GRAP. Therefore, at
`perfattr`'s specified source-period full-horizon boundary, a future GRAP policy would
have identical numerical output.

Roadmap 3 must not promote GRAP merely to duplicate this calculation. A future
proposal must first establish concrete value in separate method identity, provenance,
or a materially different approved presentation.

## References and provenance

Primary methodology:

- Frongello, Andrew S. B. “Linking Single Period Attribution Results.” *The Journal
  of Performance Measurement* 6, no. 3 (Spring 2002): 10–22.
  [Author-hosted PDF](https://frongello.com/support/Works/JPMSpring2002.pdf).
- Frongello, Andrew S. B. “Attribution Linking: Proofed and Clarified.” *The Journal
  of Performance Measurement* 7, no. 1 (Fall 2002): 54–67.
  [Author-hosted PDF](https://frongello.com/support/Works/JPMFall2002.pdf).

The Fall paper is the governing source for the recursion, proof, order dependence,
and numerical examples. The Spring paper is the original presentation.

Comparative review:

- [`gghez/pybrinson`](https://github.com/gghez/pybrinson/), reviewed at commit
  `529b0940937caacec3f2a30609b9ce6b86316a7b` on September 5, 2026.

That review helped identify the Frongello/GRAP full-horizon equivalence and the value
of primary-source regression fixtures. `pybrinson` returns horizon totals rather than
`perfattr`'s period and identifier frames, so it does not govern this specification's
source-period presentation. No code, test data, expected value, or documentation text
is copied from it.

A targeted public patent search identified no Frongello-specific claim. This is not a
legal opinion. The implementation must be written independently from the published
mathematics and distributed under `perfattr`'s MIT license.
