# Phase 4 Neutral Prepared-Input Seam

**Status:** Complete September 9, 2026.

This phase implements CLN-004 and the related test-file portion of CLN-005 from the
[project-wide KISS review](2026-09-09_project_wide_review.md). It changes module
ownership, not public calculation behavior.

## Source boundary

The new `_prepared_input.py` module owns the infrastructure genuinely shared by
arithmetic and geometric attribution:

- prepared-frame schema and value normalization;
- period-key, day-count, weight-total, and period-return validation; and
- deterministic portfolio/benchmark universe equalization.

Both calculation families import those functions from the neutral module. Geometric
attribution no longer imports private infrastructure from its arithmetic sibling.
`attribution.py` now begins with Brinson calculation logic after its public result and
policy normalization, falling from 943 to 724 lines.

The moved function bodies, error messages, ordering operations, and missing-side
semantics are unchanged. Their expanded docstrings describe the shared contract and
explicitly distinguish input preparation from attribution mathematics. No common
calculation class or generic engine was introduced.

## Test organization

The seven validation functions formerly at the end of `test_attribution.py` moved to
`test_attribution_validation.py`. Every parameter, assertion, exception expectation,
and tolerance remains intact. The original file is now 865 lines rather than sitting
at the configured 1,000-line ceiling.

A small fixture reader is shared by the new validation file and the effect-linking
boundary tests. `tests/__init__.py` makes that test-support import explicit. Test
collection remains exactly 654 cases; nothing was deleted, combined, skipped, or
marked as an expected failure.

## Verification

The final ordinary gate passed:

```text
pytest:  654 passed in 11.93s
pyright: 0 errors, 0 warnings, 0 informations
pylint:  10.00/10
```

The same 654 tests passed on Python 3.11.9 with NumPy 1.26.0 and pandas 2.2.0. The
only warning was pandas 2.2.0's previously assessed upstream PyArrow advisory.

Five-sample `selected_10x` measurements before and after the move were:

| Public operation | Input | Before | After | Peak before and after |
| --- | --- | ---: | ---: | ---: |
| Arithmetic attribution | Derived | 0.1092 s | 0.1046 s | 44.6 MiB |
| Arithmetic attribution | Authoritative | 0.1093 s | 0.1048 s | 44.6 MiB |
| Geometric attribution | Derived | 0.0878 s | 0.0849 s | 33.1 MiB |
| Geometric attribution | Authoritative | 0.0875 s | 0.0837 s | 33.1 MiB |

The slightly lower elapsed medians are ordinary run variation, not a claimed
optimization. Exact peak allocations and all existing performance gates remain
unchanged.

The source distribution and wheel built successfully, Twine accepted both artifacts,
and a clean environment installed the wheel and imported both public calculators.
No `ppar` adapter or cross-package integration behavior changed, so the 500x host gate
was not required.
