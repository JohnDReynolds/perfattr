# User Onboarding Step 1

**Status:** Complete on September 9, 2026
**Scope:** Documentation and package metadata only

## Purpose

Make the now-public project easier to install, understand, and evaluate without
changing calculations, input contracts, result schemas, or compatibility behavior.

## Changes

- Added explicit Python, stable-release, and current-prerelease installation guidance
  to the README.
- Reworked the first example to show the concise `period_summary` decision view.
- Added a result-frame chooser and clarified decimal units, failure behavior, and the
  boundary between numerical results and presentation.
- Added a task-oriented user guide covering source frames, mappings, preparation,
  accepted date coverage, calculation choices, outputs, and reconciliation evidence.
- Added a documentation index for the user guide, governing specifications, and
  engineering evidence.
- Changed README documentation references to absolute GitHub links so they work from
  the PyPI project page as well as GitHub.
- Added Documentation, Issues, and Releases links to package metadata.
- Updated released specifications that still described implemented APIs in future
  tense. No formulas or contracts changed.

## Deliberate Deferrals

- No warning, strictness option, or metadata field was added for incomplete final
  reporting periods.
- No common reconciliation schema was introduced across calculation families.
- No release version was changed and no stable release was published.
- No source code, public API, calculation, input contract, or result schema changed.

Those decisions either affect compatibility or belong to the later release step.

## Focused Verification

- Executed the README's domestic preparation and attribution workflow and checked its
  six displayed values independently to `1e-12`.
- Checked local Markdown links in the README, `docs/`, and `_extras/`.
- Checked changed documentation for the 99-character line limit.
- Parsed `pyproject.toml` and confirmed all four project URLs.
- Searched released specifications for the stale implementation-plan phrases targeted
  by this pass.
- Ran `git diff --check`.

The complete functional, static-analysis, build, metadata, and clean-install gate is
Step 2 and was intentionally not duplicated here.
