# perfattr

`perfattr` is a small, auditable portfolio performance-attribution calculation
library built with pandas and NumPy.

The 0.1.0 release provides a reusable Brinson-Fachler calculation core for
prepared reporting-period data. Portfolio accounting, vendor schemas, and
presentation remain outside the package boundary.

The calculation core accepts one or more prepared reporting periods and provides
input validation, universe equalization, Brinson-Fachler allocation and selection,
logarithmic contribution linking, Carino active-effect linking, cumulative and
full-horizon results, and financial reconciliation. The completed initial roadmap is
recorded in [`_extras/perfattr_roadmap_1.md`](_extras/perfattr_roadmap_1.md). The
portable preparation work is governed by
[`_extras/perfattr_roadmap_2.md`](_extras/perfattr_roadmap_2.md), while later candidates
are kept in the noncommitted
[`_extras/perfattr_roadmap_3.md`](_extras/perfattr_roadmap_3.md). The complete portable
calculation contract is defined in
[`docs/specification.md`](docs/specification.md).

```python
from perfattr import calculate_attribution

result = calculate_attribution(portfolio, benchmark)
print(result.period_detail)
```

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
```

Add `--workload monthly_121260 --profile` to inspect one workload's cumulative
call profile. The benchmark methodology and initial observations are recorded in
[`docs/performance.md`](docs/performance.md).

## License

`perfattr` is distributed under the MIT License.
