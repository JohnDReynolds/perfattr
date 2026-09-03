# Attribution fixture provenance

These fixtures were created for `perfattr` from the formulas in
`docs/specification.md`. They are original project data: they were not copied from
`ppar`, another attribution implementation, or a vendor data set.

Each directory contains prepared portfolio and benchmark inputs plus independently
calculated expected period detail. `expected_horizon.csv` is included when a case
has more than one period; it records the full-horizon returns and the logarithmic and
Carino linking coefficients used in the expected detail.

The cases are deliberately small:

| Case | Contract covered |
|---|---|
| `single_period_derived` | Derived contribution, missing identifiers, signed weight, and an explicit zero-weight/null-return input |
| `single_period_authoritative` | Independently optional contribution columns and a zero-weight, nonzero-contribution row with undefined return |
| `multi_period_linking` | Multiple periods, unequal day counts, logarithmic contribution linking, and Carino effect linking |
| `linking_boundaries` | Exact zero/equal-return limits, near-equal returns, and returns close to -100% |

Blank return cells represent null. All other blank cells are invalid. Values are
decimal returns, weights, contributions, or effects; `0.01` means one percent.

Expected values were evaluated directly from the written formulas with full-precision
`log1p` calculations and then stored to at least 15 significant digits. The simple
single-period values can be checked by ordinary decimal arithmetic. For example, in
`single_period_derived`, the portfolio and benchmark returns are `0.024` and `0.034`,
and the allocation and selection totals are `-0.007` and `-0.003`, giving the active
return of `-0.01`.
