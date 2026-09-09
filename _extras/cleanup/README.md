# Cleanup Reviews

This directory records read-only maintainability and simplification reviews. A review
may add documentation here, but it does not authorize source, test, configuration,
schema, compatibility, threshold, or release-gate changes.

## Reviews

- [September 9, 2026: project-wide KISS review](2026-09-09_project_wide_review.md) —
  no confirmed dead production code or live compatibility shim; four worthwhile
  cleanup themes and several deliberately retained structures
- [Phase 1 documentation cleanup](2026-09-09_phase_1_documentation_cleanup.md) —
  stale implementation-state prose removed, mathematical linking docstrings
  completed, and current Roadmap 3 candidates summarized
- [Phase 2 CI and publication gates](2026-09-09_phase_2_ci_release_gates.md) —
  minimum supported runtime dependencies tested and publication blocked on functional
  and clean-wheel verification
- [Phase 3 shared row invariants](2026-09-09_phase_3_shared_row_invariants.md) —
  duplicated contribution and effective-return rules consolidated without changing
  either public boundary
- [Phase 4 prepared-input seam](2026-09-09_phase_4_prepared_input_seam.md) —
  arithmetic and geometric attribution now share a neutral private input boundary,
  with validation tests separated intact
- [Phase 5 current-documentation
  simplification](2026-09-09_phase_5_documentation_simplification.md) —
  current usage and benchmark guidance shortened while complete performance history
  remains available as an audit record
- [Archived performance history](2026-09-09_performance_history.md) — the former
  current-facing performance document, including release-by-release standalone and
  `ppar` integration observations
