"""Benchmark hierarchical roll-up through its complete public boundary.

Attribution results and static hierarchies are constructed before measurement so
elapsed time and peak memory describe :func:`perfattr.roll_up_attribution` itself.
The reported peak is incremental Python-tracked allocation, not total process memory.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import partial
import math
import platform
import statistics

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
    roll_up_attribution,
)

_METHODS = {
    "bf-two": AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
    "bf-three": AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
    "bhb-two": AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT,
    "bhb-three": AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
}
_EFFECT_LINKERS = {
    "carino": EffectLinkingMethod.CARINO,
    "frongello": EffectLinkingMethod.FRONGELLO,
    "menchero": EffectLinkingMethod.MENCHERO,
}
_DEPTHS = {
    "normal": 2,
    "selected_10x": 3,
    "monthly_121260": 6,
    "history_25y": 8,
}


@dataclass(frozen=True)
class _HierarchyWorkload:
    """Describe one deterministic selected-result hierarchy workload.

    Attributes:
        base: Established core workload supplying row and period counts.
        leaf_count: Stable number of leaf identifiers in every period.
        depth: Exact number of ancestors reached by every leaf.
    """

    base: BenchmarkWorkload
    leaf_count: int
    depth: int

    @property
    def rows(self) -> int:
        """Return the exact source-result period-detail row count."""
        return self.base.rows_per_side

    def period_row_counts(self) -> list[int]:
        """Distribute the exact row count across the requested periods."""
        base_count, extra_rows = divmod(self.rows, self.base.periods)
        return [
            base_count + (period_index < extra_rows)
            for period_index in range(self.base.periods)
        ]


def _hierarchy_workload(name: str) -> _HierarchyWorkload:
    """Adapt an established core workload to fixed identifiers per period."""
    base = WORKLOADS[name]
    leaf_count = math.ceil(base.rows_per_side / base.periods)
    return _HierarchyWorkload(base, leaf_count, _DEPTHS[name])


def _make_side(
    workload: _HierarchyWorkload,
    *,
    benchmark: bool,
) -> pd.DataFrame:
    """Build one deterministic prepared side outside the measured operation."""
    phase = 0.71 if benchmark else 0.0
    frames: list[pd.DataFrame] = []
    for period_index, row_count in enumerate(workload.period_row_counts()):
        from_date, thru_date = month_bounds(period_index)
        positions = np.arange(row_count, dtype=np.float64)
        identifiers = [f"leaf_{index:05d}" for index in range(row_count)]
        raw_weights = 1.0 + (positions % 17.0) / 17.0
        weights = raw_weights / raw_weights.sum()
        weights[-1] = 1.0 - weights[:-1].sum()
        returns = (
            0.025 * np.sin((positions + 3.0 * period_index) / 19.0 + phase)
            + 0.004 * np.cos((positions + period_index) / 7.0)
        )
        period_data: dict[str, object] = {
            "identifier": identifiers,
            "weight": weights,
            "return": returns,
            "from_date": from_date,
            "thru_date": thru_date,
            "quantity_of_days": (thru_date - from_date).days + 1,
        }
        frames.append(pd.DataFrame(period_data))
    return pd.concat(frames, ignore_index=True)


def _make_hierarchy(workload: _HierarchyWorkload) -> pd.DataFrame:
    """Build a balanced forest whose leaves all have the requested exact depth."""
    current_nodes = [
        f"leaf_{index:05d}" for index in range(workload.leaf_count)
    ]
    edges: list[tuple[str, str]] = []
    for level in range(1, workload.depth + 1):
        parent_by_index = {
            index: f"level_{level:02d}_{index // 10:05d}"
            for index in range(len(current_nodes))
        }
        edges.extend(
            (node, parent_by_index[index])
            for index, node in enumerate(current_nodes)
        )
        current_nodes = list(dict.fromkeys(parent_by_index.values()))
    return pd.DataFrame(edges, columns=("identifier", "parent_identifier"))


def _calculate_source(
    workload: _HierarchyWorkload,
    method: AttributionMethod,
    linker: EffectLinkingMethod,
) -> AttributionResult:
    """Build the reconciled source result outside roll-up measurement."""
    portfolio = _make_side(workload, benchmark=False)
    benchmark = _make_side(workload, benchmark=True)
    calculation = partial(
        calculate_attribution,
        portfolio,
        benchmark,
        method=method,
        effect_linking_method=linker,
    )
    return calculation()


def _result_mebibytes(result: AttributionResult) -> float:
    """Return the combined deep memory of the five source-result frames."""
    return deep_frame_mebibytes(
        value for value in vars(result).values() if isinstance(value, pd.DataFrame)
    )


def _parse_args() -> argparse.Namespace:
    """Parse benchmark workload, policy, and sample selections."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    parser.add_argument(
        "--method",
        action="append",
        choices=tuple(_METHODS),
        help="Method to run; repeat to select several. The default runs all.",
    )
    parser.add_argument(
        "--effect-linking-method",
        action="append",
        choices=tuple(_EFFECT_LINKERS),
        help="Linker to run; repeat to select several. The default runs all.",
    )
    namespace = parser.parse_args()
    require_positive_samples(parser, namespace.samples)
    return namespace


def main() -> None:
    """Run the selected hierarchy matrix and print repeatable observations."""
    args = _parse_args()
    workload_names = args.workload or list(WORKLOADS)
    method_names = args.method or list(_METHODS)
    linker_names = args.effect_linking_method or list(_EFFECT_LINKERS)

    print(
        f"Python {platform.python_version()} | pandas {pd.__version__} | "
        f"NumPy {np.__version__}"
    )
    print(
        "Peak memory is incremental Python-tracked allocation during public "
        "hierarchy roll-up; source-result and hierarchy memory are separate."
    )

    for workload_name in workload_names:
        workload = _hierarchy_workload(workload_name)
        hierarchy = _make_hierarchy(workload)
        for method_name in method_names:
            method = _METHODS[method_name]
            for linker_name in linker_names:
                linker = _EFFECT_LINKERS[linker_name]
                source = _calculate_source(workload, method, linker)
                operation = partial(roll_up_attribution, source, hierarchy)
                samples = measure_elapsed(operation, args.samples)
                peak_mebibytes = measure_peak_mebibytes(operation)
                print(
                    f"{workload_name}: method={method_name}, linker={linker_name}, "
                    f"rows={workload.rows:,}, leaves={workload.leaf_count:,}, "
                    f"periods={workload.base.periods}, depth={workload.depth}"
                )
                print(
                    f"  elapsed median={statistics.median(samples):.4f}s "
                    f"samples={[round(sample, 4) for sample in samples]}"
                )
                print(
                    f"  source result={_result_mebibytes(source):.1f} MiB, "
                    f"hierarchy={deep_frame_mebibytes((hierarchy,)):.1f} MiB, "
                    f"peak traced allocation={peak_mebibytes:.1f} MiB"
                )


if __name__ == "__main__":
    main()
