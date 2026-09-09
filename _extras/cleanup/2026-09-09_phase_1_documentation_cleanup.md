# Phase 1 Documentation Cleanup

**Status:** Complete September 9, 2026.

This documentation-only phase implements the approved low-risk findings from the
[project-wide KISS review](2026-09-09_project_wide_review.md). It changes no formula,
public API, result schema, dependency, threshold, or test.

## Changes

- Replaced stale guarded, pending, deferred, and first-release wording in current
  source docstrings and specifications with descriptions of released behavior.
- Added the released currency calculation and roll-up specifications to the arithmetic
  specification's supplement index.
- Distinguished the single-period currency calculator from its released multi-period
  roll-up in the README.
- Added the existing geometric benchmark to the README command list.
- Added concise formula, limit, input, output, and reference documentation to the
  compound-return, logarithmic-smoothing, and Carino helpers.
- Added a short current-candidate summary to Roadmap 3 while retaining every detailed
  decision and completed-roadmap record below it.

This completes CLN-001 and CLN-008. It also completes the Roadmap 3 navigation slice
of CLN-007. The broader README and performance-history reductions were subsequently
completed in [Phase 5](2026-09-09_phase_5_documentation_simplification.md).

## Verification

The unchanged complete gate passed after the edits:

```text
pytest:  647 passed in 12.18s
pyright: 0 errors, 0 warnings, 0 informations
pylint:  10.00/10
```

`git diff --check` passed, all newly referenced local files exist, and the changed
files contain no lines longer than 99 characters.
