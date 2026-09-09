# Correctness Finding Resolutions

**Status:** Complete September 9, 2026.

This follow-up implements all three findings from the
[read-only correctness review](2026-09-09_read_only_review.md). While hardening the
shared day-count boundary, it also found and fixed one adjacent low-severity numeric
coercion defect. No financial formula, output schema, tolerance, warning threshold,
runtime dependency, or valid real-valued input behavior changed.

## Resolution summary

| ID | Severity | Resolution |
|---|---|---|
| COR-001 | Moderate | Final prepared returns and period totals are checked against the calculation domain |
| COR-002 | Low | Classification CSV headers are rejected instead of becoming metadata |
| COR-003 | Low | Positive day counts are range-checked before exact `int64` conversion |
| COR-004 | Low | Complex numeric inputs are rejected instead of losing their imaginary component |

## COR-001: preparation-to-calculation compatibility

`prepare_attribution` now validates both final prepared sides before constructing a
successful result. Every defined prepared identifier return and every prepared period
contribution total must be finite and greater than `-1.0`, including copied exact
reporting periods.

This preserves authoritative contribution and the existing effective-return rules.
It only moves failures for noncompoundable final output to the preparation boundary,
where the documented composition contract requires them to occur.

Two public regression tests independently cover:

- an exact authoritative period totaling -110%; and
- a valid 10% period whose separately mapped group has an effective return of -120%.

Both now raise `PreparationError` before unusable frames can be returned. The
preparation specification explicitly records the final output requirement.

## COR-002: headerless classification CSV

The canonical two-column classification reader now applies the same header rejection
rule as the headerless mapping reader. A row equal to
`classification_identifier,classification_name`, after surrounding whitespace is
removed, raises `PreparationError` instead of creating a phantom classification.

A focused reader regression test covers the conventional header followed by valid
metadata.

## COR-003: exact day-count range

A shared positive-`int64` normalizer now distinguishes integer-typed inputs from other
numeric inputs:

- integer inputs are checked before any float conversion, preserving the valid
  `int64` maximum exactly;
- floating inputs must be finite, positive, integral, and strictly below `2**63`; and
- unrepresentable values raise `AttributionError` instead of saturating during pandas
  conversion.

Public tests prove both rejection of `2**63` and exact acceptance of the signed
`int64` maximum. The calculation specification now makes the representable range
explicit.

## COR-004: adjacent complex-number coercion

During COR-003 implementation, a direct probe showed that pandas complex-valued
weights, returns, contributions, and day counts passed the shared numeric type check.
Conversion to `float64` discarded the imaginary component, emitted warnings, and let
calculation continue with a different number.

The shared numeric normalizer now rejects complex dtypes before conversion. A focused
test proves rejection of `1 + 2j`, and both governing input specifications state that
complex values are not valid real-valued financial numbers.

## Verification

The complete post-change gate passed:

```text
pytest:  647 passed in 11.08s
pyright: 0 errors, 0 warnings, 0 informations
pylint:  10.00/10
git diff --check: clean
```

Focused correctness coverage passed 141 tests across preparation, I/O, attribution,
day-count validation, and shared validation.

The established largest direct benchmarks also completed successfully on Python
3.11.9, pandas 3.0.5, NumPy 2.4.6, and Apple arm64:

| Operation | Workload | Median | Peak traced allocation |
|---|---|---:|---:|
| Arithmetic attribution | 121,260 rows per side, 120 periods | `0.1897 s` | `89.1 MiB` |
| Static-mapped preparation | 121,260 rows per side, 120 periods | `0.2457 s` | `30.5 MiB` |
| Effective-mapped preparation | 121,260 rows per side, 120 periods | `0.2596 s` | `33.3 MiB` |

These observations are consistent with the immediately preceding recorded baselines.
They establish no new performance threshold.

