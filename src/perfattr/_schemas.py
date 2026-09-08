"""Stable column and reconciliation ordering for portable result frames."""


def _insert_after(
    columns: tuple[str, ...],
    anchor: str,
    column: str,
) -> tuple[str, ...]:
    """Return an independent schema tuple with one column after its anchor."""
    insertion_index = columns.index(anchor) + 1
    return (*columns[:insertion_index], column, *columns[insertion_index:])

NORMALIZED_PERFORMANCE_COLUMNS = (
    "from_date",
    "thru_date",
    "quantity_of_days",
    "identifier",
    "weight",
    "return",
    "contribution",
)
PREPARED_REQUIRED_COLUMNS = (
    "from_date",
    "thru_date",
    "identifier",
    "weight",
    "return",
    "quantity_of_days",
)
PREPARED_PERFORMANCE_COLUMNS = (
    *PREPARED_REQUIRED_COLUMNS[:-1],
    "contribution",
    PREPARED_REQUIRED_COLUMNS[-1],
)
PREPARATION_RECONCILIATION_COLUMNS = (
    "stage",
    "side",
    "from_date",
    "thru_date",
    "check",
    "actual",
    "expected",
    "residual",
    "tolerance",
    "passed",
)
HIERARCHY_COLUMNS = (
    "identifier",
    "parent_identifier",
)
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
THREE_EFFECT_PERIOD_DETAIL_COLUMNS = _insert_after(
    _insert_after(
        PERIOD_DETAIL_COLUMNS,
        "selection_effect",
        "interaction_effect",
    ),
    "linked_selection_effect",
    "linked_interaction_effect",
)
THREE_EFFECT_PERIOD_SUMMARY_COLUMNS = _insert_after(
    _insert_after(
        PERIOD_SUMMARY_COLUMNS,
        "selection_effect",
        "interaction_effect",
    ),
    "linked_selection_effect",
    "linked_interaction_effect",
)
THREE_EFFECT_OVERALL_DETAIL_COLUMNS = _insert_after(
    OVERALL_DETAIL_COLUMNS,
    "linked_selection_effect",
    "linked_interaction_effect",
)
THREE_EFFECT_CUMULATIVE_COLUMNS = _insert_after(
    _insert_after(
        CUMULATIVE_COLUMNS,
        "linked_selection_effect",
        "linked_interaction_effect",
    ),
    "cumulative_selection_effect",
    "cumulative_interaction_effect",
)
HIERARCHY_PERIOD_ROLLUP_COLUMNS = PERIOD_DETAIL_COLUMNS
THREE_EFFECT_HIERARCHY_PERIOD_ROLLUP_COLUMNS = THREE_EFFECT_PERIOD_DETAIL_COLUMNS
HIERARCHY_OVERALL_ROLLUP_COLUMNS = (
    "from_date",
    "thru_date",
    "identifier",
    "portfolio_weight",
    "linked_portfolio_contribution",
    "benchmark_weight",
    "linked_benchmark_contribution",
    "active_weight",
    "linked_active_contribution",
    "linked_allocation_effect",
    "linked_selection_effect",
    "linked_total_effect",
)
THREE_EFFECT_HIERARCHY_OVERALL_ROLLUP_COLUMNS = _insert_after(
    HIERARCHY_OVERALL_ROLLUP_COLUMNS,
    "linked_selection_effect",
    "linked_interaction_effect",
)
HIERARCHY_RECONCILIATION_COLUMNS = (
    "scope",
    "from_date",
    "thru_date",
    "identifier",
    "check",
    "actual",
    "expected",
    "residual",
    "tolerance",
    "passed",
)
GEOMETRIC_PERIOD_DETAIL_COLUMNS = (
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
    "semi_notional_contribution",
    "benchmark_accounting_residual",
    "allocation_effect",
    "selection_effect",
)
GEOMETRIC_PERIOD_SUMMARY_COLUMNS = (
    "from_date",
    "thru_date",
    "quantity_of_days",
    "portfolio_return",
    "benchmark_return",
    "semi_notional_return",
    "geometric_excess_return",
    "allocation_effect",
    "selection_effect",
    "total_effect",
)
GEOMETRIC_CUMULATIVE_COLUMNS = GEOMETRIC_PERIOD_SUMMARY_COLUMNS
GEOMETRIC_RECONCILIATION_COLUMNS = (
    "scope",
    "from_date",
    "thru_date",
    "check",
    "actual",
    "expected",
    "difference",
    "tolerance",
    "passed",
)
GEOMETRIC_PERIOD_RECONCILIATION_CHECKS = (
    "identifier_allocation",
    "identifier_selection",
    "allocation_ratio",
    "selection_ratio",
    "geometric_excess",
    "effect_channels",
)
GEOMETRIC_CUMULATIVE_RECONCILIATION_CHECKS = (
    "compounded_portfolio_return",
    "compounded_benchmark_return",
    "compounded_semi_notional_return",
    "compounded_allocation_effect",
    "compounded_selection_effect",
    "geometric_excess",
    "allocation_ratio",
    "selection_ratio",
    "effect_channels",
)
CURRENCY_MARKET_INPUT_COLUMNS = (
    "from_date",
    "thru_date",
    "market_identifier",
    "market_weight",
    "local_asset_return",
    "local_cash_return",
)
CURRENCY_EXPOSURE_INPUT_COLUMNS = (
    "from_date",
    "thru_date",
    "currency_identifier",
    "currency_weight",
    "base_currency_cash_return",
)
CURRENCY_MARKET_DETAIL_COLUMNS = (
    "from_date",
    "thru_date",
    "market_identifier",
    "portfolio_market_weight",
    "portfolio_local_asset_return",
    "benchmark_market_weight",
    "benchmark_local_asset_return",
    "local_cash_return",
    "portfolio_local_log_return_premium",
    "benchmark_local_log_return_premium",
    "active_market_weight",
    "active_local_log_return_premium",
    "market_allocation_log_effect",
    "security_selection_log_effect",
    "total_log_effect",
)
CURRENCY_DETAIL_COLUMNS = (
    "from_date",
    "thru_date",
    "currency_identifier",
    "portfolio_currency_weight",
    "portfolio_base_currency_cash_return",
    "benchmark_currency_weight",
    "benchmark_base_currency_cash_return",
    "portfolio_base_currency_cash_log_return",
    "benchmark_base_currency_cash_log_return",
    "active_currency_weight",
    "active_base_currency_cash_log_return",
    "currency_allocation_log_effect",
    "hedge_selection_log_effect",
    "total_log_effect",
)
CURRENCY_PERIOD_SUMMARY_COLUMNS = (
    "from_date",
    "thru_date",
    "portfolio_market_log_return",
    "benchmark_market_log_return",
    "active_market_log_return",
    "portfolio_currency_log_return",
    "benchmark_currency_log_return",
    "active_currency_log_return",
    "portfolio_total_log_return",
    "benchmark_total_log_return",
    "active_total_log_return",
    "market_allocation_log_effect",
    "security_selection_log_effect",
    "currency_allocation_log_effect",
    "hedge_selection_log_effect",
    "total_log_effect",
)
CURRENCY_RECONCILIATION_COLUMNS = (
    "from_date",
    "thru_date",
    "market_log_effect_sum",
    "active_market_log_return",
    "market_reconciled",
    "currency_log_effect_sum",
    "active_currency_log_return",
    "currency_reconciled",
    "total_log_effect_sum",
    "active_total_log_return",
    "total_reconciled",
)
PERIOD_RECONCILIATION_CHECKS = tuple(
    """portfolio_weight benchmark_weight portfolio_contribution
    benchmark_contribution active_contribution effect_components total_effect""".split()
)
OVERALL_RECONCILIATION_CHECKS = tuple(
    """linked_portfolio_contribution linked_benchmark_contribution
    linked_active_contribution linked_effect_components linked_total_effect""".split()
)
THREE_EFFECT_PERIOD_RECONCILIATION_CHECKS = tuple(
    """portfolio_weight benchmark_weight portfolio_contribution
    benchmark_contribution active_contribution three_effect_components
    total_effect""".split()
)
THREE_EFFECT_OVERALL_RECONCILIATION_CHECKS = tuple(
    """linked_portfolio_contribution linked_benchmark_contribution
    linked_active_contribution linked_three_effect_components
    linked_total_effect""".split()
)
