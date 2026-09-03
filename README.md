# perfattr

`perfattr` is a small, auditable portfolio performance-attribution calculation
library built with pandas and NumPy.

The initial release will provide a reusable Brinson-Fachler calculation core for
prepared reporting-period data. Source loading, portfolio accounting, vendor schemas,
calendar logic, and presentation are intentionally outside the package boundary.

The project is in its initial specification and implementation phase. The governing
roadmap is available in [`_extras/perfattr_roadmap.md`](_extras/perfattr_roadmap.md).

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
