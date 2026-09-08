"""Benchmark multi-period currency roll-up through its public boundary.

The four prepared inputs and completed single-period currency result are built before
measurement. Elapsed time and peak memory therefore describe only
:func:`perfattr.roll_up_currency_attribution`. The reported peak is incremental
Python-tracked allocation, not total process memory.
"""

from __future__ import annotations

import argparse
from functools import partial
import statistics
from typing import cast

from benchmark_currency import currency_result_mebibytes, make_currency_inputs
from benchmark_support import (
    WORKLOADS,
    add_common_arguments,
    deep_frame_mebibytes,
    measure_elapsed,
    measure_peak_mebibytes,
    require_positive_samples,
    runtime_versions,
    selected_workload_names,
)
from perfattr import (
    CurrencyAttributionResult,
    CurrencyAttributionRollupResult,
    calculate_currency_attribution,
    roll_up_currency_attribution,
)


def _rollup_result_mebibytes(result: CurrencyAttributionRollupResult) -> float:
    """Return the combined deep memory of all roll-up result frames."""
    return deep_frame_mebibytes(
        (
            result.market_overall_detail,
            result.currency_overall_detail,
            result.cumulative,
            result.reconciliation,
        )
    )


def _parse_args() -> argparse.Namespace:
    """Parse benchmark workload and sample selections."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.epilog = (
        "Source histories use the exact deterministic Roadmap 12 workload shapes."
    )
    add_common_arguments(parser)
    namespace = parser.parse_args()
    require_positive_samples(parser, namespace.samples)
    return namespace


def _measure_rollup(
    source: CurrencyAttributionResult,
    sample_count: int,
) -> tuple[list[float], float, CurrencyAttributionRollupResult]:
    """Measure and execute one already prepared public roll-up operation."""
    operation = partial(roll_up_currency_attribution, source)
    elapsed = measure_elapsed(operation, sample_count)
    peak = measure_peak_mebibytes(operation)
    return elapsed, peak, operation()


def main() -> None:
    """Run the selected roll-up workload matrix and print observations."""
    args = _parse_args()
    selected = cast(list[str] | None, args.workload)

    print(runtime_versions())
    print(
        "Peak memory is incremental Python-tracked allocation during public currency "
        "roll-up; completed source-result memory is reported separately."
    )
    for workload_name in selected_workload_names(selected):
        workload = WORKLOADS[workload_name]
        source = calculate_currency_attribution(
            *make_currency_inputs(workload),
            base_currency="USD",
        )
        samples, peak_mebibytes, result = _measure_rollup(source, args.samples)

        print(
            f"{workload.name}: source market rows/side={workload.rows_per_side:,}; "
            f"cumulative rows={workload.periods}"
        )
        sample_values = ", ".join(f"{sample:.4f}" for sample in samples)
        measurement = (
            f"  median={statistics.median(samples):.4f}s; samples=[{sample_values}]\n"
            f"  source={currency_result_mebibytes(source):.1f} MiB; "
            f"result={_rollup_result_mebibytes(result):.1f} MiB; "
            f"peak traced allocation={peak_mebibytes:.1f} MiB"
        )
        print(measurement)


if __name__ == "__main__":
    main()
