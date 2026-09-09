# Performance

`perfattr` uses repeatable public-boundary benchmarks to detect worthwhile performance
work. Absolute elapsed times and memory observations are diagnostic, not release
thresholds: rerun the relevant benchmark on the target environment before drawing a
conclusion.

The complete release-by-release record through September 9, 2026 is preserved in the
[historical performance observations][history].

## Benchmark method

Each script constructs deterministic inputs before measurement, warms the public API,
and reports median elapsed time and incremental peak Python-tracked allocation. Input
and result-frame memory are reported separately where useful. Production validation
and reconciliation remain enabled.

| Script | Public boundary |
| --- | --- |
| [`benchmark_core.py`][core] | Arithmetic attribution methods and effect linkers |
| [`benchmark_preparation.py`][preparation] | Static/effective mapping and consolidation |
| [`benchmark_hierarchy.py`][hierarchy] | Additive roll-up of completed attribution |
| [`benchmark_geometric.py`][geometric] | Geometric excess-return attribution |
| [`benchmark_currency.py`][currency] | Single-period currency attribution |
| [`benchmark_currency_rollup.py`][currency-rollup] | Multi-period currency roll-up |

The standard workloads are:

| Workload | Rows per market/performance side | Periods |
| --- | ---: | ---: |
| `normal` | 6,063 | 60 |
| `selected_10x` | 60,630 | 60 |
| `monthly_121260` | 121,260 | 120 |
| `history_25y` | 30,300 | 300 |

The arithmetic and geometric benchmarks exercise both derived contribution from
weight and return and authoritative contribution supplied by accounting. The
arithmetic and hierarchy benchmarks also cover every released method and effect
linker. Currency benchmarks use four side-separated frames and twenty currency rows
per side and period.

Run the commands listed in the README's [Development section][development]. Use
`--help` on an individual script for policy, workload, sample-count, and profiling
options.

## Current representative observations

The following observations are the latest comparable measurements for the largest-row
standard workload, `monthly_121260`. They were collected September 6–9, 2026 on Apple
arm64 with Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. Small timing differences among
methods are ordinary run variation.

| Public operation | Median elapsed | Peak traced allocation |
| --- | ---: | ---: |
| Arithmetic attribution, default policy | 0.1874 s | 89.1 MiB |
| Static-mapped quarterly preparation | 0.2378 s | 30.5 MiB |
| Effective-mapped quarterly preparation | 0.2607 s | 33.3 MiB |
| Hierarchical roll-up, all policy combinations | 0.3426–0.3760 s | 200.4–222.6 MiB |
| Geometric attribution | 0.1531 s | 66.0 MiB |
| Currency attribution | 0.1474 s | 64.2 MiB |
| Multi-period currency roll-up | 0.0470 s | 22.0 MiB |

The hierarchy case intentionally expands every leaf through six ancestor levels, so
its larger peak reflects result construction rather than a second attribution engine.
The effective-dated preparation observation includes the vectorized interval-assignment
path documented in the [80/20 optimization review][optimization]. None of these values
establishes a machine-independent threshold or justifies another runtime dependency.

## Integration boundary

Standalone core changes use the direct benchmarks above. Changes to the `ppar` adapter
or cross-package integration must also run the permanent `ppar` 500x release-candidate
workflow. The last recorded Roadmap 13 integration retained byte-identical large-site
output and passed its unchanged scale gates; the detailed chronology is retained in
the [historical record][history].

[core]: ../scripts/benchmark_core.py
[preparation]: ../scripts/benchmark_preparation.py
[hierarchy]: ../scripts/benchmark_hierarchy.py
[geometric]: ../scripts/benchmark_geometric.py
[currency]: ../scripts/benchmark_currency.py
[currency-rollup]: ../scripts/benchmark_currency_rollup.py
[development]: ../README.md#development
[history]: ../_extras/cleanup/2026-09-09_performance_history.md
[optimization]: ../_extras/optimizations/2026-09-09_80_20_review.md
