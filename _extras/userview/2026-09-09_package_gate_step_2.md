# Package Gate Step 2

**Status:** Local gate passed on September 9, 2026; GitHub follow-up recorded below
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

The initial local Step 2 gate was complete. Commit `e43c397` then let GitHub repeat the
repository's Python 3.11–3.14, minimum-dependency, and package jobs. Selecting and
publishing a stable version remains the separately approved release step.

## GitHub Follow-up

GitHub run `34382657979` passed the Python 3.11–3.14 current-dependency jobs and the
package job, but its Linux Python 3.11 minimum-dependency job exposed eight exact-
identity failures in one-period Menchero linking. Values differed only by
platform-dependent floating-point reconstruction noise, but the established tests
correctly require an exact coefficient of one and were not weakened.

The follow-up change implements the governing one-period identity directly after
validating the Menchero inputs. A focused regression test perturbs the reconstructed
horizon return by one representable float and requires the coefficient to remain
exactly `1.0`.

The corrected source and rebuilt wheel passed:

```text
focused Menchero and integration tests: 53 passed
complete development suite:             655 passed
pylint:                                  10.00/10
pyright:                                 0 errors, 0 warnings, 0 informations
Python 3.11.9 minimum dependencies:      655 passed
Python 3.12.1:                           655 passed
Python 3.13.1:                           655 passed
Python 3.14.7:                           655 passed
sdist and wheel build:                   passed
Twine metadata validation:               passed
pip check and installed-wheel smoke:     passed
```

The minimum-dependency retest retained NumPy 1.26.0 and pandas 2.2.0. No threshold,
tolerance, dependency constraint, or test expectation changed. Repository history and
GitHub Actions retain the replacement-run result.
