"""Benchmark static and effective-dated preparation through the public API.

Deterministic source histories and mappings are built before measurement. Each timed
call includes normalization, alignment, mapping, quarterly consolidation, and
reconciliation. The reported peak is the incremental peak of Python-tracked
allocations during preparation, not total process memory.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import partial
import platform
import statistics
from typing import Literal

import numpy as np
import pandas as pd

from benchmark_support import (
    BenchmarkWorkload,
    WORKLOADS,
    add_common_arguments,
    deep_frame_mebibytes,
    measure_elapsed,
    measure_peak_mebibytes,
    month_bounds,
    require_positive_samples,
)
from perfattr import Frequency, PreparationResult, prepare_attribution

_MappingForm = Literal["static", "effective"]


@dataclass(frozen=True)
class _BenchmarkInputs:
    """Hold one independently mapped portfolio and benchmark workload."""

    portfolio: pd.DataFrame
    benchmark: pd.DataFrame
    portfolio_mapping: pd.DataFrame
    benchmark_mapping: pd.DataFrame


def _row_counts(workload: BenchmarkWorkload) -> np.ndarray:
    """Distribute an exact selected row count across all source months."""
    base_count, extra_rows = divmod(workload.rows_per_side, workload.periods)
    counts = np.full(workload.periods, base_count, dtype=np.int64)
    counts[:extra_rows] += 1
    return counts


def _make_source(
    workload: BenchmarkWorkload, prefix: str, phase: float
) -> pd.DataFrame:
    """Build one valid deterministic monthly returns-only source history."""
    counts = _row_counts(workload)
    period_indices = np.repeat(np.arange(workload.periods), counts)
    positions = np.concatenate([np.arange(count) for count in counts])
    bounds = [month_bounds(index) for index in range(workload.periods)]
    from_dates = np.asarray([bound[0] for bound in bounds], dtype="datetime64[ns]")
    thru_dates = np.asarray([bound[1] for bound in bounds], dtype="datetime64[ns]")

    raw_weights = 1.0 + ((positions + period_indices) % 17) / 17.0
    period_weight_totals = np.bincount(period_indices, weights=raw_weights)
    weights = raw_weights / period_weight_totals[period_indices]
    returns = (
        0.015 * np.sin((positions + 2 * period_indices) / 19.0 + phase)
        + 0.003 * np.cos((positions + period_indices) / 7.0)
    )

    return pd.DataFrame(
        {
            "from_date": from_dates[period_indices],
            "thru_date": thru_dates[period_indices],
            "identifier": [f"{prefix}_{position:06d}" for position in positions],
            "weight": weights,
            "return": returns,
        }
    )


def _static_mapping(prefix: str, identifier_count: int) -> pd.DataFrame:
    """Map every source identifier to one of twenty stable classifications."""
    positions = np.arange(identifier_count)
    return pd.DataFrame(
        {
            "identifier": [f"{prefix}_{position:06d}" for position in positions],
            "classification_identifier": [
                f"class_{position % 20:02d}" for position in positions
            ],
        }
    )


def _effective_mapping(
    workload: BenchmarkWorkload,
    prefix: str,
    identifier_count: int,
) -> pd.DataFrame:
    """Give every identifier one mid-quarter classification change."""
    split_period = workload.periods // 2 + 1
    history_start = month_bounds(0)[0]
    first_assignment_end = month_bounds(split_period - 1)[1]
    second_assignment_start = month_bounds(split_period)[0]
    history_end = month_bounds(workload.periods - 1)[1]
    positions = np.arange(identifier_count)
    identifiers = [f"{prefix}_{position:06d}" for position in positions]

    return pd.DataFrame(
        {
            "from_date": [history_start] * identifier_count
            + [second_assignment_start] * identifier_count,
            "thru_date": [first_assignment_end] * identifier_count
            + [history_end] * identifier_count,
            "identifier": identifiers + identifiers,
            "classification_identifier": [
                f"class_{position % 20:02d}" for position in positions
            ]
            + [f"class_{(position + 1) % 20:02d}" for position in positions],
        }
    )


def _make_mapping(
    workload: BenchmarkWorkload,
    prefix: str,
    mapping_form: _MappingForm,
) -> pd.DataFrame:
    """Build the requested mapping form for every possible source identifier."""
    identifier_count = int(_row_counts(workload).max())
    if mapping_form == "static":
        return _static_mapping(prefix, identifier_count)
    return _effective_mapping(workload, prefix, identifier_count)


def _make_inputs(
    workload: BenchmarkWorkload,
    mapping_form: _MappingForm,
) -> _BenchmarkInputs:
    """Build independent source histories and mappings outside measurement."""
    return _BenchmarkInputs(
        portfolio=_make_source(workload, "portfolio", 0.0),
        benchmark=_make_source(workload, "benchmark", 0.73),
        portfolio_mapping=_make_mapping(workload, "portfolio", mapping_form),
        benchmark_mapping=_make_mapping(workload, "benchmark", mapping_form),
    )


def _prepare(inputs: _BenchmarkInputs) -> PreparationResult:
    """Run the complete public quarterly preparation boundary."""
    return prepare_attribution(
        inputs.portfolio,
        inputs.benchmark,
        frequency=Frequency.QUARTERLY,
        portfolio_mapping=inputs.portfolio_mapping,
        benchmark_mapping=inputs.benchmark_mapping,
    )


def _input_mebibytes(inputs: _BenchmarkInputs) -> float:
    """Return deep memory used by both source histories and both mappings."""
    frames = (
        inputs.portfolio,
        inputs.benchmark,
        inputs.portfolio_mapping,
        inputs.benchmark_mapping,
    )
    return deep_frame_mebibytes(frames)


def _parse_args() -> argparse.Namespace:
    """Parse benchmark command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    parser.add_argument(
        "--mapping-form",
        action="append",
        choices=("static", "effective"),
        help="Mapping form to run; repeat to select both. The default runs both.",
    )
    args = parser.parse_args()
    require_positive_samples(parser, args.samples)
    return args


def main() -> None:
    """Run selected preparation workloads and print reproducible measurements."""
    args = _parse_args()
    mapping_forms: list[_MappingForm] = args.mapping_form or ["static", "effective"]

    print(
        f"Python {platform.python_version()} | pandas {pd.__version__} | "
        f"NumPy {np.__version__} | {platform.machine()}"
    )
    print(
        "Peak memory is incremental Python-tracked allocation during preparation; "
        "source and mapping input memory is reported separately."
    )

    for workload_name in args.workload or WORKLOADS:
        workload = WORKLOADS[workload_name]
        for mapping_form in mapping_forms:
            inputs = _make_inputs(workload, mapping_form)
            operation = partial(_prepare, inputs)
            samples = measure_elapsed(operation, args.samples)
            peak_mebibytes = measure_peak_mebibytes(operation)

            print(
                f"{workload.name}: mapping={mapping_form}, "
                f"rows/side={workload.rows_per_side:,}, periods={workload.periods}, "
                f"mapping rows/side={len(inputs.portfolio_mapping):,}"
            )
            print(
                f"  elapsed median={statistics.median(samples):.4f}s "
                f"samples={[round(sample, 4) for sample in samples]}"
            )
            print(
                f"  inputs={_input_mebibytes(inputs):.1f} MiB, "
                f"peak traced allocation={peak_mebibytes:.1f} MiB"
            )


if __name__ == "__main__":
    main()
