# perfattr

`perfattr` is a small, auditable portfolio performance-attribution calculation
library built with pandas and NumPy.

The package provides a reusable Brinson attribution calculation core and a portable
preparation layer for source-period weights and returns. Portfolio accounting,
vendor schemas, and presentation remain outside the package boundary.

## Installation and release status

`perfattr` requires Python 3.11 or later. The complete current API is published as the
`0.12.0a1` prerelease:

```bash
python -m pip install --pre --upgrade perfattr
```

Until the current feature set receives its next stable release, plain
`python -m pip install perfattr` selects the older stable `0.3.0` package. See the
[public releases][releases] for available versions.

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
- Roll currency-attribution log returns and effects directly through time, including
  cumulative prefixes and full-horizon market and currency identifier effects.
- Link contributions logarithmically and attribution effects using Carino, Frongello,
  or Menchero optimized linking, with Carino retained as the default.
- Roll already calculated leaf attribution into a static hierarchy without
  recalculating Brinson effects at parent levels.
- Preserve zero-weight fee and financing contributions without inventing returns.
- Return deterministic pandas result frames with explicit financial reconciliation.

## Documentation

Start with the task-oriented [user guide][user-guide]. The
[documentation index][docs] links every governing calculation and preparation
contract. Current benchmark guidance is in [Performance][performance], and completed
plans and future candidates remain available in the [roadmap records][roadmaps].

## Minimal arithmetic example

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
print(
    result.period_summary[
        [
            "portfolio_return",
            "benchmark_return",
            "active_return",
            "allocation_effect",
            "selection_effect",
            "total_effect",
        ]
    ]
)
```

### Which result should I use?

| Frame | Use it for |
| --- | --- |
| `period_detail` | Identifier effects within each reporting period |
| `period_summary` | Portfolio, benchmark, and effect totals by period |
| `overall_detail` | Identifier results across the complete horizon |
| `cumulative` | Chronological cumulative returns and effects |
| `reconciliation` | Evidence of the financial identities checked |

Values are decimals: `0.01` means one percent. The calculation raises before returning
a failed reconciliation. It returns numerical data rather than percent formatting,
charts, or presentation total rows. The [user guide][user-guide] explains source-
period preparation, linked versus unlinked effects, coverage checks, and each result
frame.

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

The four effects in this example sum to modeled active total log return of `0.0285`.
The host supplies net exposures after holdings, cash, and hedges; `perfattr` neither
infers exposures nor prices hedge transactions. See the
[documentation index][docs] for the currency specification's formulas, schemas, and
reconciliation rules.

### Multi-period currency roll-up

Pass a completed `CurrencyAttributionResult` to `roll_up_currency_attribution` when
you need cumulative prefixes and full-horizon identifier effects:

```python
from perfattr import roll_up_currency_attribution

currency_rollup = roll_up_currency_attribution(currency_result)
complete_horizon = currency_rollup.cumulative.iloc[-1]
print(complete_horizon)
```

Log returns and effects add directly through time, so this operation neither applies
arithmetic smoothing nor averages weights or returns. See the
[documentation index][docs] for the multi-period currency specification's exact
schemas, gap handling, and interpretation.

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

The hierarchy is a static child-to-parent forest with complete leaf coverage. It sums
already calculated descendant effects and does not rerun attribution at parent levels.
See the hierarchy contract in the [documentation index][docs] for schemas and
reconciliation rules.

## Attribution methods

Select a released arithmetic method with `AttributionMethod`:

| Method | Allocation basis | Reported effects |
| --- | --- | --- |
| BF two-effect (default) | Benchmark-relative | Allocation and selection |
| BF three-effect | Benchmark-relative | Allocation, selection, interaction |
| BHB two-effect | Absolute benchmark return | Allocation and selection |
| BHB three-effect | Absolute benchmark return | Allocation, selection, interaction |

Two-effect selection absorbs interaction; three-effect methods expose it separately.
The default is Brinson-Fachler two-effect. See the
[arithmetic specification][arithmetic-spec] and its
linked method supplements for formulas, schemas, and null behavior.

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

This separate calculation family reconciles portfolio ending wealth relative to
benchmark ending wealth. Allocation and selection combine multiplicatively and
compound directly across periods, so arithmetic effect linkers do not apply. See the
[documentation index][docs] for the geometric specification's formulas, schemas,
authoritative-contribution behavior, and reconciliation rules.

## Effect linking

Carino is the default arithmetic effect linker. Frongello provides path-dependent
recursive linking; Menchero provides order-independent optimized linking:

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

The option changes linked attribution effects only; contribution linking and unlinked
effects remain unchanged. See the
[documentation index][docs] for the Frongello and Menchero specifications, formulas,
ordering behavior, and worked examples. The [feature backlog][roadmap] records why
GRAP is not exposed as a numerically duplicate public choice.

## Input loading and mapping

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
python scripts/benchmark_geometric.py --samples 5
python scripts/benchmark_currency.py --samples 5
python scripts/benchmark_currency_rollup.py --samples 5
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
and observations are recorded in [Performance][performance].

## License

`perfattr` is distributed under the MIT License.

[arithmetic-spec]: https://github.com/JohnDReynolds/perfattr/blob/main/docs/specification.md
[docs]: https://github.com/JohnDReynolds/perfattr/blob/main/docs/README.md
[performance]: https://github.com/JohnDReynolds/perfattr/blob/main/docs/performance.md
[releases]: https://github.com/JohnDReynolds/perfattr/releases
[roadmap]: https://github.com/JohnDReynolds/perfattr/blob/main/_extras/perfattr_roadmap_3.md
[roadmaps]: https://github.com/JohnDReynolds/perfattr/tree/main/_extras
[user-guide]: https://github.com/JohnDReynolds/perfattr/blob/main/docs/user_guide.md
