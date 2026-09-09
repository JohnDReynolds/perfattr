# Stable Release 0.12.0

**Status:** Released September 9, 2026

## Purpose

Publish the complete current feature set as `perfattr==0.12.0`, so an ordinary
`pip install perfattr` no longer selects the much older `0.3.0` release.

This is a release and documentation step. It introduces no new calculation feature,
input contract, result schema, tolerance, dependency, or compatibility behavior.

## Release Changes

- Change the package version from `0.12.0a1` to `0.12.0`.
- Change the PyPI maturity classifier from Alpha to Beta. The version is stable while
  the classifier remains appropriately cautious about project maturity.
- Replace prerelease installation instructions with the ordinary stable-install
  command.
- Publish the user guide, documentation index, public project links, and specification
  wording completed during the onboarding pass.
- Include the exact cross-platform one-period Menchero identity correction found by
  the Python 3.11 minimum-dependency CI lane.

## Proposed GitHub Release Notes

`perfattr 0.12.0` makes the complete source-neutral attribution package available as a
stable installation. It includes:

- pandas DataFrame and CSV preparation with validation, selection, period alignment,
  fixed-frequency consolidation, and static or effective-dated classifications;
- Brinson-Fachler and Brinson-Hood-Beebower two- and three-effect calculations with
  Carino, Frongello, or Menchero arithmetic effect linking;
- separate geometric attribution, hierarchical result roll-up, Karnosky-Singer
  currency attribution, and multi-period currency roll-up;
- deterministic result frames with explicit financial reconciliation; and
- public onboarding documentation and Python 3.11–3.14 support.

The release also preserves the exact one-period Menchero identity across platform math
libraries. It adds no runtime dependency beyond NumPy and pandas.

## Required Gate

Before tagging the release:

- run all tests on Python 3.11 through 3.14;
- run the Python 3.11 minimum-dependency lane with NumPy 1.26.0 and pandas 2.2.0;
- require Pylint 10.00/10 and Pyright with no errors or warnings;
- build the source distribution and wheel from the release candidate;
- validate both artifacts with Twine;
- install the wheel into an isolated environment and run `pip check` plus public API,
  version, calculation, and reconciliation smoke checks; and
- require `git diff --check` and clean release-commit state.

After publication, verify the trusted-publishing workflow and install `perfattr`
without `--pre` or a version pin from the public PyPI index in a new environment.

## Release-Candidate Evidence

The feature-frozen candidate passed without changing a gate:

```text
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

The isolated artifacts are `perfattr-0.12.0.tar.gz` and
`perfattr-0.12.0-py3-none-any.whl`. Their metadata reports version `0.12.0`, Beta
maturity, Python `>=3.11`, MIT licensing, only NumPy and pandas runtime dependencies,
and all four public project URLs. The source distribution contains the public README,
documentation index, and user guide.

## Publication Evidence

Release commit `34f47b8e4875cccd5c410041e11f0db2a43cd312` passed all six jobs in
[release-candidate CI run `34385116420`][candidate-run]. The commit was tagged with
annotated tag `v0.12.0` and published as a non-prerelease
[GitHub release][github-release].

[Trusted-publishing run `34385397818`][publish-run] passed its tagged functional test,
build, tag/version, Twine, clean-wheel, artifact-upload, and PyPI publication steps.
The version-specific PyPI endpoint then returned successfully, and the default public
index reported `0.12.0` as its latest stable version.

A new Python 3.11 environment installed `perfattr` from `https://pypi.org/simple`
without `--pre` or a version pin. The public wheel:

- reported package and distribution version `0.12.0`;
- resolved from the new environment's `site-packages`;
- exposed every declared root API;
- carried the Beta classifier and four project URLs;
- passed `pip check`; and
- completed the README preparation and attribution calculation with exact expected
  total effect and passing reconciliation.

The first no-cache request reached PyPI before its default index had propagated and
selected `0.3.0`. Verification correctly remained open. The immediately subsequent
public-index check identified `0.12.0`, and the repeated unpinned request upgraded to
it successfully.

[candidate-run]: https://github.com/JohnDReynolds/perfattr/actions/runs/34385116420
[github-release]: https://github.com/JohnDReynolds/perfattr/releases/tag/v0.12.0
[publish-run]: https://github.com/JohnDReynolds/perfattr/actions/runs/34385397818
