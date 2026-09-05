# Brinson-Hood-Beebower Two-Effect Reporting Specification

**Status:** Accepted and implemented September 5, 2026. Initially released in
`perfattr==0.6.0a1`.

This document specifies an opt-in compact Brinson-Hood-Beebower (BHB) reporting
contract for [roadmap 7][roadmap-7]. It supplements the released default
[`specification.md`](specification.md) and released BHB three-effect
[specification][bhb-three-spec]. Every released rule remains unchanged unless this
document explicitly defines behavior for the new method.

[roadmap-7]: ../_extras/perfattr_roadmap_7_brinson_hood_beebower_two_effect.md
[bhb-three-spec]: brinson_hood_beebower_three_effect_specification.md

## Methodological identity

The method retains BHB allocation but reports only allocation and selection.
Selection absorbs interaction using the same portfolio-weighted convention already
used by the default BF two-effect method.

This is a derived `perfattr` reporting convention. The original BHB methodology
separates timing, security selection, and a cross-product term; this specification
does not rename that historical three-component presentation as a two-effect model.
The explicit enum identity prevents compact BHB output from being mistaken for the
default compact BF method.

## Public API

The public string enum includes the compact BHB member:

```python
class AttributionMethod(str, Enum):
    BRINSON_FACHLER_TWO_EFFECT = "Brinson-Fachler Two-Effect"
    BRINSON_FACHLER_THREE_EFFECT = "Brinson-Fachler Three-Effect"
    BRINSON_HOOD_BEEBOWER_THREE_EFFECT = "Brinson-Hood-Beebower Three-Effect"
    BRINSON_HOOD_BEEBOWER_TWO_EFFECT = "Brinson-Hood-Beebower Two-Effect"
```

Callers select it explicitly:

```python
result = calculate_attribution(
    portfolio,
    benchmark,
    method=AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
)
```

The default remains `BRINSON_FACHLER_TWO_EFFECT`. The argument remains keyword-only
and accepts only an `AttributionMethod` member. `AttributionResult.method` records the
selected convention.

## Input and normalization contract

The method uses the released prepared inputs, validation, universe equalization,
weight tolerance, effective-return normalization, and contribution authority without
new columns or exceptions.

Supplied contribution remains authoritative. Otherwise it is derived as weight times
return. The normalized effective return remains:

```text
contribution / weight    when weight is nonzero
0                        when weight and contribution are both zero
null                     when weight is zero and contribution is nonzero
```

The method never infers cash, fee, financing, derivative, or classification meaning
from identifier text.

## Notation

For identifier `g` in reporting period `t`:

- `wP[g,t]` and `wB[g,t]` are portfolio and benchmark weights;
- `rP[g,t]` and `rB[g,t]` are normalized effective returns;
- `cP[g,t]` and `cB[g,t]` are authoritative contributions;
- `P[t] = sum(cP[g,t])` and `B[t] = sum(cB[g,t])`;
- `AW[g,t] = wP[g,t] - wB[g,t]`; and
- `AR[g,t] = rP[g,t] - rB[g,t]` when both returns are defined.

## Period-effect policy

When the benchmark effective return is defined, BHB allocation is:

```text
A_BHB2[g,t] = AW[g,t] * rB[g,t]
```

This evaluates an active weight against the group's absolute benchmark return. It is
not the BF allocation opportunity-cost calculation relative to `B[t]`.

Identifier-level total is unadjusted active contribution:

```text
T_BHB2[g,t] = cP[g,t] - cB[g,t]
```

Selection is the exact reconciliation residual:

```text
S_BHB2[g,t] = T_BHB2[g,t] - A_BHB2[g,t]
```

When effective returns are defined and contributions equal weight times effective
return, that residual is algebraically:

```text
S_BHB2[g,t] = wP[g,t] * AR[g,t]
```

The direct portfolio-weighted expression is an independently tested identity, not a
second production calculation.

### Undefined effective returns

If `rB[g,t]` is null, allocation is zero. Selection retains all authoritative total
not assigned to allocation:

```text
A_BHB2 = 0                  when rB is undefined
S_BHB2 = T_BHB2 - A_BHB2
```

There is no interaction output and no need to invent an active return. This is exactly
the compact result obtained by combining the released BHB three-effect selection and
its direct-or-zero interaction policy.

## Relationship to released methods

### BHB two-effect and BHB three-effect

For every row, including the undefined-return convention:

```text
A_BHB2 = A_BHB3
T_BHB2 = T_BHB3
S_BHB2 = S_BHB3 + I_BHB3
```

Because both methods apply the same Carino coefficient to additive effects, the same
identities must hold for linked period detail, period summaries, overall detail, and
cumulative output within `1e-12` relative and absolute tolerance.

### BHB two-effect and BF two-effect

When the benchmark effective return is defined:

```text
A_BHB2 - A_BF2 = AW * B[t]
T_BHB2 - T_BF2 = AW * B[t]
S_BHB2 = S_BF2
```

With exactly normalized portfolio and benchmark weights, `sum(AW) = 0`. BHB and BF
two-effect therefore have equal period allocation and total sums while assigning
allocation and total differently by identifier. Their compact portfolio-weighted
selection values agree for ordinary defined-return rows.

These cross-method equalities do not override either method's documented
undefined-return residual behavior.

## Independent single-period example

Use the same two groups as the released BHB three-effect example:

| Group | `wP` | `wB` | `rP` | `rB` |
|---|---:|---:|---:|---:|
| A | 0.70 | 0.40 | 0.10 | 0.06 |
| B | 0.30 | 0.60 | 0.02 | 0.02 |

Portfolio return is `0.076`, benchmark return is `0.036`, and active return is
`0.040`. Compact BHB produces:

| Group | Allocation | Selection | Total |
|---|---:|---:|---:|
| A | 0.0180 | 0.0280 | 0.0460 |
| B | -0.0060 | 0.0000 | -0.0060 |
| Total | 0.0120 | 0.0280 | 0.0400 |

For A, BHB three-effect selection `0.0160` plus interaction `0.0120` gives compact
selection `0.0280`. B has zero active return, so both components and their compact
sum are zero. Allocation plus selection equals total for each group and the period.

The released compact BF method also gives A selection `0.0280`, but its A allocation
is `0.0072` rather than `0.0180`; the `0.0108` difference is
`AW * B = 0.30 * 0.036`. Group B has the offsetting difference `-0.0108`, so period
totals agree. These values are derived by hand and must not be generated from a
production implementation.

## Multi-period linking

Portfolio and benchmark contributions retain logarithmic linking. BHB allocation,
compact selection, and total each use the released Carino active coefficient `LA[t]`:

```text
linked_allocation_effect = A_BHB2[g,t] * LA[t]
linked_selection_effect  = S_BHB2[g,t] * LA[t]
linked_total_effect      = T_BHB2[g,t] * LA[t]
```

This preserves:

```text
linked_allocation_effect + linked_selection_effect = linked_total_effect
```

The released Carino limits, finite checks, and greater-than-minus-one return rules do
not change.

## Result schemas and reconciliation

BHB two-effect reuses the released default two-effect schemas exactly for
`period_detail`, `period_summary`, `overall_detail`, `cumulative`, and
`reconciliation`. It does not add, remove, rename, or reorder columns. Allocation and
identifier-level total retain the method-specific BHB meanings defined above.

It also reuses the two-effect reconciliation names, including `effect_components` and
`linked_effect_components`. Those checks compare allocation plus compact selection to
total. No hidden interaction reconciliation row is added.

All frames use a zero-based `RangeIndex`, deterministic ordering, released dtypes and
null placement, and independent caller ownership. Method metadata is the only way to
distinguish BHB two-effect from BF two-effect when schemas alone are inspected.

## Error behavior and `ppar` compatibility

The new enum introduces no new error category. Invalid method objects retain the
released `TypeError`; all input, linking, finite-value, and reconciliation errors
remain unchanged.

`ppar` continues to omit the method argument and therefore uses default BF two-effect.
Roadmap 7 does not add a `ppar` selector, schema, or presentation change. Its complete
release-candidate and unchanged 500x gates remain required before release.

## Test and documentation requirements

Expected values must be independently calculated by hand and explained in test
docstrings or fixture provenance. Required cases include:

- the distinguishing compact BHB/BF example above;
- positive, negative, and zero allocation and selection;
- authoritative contributions distinct from weight-times-return products;
- zero-weight nonzero-contribution rows and undefined effective returns;
- identifiers missing from either side and signed weights;
- exact preservation of all three released methods;
- BHB two/three collapse identities across all applicable frames;
- single and multiple periods, equal and near-equal Carino returns, and returns near
  but greater than `-1`;
- exact two-effect schema and reconciliation-name reuse;
- deterministic input permutations, caller-input nonmutation, and independent result
  ownership; and
- randomized valid inputs used only for invariants.

## Performance contract

Correctness comes first. Measure all four methods on the established direct-core
workloads, including elapsed time and peak memory. BHB two-effect should reuse the
existing vectorized BHB policy and compact aggregation path without an interaction
array, second engine, row-wise loop, or new dependency.

No new threshold is established. Existing gates remain unchanged.

## References and provenance

The allocation basis derives from:

- Brinson, Gary P., L. Randolph Hood, and Gilbert L. Beebower. “Determinants of
  Portfolio Performance.” *Financial Analysts Journal* 42, no. 4 (1986): 39–44.
  [doi:10.2469/faj.v42.n4.39](https://doi.org/10.2469/faj.v42.n4.39).

That paper supports the allocation basis and three-component decomposition, not a
historical two-effect label. Combining selection and interaction is the explicitly
disclosed `perfattr` reporting convention specified here.

The previous comparative review of `gghez/pybrinson` used commit
`529b0940937caacec3f2a30609b9ce6b86316a7b`. It reinforces explicit method identity
and shared mechanics but is not the calculation authority for this compact form. No
source code, fixtures, expected values, or documentation text are copied.
