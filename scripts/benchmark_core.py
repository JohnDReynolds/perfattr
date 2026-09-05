"""Benchmark and profile the portable attribution calculation core.

Prepared inputs are built before timing and memory tracing so the measurements focus
on :func:`perfattr.calculate_attribution`. The reported peak is the incremental peak
of Python-tracked allocations during the calculation, not total process memory.
"""

from __future__ import annotations

import argparse
import cProfile
from functools import partial
import platform
import pstats
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
from perfattr import (
    AttributionMethod,
    AttributionResult,
    EffectLinkingMethod,
    calculate_attribution,
)


_InputForm = Literal["derived", "authoritative"]
_METHODS = {
    "two-effect": AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
    "three-effect": AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    "bhb-three-effect": AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    "bhb-two-effect": AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
}
_EFFECT_LINKERS = {
    "carino": EffectLinkingMethod.CARINO,
    "frongello": EffectLinkingMethod.FRONGELLO,
}


def _period_row_counts(workload: BenchmarkWorkload) -> list[int]:
    """Distribute the exact requested row count as evenly as possible."""
    base_count, extra_rows = divmod(workload.rows_per_side, workload.periods)
    return [
        base_count + (period_index < extra_rows)
        for period_index in range(workload.periods)
    ]


def _make_side(
    workload: BenchmarkWorkload,
    *,
    side: Literal["portfolio", "benchmark"],
    input_form: _InputForm,
) -> pd.DataFrame:
    """Build one deterministic attribution input outside the measured region."""
    frames: list[pd.DataFrame] = []
    side_phase = 0.0 if side == "portfolio" else 0.73

    for period_index, row_count in enumerate(_period_row_counts(workload)):
        frames.append(
            _make_period_frame(
                period_index,
                row_count,
                side=side,
                side_phase=side_phase,
                input_form=input_form,
            )
        )

    frame = pd.concat(frames, ignore_index=True)
    if len(frame) != workload.rows_per_side:
        raise AssertionError("Generated input does not match the requested row count.")
    return frame


def _make_period_frame(
    period_index: int,
    row_count: int,
    *,
    side: Literal["portfolio", "benchmark"],
    side_phase: float,
    input_form: _InputForm,
) -> pd.DataFrame:
    """Build one side of one benchmark period."""
    from_date, thru_date = month_bounds(period_index)
    positions = np.arange(row_count, dtype=np.int64)
    identifier_shift = 0 if side == "portfolio" else max(1, row_count // 10)
    identifiers = [f"security_{value:06d}" for value in positions + identifier_shift]

    raw_weights = 1.0 + ((positions + period_index) % 17) / 17.0
    weights = raw_weights / raw_weights.sum()
    weights[-1] = 1.0 - weights[:-1].sum()
    returns = (
        0.025 * np.sin((positions + 3 * period_index) / 19.0 + side_phase)
        + 0.004 * np.cos((positions + period_index) / 7.0)
    )

    frame_data: dict[str, object] = {
        "from_date": from_date,
        "thru_date": thru_date,
        "identifier": identifiers,
        "weight": weights,
        "return": returns,
        "quantity_of_days": (thru_date - from_date).days + 1,
    }
    if input_form == "authoritative":
        frame_data["contribution"] = weights * returns
    return pd.DataFrame(frame_data)


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
    workload_names = args.workload or list(WORKLOADS)
    input_form: _InputForm = args.input_form
    method = _METHODS[args.method]
    effect_linking_method = _EFFECT_LINKERS[args.effect_linking_method]

    print(
        f"Python {platform.python_version()} | pandas {pd.__version__} | "
        f"NumPy {np.__version__}"
    )
    print(
        "Peak memory is incremental Python-tracked allocation during calculation; "
        "prepared input memory is reported separately."
    )

    for workload_name in workload_names:
        workload = WORKLOADS[workload_name]
        portfolio = _make_side(workload, side="portfolio", input_form=input_form)
        benchmark = _make_side(workload, side="benchmark", input_form=input_form)
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
