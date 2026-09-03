"""Benchmark and profile the portable attribution calculation core.

Prepared inputs are built before timing and memory tracing so the measurements focus
on :func:`perfattr.calculate_attribution`. The reported peak is the incremental peak
of Python-tracked allocations during the calculation, not total process memory.
"""

from __future__ import annotations

import argparse
import cProfile
import gc
import platform
import pstats
import statistics
import time
import tracemalloc
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

import numpy as np
import pandas as pd

from perfattr import AttributionResult, calculate_attribution

_MEBIBYTE: Final = 1024 * 1024
_InputForm = Literal["derived", "authoritative"]


@dataclass(frozen=True)
class _Workload:
    """Describe one deterministic roadmap benchmark workload."""

    name: str
    rows_per_side: int
    periods: int


_WORKLOADS: Final = {
    "normal": _Workload("normal", rows_per_side=6_063, periods=60),
    "selected_10x": _Workload("selected_10x", rows_per_side=60_630, periods=60),
    "monthly_121260": _Workload(
        "monthly_121260", rows_per_side=121_260, periods=120
    ),
    "history_25y": _Workload("history_25y", rows_per_side=30_300, periods=300),
}


def _month_bounds(month_index: int) -> tuple[date, date]:
    """Return inclusive month boundaries starting with January 2000."""
    absolute_month = 2000 * 12 + month_index
    year, zero_based_month = divmod(absolute_month, 12)
    month = zero_based_month + 1
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _period_row_counts(workload: _Workload) -> list[int]:
    """Distribute the exact requested row count as evenly as possible."""
    base_count, extra_rows = divmod(workload.rows_per_side, workload.periods)
    return [
        base_count + (period_index < extra_rows)
        for period_index in range(workload.periods)
    ]


def _make_side(
    workload: _Workload,
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
    from_date, thru_date = _month_bounds(period_index)
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
    portfolio: pd.DataFrame, benchmark: pd.DataFrame
) -> AttributionResult:
    """Call the public core API with benchmark fixture conventions."""
    return calculate_attribution(portfolio, benchmark)


def _elapsed_samples(
    portfolio: pd.DataFrame, benchmark: pd.DataFrame, sample_count: int
) -> list[float]:
    """Measure calculation wall time after one unrecorded warm-up run."""
    _calculate(portfolio, benchmark)
    samples: list[float] = []
    for _ in range(sample_count):
        started_at = time.perf_counter()
        _calculate(portfolio, benchmark)
        samples.append(time.perf_counter() - started_at)
    return samples


def _peak_mebibytes(portfolio: pd.DataFrame, benchmark: pd.DataFrame) -> float:
    """Measure peak Python-tracked allocation during one calculation."""
    gc.collect()
    tracemalloc.start()
    try:
        result = _calculate(portfolio, benchmark)
        del result
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak_bytes / _MEBIBYTE


def _input_mebibytes(portfolio: pd.DataFrame, benchmark: pd.DataFrame) -> float:
    """Return the deep in-memory size of both prepared input frames."""
    input_bytes = portfolio.memory_usage(index=True, deep=True).sum()
    input_bytes += benchmark.memory_usage(index=True, deep=True).sum()
    return float(input_bytes) / _MEBIBYTE


def _profile(portfolio: pd.DataFrame, benchmark: pd.DataFrame) -> None:
    """Print the most expensive cumulative call paths for one calculation."""
    profiler = cProfile.Profile()
    profiler.enable()
    _calculate(portfolio, benchmark)
    profiler.disable()
    pstats.Stats(profiler).strip_dirs().sort_stats("cumulative").print_stats(25)


def _parse_args() -> argparse.Namespace:
    """Parse benchmark command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workload",
        action="append",
        choices=tuple(_WORKLOADS),
        help="Workload to run; repeat to select several. The default runs all.",
    )
    parser.add_argument(
        "--input-form",
        choices=("derived", "authoritative"),
        default="derived",
        help="Use weight/return input or include authoritative contribution.",
    )
    parser.add_argument("--samples", type=int, default=3, help="Recorded timing samples.")
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Print cProfile results after measuring each selected workload.",
    )
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be at least 1")
    return args


def main() -> None:
    """Run selected roadmap workloads and print reproducible measurements."""
    args = _parse_args()
    workload_names = args.workload or list(_WORKLOADS)
    input_form: _InputForm = args.input_form

    print(
        f"Python {platform.python_version()} | pandas {pd.__version__} | "
        f"NumPy {np.__version__}"
    )
    print(
        "Peak memory is incremental Python-tracked allocation during calculation; "
        "prepared input memory is reported separately."
    )

    for workload_name in workload_names:
        workload = _WORKLOADS[workload_name]
        portfolio = _make_side(workload, side="portfolio", input_form=input_form)
        benchmark = _make_side(workload, side="benchmark", input_form=input_form)
        samples = _elapsed_samples(portfolio, benchmark, args.samples)
        peak_mebibytes = _peak_mebibytes(portfolio, benchmark)

        print(
            f"{workload.name}: form={input_form}, rows/side={workload.rows_per_side:,}, "
            f"periods={workload.periods}"
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
            _profile(portfolio, benchmark)


if __name__ == "__main__":
    main()
