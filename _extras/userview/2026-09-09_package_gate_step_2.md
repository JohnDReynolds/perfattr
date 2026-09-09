# Package Gate Step 2

**Status:** Passed on September 9, 2026
**Scope:** Complete local release-candidate verification of the Step 1 onboarding
changes

## Result

The package gate passed without changing a test, warning threshold, tolerance,
dependency constraint, public API, result schema, or calculation.

## Functional and Static Analysis

The development environment used Python 3.11.9:

```text
pytest:  654 passed in 11.96s
pylint:  10.00/10
pyright: 0 errors, 0 warnings, 0 informations
```

## Supported Python and Dependency Matrix

The built wheel passed all 654 tests in each locally available supported interpreter:

| Environment | NumPy | pandas | Result |
| --- | --- | --- | --- |
| Python 3.11.9 minimum dependencies | 1.26.0 | 2.2.0 | 654 passed |
| Python 3.12.1 | 2.5.3 | 3.0.5 | 654 passed |
| Python 3.13.1 | 2.5.3 | 3.0.5 | 654 passed |
| Python 3.14.7 | 2.5.3 | 3.0.5 | 654 passed |

The minimum-dependency run emitted pandas 2.2.0's upstream deprecation notice that
PyArrow would become required in pandas 3.0. This is not a `perfattr` warning or
failure; the current pandas 3.0.5 runs passed without it.

## Distribution Verification

An isolated PEP 517 build using Hatchling 1.32.0 produced:

```text
perfattr-0.12.0a1.tar.gz
perfattr-0.12.0a1-py3-none-any.whl
```

- Twine accepted both artifacts.
- The source distribution contains the README, license, package configuration,
  documentation index, and user guide.
- Built metadata reports Python `>=3.11`, MIT licensing, NumPy and pandas runtime
  requirements, and the Repository, Documentation, Issues, and Releases URLs.
- A separate clean Python 3.11 environment installed the wheel with NumPy 2.4.6 and
  pandas 3.0.5.
- `pip check` found no broken requirements.
- The installed package resolved from that environment's `site-packages`, exposed
  every declared root export, reported version `0.12.0a1`, and completed the README
  preparation and arithmetic calculation with passing reconciliation.

Existing artifacts in the repository's `dist/` directory were not read, overwritten,
or used. The verified artifacts and environments were created in an isolated temporary
directory.

## Readiness

The local Step 2 gate is complete. Committing and pushing the onboarding changes would
let GitHub repeat the repository's Python 3.11–3.14, minimum-dependency, and package
jobs. Selecting and publishing a stable version remains the separately approved
release step.
