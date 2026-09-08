"""Share deterministic workload definitions and measurement utilities."""

from __future__ import annotations

import argparse
from calendar import monthrange
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
import gc
import platform
import time
import tracemalloc
from typing import Final, Literal

import numpy as np
import pandas as pd


MEBIBYTE: Final = 1024 * 1024
BenchmarkInputForm = Literal["derived", "authoritative"]


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


def _period_row_counts(workload: BenchmarkWorkload) -> list[int]:
    """Distribute the exact requested row count as evenly as possible."""
    base_count, extra_rows = divmod(workload.rows_per_side, workload.periods)
    return [
        base_count + (period_index < extra_rows)
        for period_index in range(workload.periods)
    ]


def _make_attribution_period(
    period_index: int,
    row_count: int,
    *,
    side: Literal["portfolio", "benchmark"],
    input_form: BenchmarkInputForm,
) -> pd.DataFrame:
    """Build one side of one deterministic attribution benchmark period."""
    from_date, thru_date = month_bounds(period_index)
    positions = np.arange(row_count, dtype=np.int64)
    side_phase = 0.0 if side == "portfolio" else 0.73
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


def make_attribution_side(
    workload: BenchmarkWorkload,
    *,
    side: Literal["portfolio", "benchmark"],
    input_form: BenchmarkInputForm,
) -> pd.DataFrame:
    """Build one deterministic prepared side outside measurement."""
    frames = [
        _make_attribution_period(
            period_index,
            row_count,
            side=side,
            input_form=input_form,
        )
        for period_index, row_count in enumerate(_period_row_counts(workload))
    ]
    frame = pd.concat(frames, ignore_index=True)
    if len(frame) != workload.rows_per_side:
        raise AssertionError("Generated input does not match the requested row count.")
    return frame


def make_attribution_inputs(
    workload: BenchmarkWorkload,
    input_form: BenchmarkInputForm,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build deterministic portfolio and benchmark inputs outside measurement."""
    return (
        make_attribution_side(
            workload,
            side="portfolio",
            input_form=input_form,
        ),
        make_attribution_side(
            workload,
            side="benchmark",
            input_form=input_form,
        ),
    )


def selected_workload_names(selected: list[str] | None) -> list[str]:
    """Return explicitly selected workloads or the complete stable workload order."""
    return selected or list(WORKLOADS)


def runtime_versions() -> str:
    """Return the benchmark interpreter and numerical-library versions."""
    return (
        f"Python {platform.python_version()} | pandas {pd.__version__} | "
        f"NumPy {np.__version__}"
    )


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
