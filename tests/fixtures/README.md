# Attribution fixture provenance

These fixtures were created for `perfattr` from the formulas in
`docs/specification.md`. They are original project data: they were not copied from
`ppar`, another attribution implementation, or a vendor data set.

Each directory contains prepared portfolio and benchmark inputs plus independently
calculated expected values. The initial two-effect cases use
`expected_period_detail.csv`. The three-effect cases isolate their hand-calculated
Brinson-Fachler values in `expected_effects.csv` and BHB values in
`expected_bhb_effects.csv`.
The multi-period case records its independently linked BHB effects in
`expected_bhb_period_detail.csv`.
`expected_horizon.csv` is included when a case has more than one period; it records
the full-horizon returns and logarithmic and Carino linking coefficients used in the
expected detail.

The cases are deliberately small:

| Case | Contract covered |
|---|---|
| `single_period_derived` | Derived contribution, missing identifiers, signed weight, and an explicit zero-weight/null-return input |
| `single_period_authoritative` | Independently optional contribution columns and a zero-weight fee or financing-style charge with undefined return |
| `multi_period_linking` | Multiple periods, unequal day counts, logarithmic contribution linking, and Carino effect linking |
| `linking_boundaries` | Exact zero/equal-return limits, near-equal returns, and returns close to -100% |
| `three_effect_positive` | The governing specification's derived-contribution example with positive interaction |
| `three_effect_authoritative` | Contributions that imply effective returns distinct from supplied returns and both positive and negative interaction |

Blank return cells represent null. All other blank cells are invalid. Values are
decimal returns, weights, contributions, or effects; `0.01` means one percent.

Expected values were evaluated directly from the written formulas with full-precision
`log1p` calculations and then stored to at least 15 significant digits. The simple
single-period values can be checked by ordinary decimal arithmetic. For example, in
`single_period_derived`, the portfolio and benchmark returns are `0.024` and `0.034`,
and the allocation and selection totals are `-0.007` and `-0.003`, giving the active
return of `-0.01`.

For `three_effect_positive`, benchmark return is `0.036`. Group A therefore has
Brinson-Fachler allocation `0.30 * (0.06 - 0.036) = 0.0072`, selection
`0.40 * (0.10 - 0.06) = 0.016`, and interaction
`0.30 * (0.10 - 0.06) = 0.012`. Its BHB allocation is instead
`0.30 * 0.06 = 0.018`, while its unadjusted total is
`0.70 * 0.10 - 0.40 * 0.06 = 0.046`. In `three_effect_authoritative`, the
contributions imply effective portfolio returns of `0.05` and `0.10` and benchmark
returns of `0.04` and `0.06`; the supplied input returns intentionally differ and do
not determine either method's effects.

For `multi_period_linking`, BHB allocation before linking is `-0.002` and `0.008`
for Bonds and Equity in January, then `-0.0025` and `-0.002` in February. Multiplying
each period's allocation, selection, interaction, and total by the independently
recorded Carino coefficient in `expected_horizon.csv` produces
`expected_bhb_period_detail.csv`. Its linked component total is `-0.00265`, equal to
the compounded portfolio return `0.0547` minus benchmark return `0.05735`.
