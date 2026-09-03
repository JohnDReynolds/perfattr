"""Stable column and reconciliation ordering for portable result frames."""

PERIOD_DETAIL_COLUMNS = (
    "from_date",
    "thru_date",
    "quantity_of_days",
    "identifier",
    "portfolio_weight",
    "portfolio_return",
    "portfolio_contribution",
    "benchmark_weight",
    "benchmark_return",
    "benchmark_contribution",
    "active_weight",
    "active_return",
    "active_contribution",
    "allocation_effect",
    "selection_effect",
    "total_effect",
    "linked_portfolio_contribution",
    "linked_benchmark_contribution",
    "linked_active_contribution",
    "linked_allocation_effect",
    "linked_selection_effect",
    "linked_total_effect",
)
PERIOD_SUMMARY_COLUMNS = (
    "from_date",
    "thru_date",
    "quantity_of_days",
    "portfolio_return",
    "benchmark_return",
    "active_return",
    "portfolio_contribution",
    "benchmark_contribution",
    "active_contribution",
    "allocation_effect",
    "selection_effect",
    "total_effect",
    "linked_portfolio_contribution",
    "linked_benchmark_contribution",
    "linked_active_contribution",
    "linked_allocation_effect",
    "linked_selection_effect",
    "linked_total_effect",
)
OVERALL_DETAIL_COLUMNS = (
    "from_date",
    "thru_date",
    "identifier",
    "portfolio_weight",
    "portfolio_return",
    "linked_portfolio_contribution",
    "benchmark_weight",
    "benchmark_return",
    "linked_benchmark_contribution",
    "active_weight",
    "active_return",
    "linked_active_contribution",
    "linked_allocation_effect",
    "linked_selection_effect",
    "linked_total_effect",
)
CUMULATIVE_COLUMNS = (
    "from_date",
    "thru_date",
    "portfolio_return",
    "benchmark_return",
    "active_return",
    "cumulative_portfolio_return",
    "cumulative_benchmark_return",
    "cumulative_active_return",
    "linked_portfolio_contribution",
    "linked_benchmark_contribution",
    "linked_active_contribution",
    "cumulative_portfolio_contribution",
    "cumulative_benchmark_contribution",
    "cumulative_active_contribution",
    "linked_allocation_effect",
    "linked_selection_effect",
    "linked_total_effect",
    "cumulative_allocation_effect",
    "cumulative_selection_effect",
    "cumulative_total_effect",
)
RECONCILIATION_COLUMNS = (
    "scope",
    "from_date",
    "thru_date",
    "check",
    "actual",
    "expected",
    "residual",
    "tolerance",
    "passed",
)
PERIOD_RECONCILIATION_CHECKS = tuple(
    """portfolio_weight benchmark_weight portfolio_contribution
    benchmark_contribution active_contribution effect_components total_effect""".split()
)
OVERALL_RECONCILIATION_CHECKS = tuple(
    """linked_portfolio_contribution linked_benchmark_contribution
    linked_active_contribution linked_effect_components linked_total_effect""".split()
)
