# Brinson-Hood-Beebower Three-Effect Attribution Specification

**Status:** Accepted and implemented September 5, 2026. Initially released in
`perfattr==0.5.0a1`.

This document specifies the opt-in Brinson-Hood-Beebower (BHB) three-effect contract
for [roadmap 6][roadmap-6]. It supplements the released default
[`specification.md`](specification.md) and Brinson-Fachler three-effect
[specification][bf-spec]. Every released rule remains unchanged unless this document
explicitly defines behavior for the new BHB method.

[roadmap-6]: ../_extras/perfattr_roadmap_6_brinson_hood_beebower_three_effect.md
[bf-spec]: brinson_fachler_three_effect_specification.md

## User problem

The released methods use Brinson-Fachler allocation, which evaluates an active weight
against the group's benchmark return relative to the total benchmark return. Some
users require the original BHB decomposition, where allocation evaluates the same
active weight against the group's absolute benchmark return.

The opt-in method provides that convention explicitly. It does not silently reinterpret
either released BF method or claim that one convention is universally preferable.

## Public API

The released string enum exposes one BHB value:

```python
class AttributionMethod(str, Enum):
    BRINSON_FACHLER_TWO_EFFECT = "Brinson-Fachler Two-Effect"
    BRINSON_FACHLER_THREE_EFFECT = "Brinson-Fachler Three-Effect"
    BRINSON_HOOD_BEEBOWER_THREE_EFFECT = "Brinson-Hood-Beebower Three-Effect"
```

Callers select it through the released keyword-only argument:

```python
result = calculate_attribution(
    portfolio,
    benchmark,
    method=AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
)
```

The default remains `BRINSON_FACHLER_TWO_EFFECT`. Strict enum validation,
`AttributionResult.method`, and existing five-argument result construction do not
change.

## Input contract

BHB uses the released prepared input contract without new columns or different
validation. Supplied contribution remains authoritative. When contribution is absent,
it is derived as weight multiplied by return.

The normalized effective return remains:

```text
contribution / weight    when weight is nonzero
0                        when weight and contribution are both zero
null                     when weight is zero and contribution is nonzero
```

The calculation does not infer security type, cash, fees, financing, derivatives, or
classification meaning from identifier text.

## Notation

For identifier `g` in reporting period `t`:

- `wP[g,t]` and `wB[g,t]` are portfolio and benchmark weights;
- `rP[g,t]` and `rB[g,t]` are normalized effective returns;
- `cP[g,t]` and `cB[g,t]` are authoritative contributions;
- `P[t] = sum(cP[g,t])` and `B[t] = sum(cB[g,t])`;
- `AW[g,t] = wP[g,t] - wB[g,t]`; and
- `AR[g,t] = rP[g,t] - rB[g,t]` when both effective returns are defined.

Universe equalization, missing-side behavior, weight checks, finite-value rules, and
tolerances remain governed by the released specifications.

## BHB three-effect policy

When the benchmark effective return is defined, BHB allocation is:

```text
A_BHB[g,t] = AW[g,t] * rB[g,t]
```

Unlike BF allocation, this uses zero—not the total benchmark return—as its reference
return. Consequently, overweighting a positive-return group produces positive BHB
allocation even when that group underperforms the total benchmark. The signed formula
is authoritative; `perfattr` does not label an effect favorable or unfavorable.

The BHB identifier-level total is unadjusted active contribution:

```text
T_BHB[g,t] = cP[g,t] - cB[g,t]
```

When both effective returns are defined, interaction is calculated directly:

```text
I_BHB[g,t] = AW[g,t] * AR[g,t]
```

Selection is the exact reconciliation residual:

```text
S_BHB[g,t] = T_BHB[g,t] - A_BHB[g,t] - I_BHB[g,t]
```

Because defined effective returns satisfy `cP = wP * rP` and
`cB = wB * rB`, the residual is algebraically equivalent to:

```text
S_BHB[g,t] = wB[g,t] * AR[g,t]
```

The residual calculation is normative because it preserves authoritative accounting
facts and avoids an additional floating-point reconciliation path. The direct formula
is an independently tested identity, not a second production calculation.

For every ordinary defined-return row:

```text
A_BHB + S_BHB + I_BHB = T_BHB
```

## Undefined effective returns

If `rB[g,t]` is null, BHB allocation is zero rather than an invented benchmark return.
If either effective return is null, active return is null and interaction is zero.
Selection retains the exact residual:

```text
A_BHB = 0                              when rB is undefined
I_BHB = 0                              when rP or rB is undefined
S_BHB = T_BHB - A_BHB - I_BHB
```

These are disclosed boundary conventions, not claims that the unavailable economic
effects are known to be zero. They preserve zero-weight authoritative charges, keep
all effect columns finite, and avoid a fourth residual channel. Return columns retain
their released null placement.

## Relationship to Brinson-Fachler

For a row with defined `rB`:

```text
A_BHB - A_BF = AW * B
T_BHB - T_BF = AW * B
```

When `rB` is defined, BHB and BF allocation and total shift by the same amount,
interaction follows the same direct-or-zero policy, and therefore:

```text
S_BHB = S_BF_three_effect
I_BHB = I_BF_three_effect
```

If both weight vectors sum exactly to one, `sum(AW) = 0`; BHB and BF always have equal
period total-effect sums even though their identifier values differ. Their period
allocation sums are also equal when every benchmark effective return is defined. For
accepted weights that are merely within the released normalization tolerance, only
the ordinary reconciliation tolerance is promised—no hidden renormalization is
introduced.

The equalities for allocation and selection do not apply when their required effective
returns are undefined. Each method follows its documented residual convention.

## Independent single-period example

Use the same two-group inputs as the released BF three-effect example so the
methodological difference is directly visible:

| Group | `wP` | `wB` | `rP` | `rB` |
|---|---:|---:|---:|---:|
| A | 0.70 | 0.40 | 0.10 | 0.06 |
| B | 0.30 | 0.60 | 0.02 | 0.02 |

The portfolio return is `0.076`, benchmark return is `0.036`, and active return is
`0.040`. BHB produces:

| Group | Allocation | Selection | Interaction | Total |
|---|---:|---:|---:|---:|
| A | 0.0180 | 0.0160 | 0.0120 | 0.0460 |
| B | -0.0060 | 0.0000 | 0.0000 | -0.0060 |
| Total | 0.0120 | 0.0160 | 0.0120 | 0.0400 |

For A, allocation is `0.30 * 0.06 = 0.0180`; selection is
`0.40 * (0.10 - 0.06) = 0.0160`; interaction is
`0.30 * (0.10 - 0.06) = 0.0120`; and total is
`0.70 * 0.10 - 0.40 * 0.06 = 0.0460`.

The released BF example assigns allocation `0.0072` and total `0.0352` to A. Both BHB
values exceed their BF counterparts by `0.30 * 0.036 = 0.0108`. Group B differs by
`-0.0108`, so the period totals agree. These values are derived here by hand and must
not be generated from production output or another implementation.

## Multi-period linking

Portfolio and benchmark contributions retain logarithmic linking. BHB allocation,
selection, interaction, and total each use the released Carino active coefficient
`LA[t]`:

```text
linked_allocation_effect  = A_BHB[g,t] * LA[t]
linked_selection_effect   = S_BHB[g,t] * LA[t]
linked_interaction_effect = I_BHB[g,t] * LA[t]
linked_total_effect       = T_BHB[g,t] * LA[t]
```

Applying one coefficient to every additive component preserves:

```text
linked_allocation_effect
+ linked_selection_effect
+ linked_interaction_effect
= linked_total_effect
```

The released Carino limits, finite checks, and greater-than-minus-one return
requirements do not change. Although BHB period `total_effect` equals period active
contribution, `linked_total_effect` need not equal `linked_active_contribution` by
identifier because those columns use different released linking allocations.

## Result schemas

BHB reuses every released three-effect schema exactly:

- `period_detail` and `period_summary` include `interaction_effect` immediately after
  `selection_effect` and `linked_interaction_effect` immediately after
  `linked_selection_effect`;
- `overall_detail` includes `linked_interaction_effect` immediately after
  `linked_selection_effect`;
- `cumulative` includes both linked interaction and cumulative interaction in their
  released three-effect positions; and
- `reconciliation` uses the released `three_effect_components` and
  `linked_three_effect_components` check names.

No column is added, removed, renamed, reordered, or assigned a different dtype.
`AttributionResult.method` makes the schema's financial policy explicit. Rows retain
deterministic ordering and `RangeIndex`; every frame remains newly allocated and
caller-owned.

## Reconciliation identities

In addition to all released weight, contribution, and active-return checks, BHB
enforces:

```text
sum(A_BHB + S_BHB + I_BHB) = sum(T_BHB) = P[t] - B[t]

sum(linked_allocation_effect
    + linked_selection_effect
    + linked_interaction_effect)
    = sum(linked_total_effect)
    = compounded_portfolio_return - compounded_benchmark_return
```

The relative and absolute tolerance remains `1e-12`. Failure raises
`AttributionError`; no partial result is returned.

Cross-method identities belong in independent tests rather than redundant production
reconciliation rows. Production reconciliation remains focused on the selected
method's conservation rules.

## Error behavior

The new enum value introduces no new error category. Invalid method objects retain the
released `TypeError`; all input, period, linking, finite-value, and reconciliation
errors remain unchanged. Selecting BHB never converts an error into a warning or
partial result.

## `ppar` compatibility

`ppar` continues to omit the `method` argument and therefore receives the unchanged
default BF two-effect result. Roadmap 6 does not add a BHB selector, schema, or
presentation behavior to `ppar`.

The candidate wheel must nevertheless pass `ppar`'s complete release-candidate and
unchanged 500x gates. Later BHB exposure in `ppar` requires separate product, API,
schema, presentation, and release approval.

## Test and documentation requirements

Expected values must be calculated independently by hand and explained in test
docstrings and comments. Required cases include:

- the distinguishing BHB/BF table above;
- positive, negative, and zero allocation and interaction;
- authoritative contributions that differ from supplied-return products;
- zero-weight nonzero-contribution rows with null effective returns;
- identifiers missing from either side and signed weights;
- exact BF two-effect and three-effect preservation;
- BHB/BF identifier and period-level identities;
- single and multiple periods, including equal and near-equal Carino returns;
- returns near, but greater than, `-1`;
- exact three-effect schema and reconciliation-name reuse;
- deterministic input permutations;
- caller-input nonmutation and independent result ownership; and
- randomized valid inputs used only for invariants, never expected-value generation.

Nontrivial calculations and tests must document financial purpose, formulas,
assumptions, undefined-return behavior, and numerical limits under `AGENTS.md`.

## Performance contract

Correctness comes first. Measure all three methods on the established realistic
direct-core workloads, including elapsed time and peak memory. BHB should reuse the
existing vectorized calculation and three-effect aggregation path; no second engine,
row-wise loop, or new dependency is permitted.

No new threshold is established by this proposal. Existing gates remain unchanged.

## References and provenance

Primary methodology:

- Brinson, Gary P., L. Randolph Hood, and Gilbert L. Beebower. “Determinants of
  Portfolio Performance.” *Financial Analysts Journal* 42, no. 4 (July–August 1986):
  39–44. [doi:10.2469/faj.v42.n4.39](https://doi.org/10.2469/faj.v42.n4.39).

The publisher record and the paper's CFA/AIMR 1995 reprint were reviewed on September
5, 2026. The original paper names the components timing, security selection, and
“other”; its tables define the third component as the active-weight/active-return
cross-product. This specification uses the now-common allocation, selection, and
interaction labels while retaining that algebra.

Comparative design review:

- [`gghez/pybrinson`](https://github.com/gghez/pybrinson/), reviewed at commit
  `529b0940937caacec3f2a30609b9ce6b86316a7b` on September 5, 2026.

That review supports a distinct BHB method identity, a shared three-effect result
shape, explicit conservation checks, and cross-method invariant tests. It does not
govern `perfattr`'s API, authoritative-contribution rules, null policy, or tolerance.
No source code, fixtures, expected values, or documentation text is copied.
