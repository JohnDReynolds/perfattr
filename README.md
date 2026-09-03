# perfattr

`perfattr` is a small, auditable portfolio performance-attribution calculation
library built with pandas and NumPy.

The initial release will provide a reusable Brinson-Fachler calculation core for
prepared reporting-period data. Source loading, portfolio accounting, vendor schemas,
calendar logic, and presentation are intentionally outside the package boundary.

The first functional alpha slice calculates one prepared reporting period, including
input validation, universe equalization, Brinson-Fachler allocation and selection,
and financial reconciliation. Multi-period linking remains the next calculation
milestone. The governing roadmap is available in
[`_extras/perfattr_roadmap.md`](_extras/perfattr_roadmap.md), and the complete portable
calculation contract is defined in [`docs/specification.md`](docs/specification.md).

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
python -m pylint src/perfattr tests
python -m pyright
```

## License

`perfattr` is distributed under the MIT License.
