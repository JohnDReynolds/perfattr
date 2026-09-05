"""Build and validate attribution-result reconciliation evidence."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from perfattr._exceptions import AttributionError
from perfattr._linking import _compound_returns
from perfattr._schemas import (
    OVERALL_RECONCILIATION_CHECKS,
    PERIOD_RECONCILIATION_CHECKS,
    RECONCILIATION_COLUMNS,
    THREE_EFFECT_OVERALL_RECONCILIATION_CHECKS,
    THREE_EFFECT_PERIOD_RECONCILIATION_CHECKS,
)
from perfattr._validation import float_array as _float_array
from perfattr._validation import is_close as _is_close
from perfattr.method import AttributionMethod, uses_explicit_interaction


def _column_sum(frame: pd.DataFrame, column: str) -> float:
    """Return a numeric result column's sum as an ordinary float."""
    return float(_float_array(frame, column).sum())


def _build_period_reconciliation(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    method: AttributionMethod = AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
) -> pd.DataFrame:
    """Build reconciliation inputs for every reporting period.

    Args:
        detail: Linked period-detail rows for the selected attribution method.
        summary: Linked period-summary rows for the same method.
        method: Approved attribution effect convention.

    Returns:
        Unfinished period reconciliation rows ready for tolerance evaluation.
    """
    aggregate_columns = """portfolio_weight benchmark_weight
    portfolio_contribution benchmark_contribution active_contribution
    allocation_effect selection_effect total_effect""".split()
    reconciliation_checks = PERIOD_RECONCILIATION_CHECKS
    if uses_explicit_interaction(method):
        aggregate_columns.insert(
            aggregate_columns.index("selection_effect") + 1,
            "interaction_effect",
        )
        reconciliation_checks = THREE_EFFECT_PERIOD_RECONCILIATION_CHECKS
    period_totals = cast(
        pd.DataFrame,
        detail.groupby(
            ["from_date", "thru_date"],
            as_index=False,
            sort=False,
            observed=True,
        )[aggregate_columns].sum(),
    )
    effect_components = (
        _float_array(period_totals, "allocation_effect")
        + _float_array(period_totals, "selection_effect")
    )
    if uses_explicit_interaction(method):
        effect_components = effect_components + _float_array(
            period_totals,
            "interaction_effect",
        )
    period_actual = np.column_stack(
        (
            _float_array(period_totals, "portfolio_weight"),
            _float_array(period_totals, "benchmark_weight"),
            _float_array(period_totals, "portfolio_contribution"),
            _float_array(period_totals, "benchmark_contribution"),
            _float_array(period_totals, "active_contribution"),
            effect_components,
            _float_array(period_totals, "total_effect"),
        )
    )
    period_expected = np.column_stack(
        (
            np.ones(len(summary), dtype=np.float64),
            np.ones(len(summary), dtype=np.float64),
            _float_array(summary, "portfolio_return"),
            _float_array(summary, "benchmark_return"),
            _float_array(summary, "active_return"),
            _float_array(summary, "total_effect"),
            _float_array(summary, "active_return"),
        )
    )
    check_count = len(reconciliation_checks)
    return pd.DataFrame(
        {
            "scope": "period",
            "from_date": np.repeat(
                np.asarray(summary["from_date"], dtype="datetime64[ns]"),
                check_count,
            ),
            "thru_date": np.repeat(
                np.asarray(summary["thru_date"], dtype="datetime64[ns]"),
                check_count,
            ),
            "check": np.tile(reconciliation_checks, len(summary)),
            "actual": period_actual.ravel(),
            "expected": period_expected.ravel(),
        }
    )


def _build_overall_reconciliation(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    method: AttributionMethod = AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
) -> pd.DataFrame:
    """Build reconciliation inputs for the complete requested horizon.

    Args:
        detail: Linked period-detail rows for the selected attribution method.
        summary: Linked period-summary rows for the same method.
        method: Approved attribution effect convention.

    Returns:
        Unfinished overall reconciliation rows ready for tolerance evaluation.
    """
    portfolio_return = _compound_returns(_float_array(summary, "portfolio_return"))
    benchmark_return = _compound_returns(_float_array(summary, "benchmark_return"))
    active_return = portfolio_return - benchmark_return
    linked_effect_components = (
        _column_sum(detail, "linked_allocation_effect")
        + _column_sum(detail, "linked_selection_effect")
    )
    reconciliation_checks = OVERALL_RECONCILIATION_CHECKS
    if uses_explicit_interaction(method):
        linked_effect_components += _column_sum(
            detail,
            "linked_interaction_effect",
        )
        reconciliation_checks = THREE_EFFECT_OVERALL_RECONCILIATION_CHECKS
    overall_actual = np.asarray(
        [
            _column_sum(detail, "linked_portfolio_contribution"),
            _column_sum(detail, "linked_benchmark_contribution"),
            _column_sum(detail, "linked_active_contribution"),
            linked_effect_components,
            _column_sum(detail, "linked_total_effect"),
        ],
        dtype=np.float64,
    )
    overall_expected = np.asarray(
        [
            portfolio_return,
            benchmark_return,
            active_return,
            overall_actual[4],
            active_return,
        ],
        dtype=np.float64,
    )
    return pd.DataFrame(
        {
            "scope": "overall",
            "from_date": detail.at[0, "from_date"],
            "thru_date": detail.at[len(detail) - 1, "thru_date"],
            "check": reconciliation_checks,
            "actual": overall_actual,
            "expected": overall_expected,
        }
    )


def _build_reconciliation(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    reconciliation_tolerance: float,
    method: AttributionMethod = AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
) -> pd.DataFrame:
    """Build positive period and overall financial reconciliation evidence.

    Args:
        detail: Linked period-detail rows for the selected attribution method.
        summary: Linked period-summary rows for the same method.
        reconciliation_tolerance: Positive absolute and relative comparison tolerance.
        method: Approved attribution effect convention.

    Returns:
        A new deterministic reconciliation frame containing only passing checks.

    Raises:
        AttributionError: If any period or overall reconciliation identity fails.
    """
    reconciliation = pd.concat(
        [
            _build_period_reconciliation(detail, summary, method),
            _build_overall_reconciliation(detail, summary, method),
        ],
        ignore_index=True,
    )
    reconciliation["residual"] = (
        reconciliation["actual"] - reconciliation["expected"]
    )
    reconciliation["tolerance"] = reconciliation_tolerance
    reconciliation["passed"] = _is_close(
        _float_array(reconciliation, "actual"),
        _float_array(reconciliation, "expected"),
        reconciliation_tolerance,
    )
    reconciliation = reconciliation.loc[:, RECONCILIATION_COLUMNS]
    reconciliation["scope"] = reconciliation["scope"].astype("string[python]")
    reconciliation["check"] = reconciliation["check"].astype("string[python]")
    reconciliation["passed"] = reconciliation["passed"].astype("bool")
    passed = cast(pd.Series, reconciliation["passed"])
    if not bool(np.asarray(passed, dtype=np.bool_).all()):
        failed = cast(
            pd.Series,
            reconciliation.loc[~reconciliation["passed"], "check"],
        )
        failed_checks = ", ".join(cast(pd.Series, failed.astype(str)))
        raise AttributionError(f"calculation reconciliation failed: {failed_checks}")
    return cast(pd.DataFrame, reconciliation.reset_index(drop=True))


def _validate_result_values(
    name: str,
    frame: pd.DataFrame,
    nullable_columns: tuple[str, ...] = (),
) -> None:
    """Require finite result numbers except in specified undefined-return fields."""
    numeric = cast(pd.DataFrame, frame.select_dtypes(include="number"))
    for column in numeric.columns:
        values = _float_array(numeric, column)
        valid = np.isfinite(values)
        if column in nullable_columns:
            valid |= np.isnan(values)
        if not valid.all():
            raise AttributionError(
                f"{name} column {column!r} contains a non-finite value"
            )


__all__ = ["_build_reconciliation", "_validate_result_values"]
