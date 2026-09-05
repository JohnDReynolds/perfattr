# Brinson-Fachler Three-Effect Attribution Specification

**Status:** Accepted September 5, 2026.

This document specifies the approved opt-in Brinson-Fachler three-effect calculation
governed by
[`perfattr_roadmap_5_brinson_fachler_three_effect.md`][roadmap-5]. It supplements the
released [`specification.md`](specification.md). Every released rule remains unchanged
unless this document explicitly defines behavior for the new method.

[roadmap-5]: ../_extras/perfattr_roadmap_5_brinson_fachler_three_effect.md

## User problem

The released calculation combines interaction with portfolio-weighted selection. This
is intentionally compact, but users who need a conventional three-effect
Brinson-Fachler report cannot observe how much active return came from
benchmark-weighted selection versus the interaction between active weight and active
group return.

The new method separates those components without changing allocation, total effect,
input preparation, or the default two-effect result.

## Public API

Add this public string enum:

```python
class AttributionMethod(str, Enum):
    BRINSON_FACHLER_TWO_EFFECT = "Brinson-Fachler Two-Effect"
    BRINSON_FACHLER_THREE_EFFECT = "Brinson-Fachler Three-Effect"
```

Export `AttributionMethod` from `perfattr`. Extend the calculation entry point to:

```python
def calculate_attribution(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    method: AttributionMethod = AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
    reconciliation_tolerance: float = 1e-12,
) -> AttributionResult:
    ...
```

The argument must be an `AttributionMethod`. A different object, including an
unvalidated string, raises `TypeError`. This keeps misspelled method names from
silently selecting financial behavior.

`AttributionResult` adds this sixth field after its five released frame fields:

```python
method: AttributionMethod = AttributionMethod.BRINSON_FACHLER_TWO_EFFECT
```

Existing five-positional-argument construction therefore remains valid. Callers should
still prefer keyword access to public result attributes.

## Input contract

Both methods use the released prepared input contract without new columns or different
validation. Supplied contribution remains authoritative. When contribution is absent,
it is derived as weight multiplied by return.

The normalized effective return for a row is:

```text
contribution / weight    when weight is nonzero
0                        when weight and contribution are both zero
null                     when weight is zero and contribution is nonzero
```

The calculation never infers cash, fees, financing, derivatives, or classifications
from identifier text.

## Notation

For identifier `g` in reporting period `t`:

- `wP[g,t]` and `wB[g,t]` are portfolio and benchmark weights;
- `rP[g,t]` and `rB[g,t]` are normalized effective returns;
- `cP[g,t]` and `cB[g,t]` are authoritative contributions;
- `B[t]` is total benchmark return, equal to the sum of benchmark contributions;
- `AW[g,t] = wP[g,t] - wB[g,t]`; and
- `AR[g,t] = rP[g,t] - rB[g,t]` when both effective returns are defined.

Universe equalization, missing-side behavior, numerical tolerance, and weight and
contribution validation remain as specified in `specification.md`.

## Shared allocation and total effect

Both methods retain the released Brinson-Fachler allocation:

```text
A[g,t] = AW[g,t] * (rB[g,t] - B[t])
```

If `rB[g,t]` is undefined, allocation is zero rather than an invented benchmark group
return.

Both methods retain the released total effect:

```text
T[g,t] = cP[g,t] - cB[g,t] - AW[g,t] * B[t]
```

Consequently, period total effect continues to sum to portfolio return minus benchmark
return even when supplied contribution cannot be reconstructed from the input return.

## Released two-effect method

The default method remains exactly:

```text
S2[g,t] = T[g,t] - A[g,t]
```

It returns no interaction column. When both effective returns are defined:

```text
S2[g,t] = wP[g,t] * AR[g,t]
```

No existing numerical path, frame column, column ordering, null placement,
reconciliation check name, or error behavior may change for this method.

## Opt-in three-effect method

When both effective returns are defined, interaction is:

```text
I[g,t] = AW[g,t] * AR[g,t]
```

Selection is calculated as the exact residual:

```text
S3[g,t] = T[g,t] - A[g,t] - I[g,t]
```

Because defined effective returns satisfy `cP = wP * rP` and `cB = wB * rB`, this is
algebraically equivalent to conventional benchmark-weighted selection:

```text
S3[g,t] = wB[g,t] * AR[g,t]
```

The residual calculation is normative because it preserves the authoritative
contribution contract and minimizes an independent floating-point path. The direct
benchmark-weighted formula is an independently tested identity, not a second
production calculation.

For every row with defined effective returns:

```text
S2[g,t] = S3[g,t] + I[g,t]
A[g,t] + S3[g,t] + I[g,t] = T[g,t]
```

## Undefined effective returns

If either effective return is null, `AR[g,t]` is mathematically undefined. The
three-effect method must then use:

```text
I[g,t] = 0
S3[g,t] = T[g,t] - A[g,t]
```

This is a disclosed boundary convention, not an assertion that the economic
interaction is known to be zero. It means the available authoritative active
contribution remains in selection because there is no defensible return difference
with which to split it.

This rule preserves zero-weight, nonzero-contribution fees and financing. It avoids an
unexplained fourth residual effect, never fabricates a return, and keeps all effect
columns finite. Return columns retain their released null placement.

## Independent single-period example

Use this two-group derived-contribution case as one required hand-calculated fixture:

| Group | `wP` | `wB` | `rP` | `rB` |
|---|---:|---:|---:|---:|
| A | 0.70 | 0.40 | 0.10 | 0.06 |
| B | 0.30 | 0.60 | 0.02 | 0.02 |

The portfolio return is `0.076`, the benchmark return is `0.036`, and active return is
`0.040`. The independently calculated effects are:

| Group | Allocation | Selection | Interaction | Total |
|---|---:|---:|---:|---:|
| A | 0.0072 | 0.0160 | 0.0120 | 0.0352 |
| B | 0.0048 | 0.0000 | 0.0000 | 0.0048 |
| Total | 0.0120 | 0.0160 | 0.0120 | 0.0400 |

For A, released two-effect selection is `0.0280`, exactly the sum of three-effect
selection `0.0160` and interaction `0.0120`. Tests must also include an independently
calculated negative-interaction case so sign errors cannot pass unnoticed.

## Multi-period linking

Portfolio and benchmark contributions retain logarithmic linking. Allocation,
selection, interaction, and total effect each use the released Carino active
coefficient `LA[t]`:

```text
linked_allocation_effect  = A[g,t]  * LA[t]
linked_selection_effect   = S3[g,t] * LA[t]
linked_interaction_effect = I[g,t]  * LA[t]
linked_total_effect       = T[g,t]  * LA[t]
```

Because the same coefficient multiplies each component:

```text
linked_allocation_effect
+ linked_selection_effect
+ linked_interaction_effect
= linked_total_effect
```

The released Carino limit behavior, finite checks, and greater-than-minus-one return
requirements do not change.

## Result schemas

### Default two-effect schemas

Every default frame retains exactly the schemas listed in `specification.md`. The new
method metadata is an `AttributionResult` attribute, not a DataFrame column.

### Three-effect `period_detail`

Insert `interaction_effect` immediately after `selection_effect` and
`linked_interaction_effect` immediately after `linked_selection_effect`. Every other
column and its order remain as in the released frame.

### Three-effect `period_summary`

Use the same two insertions and positions as `period_detail`.

### Three-effect `overall_detail`

Insert `linked_interaction_effect` immediately after `linked_selection_effect`.

### Three-effect `cumulative`

Insert `linked_interaction_effect` immediately after `linked_selection_effect`, and
insert `cumulative_interaction_effect` immediately after
`cumulative_selection_effect`.

### Three-effect `reconciliation`

The reconciliation frame columns remain unchanged. Period rows use
`three_effect_components` where the default method uses `effect_components`.
Full-horizon rows use `linked_three_effect_components` where the default method uses
`linked_effect_components`. All other check names and their order remain unchanged.

Result rows retain the released deterministic ordering and `RangeIndex`. Every result
frame remains newly allocated and caller-owned.

## Reconciliation identities

In addition to every unchanged weight, contribution, active-contribution, and total
check, the three-effect method enforces:

```text
sum(allocation_effect + selection_effect + interaction_effect)
    = sum(total_effect)

sum(linked_allocation_effect
    + linked_selection_effect
    + linked_interaction_effect)
    = sum(linked_total_effect)
```

The released relative and absolute tolerance defaults remain `1e-12`. A failed check
raises `AttributionError`; no partial result is returned.

The two-effect collapse identity is required in independently calculated tests. It
does not need a redundant production reconciliation row because three-effect
selection is already defined as the exact residual.

## Error behavior

The new method introduces only one new public-boundary error:

- a non-`AttributionMethod` `method` argument raises `TypeError` identifying the
  invalid argument.

All input, period, linking, finite-value, and reconciliation errors remain unchanged.
Selecting the new method never turns an existing error into a warning or partial
result.

## `ppar` compatibility

`ppar` continues to call `calculate_attribution()` without a method argument and
therefore receives the exact two-effect schema it already translates. Roadmap 5 does
not add interaction columns, method selection, or presentation behavior to `ppar`.

The candidate wheel must nevertheless pass `ppar`'s complete product gate and
unchanged 500x scale check. A later request to expose the method through `ppar` requires
separate API, schema, presentation, dependency, and release approval.

## Test and documentation requirements

Expected values must be calculated independently by hand and explained in test
docstrings and comments. Required cases include:

- the positive-interaction table above;
- a negative-interaction case;
- zero active weight and zero active return;
- nonzero authoritative contributions;
- zero-weight nonzero-contribution rows with null effective return;
- identifiers missing from either side;
- signed weights;
- single-period and multi-period results;
- equal and near-equal Carino returns;
- returns near, but greater than, `-1`;
- exact default schema preservation;
- three-effect column ordering and check names;
- input-row permutation;
- caller-input nonmutation and independent result ownership; and
- randomized valid inputs used only for invariants, never expected-value generation.

Nontrivial production functions and tests must document financial purpose, formulas,
assumptions, undefined-return behavior, and numerical limits using the conventions in
`AGENTS.md`.

## Performance contract

Correctness comes first. Measure both methods on the established realistic direct-core
workload, recording elapsed time and peak memory. The three-effect method should add
only one vector, one Carino multiplication, and aggregation of the corresponding
columns; no second calculation engine or row-wise loop is permitted.

No new performance threshold is established by this proposal. Existing thresholds
and the `ppar` 500x gate remain unchanged.

## References and provenance

Primary methodology:

- Brinson, Gary P., and Nimrod Fachler. “Measuring Non-U.S. Equity Portfolio
  Performance.” *The Journal of Portfolio Management* 11, no. 3 (1985): 73–76.
  [doi:10.3905/jpm.1985.409005](https://doi.org/10.3905/jpm.1985.409005).

Crossref metadata for the title, authors, journal, volume, issue, pages, publication
date, and DOI was verified on September 5, 2026.

Comparative design review:

- [`gghez/pybrinson`](https://github.com/gghez/pybrinson/), reviewed at commit
  `529b0940937caacec3f2a30609b9ce6b86316a7b` on September 5, 2026.

The review reinforced explicit method identity, independent effect channels, the
two-effect collapse identity, and applying one linking coefficient consistently to
each additive effect. It does not govern `perfattr`'s APIs or its authoritative-
contribution and null-return policies. No external source, fixture, expected value, or
documentation text is copied into this project.
