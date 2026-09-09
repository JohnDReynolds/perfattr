# Phase 3 Shared Performance-Row Invariants

**Status:** Complete September 9, 2026.

This phase implements CLN-003 from the
[project-wide KISS review](2026-09-09_project_wide_review.md). The source-preparation
and prepared-calculation boundaries now use one private implementation of their shared
contribution and effective-return rules.

## Refactor boundary

The new `_performance_rows.py` helper owns only these established invariants:

- every defined input return is greater than `-1`;
- a nonzero weight requires a defined return;
- supplied contribution is authoritative and finite;
- zero weight with nonzero contribution requires a null input return and produces a
  null effective return;
- zero weight with zero contribution produces a zero effective return;
- omitted contribution is weight times return; and
- derived contribution and defined effective returns must remain finite.

The helper accepts the caller's domain error type and context. It modifies only the
independently owned normalization frame, never the user's DataFrame. Preparation and
attribution retain their exact public exception types and messages, including their
intentional difference when derived contribution overflows.

Source schemas, dates, identities, day counts, period structure, weight totals,
mapping, consolidation, and calculation formulas remain in their existing layers.
The final preparation calculation-domain check also remains: it validates reporting
rows after mapping or consolidation, not the source rows covered by the new helper.
No generic validation framework was introduced.

## Focused tests

Seven tests compare economically identical rows through both boundaries and cover:

- derived contribution with signed weights and an unexposed null-return row;
- authoritative contribution that differs from weight times input return;
- zero-weight fees and zero-contribution rows;
- returns equal to `-1`;
- null return with nonzero exposure;
- a defined return on an unexposed nonzero contribution;
- non-finite effective returns; and
- overflowed derived contribution with each boundary's exact diagnostic.

Expected numerical values are stated from the governing formulas. Boundary parity is
required exactly; no existing assertion or tolerance was weakened.

## Verification

The final complete gate passed in the ordinary development environment:

```text
pytest:  654 passed in 12.07s
pyright: 0 errors, 0 warnings, 0 informations
pylint:  10.00/10
```

The same 654 tests passed on Python 3.11.9 with the exact supported dependency floor,
NumPy 1.26.0 and pandas 2.2.0. pandas emitted the upstream PyArrow advisory already
assessed in the Phase 2 record.

Final five-sample direct measurements on the realistic `selected_10x` workload were:

| Public operation | Input form | Median | Peak traced allocation |
| --- | --- | ---: | ---: |
| Arithmetic attribution | Derived | 0.1092 s | 44.6 MiB |
| Arithmetic attribution | Authoritative | 0.1093 s | 44.6 MiB |
| Geometric attribution | Derived | 0.0878 s | 33.1 MiB |
| Geometric attribution | Authoritative | 0.0875 s | 33.1 MiB |
| Static preparation | Returns only | 0.1537 s | 15.3 MiB |
| Effective-dated preparation | Returns only | 0.1658 s | 16.7 MiB |

The measurements are consistent with the established observations and introduce no
performance threshold. An intermediate version briefly retained an unnecessary
authoritative-contribution array; benchmark evidence caught it, and the final helper
restores the prior 44.6 MiB arithmetic and 33.1 MiB geometric peaks.

The `ppar` 500x workflow was not required because no adapter or cross-package
integration behavior changed. Direct `perfattr` measurements cover the modified
standalone boundaries.
