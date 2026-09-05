# perfattr

`perfattr` is a small, auditable portfolio performance-attribution calculation
library built with pandas and NumPy.

The package provides a reusable Brinson-Fachler calculation core and a portable
preparation layer for source-period weights and returns. Portfolio accounting, vendor
schemas, and presentation remain outside the package boundary.

## Main features

- Accept weights and returns, or authoritative contributions when accounting results
  are available.
- Validate, select, and align portfolio and benchmark histories.
- Consolidate smaller source periods into complete monthly, quarterly, or yearly
  reporting periods using calendar and holiday rules.
- Apply static or effective-dated classification mappings before consolidation.
- Calculate Brinson-Fachler allocation with either compact two-effect selection or
  explicit three-effect selection and interaction.
- Link contributions logarithmically and attribution effects using Carino linking.
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
The opt-in Brinson-Fachler three-effect work is governed by
[`_extras/perfattr_roadmap_5_brinson_fachler_three_effect.md`][three-effect-roadmap]
and [`docs/brinson_fachler_three_effect_specification.md`][three-effect-spec].
The complete portable calculation contract is defined in
[`docs/specification.md`](docs/specification.md), and the accepted roadmap 2 preparation
contract is in [`docs/preparation_specification.md`](docs/preparation_specification.md).

[effective-spec]: docs/effective_dated_classification_specification.md
[effective-roadmap]: _extras/perfattr_roadmap_4_effective_dated_classification.md
[three-effect-roadmap]: _extras/perfattr_roadmap_5_brinson_fachler_three_effect.md
[three-effect-spec]: docs/brinson_fachler_three_effect_specification.md

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

## Attribution methods

The default remains the released two-effect Brinson-Fachler convention: allocation is
reported separately, while portfolio-weighted selection absorbs interaction. Opt in
to explicit interaction with the public method enum:

```python
from perfattr import AttributionMethod, calculate_attribution

three_effect = calculate_attribution(
    prepared.portfolio,
    prepared.benchmark,
    method=AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
)
print(
    three_effect.period_detail[
        ["allocation_effect", "selection_effect", "interaction_effect"]
    ]
)
```

For portfolio and benchmark weights `wP` and `wB`, effective returns `rP` and `rB`,
and total benchmark return `B`, the three effects are:

```text
allocation  = (wP - wB) * (rB - B)
selection   = wB * (rP - rB)
interaction = (wP - wB) * (rP - rB)
```

Positive and negative values follow these signed formulas; `perfattr` does not label
an effect as favorable or unfavorable. Supplied contribution remains authoritative.
If either effective return is undefined, interaction is zero and selection retains
the reconciled residual rather than inventing a return.

The opt-in result inserts `interaction_effect` immediately after `selection_effect`
and `linked_interaction_effect` immediately after `linked_selection_effect` wherever
those channels apply. Cumulative output also places
`cumulative_interaction_effect` immediately after `cumulative_selection_effect`.
`AttributionResult.method` records the selected convention. See the
[three-effect specification][three-effect-spec] for the complete schemas, linking
rules, null policy, and independently calculated example.

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

Run the four roadmap performance workloads:

```bash
python scripts/benchmark_core.py --samples 5
python scripts/benchmark_core.py --samples 5 --input-form authoritative
python scripts/benchmark_preparation.py --samples 5
```

Pass `--method three-effect` to `benchmark_core.py` to measure the opt-in calculation;
the default remains `--method two-effect`.

Add `--workload monthly_121260 --profile` to inspect one workload's cumulative
calculation-core call profile. The preparation benchmark compares static and
effective-dated mappings through quarterly consolidation. The benchmark methodology
and observations are recorded in [`docs/performance.md`](docs/performance.md).

## License

`perfattr` is distributed under the MIT License.
