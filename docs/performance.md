# Performance observations

This document records repeatable observations rather than release thresholds. Run the
benchmark again on the target environment before drawing conclusions from the absolute
times.

## Method

[`scripts/benchmark_core.py`](../scripts/benchmark_core.py) builds deterministic,
prepared inputs before measurement, warms the public API once, and reports the median
of the requested elapsed-time samples. Peak memory is the incremental peak of
Python-tracked allocations while `calculate_attribution` runs; prepared input memory
is reported separately. `--method two-effect` is the unchanged default;
`--method three-effect` measures Brinson-Fachler with explicit interaction, and
`--method bhb-three-effect` and `--method bhb-two-effect` measure explicit and compact
Brinson-Hood-Beebower on the same inputs. `--effect-linking-method carino` is the
unchanged benchmark default; `--effect-linking-method frongello` selects the
path-dependent linker, and `--effect-linking-method menchero` selects the optimized
order-independent linker. Neither option changes contribution linking or workload
construction.

The four workloads correspond to the roadmap shapes:

- `normal`: 6,063 rows per side across 60 monthly periods;
- `selected_10x`: 60,630 rows per side across 60 monthly periods;
- `monthly_121260`: 121,260 rows per side across 120 monthly periods; and
- `history_25y`: 30,300 rows per side across 300 monthly periods.

The default `derived` form supplies weights and returns. The `authoritative` form also
supplies contribution, matching the accounting-integrated contract.

[`scripts/benchmark_preparation.py`](../scripts/benchmark_preparation.py) uses the same
four selected-history sizes with monthly returns-only source rows. It measures the
complete public `prepare_attribution` boundary: normalization, alignment, independent
mapping of both sides, quarterly consolidation, and reconciliation. The static form
maps each identifier to one of twenty classifications. The effective form gives every
identifier two inclusive assignments and changes its classification at a month
boundary inside a quarter. Source frames and mappings are constructed before timing.

[`scripts/benchmark_hierarchy.py`](../scripts/benchmark_hierarchy.py) constructs a
reconciled `AttributionResult` and a static hierarchy before measurement, then times
the complete public `roll_up_attribution` boundary. It uses the established selected-
history row counts with fixed leaf universes per period and depths of two, three, six,
and eight. The default command crosses all four attribution methods with all three
effect linkers. Source-result and hierarchy memory are reported separately from the
incremental Python-tracked allocation during roll-up.

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

## 0.2.0 release-candidate observations

These observations were collected on September 4, 2026, on the same Apple arm64
machine using Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. Each elapsed result is the
median of five samples.

| Workload | Input form | Median elapsed | Prepared inputs | Peak traced allocation |
| --- | --- | ---: | ---: | ---: |
| `normal` | derived | 0.0314 s | 2.0 MiB | 4.6 MiB |
| `selected_10x` | derived | 0.1066 s | 20.4 MiB | 44.6 MiB |
| `monthly_121260` | derived | 0.1782 s | 40.7 MiB | 89.1 MiB |
| `history_25y` | derived | 0.0598 s | 10.2 MiB | 22.4 MiB |
| `normal` | authoritative | 0.0290 s | 2.1 MiB | 4.6 MiB |
| `selected_10x` | authoritative | 0.1040 s | 21.3 MiB | 44.6 MiB |
| `monthly_121260` | authoritative | 0.1831 s | 42.6 MiB | 89.1 MiB |
| `history_25y` | authoritative | 0.0616 s | 10.6 MiB | 22.4 MiB |

The required `ppar` 500x integration gate also passed after the complete preparation
migration. The large-source workflow processed 12,126 and 6,063,000 source rows in
10.30 and 10.47 seconds respectively, with byte-identical artifacts. The 10x selected
workload took 1.65 and 2.55 seconds. The 5x long-history workload took 10.27 and 13.79
seconds, a 1.343x ratio below its 1.58x warning and 1.65x failure gates.

The `0.2.1` patch batches reporting-period assignment, consolidation, and independent
reconciliation across the complete history while retaining the same formulas and
checks. In two consecutive warm-state integration measurements, the 5x long-history
workload completed in 1.51 versus 2.15 seconds (1.424x) and 1.34 versus 2.11 seconds
(1.571x). Both runs passed the unchanged 1.58x warning and 1.65x failure boundaries;
all large-source artifacts remained byte-identical.

The `0.2.2` patch performs the independent reporting-return reconciliation against
compact source-period arrays instead of repeatedly filtering complete identifier-level
frames. Two consecutive warm-state integration measurements completed in 1.39 versus
2.11 seconds (1.520x) and 1.31 versus 2.03 seconds (1.553x). Both passed the unchanged
boundaries without changing the financial checks or `ppar` report content.

## Effective-dated preparation baseline

These observations were collected on September 4, 2026, on the same Apple arm64
machine using Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. Each elapsed result is the
median of five samples. Input memory includes both source histories and both mappings;
peak memory is the incremental Python-tracked allocation while preparation runs.

| Workload | Mapping | Median elapsed | Inputs | Peak traced allocation |
| --- | --- | ---: | ---: | ---: |
| `normal` | static | 0.0935 s | 1.2 MiB | 1.7 MiB |
| `normal` | effective | 0.1227 s | 1.3 MiB | 2.9 MiB |
| `selected_10x` | static | 0.1487 s | 12.4 MiB | 15.3 MiB |
| `selected_10x` | effective | 0.4647 s | 13.0 MiB | 15.4 MiB |
| `monthly_121260` | static | 0.2582 s | 24.6 MiB | 30.5 MiB |
| `monthly_121260` | effective | 0.8773 s | 25.1 MiB | 30.6 MiB |
| `history_25y` | static | 0.2524 s | 6.1 MiB | 8.4 MiB |
| `history_25y` | effective | 0.3978 s | 6.2 MiB | 9.6 MiB |

Effective assignment costs more elapsed time because it validates and resolves an
inclusive interval for every mapped source row. The largest absolute difference was
0.6191 seconds for 121,260 rows per side, whose effective run remained below one
second. Peak traced allocation for that workload increased by 0.1 MiB. The normal
selected history added 0.0292 seconds and 1.2 MiB. These are initial observations, not
release thresholds. The absolute results do not justify complicating the resolver or
adding a dependency; profile again if a real workflow identifies this stage as a
bottleneck.

The complete 247-test functional suite also passed in isolated environments under
each supported CI interpreter family: Python 3.11, 3.12, 3.13, and 3.14. Pyright
reported zero errors and warnings, and Pylint reported 10.00/10 with no messages on
the project's Python 3.11 development environment.

## 0.4.0a1 attribution-method observations

These release-candidate observations were collected on September 5, 2026, on the same
Apple arm64 machine using Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. Each elapsed
result is the median of five samples. Both methods used the identical deterministic
derived-contribution inputs.

| Workload | Method | Median elapsed | Prepared inputs | Peak traced allocation |
| --- | --- | ---: | ---: | ---: |
| `normal` | two-effect | 0.0302 s | 2.0 MiB | 4.6 MiB |
| `normal` | three-effect | 0.0299 s | 2.0 MiB | 4.8 MiB |
| `selected_10x` | two-effect | 0.1058 s | 20.4 MiB | 44.6 MiB |
| `selected_10x` | three-effect | 0.1072 s | 20.4 MiB | 47.1 MiB |
| `monthly_121260` | two-effect | 0.1877 s | 40.7 MiB | 89.1 MiB |
| `monthly_121260` | three-effect | 0.1889 s | 40.7 MiB | 94.1 MiB |
| `history_25y` | two-effect | 0.0640 s | 10.2 MiB | 22.4 MiB |
| `history_25y` | three-effect | 0.0656 s | 10.2 MiB | 23.6 MiB |

The three-effect elapsed medians ranged from 0.3% lower to 2.5% higher than the
two-effect observations, which is ordinary benchmark variation at these durations.
Peak traced allocation increased by 0.2 to 5.0 MiB, consistent with carrying the two
additional interaction columns rather than a second calculation engine. These are
observations, not new thresholds; no optimization or dependency is justified by the
measured differences.

## Roadmap 6 BHB release-candidate observations

These observations were collected on September 5, 2026, on the same Apple arm64
machine using Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. Each elapsed result is the
median of five samples using identical deterministic derived-contribution inputs.

| Workload | Method | Median elapsed | Prepared inputs | Peak traced allocation |
| --- | --- | ---: | ---: | ---: |
| `normal` | BF two-effect | 0.0330 s | 2.0 MiB | 4.6 MiB |
| `normal` | BF three-effect | 0.0301 s | 2.0 MiB | 4.8 MiB |
| `normal` | BHB three-effect | 0.0303 s | 2.0 MiB | 4.8 MiB |
| `selected_10x` | BF two-effect | 0.1092 s | 20.4 MiB | 44.6 MiB |
| `selected_10x` | BF three-effect | 0.1057 s | 20.4 MiB | 47.1 MiB |
| `selected_10x` | BHB three-effect | 0.1070 s | 20.4 MiB | 47.1 MiB |
| `monthly_121260` | BF two-effect | 0.1845 s | 40.7 MiB | 89.0 MiB |
| `monthly_121260` | BF three-effect | 0.1866 s | 40.7 MiB | 94.1 MiB |
| `monthly_121260` | BHB three-effect | 0.1880 s | 40.7 MiB | 94.1 MiB |
| `history_25y` | BF two-effect | 0.0632 s | 10.2 MiB | 22.4 MiB |
| `history_25y` | BF three-effect | 0.0641 s | 10.2 MiB | 23.6 MiB |
| `history_25y` | BHB three-effect | 0.0640 s | 10.2 MiB | 23.6 MiB |

BHB elapsed medians ranged from 0.2% lower to 1.2% higher than BF three-effect, and
their peak traced allocations were equal at the reported precision. This is
consistent with sharing the same vectorized three-effect aggregation path. The
measurements are observations, not release thresholds, and do not justify a new
optimization or dependency.

## Roadmap 7 compact BHB release-candidate observations

These observations were collected on September 5, 2026, on the same Apple arm64
machine using Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. Each elapsed result is the
median of five samples using identical deterministic derived-contribution inputs.

| Workload | Method | Median elapsed | Prepared inputs | Peak traced allocation |
| --- | --- | ---: | ---: | ---: |
| `normal` | BF two-effect | 0.0270 s | 2.0 MiB | 4.6 MiB |
| `normal` | BF three-effect | 0.0271 s | 2.0 MiB | 4.8 MiB |
| `normal` | BHB three-effect | 0.0275 s | 2.0 MiB | 4.8 MiB |
| `normal` | BHB two-effect | 0.0272 s | 2.0 MiB | 4.6 MiB |
| `selected_10x` | BF two-effect | 0.0956 s | 20.4 MiB | 44.6 MiB |
| `selected_10x` | BF three-effect | 0.0957 s | 20.4 MiB | 47.1 MiB |
| `selected_10x` | BHB three-effect | 0.0965 s | 20.4 MiB | 47.1 MiB |
| `selected_10x` | BHB two-effect | 0.0963 s | 20.4 MiB | 44.6 MiB |
| `monthly_121260` | BF two-effect | 0.1719 s | 40.7 MiB | 89.1 MiB |
| `monthly_121260` | BF three-effect | 0.1750 s | 40.7 MiB | 94.1 MiB |
| `monthly_121260` | BHB three-effect | 0.1758 s | 40.7 MiB | 94.1 MiB |
| `monthly_121260` | BHB two-effect | 0.1729 s | 40.7 MiB | 89.1 MiB |
| `history_25y` | BF two-effect | 0.0569 s | 10.2 MiB | 22.4 MiB |
| `history_25y` | BF three-effect | 0.0579 s | 10.2 MiB | 23.6 MiB |
| `history_25y` | BHB three-effect | 0.0586 s | 10.2 MiB | 23.6 MiB |
| `history_25y` | BHB two-effect | 0.0574 s | 10.2 MiB | 22.4 MiB |

Compact BHB medians were 0.6% to 0.9% above compact BF in this run, and their peak
traced allocations were equal at the reported precision. Compact BHB also retained
the lower memory footprint expected from omitting the two interaction columns carried
by three-effect output. These remain observations rather than thresholds; no
optimization, dependency, formula, or release gate is changed.

## Roadmap 8 Frongello release-candidate observations

These observations were collected on September 5, 2026, on the same Apple arm64
machine using Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. Each elapsed result is the
median of five samples using identical deterministic derived-contribution inputs.
Carino and Frongello were measured through the same public calculation boundary for
every attribution method.

| Workload | Method | Carino time | Frongello time | Carino peak | Frongello peak |
| --- | --- | ---: | ---: | ---: | ---: |
| `normal` | BF two-effect | 0.0351 s | 0.0321 s | 4.6 MiB | 4.6 MiB |
| `normal` | BF three-effect | 0.0322 s | 0.0340 s | 4.8 MiB | 4.8 MiB |
| `normal` | BHB three-effect | 0.0327 s | 0.0339 s | 4.8 MiB | 4.8 MiB |
| `normal` | BHB two-effect | 0.0321 s | 0.0324 s | 4.6 MiB | 4.6 MiB |
| `selected_10x` | BF two-effect | 0.1116 s | 0.1165 s | 44.6 MiB | 44.6 MiB |
| `selected_10x` | BF three-effect | 0.1149 s | 0.1147 s | 47.1 MiB | 47.1 MiB |
| `selected_10x` | BHB three-effect | 0.1107 s | 0.1165 s | 47.1 MiB | 47.1 MiB |
| `selected_10x` | BHB two-effect | 0.1110 s | 0.1115 s | 44.6 MiB | 44.6 MiB |
| `monthly_121260` | BF two-effect | 0.1921 s | 0.2032 s | 89.1 MiB | 89.1 MiB |
| `monthly_121260` | BF three-effect | 0.1961 s | 0.2044 s | 94.1 MiB | 94.1 MiB |
| `monthly_121260` | BHB three-effect | 0.1959 s | 0.2059 s | 94.1 MiB | 94.1 MiB |
| `monthly_121260` | BHB two-effect | 0.1990 s | 0.1964 s | 89.1 MiB | 89.1 MiB |
| `history_25y` | BF two-effect | 0.0661 s | 0.0703 s | 22.4 MiB | 22.4 MiB |
| `history_25y` | BF three-effect | 0.0671 s | 0.0716 s | 23.6 MiB | 23.6 MiB |
| `history_25y` | BHB three-effect | 0.0716 s | 0.0732 s | 23.6 MiB | 23.6 MiB |
| `history_25y` | BHB two-effect | 0.0669 s | 0.0679 s | 22.4 MiB | 22.4 MiB |

Prepared inputs were 2.0, 20.4, 40.7, and 10.2 MiB respectively for the four
workloads under both linkers. Frongello medians ranged from 8.5% below to 6.7% above
the paired Carino measurements. At these short absolute durations, the lower normal-
workload value is ordinary measurement variation; the largest observed absolute
increase was 0.0111 seconds on 121,260 rows per side. Peak traced allocations were
identical at the reported precision for every paired method and workload, consistent
with calculating one short factor vector per reporting period rather than expanding
the identifier grid.

These are observations only. They provide no evidence for an optimization or a new
performance threshold, and no dependency, formula, tolerance, warning, or established
gate changed.

## Roadmap 9 Menchero release-candidate observations

These observations were collected on September 6, 2026, on the same Apple arm64
machine using Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. Each elapsed result is the
median of five samples using identical deterministic derived-contribution inputs.
Carino, Frongello, and Menchero were measured through the same public calculation
boundary for every attribution method and all four established workloads.

| Workload | Method | Carino | Frongello | Menchero | Peak per linker |
| --- | --- | ---: | ---: | ---: | ---: |
| `normal` | BF two-effect | 0.0416 s | 0.0326 s | 0.0329 s | 4.6 MiB |
| `normal` | BF three-effect | 0.0329 s | 0.0317 s | 0.0322 s | 4.8 MiB |
| `normal` | BHB three-effect | 0.0320 s | 0.0332 s | 0.0327 s | 4.8 MiB |
| `normal` | BHB two-effect | 0.0319 s | 0.0343 s | 0.0327 s | 4.6 MiB |
| `selected_10x` | BF two-effect | 0.1139 s | 0.1071 s | 0.1100 s | 44.6 MiB |
| `selected_10x` | BF three-effect | 0.1109 s | 0.1090 s | 0.1103 s | 47.1 MiB |
| `selected_10x` | BHB three-effect | 0.1088 s | 0.1151 s | 0.1129 s | 47.1 MiB |
| `selected_10x` | BHB two-effect | 0.1126 s | 0.1170 s | 0.1094 s | 44.6 MiB |
| `monthly_121260` | BF two-effect | 0.2008 s | 0.1939 s | 0.1964 s | 89.1 MiB |
| `monthly_121260` | BF three-effect | 0.1921 s | 0.1918 s | 0.1968 s | 94.1 MiB |
| `monthly_121260` | BHB three-effect | 0.1917 s | 0.1936 s | 0.2010 s | 94.1 MiB |
| `monthly_121260` | BHB two-effect | 0.1989 s | 0.1997 s | 0.1928 s | 89.1 MiB |
| `history_25y` | BF two-effect | 0.0702 s | 0.0645 s | 0.0675 s | 22.4 MiB |
| `history_25y` | BF three-effect | 0.0698 s | 0.0668 s | 0.0699 s | 23.6 MiB |
| `history_25y` | BHB three-effect | 0.0673 s | 0.0697 s | 0.0706 s | 23.6 MiB |
| `history_25y` | BHB two-effect | 0.0673 s | 0.0713 s | 0.0668 s | 22.4 MiB |

Menchero medians ranged from 20.9% below to 4.9% above the paired Carino observations,
with a largest absolute increase of 0.0093 seconds. The large percentage decrease is
the visibly noisy 0.0416-second normal Carino sample rather than evidence that
Menchero accelerates the shared calculation. Against Frongello, Menchero ranged from
6.5% below to 4.7% above, with a largest absolute increase of 0.0074 seconds. Peak
traced allocations were identical at reported precision for every paired method and
workload, consistent with adding only a short period-coefficient vector.

These observations provide no evidence for an optimization or a new performance
threshold. No dependency, formula, tolerance, warning, or established gate changed.

## Roadmap 10 hierarchical roll-up observations

These observations were collected on September 6, 2026, on the same Apple arm64
machine using Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6. The complete 48-case
matrix crossed four selected-result workloads, all four attribution methods, and all
three effect linkers. Each elapsed range below contains the median of three samples
for every policy combination.

| Workload | Rows | Periods | Leaves | Depth | Median range | Peak range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `normal` | 6,063 | 60 | 102 | 2 | 0.0404–0.0511 s | 5.2–5.7 MiB |
| `selected_10x` | 60,630 | 60 | 1,011 | 3 | 0.1470–0.1687 s | 50.4–55.9 MiB |
| `monthly_121260` | 121,260 | 120 | 1,011 | 6 | 0.3426–0.3760 s | 200.4–222.6 MiB |
| `history_25y` | 30,300 | 300 | 101 | 8 | 0.1273–0.1390 s | 66.9–74.3 MiB |

The source results occupied 1.5–29.4 MiB and were built before measurement. The
largest depth-six case expands 121,260 source rows through six ancestor relationships,
which explains its higher incremental peak. Three-effect results consistently used
more memory because they carry interaction and linked-interaction columns. Linker
choice produced no material structural difference because roll-up sums already
linked values rather than applying a linker again.

All cases remained below 0.4 seconds in this environment. These results establish a
repeatable baseline, not a release threshold. They do not justify complicating the
direct-from-leaf design, changing an invariant, or adding a dependency.

## `ppar` adapter observation

An isolated 121,260-row-per-side adapter profile used Python 3.12.1, pandas 3.0.0,
NumPy 2.4.2, and Polars 1.38.0. It identified per-value Python-list materialization at
the pandas/Polars boundary as the dominant non-core cost. Passing existing columnar
NumPy arrays in both directions reduced the median of five samples from approximately
0.52 seconds to 0.23 seconds and reduced peak traced allocation from 142.9 MiB to
113.1 MiB. The completed differential suite established migration parity; the
permanent 500x integration gate remains the authority for workflow performance.

After the change, the permanent `ppar` 500x integration command passed all scenarios.
The large-source workflow took 1.41 seconds at both 12,126 and 6,063,000 source rows;
the selected-input workflow grew from 0.23 to 0.47 seconds at 10x rows; and the
long-history workflow grew from 1.28 to 1.85 seconds at 5x history. These timings are
observations, not thresholds.

The effective-dated generic mapping exposure was subsequently tested through the
unchanged complete `ppar` release-candidate workflow against the adjacent `perfattr`
wheel. The suite passed 332 tests and 501 subtests, and the 500x scenarios retained
byte-identical large-site output and financial equivalence. Large-site elapsed time
was 1.46 versus 1.53 seconds; the 10x selected workload was 0.41 versus 0.83 seconds;
and the 5x long-history workload was 1.46 versus 2.28 seconds. Its 1.567x ratio passed
the unchanged 1.58x warning and 1.65x failure boundaries.

For the `perfattr==0.4.0a1` candidate, `ppar` continued to call the default two-effect
boundary without an API or schema change. Its complete release-candidate command
passed 305 tests and 477 subtests, every static, documentation, image, package, and
installed-demo check, and the unchanged 500x workflow. The final scale run retained
byte-identical large-site artifacts and observed 1.070x large-site, 2.025x selected-
input, and 1.490x long-history time ratios. One earlier long-history run observed a
1.582x warning; its immediate repeat was 1.537x, and the final complete-gate value was
1.490x. No threshold changed. Removing `ppar`'s speculative dependency upper bound
was the only host-package metadata change; its minimum version, adapter call, output,
and presentation behavior remained unchanged.

The Roadmap 6 BHB candidate was subsequently installed into the unchanged `ppar`
development environment. `ppar` continued to omit the method argument and therefore
used its established BF two-effect boundary without exposing BHB or changing a host
schema. The complete release-candidate workflow again passed 305 tests and 477
subtests plus all static, documentation, image, package, wheel, and installed-demo
checks. The unchanged 500x gate retained large-site equivalence and observed 1.050x
large-site and 2.101x selected-input time ratios. Long-history measured 1.568x, below
the existing 1.58x warning and 1.65x failure boundaries. No `ppar` source, threshold,
or dependency metadata changed.

The Roadmap 7 compact-BHB candidate was then installed into the same unchanged
`ppar` development environment. The adapter still omitted the method argument and
therefore remained on BF two-effect without exposing compact BHB or changing a host
schema. The complete release-candidate workflow passed 305 tests and 477 subtests,
Mypy, Pyright, both Pylint checks, documentation and image validation, universal-wheel
build and Twine validation, package metadata, and both installed demonstration paths.
The required 500x run retained byte-identical large-site output and observed 1.105x
large-site and 2.049x selected-input time ratios. Long-history measured 1.583x, above
the unchanged 1.58x warning but below the 1.65x failure boundary, so the gate passed.
An immediate repeat observed 1.059x large-site, 2.007x selected-input, and 1.563x
long-history ratios, with no warning. No `ppar` source, configuration, dependency
metadata, threshold, or presentation behavior changed.

The Roadmap 8 Frongello candidate was installed into `ppar`'s Python 3.12.1
development environment. Inspection confirmed that the adapter still omits
`effect_linking_method`, so all host calculations remained on default Carino and no
Frongello option or metadata entered the host product. The complete release-candidate
workflow passed 305 tests and 477 subtests, Mypy, Pyright, both Pylint checks,
documentation and image validation, universal-wheel construction, Twine, package
metadata, and installed generic and Axys/APX demonstrations.

The unchanged 500x gate retained byte-identical large-site output and observed a
1.113x large-site ratio and 2.019x selected-input ratio, both without machine-specific
performance thresholds. Long-history measured 1.573x, below the unchanged 1.58x
warning and 1.65x failure boundaries. No `ppar` file, adapter call, schema,
presentation behavior, dependency declaration, tolerance, warning, or threshold was
changed for this verification.

The Roadmap 10 hierarchy candidate was then installed without dependencies into the
same `ppar` Python 3.12.1 release-candidate environment. Inspection confirmed that
the host adapter does not import or call the new opt-in hierarchy boundary and still
uses default Brinson-Fachler two-effect attribution with Carino linking. The complete
gate passed 305 tests and 477 subtests, Mypy, Pyright, both Pylint checks,
documentation and image validation, universal-wheel construction, Twine, package
metadata, and installed generic and Axys/APX demonstrations.

The unchanged 500x check retained large-site equivalence and observed a 1.060x
large-site ratio and 2.018x selected-input ratio, both without machine-specific
performance thresholds. Long-history measured 1.521x, below the unchanged 1.58x
warning and 1.65x failure boundaries. Roadmap 10 made no `ppar` source, schema,
presentation, dependency, tolerance, warning, or threshold change.
