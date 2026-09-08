# Attribution fixture provenance

These fixtures were created for `perfattr` from the formulas in
`docs/specification.md`. They are original project data: they were not copied from
`ppar`, another attribution implementation, or a vendor data set.

Each directory contains prepared portfolio and benchmark inputs plus independently
calculated expected values. The initial two-effect cases use
`expected_period_detail.csv`. The three-effect cases isolate their hand-calculated
Brinson-Fachler values in `expected_effects.csv` and BHB values in
`expected_bhb_effects.csv`. Their independently collapsed BHB two-effect values are
in `expected_bhb_two_effects.csv`.
The multi-period case records its independently linked BHB effects in
`expected_bhb_period_detail.csv`.
The multi-period and linking-boundary cases record compact BHB effects and linked
effects in `expected_bhb_two_effect_period_detail.csv`.
`expected_horizon.csv` is included when a case has more than one period; it records
the full-horizon returns and logarithmic and Carino linking coefficients used in the
expected detail.
The `multi_period_linking/expected_frongello_*.csv` files form a complete public-result
fixture for Frongello: period detail, period summary, identifier-level overall detail,
cumulative output, and reconciliation evidence. They retain independently calculated
logarithmic contributions because selecting Frongello changes effects only.
The matching `expected_menchero_*.csv` files form the complete Menchero public-result
fixture. Their effect values use independently evaluated optimized coefficients; all
unchanged values retain the original independently derived fixture arithmetic.

The cases are deliberately small:

| Case | Contract covered |
|---|---|
| `single_period_derived` | Derived contribution, missing identifiers, signed weight, and an explicit zero-weight/null-return input |
| `single_period_authoritative` | Independently optional contribution columns and a zero-weight fee or financing-style charge with undefined return |
| `multi_period_linking` | Multiple periods, unequal day counts, logarithmic contribution linking, and Carino effect linking |
| `linking_boundaries` | Exact zero/equal-return limits, near-equal returns, and returns close to -100% |
| `three_effect_positive` | The governing specification's derived-contribution example with positive interaction |
| `three_effect_authoritative` | Contributions that imply effective returns distinct from supplied returns and both positive and negative interaction |

## Currency-attribution calculations

Currency tests are expressed directly in `test_currency_market.py` and
`test_currency_calculation.py` because their four input frames and literal expected
values are compact. Most are original project-authored examples derived independently
from `docs/currency_attribution_specification.md`. Their docstrings show the local
log-return premiums, benchmark aggregate references, four effect formulas, and market,
currency, and complete reconciliation totals. Randomized expectations are direct
weighted-return calculations, not captured production output.

The sole source-derived case uses three rows from Karnosky and Singer (1994), Table 21,
printed page 66: Australia, Japan, and the United States. It transcribes passive and
active currency weights and U.S.-dollar cash returns. Each side's selected weights are
divided by its three-country subtotal to satisfy the package's unit-sum input contract;
the returns remain the reported values. Because the monograph works on a continuously
compounded basis, the test applies `expm1` before calling the simple-return public API
and requires the returned `log1p` values to recover `-3.25%`, `5.00%`, and `4.09%`.
One return series is available, so it is supplied to both sides and independently
implies zero hedge selection.

Only those numerical facts and the methodology are reused. No implementation source,
fixture file, table image, or prose was copied from the monograph, `ppar`, `pybrinson`,
or another package. This limited factual transcription is compatible with the
project's MIT outbound license.

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

The BHB two-effect tables retain each BHB allocation and total, then add the
independent three-effect selection and interaction values. For example, Group A in
`three_effect_positive` has compact selection `0.016 + 0.012 = 0.028`; Group B in
`three_effect_authoritative` has `0.020 + (-0.004) = 0.016`. The tables record those
literal expectations rather than values generated by the implementation.

For `multi_period_linking`, BHB allocation before linking is `-0.002` and `0.008`
for Bonds and Equity in January, then `-0.0025` and `-0.002` in February. Multiplying
each period's allocation, selection, interaction, and total by the independently
recorded Carino coefficient in `expected_horizon.csv` produces
`expected_bhb_period_detail.csv`. Its linked component total is `-0.00265`, equal to
the compounded portfolio return `0.0547` minus benchmark return `0.05735`.

The compact BHB multi-period table retains those allocation and total values and
combines selection with interaction before applying the same independently recorded
Carino coefficient. Its unlinked selections are `-0.008`, `0.012`, `0.0025`, and
`-0.010`; linked selections are therefore `-0.008007828265472380`,
`0.012011742398208570`, `0.002637455277466764`, and
`-0.010549821109867057`. In `linking_boundaries`, active weights are zero, so BHB
allocation is zero and compact selection equals total. The March total effects of
`0.05` and `-0.05` are multiplied by the independently calculated active coefficient
`0.000001000049999195771`; April's coefficient is its exact limit value of one.

## Frongello calculations for `multi_period_linking`

These expectations apply the prefix-portfolio, suffix-benchmark formula documented
in `docs/frongello_recursive_linking_specification.md`. They were worked from the CSV
inputs and the formula, then written as literals; they were not captured from
`perfattr`, `ppar`, `pybrinson`, or another implementation.

The portfolio period returns are the row-contribution sums `0.060` and `-0.005`.
The benchmark returns are `0.050` and `0.007`. With two chronological periods, the
Frongello factors are therefore:

```text
January  K[1] = 1.000 * (1 + 0.007) = 1.007
February K[2] = (1 + 0.060) * 1.000 = 1.060
```

The default compact Brinson-Fachler effects and their linked values are:

| Period | Identifier | Allocation | Selection | Total | Linked allocation | Linked selection | Linked total |
|---|---|---:|---:|---:|---:|---:|---:|
| January | Bonds | `0.0030` | `-0.0080` | `-0.0050` | `0.003021` | `-0.008056` | `-0.005035` |
| January | Equity | `0.0030` | `0.0120` | `0.0150` | `0.003021` | `0.012084` | `0.015105` |
| February | Bonds | `-0.0018` | `0.0025` | `0.0007` | `-0.001908` | `0.002650` | `0.000742` |
| February | Equity | `-0.0027` | `-0.0100` | `-0.0127` | `-0.002862` | `-0.010600` | `-0.013462` |

For example, January Bonds allocation is
`(0.40 - 0.50) * (0.02 - 0.05) = 0.003`; its linked value is
`0.003 * 1.007 = 0.003021`. February Equity selection is
`0.50 * (-0.04 - -0.02) = -0.010`; its linked value is
`-0.010 * 1.060 = -0.010600`. These examples also show positive and negative effects.
None of the four rows has a zero total, but zero values are deliberately retained in
the unchanged contribution columns, and separate one-period fixtures test zero
effects and zero-weight rows under the identity factor.

Summing the linked rows produces the two period summaries:

```text
January:  allocation 0.006042 + selection 0.004028 = total  0.010070
February: allocation -0.004770 + selection -0.007950 = total -0.012720
```

Summing by identifier produces:

```text
Bonds:  allocation 0.001113 + selection -0.005406 = total -0.004293
Equity: allocation 0.000159 + selection  0.001484 = total  0.001643
```

The cumulative rows are partial sums of these complete-horizon source allocations,
not independent as-of Frongello calculations. They end at allocation `0.001272`,
selection `-0.003922`, and total `-0.002650`. That total independently reconciles to:

```text
portfolio horizon = (1.060 * 0.995) - 1 = 0.054700
benchmark horizon = (1.050 * 1.007) - 1 = 0.057350
active horizon    = 0.054700 - 0.057350 = -0.002650
```

Portfolio and benchmark contributions retain the logarithmic coefficients stored in
`expected_horizon.csv`. For example, January benchmark contributions
`0.010035243908336232 + 0.040140975633344930` sum to
`0.050176219541681162`. Summing both periods gives linked portfolio and benchmark
contributions `0.054700` and `0.057350`, so their difference is also `-0.002650`.

The overall identifier weights use 31 January days and 29 February days. Bonds'
portfolio weight, for example, is `(0.40 * 31 + 0.50 * 29) / 60 =
0.448333333333333333`. Identifier returns compound their source returns: Bonds'
benchmark return is `(1.02 * 1.025) - 1 = 0.0455`, and Equity's portfolio return is
`(1.10 * 0.96) - 1 = 0.0560`. The expected overall-detail file records all such
values, not only the new effect channels.

Every period reconciliation compares weights to one, contribution sums to the
period returns, component sums to total effect, and total effect to active return.
The five horizon checks compare linked portfolio contribution to `0.0547`, linked
benchmark contribution to `0.05735`, and linked active contribution, component sum,
and linked total effect to `-0.00265`. Literal zero residuals in the fixture express
the mathematical expectation; tests allow only the governing `1e-12` floating-point
tolerance.

The primary two-period linker-only example in `tests/test_frongello_linking.py` is
transcribed from Andrew S. B. Frongello, “Attribution Linking: Proofed and Clarified,”
*The Journal of Performance Measurement* 7, no. 1 (Fall 2002), 54–67. Its docstrings
show the original and reversed chronology arithmetic. Only the published input
numbers and method were used; no source code or fixture was copied.

## Menchero calculations for `multi_period_linking`

These original expectations apply the optimized period-coefficient formula in
`docs/menchero_optimized_linking_specification.md`. They were derived from the literal
CSV inputs with 50-digit decimal arithmetic and then written as fixture values; they
were not captured from `perfattr`, `ppar`, `pybrinson`, or any other implementation.
The existing independently calculated contribution, exposure, return, and unlinked
effect values are unchanged because Menchero selects only active-effect linking.

The two period returns and compounded horizon returns are:

```text
P[1] =  0.060       B[1] = 0.050       d[1] =  0.010
P[2] = -0.005       B[2] = 0.007       d[2] = -0.012
P[H] = (1.060 * 0.995) - 1 = 0.054700
B[H] = (1.050 * 1.007) - 1 = 0.057350
D    = P[H] - B[H]        = -0.002650
```

For two periods, the stable difference-of-powers mean reduces to the arithmetic mean
of the two positive horizon roots:

```text
M = (sqrt(1.054700) + sqrt(1.057350)) / 2
  = 1.0276305680441572855867437657161313592361915910889

E = D - M * (0.010 - 0.012)
  = -0.0005947388639116854288265124685677372815276168178222

Q = 0.010**2 + (-0.012)**2
  = 0.000244

K[1] = M + E *  0.010 / Q
     = 1.0032560244412193581758211235617158968785023772437
K[2] = M + E * -0.012 / Q
     = 1.0568800203676827984798509363014299140654186477031
```

Applying the same coefficient to every effect in its source period gives:

| Period | Identifier | Allocation | Selection | Total | Linked allocation | Linked selection | Linked total |
|---|---|---:|---:|---:|---:|---:|---:|
| January | Bonds | `0.0030` | `-0.0080` | `-0.0050` | `0.003009768073323658` | `-0.008026048195529755` | `-0.005016280122206097` |
| January | Equity | `0.0030` | `0.0120` | `0.0150` | `0.003009768073323658` | `0.012039072293294632` | `0.015048840366618290` |
| February | Bonds | `-0.0018` | `0.0025` | `0.0007` | `-0.001902384036661829` | `0.002642200050919207` | `0.000739816014257378` |
| February | Equity | `-0.0027` | `-0.0100` | `-0.0127` | `-0.002853576054992744` | `-0.010568800203676828` | `-0.013422376258669572` |

For example, January Bonds selection is
`-0.008 * 1.003256024441219358... = -0.008026048195529755...`.
February Equity allocation is
`-0.0027 * 1.056880020367682798... = -0.002853576054992744...`.
The positive, negative, and zero source values are preserved rather than classified
or adjusted by the linker.

Summing the independently linked rows by period gives:

```text
January:  allocation  0.006019536146647316
          selection   0.004013024097764877
          total       0.010032560244412194

February: allocation -0.004755960091654573
          selection  -0.007926600152757621
          total      -0.012682560244412194
```

Summing the same source rows by identifier gives:

```text
Bonds:  allocation  0.001107384036661829
        selection  -0.005383848144610548
        total      -0.004276464107948719

Equity: allocation  0.000156192018330915
        selection   0.001470272089617804
        total       0.001626464107948719
```

The cumulative rows are partial sums of complete-horizon source allocations. They end
at allocation `0.001263576054992744`, selection `-0.003913576054992744`, and total
`-0.002650000000000000`. Thus the independent effect calculation reconciles to both
the compounded active horizon return and the independently logarithmically linked
active contribution.

The five Menchero CSVs record every public frame, including all 19 reconciliation
rows. Literal zero residuals state the exact financial identities; fixture comparison
allows only the unchanged `1e-12` floating-point tolerance. Separate parametrized
one-period tests use `single_period_derived` and `single_period_authoritative` to
cover signed and zero weights, missing sides, positive, negative, and zero values,
authoritative contribution, and null effective return. Dedicated two-period tests
cover ordinary explicit cash and a disappearing zero-weight fee or financing-style
charge. Neither identifier name selects special attribution or linking behavior.

The six-period coefficient example in `tests/test_menchero_linking.py` uses the
published inputs disclosed by José G. Menchero, “An Optimized Approach to Linking
Attribution Effects over Time,” *The Journal of Performance Measurement* 5, no. 1
(Fall 2000), 36–42, and the related public patent record. Its expected horizon returns,
coefficients, and effect totals were independently recomputed from the disclosed
formula. No external source code, test fixture, or generated package output was used.

## Hierarchical result-roll-up calculations

The hierarchy expectations are literal Python data in
`tests/test_hierarchy_period_rollup.py`, rather than CSV files. They were written from
the formulas in `docs/hierarchical_result_rollup_specification.md` and were not copied
or captured from `perfattr`, `ppar`, `pybrinson`, or another implementation.

The one-period source facts contain leaves A, B, C, D, and FEE. Portfolio weights and
contributions are `0.6/0.060`, `0.5/0.020`, `-0.1/-0.020`, and `0.0/-0.001` for A, B,
C, and FEE; the benchmark facts are `0.5/0.040`, `0.3/0.015`, and `0.2/0.006` for A,
B, and D. Thus Sector 1 has portfolio weight/contribution `1.1/0.080` and benchmark
weight/contribution `0.8/0.055`; its effective returns are independently
`0.080 / 1.1` and `0.055 / 0.8`. Sector 2 retains the signed portfolio facts
`-0.1/-0.020`, while Costs retains the zero-weight authoritative fee and therefore
has a null portfolio return.

Every parent effect is the literal sum of its leaf effects. Sector 1's
Brinson-Fachler allocation is `-0.0003`, whereas recalculation from its parent facts
would produce `0.002325`. Its BHB allocation is `0.018`, whereas parent recalculation
would produce `0.020625`. The expected tables intentionally retain the former sums;
the latter values demonstrate the different, deferred hierarchical-recalculation
question. One-period linking is the identity, so the same independently derived
values apply to Carino, Frongello, and Menchero without using production output as an
oracle.

The expected horizon frame contains only the additive fields that remain valid from
the released result. Reconciliation expectations repeat each independently known
parent value as the sum of its immediate active children, compare the Total root with
all five leaves, and separately calculate active-value and effect-component
identities. Tests cover every method/linker combination at `1e-12`, plus a multi-root
forest, nontrivial multi-period linked values, source corruption, and a deliberately
tampered parent effect.
