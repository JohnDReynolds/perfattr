# perfattr

`perfattr` is a small, auditable portfolio performance-attribution calculation
library built with pandas and NumPy.

The package provides a reusable Brinson attribution calculation core and a portable
preparation layer for source-period weights and returns. Portfolio accounting,
vendor schemas, and presentation remain outside the package boundary.

## Main features

- Accept weights and returns, or authoritative contributions when accounting results
  are available.
- Validate, select, and align portfolio and benchmark histories.
- Consolidate smaller source periods into complete monthly, quarterly, or yearly
  reporting periods using calendar and holiday rules.
- Apply static or effective-dated classification mappings before consolidation.
- Calculate Brinson-Fachler or Brinson-Hood-Beebower with compact two-effect selection
  or explicit three-effect selection and interaction.
- Calculate separate Bacon/Burnie geometric excess-return attribution when portfolio
  wealth should be measured relative to benchmark wealth.
- Separate global market and currency decisions with single-period Karnosky-Singer
  attribution using caller-supplied net currency exposures.
- Link contributions logarithmically and attribution effects using Carino, Frongello,
  or Menchero optimized linking, with Carino retained as the default.
- Roll already calculated leaf attribution into a static hierarchy without
  recalculating Brinson effects at parent levels.
- Preserve zero-weight fee and financing contributions without inventing returns.
- Return deterministic pandas result frames with explicit financial reconciliation.

The completed initial calculation roadmap is recorded in
[`_extras/perfattr_roadmap_1.md`](_extras/perfattr_roadmap_1.md). The completed portable
preparation work is recorded in
[`_extras/perfattr_roadmap_2.md`](_extras/perfattr_roadmap_2.md), while later candidates
are kept in the noncommitted
[`_extras/perfattr_roadmap_3.md`](_extras/perfattr_roadmap_3.md). Effective-dated
classification was the first promoted candidate and its completed work is recorded in
[`_extras/perfattr_roadmap_4_effective_dated_classification.md`][effective-roadmap], with
its accepted contract in
[`docs/effective_dated_classification_specification.md`][effective-spec].
The released opt-in Brinson-Fachler three-effect work is recorded in
[`_extras/perfattr_roadmap_5_brinson_fachler_three_effect.md`][three-effect-roadmap]
and [`docs/brinson_fachler_three_effect_specification.md`][three-effect-spec].
The released Brinson-Hood-Beebower three-effect work is recorded in
[`_extras/perfattr_roadmap_6_brinson_hood_beebower_three_effect.md`][bhb-roadmap]
and [`docs/brinson_hood_beebower_three_effect_specification.md`][bhb-spec].
The released compact Brinson-Hood-Beebower work is recorded in
[`_extras/perfattr_roadmap_7_brinson_hood_beebower_two_effect.md`][bhb-two-roadmap]
and [`docs/brinson_hood_beebower_two_effect_specification.md`][bhb-two-spec].
The released opt-in Frongello effect-linking work is recorded in
[`_extras/perfattr_roadmap_8_frongello_recursive_linking.md`][frongello-roadmap]
and [`docs/frongello_recursive_linking_specification.md`][frongello-spec].
The released opt-in Menchero optimized-linking work is recorded in
[`_extras/perfattr_roadmap_9_menchero_optimized_linking.md`][menchero-roadmap]
and [`docs/menchero_optimized_linking_specification.md`][menchero-spec].
The released hierarchical result-roll-up work is recorded in
[`_extras/perfattr_roadmap_10_hierarchical_result_rollup.md`][hierarchy-roadmap]
and [`docs/hierarchical_result_rollup_specification.md`][hierarchy-spec].
The released geometric excess-return attribution work is recorded in
[`_extras/perfattr_roadmap_11_geometric_attribution.md`][geometric-roadmap]
and [`docs/geometric_attribution_specification.md`][geometric-spec].
The released single-period currency-attribution work is recorded in
[`_extras/perfattr_roadmap_12_currency_attribution.md`][currency-roadmap] and its
accepted [`docs/currency_attribution_specification.md`][currency-spec]. The complete
independently reconciled calculation, documentation, direct performance evidence, and
release-candidate gates were released in `perfattr==0.11.0a1`.
The complete portable calculation contract is defined in
[`docs/specification.md`](docs/specification.md), and the accepted roadmap 2 preparation
contract is in [`docs/preparation_specification.md`](docs/preparation_specification.md).

[effective-spec]: docs/effective_dated_classification_specification.md
[effective-roadmap]: _extras/perfattr_roadmap_4_effective_dated_classification.md
[three-effect-roadmap]: _extras/perfattr_roadmap_5_brinson_fachler_three_effect.md
[three-effect-spec]: docs/brinson_fachler_three_effect_specification.md
[bhb-roadmap]: _extras/perfattr_roadmap_6_brinson_hood_beebower_three_effect.md
[bhb-spec]: docs/brinson_hood_beebower_three_effect_specification.md
[bhb-two-roadmap]: _extras/perfattr_roadmap_7_brinson_hood_beebower_two_effect.md
[bhb-two-spec]: docs/brinson_hood_beebower_two_effect_specification.md
[frongello-roadmap]: _extras/perfattr_roadmap_8_frongello_recursive_linking.md
[frongello-spec]: docs/frongello_recursive_linking_specification.md
[menchero-roadmap]: _extras/perfattr_roadmap_9_menchero_optimized_linking.md
[menchero-spec]: docs/menchero_optimized_linking_specification.md
[hierarchy-roadmap]: _extras/perfattr_roadmap_10_hierarchical_result_rollup.md
[hierarchy-spec]: docs/hierarchical_result_rollup_specification.md
[geometric-roadmap]: _extras/perfattr_roadmap_11_geometric_attribution.md
[geometric-spec]: docs/geometric_attribution_specification.md
[currency-roadmap]: _extras/perfattr_roadmap_12_currency_attribution.md
[currency-spec]: docs/currency_attribution_specification.md

```python
import pandas as pd

from perfattr import calculate_attribution, prepare_attribution

portfolio = pd.DataFrame(
    [
        {
            "from_date": "2024-01-01",
            "thru_date": "2024-01-31",
            "identifier": "Equity",
            "weight": 0.60,
            "return": 0.04,
        },
        {
            "from_date": "2024-01-01",
            "thru_date": "2024-01-31",
            "identifier": "Bonds",
            "weight": 0.40,
            "return": 0.01,
        },
    ]
)
benchmark = pd.DataFrame(
    [
        {
            "from_date": "2024-01-01",
            "thru_date": "2024-01-31",
            "identifier": "Equity",
            "weight": 0.50,
            "return": 0.03,
        },
        {
            "from_date": "2024-01-01",
            "thru_date": "2024-01-31",
            "identifier": "Bonds",
            "weight": 0.50,
            "return": 0.015,
        },
    ]
)

prepared = prepare_attribution(portfolio, benchmark)
result = calculate_attribution(prepared.portfolio, prepared.benchmark)
print(result.period_detail)
```

## Currency attribution

Use `calculate_currency_attribution` when global market allocation and net currency
exposure are separate decisions. It accepts four prepared frames: portfolio and
benchmark market facts, plus portfolio and benchmark currency facts. Market weights
and currency weights are independent vectors; multiple markets may share a currency,
and hedges may make a currency exposure zero, negative, or greater than one.

Inputs are ordinary simple period returns. The result uses explicitly named log-return
and log-effect columns because the Karnosky-Singer decomposition is additive on a
continuously compounded basis. This small example uses `expm1` only to create simple
inputs from convenient hand-calculated log returns:

```python
import numpy as np
import pandas as pd

from perfattr import calculate_currency_attribution

market_columns = [
    "from_date",
    "thru_date",
    "market_identifier",
    "market_weight",
    "local_asset_return",
    "local_cash_return",
]
currency_columns = [
    "from_date",
    "thru_date",
    "currency_identifier",
    "currency_weight",
    "base_currency_cash_return",
]
period = ("2024-01-01", "2024-01-31")

portfolio_markets = pd.DataFrame(
    [
        (*period, "Equity", 0.60, np.expm1(0.08), 0.0),
        (*period, "Bonds", 0.40, np.expm1(0.02), 0.0),
    ],
    columns=market_columns,
)
benchmark_markets = pd.DataFrame(
    [
        (*period, "Equity", 0.50, np.expm1(0.05), 0.0),
        (*period, "Bonds", 0.50, np.expm1(0.03), 0.0),
    ],
    columns=market_columns,
)
portfolio_currencies = pd.DataFrame(
    [
        (*period, "EUR", 0.70, np.expm1(0.04)),
        (*period, "USD", 0.30, np.expm1(0.015)),
    ],
    columns=currency_columns,
)
benchmark_currencies = pd.DataFrame(
    [
        (*period, "EUR", 0.50, np.expm1(0.03)),
        (*period, "USD", 0.50, np.expm1(0.01)),
    ],
    columns=currency_columns,
)

currency_result = calculate_currency_attribution(
    portfolio_markets,
    benchmark_markets,
    portfolio_currencies,
    benchmark_currencies,
    base_currency="USD",
)
print(currency_result.period_summary)
```

The benchmark market log return is `0.04`. Market allocation is `0.002` and
portfolio-weighted security selection is `0.014`, giving active market return `0.016`.
The benchmark currency log return is `0.02`. Currency allocation is `0.004` and
portfolio-weighted hedge selection is `0.0085`, giving active currency return
`0.0125`. All four effects sum to the modeled active total log return `0.0285`.

The host supplies net currency exposures after holdings, cash, and hedges; `perfattr`
does not infer exposures or price hedge transactions. Portfolio-weighted selection
absorbs each grid's interaction effect. This first calculation does not link currency
effects through time, roll them through a hierarchy, add separate interaction columns,
or force fees, flows, financing, or an accounting residual into the modeled total.
Each input period is calculated and reconciled independently. See the accepted
[currency specification][currency-spec] for exact schemas and interpretation.

## Hierarchical result roll-up

Use `roll_up_attribution` after calculation when leaf results also need additive
parent totals:

```python
from perfattr import roll_up_attribution

hierarchy = pd.DataFrame(
    {
        "identifier": ["Equity", "Bonds"],
        "parent_identifier": ["Total", "Total"],
    }
)
parent_result = roll_up_attribution(result, hierarchy)
print(parent_result.period_rollup)
```

The hierarchy is a static child-to-parent forest with complete leaf coverage. Parent
effects are sums of the already calculated descendant effects; the function does not
rerun Brinson formulas or linking at a higher level. `period_rollup` includes parent
effective returns derived from summed weight and authoritative contribution.
`overall_rollup` deliberately omits returns and cumulative values because the source
result does not retain enough information to reconstruct them faithfully in every
case. Leaf rows remain in the original `AttributionResult`, while the hierarchy result
contains parent rows only and includes explicit parent and root reconciliation.

## Attribution methods

The default remains the released two-effect Brinson-Fachler convention: allocation is
reported separately, while portfolio-weighted selection absorbs interaction. The
public method enum also provides an explicit-interaction Brinson-Fachler calculation
and compact or explicit-interaction Brinson-Hood-Beebower (BHB) calculations:

```python
from perfattr import AttributionMethod, calculate_attribution

three_effect = calculate_attribution(
    prepared.portfolio,
    prepared.benchmark,
    method=AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
)
bhb_three_effect = calculate_attribution(
    prepared.portfolio,
    prepared.benchmark,
    method=AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
)
bhb_two_effect = calculate_attribution(
    prepared.portfolio,
    prepared.benchmark,
    method=AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
)
print(
    three_effect.period_detail[
        ["allocation_effect", "selection_effect", "interaction_effect"]
    ]
)
```

For portfolio and benchmark weights `wP` and `wB`, effective returns `rP` and `rB`,
and total benchmark return `B`, the explicit effects are:

```text
Brinson-Fachler allocation = (wP - wB) * (rB - B)
BHB allocation             = (wP - wB) * rB
selection                  = wB * (rP - rB)
interaction                = (wP - wB) * (rP - rB)
compact selection          = total - allocation
```

BHB uses the group's absolute benchmark return, so overweighting a positive-return
group produces positive allocation even when that return trails the total benchmark.
Brinson-Fachler instead measures the group return relative to the total benchmark;
the two methods can therefore assign opposite allocation signs. `perfattr` reports
the signed formulas without labeling an effect favorable or unfavorable.

At identifier level, BHB `total_effect` is unadjusted active contribution, while the
Brinson-Fachler total includes its benchmark-relative adjustment. With exactly
normalized portfolio and benchmark weights, their period totals agree. Supplied
contribution remains authoritative. If either effective return is undefined,
interaction is zero and selection retains the reconciled residual rather than
inventing a return.

Compact BHB is a derived `perfattr` reporting convention, not a claim that the
original BHB methodology defined a historical two-effect model. It retains BHB
allocation and total, omits the interaction column, and reports selection directly as
`total_effect - allocation_effect`. When returns are defined, compact BHB and compact
Brinson-Fachler therefore share portfolio-weighted selection but can assign different
identifier-level allocation and total values.

The opt-in result inserts `interaction_effect` immediately after `selection_effect`
and `linked_interaction_effect` immediately after `linked_selection_effect` wherever
those channels apply. Cumulative output also places
`cumulative_interaction_effect` immediately after `cumulative_selection_effect`.
`AttributionResult.method` records the selected convention. See the
[Brinson-Fachler specification][three-effect-spec], [BHB three-effect
specification][bhb-spec], and [compact BHB specification][bhb-two-spec] for the
complete schemas, linking rules, null policies, and independently calculated examples.

## Geometric excess-return attribution

Use `calculate_geometric_attribution` when the reporting question is how portfolio
ending wealth compares with benchmark ending wealth:

```python
from perfattr import calculate_geometric_attribution

geometric_result = calculate_geometric_attribution(
    prepared.portfolio,
    prepared.benchmark,
)
print(geometric_result.cumulative.tail(1))
```

This is a separate calculation family, not another arithmetic attribution method or
effect linker. The arithmetic calculator reconciles the return difference
`portfolio_return - benchmark_return` through additive effects. The geometric
calculator instead reconciles:

```text
(1 + portfolio_return) / (1 + benchmark_return) - 1
```

It first compares a semi-notional portfolio—portfolio weights earning benchmark
identifier returns—with the benchmark to calculate allocation. It then compares the
portfolio with that semi-notional portfolio to calculate portfolio-weighted
selection. Interaction remains absorbed in selection, and the two channel totals
combine multiplicatively:

```text
1 + total_effect = (1 + allocation_effect) * (1 + selection_effect)
```

Allocation and selection compound directly across periods, so Carino, Frongello, and
Menchero arithmetic smoothing do not apply. The result provides identifier effects by
period, period totals, cumulative prefixes, and explicit multiplicative
reconciliation. It deliberately has no `overall_detail`: allocating cross-period and
cross-channel compounding terms back to identifiers would require another financial
policy.

Prepared inputs and authoritative-contribution behavior remain unchanged. Cash is an
ordinary identifier. A zero-weight portfolio fee remains in selection; a zero-weight
benchmark charge is preserved through the disclosed benchmark accounting residual.
If a nonzero portfolio weight would require an undefined benchmark return, the
calculation rejects the input rather than substituting zero. See the [geometric
specification][geometric-spec] for exact formulas, schemas, null behavior, and
reconciliation checks.

## Effect linking

Carino remains the default effect linker. Frongello is an explicit opt-in for clients
that need path-dependent recursive linking. Menchero optimized linking is an opt-in
for clients that require order-independent, minimum-correction allocation of the
multi-period compounding residual:

```python
from perfattr import EffectLinkingMethod, calculate_attribution

frongello_result = calculate_attribution(
    prepared.portfolio,
    prepared.benchmark,
    effect_linking_method=EffectLinkingMethod.FRONGELLO,
)
menchero_result = calculate_attribution(
    prepared.portfolio,
    prepared.benchmark,
    effect_linking_method=EffectLinkingMethod.MENCHERO,
)
print(frongello_result.effect_linking_method)
print(menchero_result.effect_linking_method)
```

The option changes only linked allocation, selection, optional interaction, and total
effects. Portfolio and benchmark contributions remain logarithmically linked, and
unlinked effects and result-frame schemas do not change. Each period-detail linked
effect is the originating source-period effect allocated to the complete requested
horizon; intermediate cumulative rows are partial sums of those allocations, not
independent as-of calculations.

Frongello's coefficient for a source period depends on earlier portfolio growth and
later benchmark growth, so changing the economic chronology can change the allocation
among effect channels. Menchero uses one common horizon scale plus the smallest
least-squares period corrections needed to reconcile the compounded active return.
Moving complete economic periods therefore moves their coefficients with them without
changing complete-horizon effect totals. A one-period calculation is the identity
under both policies.

Neither policy changes portfolio or benchmark contribution linking. Cash, fees,
financing, authoritative contribution, signed weights, and missing identifiers all
receive the same ordinary coefficient as other effects in their source period. See
the [Frongello specification][frongello-spec] and [Menchero
specification][menchero-spec] for formulas, worked examples, ordering behavior, and
compatibility contracts.

GRAP is intentionally not exposed as another linker name because its unrolled result
at this library's source-period boundary is the same numerical allocation already
provided by Frongello. A duplicate public identity would imply a calculation choice
where none exists.

Canonical CSV inputs can be loaded with `read_performance_csv`; optional mapping and
classification readers are also available at the package root.

Mapping CSV files are headerless and use one uniform form per file. Existing static
files remain two columns (`identifier,classification_identifier`). Effective-dated
files use four columns in the order `from_date,thru_date,identifier,
classification_identifier`. For example:

```text
2024-01-01,2024-01-31,ASSET,Equity
2024-02-01,2024-12-31,ASSET,Fixed Income
```

The dates are closed and inclusive. A source period for a mapped identifier must be
contained in exactly one assignment; `perfattr` does not split a source period at a
classification boundary.

## Cash, fees, and financing

Cash receives no special treatment: supply it as an ordinary identifier, or map it to
a Cash classification, with the weight and return chosen by the host accounting
system. `perfattr` never invents cash or hides a residual in it.

A fee or financing charge without exposure can be supplied as a zero-weight row with
an authoritative nonzero contribution and a null return. The contribution is
preserved and included in the ordinary attribution and linking calculations;
`perfattr` does not infer the row from its name or calculate the charge. Financing with
an explicit exposure and return can instead be represented as an ordinary identifier.

## Development

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the package and development dependencies:

```bash
python -m pip install --editable ".[dev]"
```

Run the initial checks:

```bash
python -m pytest
python -m pylint src/perfattr tests scripts
python -m pyright
```

Run the direct performance benchmarks:

```bash
python scripts/benchmark_core.py --samples 5
python scripts/benchmark_core.py --samples 5 --input-form authoritative
python scripts/benchmark_preparation.py --samples 5
python scripts/benchmark_hierarchy.py --samples 5
python scripts/benchmark_currency.py --samples 5
```

Pass `--method three-effect`, `--method bhb-three-effect`, or
`--method bhb-two-effect` to `benchmark_core.py` to measure an opt-in calculation;
the default remains `--method two-effect`. Pass
`--effect-linking-method frongello` or `--effect-linking-method menchero` to measure an
opt-in linker; the benchmark default remains Carino.
The hierarchy benchmark runs all four attribution methods and all three linkers by
default across the established selected-result sizes and hierarchy depths. Repeat
`--method` or `--effect-linking-method` to select a smaller policy subset.

Add `--workload monthly_121260 --profile` to inspect one workload's cumulative
calculation-core call profile. The preparation benchmark compares static and
effective-dated mappings through quarterly consolidation. The benchmark methodology
and observations are recorded in [`docs/performance.md`](docs/performance.md).

## License

`perfattr` is distributed under the MIT License.
