# Phase 5 Current-Documentation Simplification

**Status:** Complete September 9, 2026.

This documentation-only phase completes CLN-007 from the
[project-wide KISS review](2026-09-09_project_wide_review.md). It changes no formula,
public API, result schema, dependency, threshold, test, or release gate.

## Changes

- Reduced the README from 542 to 378 lines while retaining its distinguishing-feature
  list, minimal arithmetic and currency examples, short examples for other public
  calculation families, development commands, and governing-document links.
- Replaced duplicated formula and release-history prose in the README with concise
  behavior descriptions and direct links to the governing specifications.
- Reduced `docs/performance.md` from 559 to 85 lines. It now explains the current
  benchmark method, workload shapes, representative observations, and boundary between
  standalone and `ppar` integration checks.
- Preserved the complete former performance document as
  [dated audit history](2026-09-09_performance_history.md), including every standalone
  baseline and `ppar` release-candidate observation.
- Added a disposition table to the original review so completed findings and the one
  deliberately optional compatibility decision are visible without reconstructing the
  implementation history.

Roadmap 3 already received the recommended current-candidate summary in Phase 1. Its
detailed decisions and completed feature history remain intact because they are the
appropriate audit record for future feature selection.

## Verification

The unchanged complete gate passed after the edits:

```text
pytest:  654 passed in 11.60s
pyright: 0 errors, 0 warnings, 0 informations
pylint:  10.00/10
```

`git diff --check` passed, every local Markdown link resolves, and the changed
Markdown files contain no lines longer than 99 characters.
