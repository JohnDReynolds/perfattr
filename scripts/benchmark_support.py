"""Share deterministic workload definitions and measurement utilities."""

from __future__ import annotations

import argparse
from calendar import monthrange
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
import gc
import time
import tracemalloc
from typing import Final

import pandas as pd


MEBIBYTE: Final = 1024 * 1024


@dataclass(frozen=True)
class BenchmarkWorkload:
    """Describe one deterministic roadmap benchmark workload.

    Attributes:
        name: Stable command-line and reporting name.
        rows_per_side: Exact portfolio and benchmark row count.
        periods: Number of monthly periods in each side.
    """

    name: str
    rows_per_side: int
    periods: int


WORKLOADS: Final = {
    "normal": BenchmarkWorkload("normal", rows_per_side=6_063, periods=60),
    "selected_10x": BenchmarkWorkload(
        "selected_10x", rows_per_side=60_630, periods=60
    ),
    "monthly_121260": BenchmarkWorkload(
        "monthly_121260", rows_per_side=121_260, periods=120
    ),
    "history_25y": BenchmarkWorkload(
        "history_25y", rows_per_side=30_300, periods=300
    ),
}


def month_bounds(month_index: int) -> tuple[date, date]:
    """Return inclusive month boundaries starting with January 2000.

    Args:
        month_index: Zero-based month offset from January 2000.

    Returns:
        The first and last calendar date of the requested month.
    """
    absolute_month = 2000 * 12 + month_index
    year, zero_based_month = divmod(absolute_month, 12)
    month = zero_based_month + 1
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared workload and timing options to a benchmark parser.

    Args:
        parser: Parser owned by the calling benchmark.
    """
    parser.add_argument(
        "--workload",
        action="append",
        choices=tuple(WORKLOADS),
        help="Workload to run; repeat to select several. The default runs all.",
    )
    parser.add_argument("--samples", type=int, default=3, help="Recorded timing samples.")


def require_positive_samples(
    parser: argparse.ArgumentParser,
    sample_count: int,
) -> None:
    """Reject a nonpositive timing sample count through the owning parser.

    Args:
        parser: Parser used to report the command-line error.
        sample_count: Requested number of recorded timing runs.
    """
    if sample_count < 1:
        parser.error("--samples must be at least 1")


def measure_elapsed(operation: Callable[[], object], sample_count: int) -> list[float]:
    """Measure an operation after one unrecorded warm-up.

    Args:
        operation: Complete public boundary to invoke.
        sample_count: Number of recorded wall-time samples.

    Returns:
        Elapsed seconds for each recorded invocation.
    """
    operation()
    samples: list[float] = []
    for _ in range(sample_count):
        started_at = time.perf_counter()
        operation()
        samples.append(time.perf_counter() - started_at)
    return samples


def measure_peak_mebibytes(operation: Callable[[], object]) -> float:
    """Measure incremental peak Python-tracked allocation for one operation.

    Args:
        operation: Complete public boundary to invoke.

    Returns:
        Peak traced allocation in mebibytes.
    """
    gc.collect()
    tracemalloc.start()
    try:
        result = operation()
        del result
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak_bytes / MEBIBYTE


def deep_frame_mebibytes(frames: Iterable[pd.DataFrame]) -> float:
    """Return the combined deep memory footprint of pandas frames.

    Args:
        frames: Input frames whose independent memory should be counted.

    Returns:
        Combined pandas-reported memory in mebibytes.
    """
    input_bytes = sum(
        int(frame.memory_usage(index=True, deep=True).sum()) for frame in frames
    )
    return input_bytes / MEBIBYTE
