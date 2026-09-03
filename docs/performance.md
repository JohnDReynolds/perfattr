# Performance observations

This document records repeatable observations rather than release thresholds. Run the
benchmark again on the target environment before drawing conclusions from the absolute
times.

## Method

[`scripts/benchmark_core.py`](../scripts/benchmark_core.py) builds deterministic,
prepared inputs before measurement, warms the public API once, and reports the median
of the requested elapsed-time samples. Peak memory is the incremental peak of
Python-tracked allocations while `calculate_attribution` runs; prepared input memory
is reported separately.

The four workloads correspond to the roadmap shapes:

- `normal`: 6,063 rows per side across 60 monthly periods;
- `selected_10x`: 60,630 rows per side across 60 monthly periods;
- `monthly_121260`: 121,260 rows per side across 120 monthly periods; and
- `history_25y`: 30,300 rows per side across 300 monthly periods.

The default `derived` form supplies weights and returns. The `authoritative` form also
supplies contribution, matching the accounting-integrated contract.

## Initial standalone baseline

These observations were collected on September 3, 2026, on an Apple arm64 machine
using Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. Each elapsed result is the median of
five samples.

| Workload | Input form | Median elapsed | Prepared inputs | Peak traced allocation |
| --- | --- | ---: | ---: | ---: |
| `normal` | derived | 0.0270 s | 2.0 MiB | 4.6 MiB |
| `selected_10x` | derived | 0.0971 s | 20.4 MiB | 44.6 MiB |
| `monthly_121260` | derived | 0.1723 s | 40.7 MiB | 89.0 MiB |
| `history_25y` | derived | 0.0576 s | 10.2 MiB | 22.4 MiB |
| `normal` | authoritative | 0.0275 s | 2.1 MiB | 4.6 MiB |
| `selected_10x` | authoritative | 0.0969 s | 21.3 MiB | 44.6 MiB |
| `monthly_121260` | authoritative | 0.1718 s | 42.6 MiB | 89.1 MiB |
| `history_25y` | authoritative | 0.0575 s | 10.6 MiB | 22.4 MiB |

Profiling the largest workload placed most core time in required input validation and
normalization. The absolute time was already modest, so no core refactor or additional
dependency was justified.

## `ppar` adapter observation

An isolated 121,260-row-per-side adapter profile used Python 3.12.1, pandas 3.0.0,
NumPy 2.4.2, and Polars 1.38.0. It identified per-value Python-list materialization at
the pandas/Polars boundary as the dominant non-core cost. Passing existing columnar
NumPy arrays in both directions reduced the median of five samples from approximately
0.52 seconds to 0.23 seconds and reduced peak traced allocation from 142.9 MiB to
113.1 MiB. The comprehensive cross-engine tests and 500x integration gate remain the
authority for correctness and workflow performance.

After the change, the pandas-backed 500x integration command passed all scenarios.
The large-source workflow took 1.41 seconds at both 12,126 and 6,063,000 source rows;
the selected-input workflow grew from 0.23 to 0.47 seconds at 10x rows; and the
long-history workflow grew from 1.28 to 1.85 seconds at 5x history. These timings are
observations, not thresholds.
