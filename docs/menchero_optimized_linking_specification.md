# Menchero Optimized Effect-Linking Specification

**Status:** Accepted and implemented September 6, 2026. Prepared for initial release
in `perfattr==0.8.0a1`.

This document specifies the opt-in Menchero optimized effect-linking contract for
[roadmap 9][roadmap-9]. It supplements the released default
[`specification.md`](specification.md) and the existing effect-linking boundary. Every
released input, attribution-method, schema, ownership, validation, and reconciliation
rule remains unchanged unless this document explicitly defines Menchero behavior.

[roadmap-9]: ../_extras/perfattr_roadmap_9_menchero_optimized_linking.md

## Methodological identity

Menchero optimized linking converts additive single-period attribution effects into
additive complete-horizon effects. It applies one common scale plus a least-squares
period correction so that the linked effects reconcile to the arithmetic difference
between compounded portfolio and benchmark returns.

This contract selects the optimized arithmetic **period-coefficient** method presented
by Menchero (2000). It does not implement:

- Menchero's separate fully geometric attribution method;
- the later quadratic, component-level metric-preserving coefficient extension;
- geometric excess return or multiplicative effect schemas; or
- a generic optimization or linking framework.

The selected effect linker remains independent of the selected single-period
`AttributionMethod`. All four released attribution methods may use Carino, Frongello,
or Menchero without changing their unlinked period effects.

## User problem

Some clients and established reporting systems require Menchero's order-independent,
minimum-correction treatment of the compounding residual. Carino and Frongello already
close the same complete-horizon identity, but distribute effects differently. GRAP
adds no distinct numerical result at `perfattr`'s boundary; Menchero does.

## Public API

Extend the released string enum by one member:

```python
class EffectLinkingMethod(str, Enum):
    CARINO = "Carino"
    FRONGELLO = "Frongello"
    MENCHERO = "Menchero"
```

The released keyword-only `effect_linking_method` argument and matching
`AttributionResult.effect_linking_method` metadata remain unchanged. The new member
must be exported from `perfattr.method` and the root package.

The argument continues to accept only an `EffectLinkingMethod` member. Strings,
members of other enums, and arbitrary objects raise `TypeError`. Carino remains the
default for calculation and direct result construction.

## Why the policy remains effect linking

The engine has two separate linking responsibilities:

- portfolio and benchmark contributions use released logarithmic linking; and
- allocation, selection, optional interaction, and total use the selected
  active-effect linker.

Menchero selects only the second responsibility. It does not change linked portfolio
or benchmark contributions, and `linked_active_contribution` remains their difference.
The generic `linked_*_effect` columns already accommodate the selected effect policy.

## Inputs and single-period effects

Menchero adds no input column and changes no normalization rule. Prepared inputs,
contribution authority, effective-return behavior, period matching, universe
equalization, weight validation, return limits, and deterministic sorting remain
unchanged.

The selected `AttributionMethod` first produces the released unlinked allocation,
selection, optional interaction, and total effects. Menchero operates only on those
finite effects and total portfolio and benchmark period returns. It does not
reinterpret identifiers, cash, fees, financing, derivatives, or classifications.

## Notation

For chronological source periods `t = 1, ..., T`:

- `P[t]` is the released total portfolio return in period `t`;
- `B[t]` is the released total benchmark return in period `t`;
- `d[t] = P[t] - B[t]` is the single-period active return;
- `P[H] = product_t(1 + P[t]) - 1` is the portfolio horizon return;
- `B[H] = product_t(1 + B[t]) - 1` is the benchmark horizon return;
- `D = P[H] - B[H]` is the horizon arithmetic active return;
- `G[g,c,t]` is an unlinked effect for identifier `g` and channel `c`;
- `K[t]` is the Menchero coefficient for period `t`; and
- `L[g,c,t] = G[g,c,t] * K[t]` is the linked source-period effect.

Channel `c` is allocation, selection, interaction when present, or total. Returns and
effects are decimal values.

## Governing optimized coefficients

Define the common scale `M`:

```text
M = (D / T)
    / ((1 + P[H]) ** (1 / T) - (1 + B[H]) ** (1 / T))
```

when `P[H] != B[H]`. Its continuous equal-return limit is:

```text
M = (1 + P[H]) ** ((T - 1) / T)       when P[H] = B[H]
```

The common scale captures the characteristic growth across the complete horizon. It
does not generally eliminate the entire compounding residual. Define:

```text
E = D - M * sum_t(d[t])
Q = sum_t(d[t] ** 2)
```

When `Q > 0`, the minimum-squared correction and final period coefficient are:

```text
alpha[t] = E * d[t] / Q
K[t]     = M + alpha[t]
```

When `Q = 0`, every `d[t]` is exactly zero, `D` and `E` are zero, and the unique
minimum-norm correction is:

```text
alpha[t] = 0
K[t]     = M
```

The same `K[t]` multiplies every identifier and every effect channel in period `t`.
Do not optimize or redistribute individual effect channels separately.

### Why the correction is optimized

The corrections solve:

```text
minimize sum_t(alpha[t] ** 2)

subject to
sum_t((M + alpha[t]) * d[t]) = D
```

The least-squares solution is the formula above. It changes the common scale only as
much as needed to remove the residual while preserving one coefficient per period.

## Stable evaluation of the common scale

Directly subtracting nearly equal horizon roots can turn the published expression
into an inaccurate `0 / 0`. A tolerance branch based on `abs(D)` would also introduce
an arbitrary discontinuity.

Let:

```text
x = (1 + P[H]) ** (1 / T)
y = (1 + B[H]) ** (1 / T)
```

The difference-of-powers identity gives the mathematically equivalent continuous
form:

```text
M = mean(x ** (T - 1 - j) * y ** j for j = 0, ..., T - 1)
```

This expression equals the published quotient when `x != y` and equals `x ** (T-1)`
when `x = y`. The implementation should evaluate the positive terms from accumulated
log growth with a scaled or log-space mean. It must not decide that horizon returns
are equal merely because their difference falls below the reconciliation tolerance.

The correction denominator should likewise use a scaled Euclidean norm so finite
large active returns do not overflow merely when squared. A genuinely non-finite
coefficient or linked effect still raises `AttributionError`.

## Equal horizon returns do not imply zero corrections

When `P[H] = B[H]`, only the common-scale quotient takes its equal-return limit. The
period corrections are zero only when `E` is zero. Period paths can compound to the
same horizon return while `sum(d[t])` is nonzero, in which case nonzero corrections
are required for reconciliation.

For example:

| Period | `P[t]` | `B[t]` | `d[t]` |
|---|---:|---:|---:|
| 1 | `0.20` | `0.00` | `0.20` |
| 2 | `-0.10` | `0.08` | `-0.18` |

Both sides compound to `0.08`, but the arithmetic active returns sum to `0.02`.
Therefore:

```text
M        = 1.08 ** 0.5
         = 1.0392304845413264
alpha[1] = -0.0574160488696866
alpha[2] =  0.0516744439827179
K[1]     =  0.9818144356716398
K[2]     =  1.0909049285240443
```

Then `K[1] * 0.20 + K[2] * -0.18` is zero within `float64` precision, matching the
zero horizon active return. An implementation that sets every `alpha[t]` to zero
whenever the horizon returns match would fail this valid case.

## Source-period and cumulative interpretation

Each `period_detail.linked_*_effect` value remains the originating source-period
effect allocated to the selected complete horizon:

```text
L[g,c,t] = G[g,c,t] * K[t]
```

The released aggregation pipeline remains unchanged:

- `period_summary` sums linked identifier rows within each period;
- `overall_detail` sums linked source-period rows for each identifier;
- `cumulative` cumulatively sums the complete-horizon source allocations; and
- the final cumulative row equals the Menchero horizon result.

Intermediate cumulative rows are partial sums of complete-horizon allocations, not
independently relinked as-of calculations. An identifier absent from a later period
does not receive a synthetic row.

## Financial identities

The released single-period total-effect identity is:

```text
sum_g(G[g,total,t]) = d[t]
```

The optimized corrections give:

```text
sum_t(K[t] * d[t])
    = M * sum_t(d[t]) + E
    = D
```

Therefore:

```text
sum_t sum_g(L[g,total,t])
    = compounded_portfolio_return - compounded_benchmark_return
```

Because one coefficient multiplies every channel in a period, the released two- and
three-effect component identities remain true per source row, period summary,
identifier horizon, and final cumulative result within the unchanged `1e-12` relative
and absolute tolerance.

## One-period and order behavior

For `T = 1`, the continuous common scale is one, the residual is zero, and:

```text
K[1] = 1
linked effect = unlinked effect
```

The public calculator continues to accept a one-period Menchero request, matching the
released Carino and Frongello behavior.

Menchero coefficients are commutative across time. Reordering complete economic
periods leaves `P[H]`, `B[H]`, `M`, `E`, and `Q` unchanged; each period retains the
coefficient determined by its own `d[t]`. Consequently, complete-horizon identifier
and effect totals are unchanged when dates and all corresponding facts are permuted
together. Caller row order without changed dates already remains irrelevant.

This deliberate property distinguishes Menchero from path-dependent Frongello.

## Primary-source regression example

The identified patent record reproduces Menchero's six-period example:

| Period | `P[t]` | `B[t]` | Issue selection | Sector selection |
|---|---:|---:|---:|---:|
| 1 | `0.10` | `0.05` | `0.02` | `0.03` |
| 2 | `0.25` | `0.15` | `0.09` | `0.01` |
| 3 | `0.10` | `0.20` | `-0.02` | `-0.08` |
| 4 | `-0.10` | `0.10` | `-0.13` | `-0.07` |
| 5 | `0.05` | `-0.08` | `0.03` | `0.10` |
| 6 | `0.15` | `-0.05` | `0.10` | `0.10` |

Independent decimal calculation from those inputs gives:

```text
P[H] = 0.643709375
B[H] = 0.393068600
D    = 0.250640775
M    = 1.4138296690053345
```

The period coefficients are:

```text
K = [
    1.4122180419446309,
    1.4106064148839273,
    1.4170529231267417,
    1.4202761772481490,
    1.4096394386475051,
    1.4073831607625201,
]
```

They link issue selection to `0.1252494759093290` and sector selection to
`0.1253912990906710`, summing to `0.250640775`. Tests must reproduce these values
from literal inputs and independently explained arithmetic, not capture production
output.

## Authoritative contributions and null behavior

Supplied contributions remain authoritative before effects are calculated. Menchero
does not reconstruct them as weight multiplied by return.

A zero-weight, nonzero-contribution row retains its released null effective return and
finite effect values. Its already-calculated effects use the ordinary period
coefficient. Cash and exposed financing likewise receive no special linking treatment.
Menchero creates no new null linked-effect values.

## Numerical and error behavior

Every period and compounded horizon return remains finite and greater than `-1` under
the released contract. Menchero does not relax this requirement because contribution
linking still uses logarithms and the common scale requires positive growth bases.

Common-scale terms, active differences, residual, norm, corrections, coefficients,
linked effects, aggregates, and reconciliation values must be finite. A non-finite
value raises `AttributionError`; it must not be clipped, replaced by zero, or hidden in
a residual. Finite negative coefficients are permitted because the methodology does
not define coefficient positivity as an input-validation rule.

Exact mathematical degeneracy uses exact structural checks such as a zero scaled norm.
The `reconciliation_tolerance` must not select a different financial formula.
Numerical comparisons retain the unchanged `1e-12` relative and absolute tolerance.

## Schemas, ownership, and compatibility

No result-frame column is added, removed, renamed, reordered, or reinterpreted beyond
the selected meaning already conveyed by the generic linked-effect names. Released
dtypes, null placement, deterministic row ordering, zero-based `RangeIndex`, and
independent ownership guarantees remain in force.

Omitted and explicit Carino calls must remain exactly compatible with
`perfattr==0.7.0a1`. Frongello values and behavior must also remain unchanged. Selecting
Menchero may change only linked and cumulative effect values plus the explicit result
metadata; it must not change unlinked effects, contributions, returns, schemas, or
reconciliation names.

## `ppar` compatibility

`ppar` currently omits `effect_linking_method`, so it remains on default Carino.
Roadmap 9 adds no `ppar` selector, schema, audit field, report label, or presentation
behavior. The complete `ppar` release-candidate and unchanged 500x gates remain
required because the shared public enum changes.

## Test requirements

In addition to the roadmap matrix, tests must prove:

- the six-period primary-source coefficients and linked totals above;
- the stable common-scale form agrees with the published quotient away from equality;
- exact and near-equal horizon returns remain finite and continuous;
- equal horizon returns with nonzero period corrections reconcile correctly;
- an all-zero active-return vector uses the minimum-norm zero correction even when
  component effects offset within each period;
- one-period identity and complete-period permutation invariance;
- Menchero and Frongello differ on a deliberately path-sensitive fixture;
- all four attribution methods retain their component and collapse identities;
- logarithmically linked contribution columns remain unchanged;
- cash, authoritative contribution, null effective return, disappearing identifier,
  signed-weight, and near-`-1` cases retain released behavior;
- invalid enum inputs fail before financial calculation;
- default Carino and opt-in Frongello output remain unchanged;
- input nonmutation, deterministic order, and independent result ownership hold; and
- randomized valid inputs supplement but never replace hand-calculated expectations.

Every nontrivial fixture and test must explain the formula, expected arithmetic,
financial interpretation, and edge condition in comments or docstrings.

## Performance contract

Correctness comes first. Menchero requires `O(T)` coefficient work and one vector
multiplication over existing effect rows. Stable evaluation must not introduce a
quadratic period loop, row-wise pandas callback, expanded identifier grid, second
attribution engine, or runtime dependency.

Measure elapsed time and peak memory for all three effect linkers across all four
attribution methods on the established direct-core workloads. Establish no new
threshold before correct, repeatable evidence exists. All released gates remain
unchanged.

## Comparative `pybrinson` review

`gghez/pybrinson` was reviewed at commit
`529b0940937caacec3f2a30609b9ce6b86316a7b`. Its implementation reinforced the value
of a separate Menchero identity, a primary patent-status gate, one coefficient per
period, and cross-linker reconciliation tests.

This specification deliberately does not adopt its one-period rejection or its
near-zero horizon-active shortcut. The released `perfattr` calculator already defines
one-period linking as the identity. More importantly, matching compounded returns can
still require nonzero period corrections, as the equal-horizon example above proves.

No `pybrinson` code, test value, fixture, or documentation text is copied. Primary
methodology and patent records govern this proposal.

## References, intellectual property, and provenance

Primary methodology:

- Menchero, José G. “An Optimized Approach to Linking Attribution Effects over Time.”
  *The Journal of Performance Measurement* 5, no. 1 (Fall 2000): 36–42.
- Menchero, José G. “Multiperiod Arithmetic Attribution.” *Financial Analysts
  Journal* 60, no. 4 (2004): 76–91.
  [DOI](https://doi.org/10.2469/faj.v60.n4.2638).

The 2000 paper establishes the selected optimized period coefficients. The 2004 paper
provides a broader framework for evaluating multiperiod arithmetic linking. The
formula and worked example are also disclosed in the inventor's patent record:

- [US 7,249,079 B1](https://patents.google.com/patent/US7249079B1/en), “Method and
  system for multi-period performance attribution.”
- [US 7,246,091 B1](https://patents.google.com/patent/US7246091B1/en), related
  continuation-in-part.
- [US 7,249,082 B2](https://patents.google.com/patent/US7249082B2/en), later
  metric-preserving continuation-in-part.

The public records currently label these US patents `Expired - Lifetime`, with listed
expiration dates of January 26, 2023; December 31, 2022; and February 18, 2024,
respectively. Google Patents warns that its legal status is an assumption rather than
a legal conclusion. This targeted review found no active member in the displayed
US/AU/WO family, but it is not a legal opinion or a worldwide freedom-to-operate
determination. Recheck the records immediately before merging implementation and
before publication; stop if the status is no longer clear.

Implementation and expected values must be independently derived from disclosed
mathematics. Do not copy source or fixtures from another package. Record fixture
provenance and distribute original project work under the existing MIT license.
