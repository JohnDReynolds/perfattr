# Phase 2 CI and Publication Gates

**Status:** Complete September 9, 2026.

This phase implements CLN-002 from the
[project-wide KISS review](2026-09-09_project_wide_review.md). It changes only GitHub
Actions verification. It does not change a dependency declaration, calculation,
public API, result schema, test, tolerance, or established threshold.

## Continuous integration

The ordinary Python 3.11 through 3.14 matrix remains unchanged. One additional,
deliberately non-matrixed job now installs the exact declared runtime floor on Python
3.11:

```text
NumPy 1.26.0
pandas 2.2.0
```

The job installs `perfattr` and current pytest, then runs the complete functional
suite. Keeping this as one lane avoids a low-value cross-product of Python and
dependency versions.

## Publication workflow

The release-tag build job now must complete these checks before its artifacts become
available to the trusted-publishing job:

1. install the tagged package and only the tools needed by the release gate;
2. run the complete functional suite;
3. build the source distribution and wheel;
4. verify the tag-derived wheel name and distribution metadata; and
5. install and import the built wheel in a clean environment.

The existing artifact upload and PyPI trusted-publishing steps are unchanged. Because
the publishing job depends on the build job, any new gate failure prevents upload to
PyPI.

## Local verification

The new lower-bound command was reproduced in an isolated Python 3.11.9 environment:

```text
NumPy:   1.26.0
pandas:  2.2.0
pytest:  647 passed in 10.81s
```

pandas 2.2.0 emitted its historical advisory that PyArrow might become mandatory in a
future pandas release. This is an upstream deprecation notice rather than a
`perfattr` defect. Adding PyArrow solely to suppress it would incorrectly enlarge the
project's two-dependency runtime boundary.

The publication sequence was also reproduced with a temporary output directory:

```text
sdist build:       passed
wheel build:       passed
Twine metadata:    passed for both distributions
clean-wheel import: passed; reported perfattr 0.12.0a1
```

Both workflow files parse as YAML, `git diff --check` passes, and neither workflow has
a line longer than 99 characters. GitHub Actions itself will exercise the new jobs
after the changes are pushed.
