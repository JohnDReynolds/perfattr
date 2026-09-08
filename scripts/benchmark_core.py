"""Benchmark and profile the portable attribution calculation core.

Prepared inputs are built before timing and memory tracing so the measurements focus
on :func:`perfattr.calculate_attribution`. The reported peak is the incremental peak
of Python-tracked allocations during the calculation, not total process memory.
"""

from __future__ import annotations

import argparse
import cProfile
from functools import partial
import pstats
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
from perfattr import (
    AttributionMethod,
    AttributionResult,
    EffectLinkingMethod,
    calculate_attribution,
)


_METHODS = {
    "two-effect": AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
    "three-effect": AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    "bhb-three-effect": AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    "bhb-two-effect": AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
}
_EFFECT_LINKERS = {
    "carino": EffectLinkingMethod.CARINO,
    "frongello": EffectLinkingMethod.FRONGELLO,
    "menchero": EffectLinkingMethod.MENCHERO,
}


def _calculate(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    method: AttributionMethod,
    effect_linking_method: EffectLinkingMethod,
) -> AttributionResult:
    """Call the public core API with benchmark fixture conventions."""
    return calculate_attribution(
        portfolio,
        benchmark,
        method=method,
        effect_linking_method=effect_linking_method,
    )


def _input_mebibytes(portfolio: pd.DataFrame, benchmark: pd.DataFrame) -> float:
    """Return the deep in-memory size of both prepared input frames."""
    return deep_frame_mebibytes((portfolio, benchmark))


def _profile(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    method: AttributionMethod,
    effect_linking_method: EffectLinkingMethod,
) -> None:
    """Print the most expensive cumulative call paths for one calculation."""
    profiler = cProfile.Profile()
    profiler.enable()
    _calculate(portfolio, benchmark, method, effect_linking_method)
    profiler.disable()
    pstats.Stats(profiler).strip_dirs().sort_stats("cumulative").print_stats(25)


def _parse_args() -> argparse.Namespace:
    """Parse benchmark command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    parser.add_argument(
        "--input-form",
        choices=("derived", "authoritative"),
        default="derived",
        help="Use weight/return input or include authoritative contribution.",
    )
    parser.add_argument(
        "--method",
        choices=tuple(_METHODS),
        default="two-effect",
        help="Select the attribution effect convention (default: two-effect).",
    )
    parser.add_argument(
        "--effect-linking-method",
        choices=tuple(_EFFECT_LINKERS),
        default="carino",
        help="Select the active-effect linker (default: carino).",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Print cProfile results after measuring each selected workload.",
    )
    args = parser.parse_args()
    require_positive_samples(parser, args.samples)
    return args


def main() -> None:
    """Run selected roadmap workloads and print reproducible measurements."""
    args = _parse_args()
    workload_names = selected_workload_names(cast(list[str] | None, args.workload))
    input_form: BenchmarkInputForm = args.input_form
    method = _METHODS[args.method]
    effect_linking_method = _EFFECT_LINKERS[args.effect_linking_method]

    print(runtime_versions())
    print(
        "Peak memory is incremental Python-tracked allocation during calculation; "
        "prepared input memory is reported separately."
    )

    for workload_name in workload_names:
        workload = WORKLOADS[workload_name]
        portfolio, benchmark = make_attribution_inputs(workload, input_form)
        operation = partial(
            _calculate,
            portfolio,
            benchmark,
            method,
            effect_linking_method,
        )
        samples = measure_elapsed(operation, args.samples)
        peak_mebibytes = measure_peak_mebibytes(operation)

        print(
            f"{workload.name}: method={args.method}, "
            f"effect-linker={args.effect_linking_method}, form={input_form}, "
            f"rows/side={workload.rows_per_side:,}, periods={workload.periods}"
        )
        print(
            f"  elapsed median={statistics.median(samples):.4f}s "
            f"samples={[round(sample, 4) for sample in samples]}"
        )
        print(
            f"  prepared inputs={_input_mebibytes(portfolio, benchmark):.1f} MiB, "
            f"peak traced allocation={peak_mebibytes:.1f} MiB"
        )
        if args.profile:
            _profile(portfolio, benchmark, method, effect_linking_method)


if __name__ == "__main__":
    main()
