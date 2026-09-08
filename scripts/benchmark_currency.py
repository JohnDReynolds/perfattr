"""Benchmark currency attribution through its complete public boundary.

Four deterministic prepared frames are built before measurement. Elapsed time and
peak memory therefore describe :func:`perfattr.calculate_currency_attribution` rather
than source preparation. The reported peak is incremental Python-tracked allocation,
not total process memory.
"""

from __future__ import annotations

import argparse
from functools import partial
import statistics
from typing import cast

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
    runtime_versions,
)
from perfattr import CurrencyAttributionResult, calculate_currency_attribution
from perfattr._schemas import CURRENCY_EXPOSURE_INPUT_COLUMNS


_CURRENCY_COUNT = 20


def _period_layout(workload: BenchmarkWorkload) -> tuple[np.ndarray, np.ndarray]:
    """Return each market row's period and within-period position."""
    base_count, extra_rows = divmod(workload.rows_per_side, workload.periods)
    counts = np.full(workload.periods, base_count, dtype=np.int64)
    counts[:extra_rows] += 1
    period_indices = np.repeat(np.arange(workload.periods), counts)
    positions = np.concatenate([np.arange(count) for count in counts])
    return period_indices, positions


def _period_dates(period_count: int) -> tuple[np.ndarray, np.ndarray]:
    """Return deterministic inclusive month boundaries as NumPy dates."""
    bounds = [month_bounds(index) for index in range(period_count)]
    return (
        np.asarray([bound[0] for bound in bounds], dtype="datetime64[ns]"),
        np.asarray([bound[1] for bound in bounds], dtype="datetime64[ns]"),
    )


def _market_weights(period_indices: np.ndarray, positions: np.ndarray) -> np.ndarray:
    """Normalize deterministic positive market weights within each period."""
    raw_weights = 1.0 + ((positions + period_indices) % 19) / 19.0
    totals = np.bincount(period_indices, weights=raw_weights)
    return raw_weights / totals[period_indices]


def _make_market_side(
    workload: BenchmarkWorkload,
    *,
    portfolio: bool,
) -> pd.DataFrame:
    """Build one prepared market side with a common local-cash reference."""
    period_indices, positions = _period_layout(workload)
    from_dates, thru_dates = _period_dates(workload.periods)
    phase = 0.0 if portfolio else 0.61
    local_asset_returns = (
        0.035 * np.sin((positions + 2 * period_indices) / 23.0 + phase)
        + 0.004 * np.cos((positions + period_indices) / 11.0)
    )
    local_cash_returns = 0.002 + 0.0005 * np.sin(
        (positions + period_indices) / 17.0
    )
    return pd.DataFrame(
        {
            "from_date": from_dates[period_indices],
            "thru_date": thru_dates[period_indices],
            "market_identifier": [
                f"market_{position:06d}" for position in positions
            ],
            "market_weight": _market_weights(period_indices, positions),
            "local_asset_return": local_asset_returns,
            "local_cash_return": local_cash_returns,
        }
    )


def _currency_weights(period_index: int, *, portfolio: bool) -> np.ndarray:
    """Return deterministic net exposures, including signed portfolio values."""
    positions = np.arange(_CURRENCY_COUNT, dtype=np.float64)
    benchmark = 1.0 + ((positions + period_index) % 7) / 7.0
    benchmark /= benchmark.sum()
    if not portfolio:
        return benchmark
    active = 0.08 * np.sin(positions + period_index)
    active -= active.mean()
    exposures = benchmark + active
    exposures[-1] = 1.0 - exposures[:-1].sum()
    return exposures


def _make_currency_side(
    workload: BenchmarkWorkload,
    *,
    portfolio: bool,
) -> pd.DataFrame:
    """Build one prepared net-currency side with twenty currencies per period."""
    rows: list[tuple[object, ...]] = []
    phase = 0.37 if portfolio else 0.0
    for period_index in range(workload.periods):
        from_date, thru_date = month_bounds(period_index)
        positions = np.arange(_CURRENCY_COUNT, dtype=np.float64)
        returns = (
            0.02 * np.sin((positions + period_index) / 5.0 + phase)
            + 0.003 * np.cos((positions + 2 * period_index) / 13.0)
        )
        rows.extend(
            (from_date, thru_date, f"currency_{index:02d}", weight, cash_return)
            for index, (weight, cash_return) in enumerate(
                zip(
                    _currency_weights(period_index, portfolio=portfolio),
                    returns,
                    strict=True,
                )
            )
        )
    return pd.DataFrame(
        rows,
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )


def make_currency_inputs(workload: BenchmarkWorkload) -> tuple[pd.DataFrame, ...]:
    """Build all four side-separated currency-attribution inputs."""
    return (
        _make_market_side(workload, portfolio=True),
        _make_market_side(workload, portfolio=False),
        _make_currency_side(workload, portfolio=True),
        _make_currency_side(workload, portfolio=False),
    )


def currency_result_mebibytes(result: CurrencyAttributionResult) -> float:
    """Return the combined deep memory of all currency result frames."""
    return deep_frame_mebibytes(
        (
            result.market_detail,
            result.currency_detail,
            result.period_summary,
            result.reconciliation,
        )
    )


def _parse_args() -> argparse.Namespace:
    """Parse benchmark workload and sample selections."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.epilog = "Every selected period contains twenty currency rows per side."
    add_common_arguments(parser)
    namespace = parser.parse_args()
    require_positive_samples(parser, namespace.samples)
    return namespace


def main() -> None:
    """Run the selected currency workload matrix and print observations."""
    args = _parse_args()
    selected = cast(list[str] | None, args.workload)
    workload_names = selected or list(WORKLOADS)

    print(runtime_versions())
    print(
        "Peak memory is incremental Python-tracked allocation during public currency "
        "attribution; prepared four-frame input memory is reported separately."
    )
    for workload_name in workload_names:
        workload = WORKLOADS[workload_name]
        inputs = make_currency_inputs(workload)
        operation = partial(
            calculate_currency_attribution,
            *inputs,
            base_currency="USD",
        )
        samples = measure_elapsed(operation, args.samples)
        peak_mebibytes = measure_peak_mebibytes(operation)
        result = operation()

        print(
            f"{workload.name}: market rows/side={workload.rows_per_side:,}, "
            f"currency rows/side={workload.periods * _CURRENCY_COUNT:,}, "
            f"periods={workload.periods}"
        )
        sample_values = ", ".join(f"{sample:.4f}" for sample in samples)
        measurement = (
            f"  median={statistics.median(samples):.4f}s; samples=[{sample_values}]\n"
            f"  inputs={deep_frame_mebibytes(inputs):.1f} MiB; "
            f"result={currency_result_mebibytes(result):.1f} MiB; "
            f"peak traced allocation={peak_mebibytes:.1f} MiB"
        )
        print(measurement)


if __name__ == "__main__":
    main()
