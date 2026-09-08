"""Benchmark geometric attribution through its complete public boundary.

Prepared portfolio and benchmark inputs are built before measurement so elapsed time
and peak memory describe :func:`perfattr.calculate_geometric_attribution` itself. The
reported peak is incremental Python-tracked allocation, not total process memory.
"""

from __future__ import annotations

import argparse
from functools import partial
import statistics
from typing import cast

import pandas as pd

from benchmark_support import (
    BenchmarkInputForm,
    WORKLOADS,
    add_common_arguments,
    deep_frame_mebibytes,
    make_attribution_inputs,
    measure_elapsed,
    measure_peak_mebibytes,
    require_positive_samples,
    runtime_versions,
    selected_workload_names,
)
from perfattr import GeometricAttributionResult, calculate_geometric_attribution


def _calculate(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> GeometricAttributionResult:
    """Call the public geometric attribution API."""
    return calculate_geometric_attribution(portfolio, benchmark)


def _result_mebibytes(result: GeometricAttributionResult) -> float:
    """Return the combined deep memory of all geometric result frames."""
    return deep_frame_mebibytes(
        (
            result.period_detail,
            result.period_summary,
            result.cumulative,
            result.reconciliation,
        )
    )


def _parse_args() -> argparse.Namespace:
    """Parse benchmark workload, input-form, and sample selections."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    parser.add_argument(
        "--input-form",
        action="append",
        choices=("derived", "authoritative"),
        help="Input form to run; repeat to select both. The default runs both.",
    )
    namespace = parser.parse_args()
    require_positive_samples(parser, namespace.samples)
    return namespace


def main() -> None:
    """Run the selected geometric workload matrix and print observations."""
    args = _parse_args()
    workload_names = selected_workload_names(
        cast(list[str] | None, args.workload)
    )
    input_forms = cast(
        list[BenchmarkInputForm],
        args.input_form or ["derived", "authoritative"],
    )

    print(runtime_versions())
    print(
        "Peak memory is incremental Python-tracked allocation during public "
        "geometric attribution; prepared input memory is reported separately."
    )

    for workload_name in workload_names:
        workload = WORKLOADS[workload_name]
        for input_form in input_forms:
            portfolio, benchmark = make_attribution_inputs(workload, input_form)
            operation = partial(_calculate, portfolio, benchmark)
            samples = measure_elapsed(operation, args.samples)
            peak_mebibytes = measure_peak_mebibytes(operation)
            result = operation()

            print(
                f"{workload.name}: form={input_form}, "
                f"rows/side={workload.rows_per_side:,}, "
                f"periods={workload.periods}"
            )
            print(
                f"  elapsed median={statistics.median(samples):.4f}s "
                f"samples={[round(sample, 4) for sample in samples]}"
            )
            print(
                f"  prepared inputs="
                f"{deep_frame_mebibytes((portfolio, benchmark)):.1f} MiB, "
                f"result={_result_mebibytes(result):.1f} MiB, "
                f"peak traced allocation={peak_mebibytes:.1f} MiB"
            )


if __name__ == "__main__":
    main()
