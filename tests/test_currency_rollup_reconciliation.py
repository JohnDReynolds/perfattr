"""Reconciliation and edge-case tests for public currency roll-up results."""

from __future__ import annotations

from collections.abc import Callable
from math import fsum
from typing import cast

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest

from perfattr import (
    AttributionError,
    CurrencyAttributionResult,
    roll_up_currency_attribution,
)
from perfattr._schemas import (
    CURRENCY_ROLLUP_CUMULATIVE_CHECKS,
    CURRENCY_ROLLUP_CUMULATIVE_COLUMNS,
    CURRENCY_ROLLUP_OVERALL_CHECKS,
    CURRENCY_ROLLUP_RECONCILIATION_COLUMNS,
)


_SOURCE_FRAME_NAMES = (
    "market_detail",
    "currency_detail",
    "period_summary",
    "reconciliation",
)
_FloatArrays = dict[str, npt.NDArray[np.float64]]


def _series_number(row: pd.Series, column: str) -> float:
    """Return an explicitly typed number from a heterogeneous result row."""
    return cast(float, row.at[column])


def _zero_numeric_values(frame: pd.DataFrame) -> None:
    """Set every float64 source-result value to exact zero in place."""
    numeric_columns = [
        column for column in frame.columns if frame[column].dtype == np.dtype("float64")
    ]
    frame.loc[:, numeric_columns] = 0.0


def test_reconciliation_has_exact_order_dtypes_and_positive_evidence(
    currency_source_result: CurrencyAttributionResult,
) -> None:
    """One period produces fifteen prefix checks followed by six horizon checks."""
    result = roll_up_currency_attribution(currency_source_result)
    reconciliation = result.reconciliation

    assert tuple(reconciliation.columns) == CURRENCY_ROLLUP_RECONCILIATION_COLUMNS
    assert list(reconciliation["scope"]) == ["cumulative"] * 15 + ["overall"] * 6
    assert list(reconciliation["check"]) == [
        *CURRENCY_ROLLUP_CUMULATIVE_CHECKS,
        *CURRENCY_ROLLUP_OVERALL_CHECKS,
    ]
    assert str(reconciliation["scope"].dtype) == "string"
    assert str(reconciliation["from_date"].dtype) == "datetime64[ns]"
    assert str(reconciliation["thru_date"].dtype) == "datetime64[ns]"
    assert str(reconciliation["check"].dtype) == "string"
    for column in ("actual", "expected", "difference", "tolerance"):
        assert reconciliation[column].dtype == np.dtype("float64")
    assert reconciliation["passed"].dtype == np.dtype("bool")
    assert isinstance(reconciliation.index, pd.RangeIndex)
    np.testing.assert_allclose(
        reconciliation["difference"],
        reconciliation["actual"] - reconciliation["expected"],
        rtol=0.0,
        atol=0.0,
    )
    assert np.asarray(reconciliation["passed"], dtype=np.bool_).all()


def test_reconciliation_rows_encode_the_accepted_financial_identities(
    currency_source_result: CurrencyAttributionResult,
) -> None:
    """Named checks must compare the intended cumulative and horizon quantities."""
    result = roll_up_currency_attribution(currency_source_result)
    cumulative = cast(pd.Series, result.cumulative.iloc[0])
    checks = result.reconciliation.set_index("check")

    market_effect = cast(pd.Series, checks.loc["market_effect_identity"])
    assert _series_number(market_effect, "actual") == pytest.approx(
        _series_number(cumulative, "market_allocation_log_effect")
        + _series_number(cumulative, "security_selection_log_effect"),
        abs=1e-15,
    )
    assert _series_number(market_effect, "expected") == pytest.approx(
        _series_number(cumulative, "active_market_log_return"),
        abs=1e-15,
    )
    total_components = cast(pd.Series, checks.loc["active_total_components"])
    assert _series_number(total_components, "actual") == pytest.approx(
        _series_number(cumulative, "active_total_log_return"), abs=1e-15
    )
    assert _series_number(total_components, "expected") == pytest.approx(
        _series_number(cumulative, "active_market_log_return")
        + _series_number(cumulative, "active_currency_log_return"),
        abs=1e-15,
    )
    market_overall = cast(pd.Series, checks.loc["market_total_detail"])
    assert _series_number(market_overall, "actual") == pytest.approx(
        result.market_overall_detail["total_log_effect"].sum(),
        abs=1e-15,
    )
    assert _series_number(market_overall, "expected") == pytest.approx(
        _series_number(cumulative, "active_market_log_return"),
        abs=1e-15,
    )


def test_explicit_tolerance_is_recorded_without_changing_values(
    currency_source_result: CurrencyAttributionResult,
) -> None:
    """The accepted tolerance changes comparison policy, not financial output."""
    default = roll_up_currency_attribution(currency_source_result)
    explicit = roll_up_currency_attribution(
        currency_source_result,
        reconciliation_tolerance=1e-10,
    )

    np.testing.assert_array_equal(explicit.reconciliation["tolerance"], 1e-10)
    pd.testing.assert_frame_equal(default.cumulative, explicit.cumulative)
    pd.testing.assert_frame_equal(
        default.market_overall_detail,
        explicit.market_overall_detail,
    )
    pd.testing.assert_frame_equal(
        default.currency_overall_detail,
        explicit.currency_overall_detail,
    )


def test_zero_effects_and_non_ascii_base_currency_remain_explicit(
    currency_source_result: CurrencyAttributionResult,
) -> None:
    """Zero is a real additive value and Unicode metadata must be preserved exactly."""
    for name in _SOURCE_FRAME_NAMES:
        _zero_numeric_values(getattr(currency_source_result, name))
    currency_source_result.base_currency = "円"

    result = roll_up_currency_attribution(currency_source_result)

    assert result.base_currency == "円"
    numeric_cumulative = result.cumulative.loc[
        :, list(CURRENCY_ROLLUP_CUMULATIVE_COLUMNS[2:])
    ].to_numpy(dtype=np.float64)
    assert not numeric_cumulative.any()
    assert not result.market_overall_detail.select_dtypes(include="number").to_numpy().any()
    assert not result.currency_overall_detail.select_dtypes(include="number").to_numpy().any()
    assert np.asarray(result.reconciliation["passed"], dtype=np.bool_).all()


def test_long_history_reconciles_every_prefix_without_synthesizing_rows(
    currency_source_result: CurrencyAttributionResult,
    repeat_currency_result: Callable[..., CurrencyAttributionResult],
) -> None:
    """Three hundred supplied monthly periods produce exactly three hundred prefixes."""
    source = repeat_currency_result(currency_source_result, 300)
    period_values = source.period_summary.loc[
        :, list(CURRENCY_ROLLUP_CUMULATIVE_COLUMNS[2:])
    ].to_numpy(dtype=np.float64)

    result = roll_up_currency_attribution(source)

    assert len(result.cumulative) == 300
    assert len(result.reconciliation) == 300 * 15 + 6
    np.testing.assert_allclose(
        result.cumulative.iloc[-1, 2:].to_numpy(dtype=np.float64),
        period_values.sum(axis=0),
        rtol=1e-12,
        atol=1e-12,
    )
    assert np.asarray(result.reconciliation["passed"], dtype=np.bool_).all()


def _random_summary_values(random: np.random.Generator) -> _FloatArrays:
    """Build sixty mutually reconciling random log-return and effect vectors."""
    portfolio_market = random.normal(0.004, 0.025, 60)
    benchmark_market = random.normal(0.003, 0.020, 60)
    portfolio_currency = random.normal(0.001, 0.012, 60)
    benchmark_currency = random.normal(0.0005, 0.010, 60)
    active_market = portfolio_market - benchmark_market
    active_currency = portfolio_currency - benchmark_currency
    market_allocation = random.normal(0.0, 0.01, 60)
    currency_allocation = random.normal(0.0, 0.005, 60)
    portfolio_total = portfolio_market + portfolio_currency
    benchmark_total = benchmark_market + benchmark_currency
    return {
        "portfolio_market_log_return": portfolio_market,
        "benchmark_market_log_return": benchmark_market,
        "active_market_log_return": active_market,
        "portfolio_currency_log_return": portfolio_currency,
        "benchmark_currency_log_return": benchmark_currency,
        "active_currency_log_return": active_currency,
        "portfolio_total_log_return": portfolio_total,
        "benchmark_total_log_return": benchmark_total,
        "active_total_log_return": portfolio_total - benchmark_total,
        "market_allocation_log_effect": market_allocation,
        "security_selection_log_effect": active_market - market_allocation,
        "currency_allocation_log_effect": currency_allocation,
        "hedge_selection_log_effect": active_currency - currency_allocation,
        "total_log_effect": active_market + active_currency,
    }


def _apply_random_source_values(
    source: CurrencyAttributionResult,
    values: _FloatArrays,
) -> None:
    """Apply reconciled random vectors to all source frames consistently."""
    for column, column_values in values.items():
        source.period_summary[column] = column_values

    source.market_detail["market_identifier"] = pd.Series(
        [f"Market {index % 5}" for index in range(60)],
        dtype="string[python]",
    )
    for column in (
        "market_allocation_log_effect",
        "security_selection_log_effect",
        "total_log_effect",
    ):
        source.market_detail[column] = (
            values["active_market_log_return"]
            if column == "total_log_effect"
            else values[column]
        )

    source.currency_detail["currency_identifier"] = pd.Series(
        [f"Currency {index % 4}" for index in range(60)],
        dtype="string[python]",
    )
    for column in (
        "currency_allocation_log_effect",
        "hedge_selection_log_effect",
        "total_log_effect",
    ):
        source.currency_detail[column] = (
            values["active_currency_log_return"]
            if column == "total_log_effect"
            else values[column]
        )

    for source_column, value_column in (
        ("market_log_effect_sum", "active_market_log_return"),
        ("active_market_log_return", "active_market_log_return"),
        ("currency_log_effect_sum", "active_currency_log_return"),
        ("active_currency_log_return", "active_currency_log_return"),
        ("total_log_effect_sum", "total_log_effect"),
        ("active_total_log_return", "active_total_log_return"),
    ):
        source.reconciliation[source_column] = values[value_column]


def test_random_reconciled_history_preserves_every_additive_identity(
    currency_source_result: CurrencyAttributionResult,
    repeat_currency_result: Callable[..., CurrencyAttributionResult],
) -> None:
    """Random finite periods must reconcile cumulatively and by identifier.

    This fixed-seed synthetic result isolates Roadmap 13 from the already tested
    Roadmap 12 formulas. Sixty periods receive independent portfolio and benchmark
    market and currency log returns. Random allocation values split each active grid,
    with selection calculated as the exact balancing channel. Rotating identifiers
    cover late starts, early endings, and reappearance without creating absent rows.
    """
    source = repeat_currency_result(currency_source_result, 60)
    _apply_random_source_values(
        source,
        _random_summary_values(np.random.default_rng(1305)),
    )

    result = roll_up_currency_attribution(source)

    source_matrix = source.period_summary.loc[
        :, list(CURRENCY_ROLLUP_CUMULATIVE_COLUMNS[2:])
    ].to_numpy(dtype=np.float64)
    np.testing.assert_allclose(
        result.cumulative.iloc[:, 2:].to_numpy(dtype=np.float64),
        np.add.accumulate(source_matrix, axis=0),
        rtol=1e-12,
        atol=1e-12,
    )
    for detail, overall, identifier_column in (
        (
            source.market_detail,
            result.market_overall_detail,
            "market_identifier",
        ),
        (
            source.currency_detail,
            result.currency_overall_detail,
            "currency_identifier",
        ),
    ):
        for identifier in overall[identifier_column]:
            source_rows = detail.loc[detail[identifier_column] == identifier]
            overall_row = overall.loc[overall[identifier_column] == identifier].iloc[0]
            for column in overall.columns[3:]:
                assert overall_row[column] == pytest.approx(
                    fsum(float(value) for value in source_rows[column]),
                    rel=1e-12,
                    abs=1e-12,
                )
    assert np.asarray(result.reconciliation["passed"], dtype=np.bool_).all()


def test_cumulative_overflow_returns_no_partial_result(
    currency_source_result: CurrencyAttributionResult,
    repeat_currency_result: Callable[..., CurrencyAttributionResult],
) -> None:
    """Two finite source periods whose sum overflows must fail before returning.

    The synthetic result isolates the roll-up boundary. Every source identity remains
    valid at ``1e308``: portfolio market and total, active market and total, market
    allocation, total effect, and their reconciliation evidence all agree. Only the
    second-period cumulative addition exceeds the finite float64 domain.
    """
    for name in _SOURCE_FRAME_NAMES:
        _zero_numeric_values(getattr(currency_source_result, name))
    currency_source_result.market_detail.loc[
        0, ["market_allocation_log_effect", "total_log_effect"]
    ] = 1e308
    currency_source_result.period_summary.loc[
        0,
        [
            "portfolio_market_log_return",
            "active_market_log_return",
            "portfolio_total_log_return",
            "active_total_log_return",
            "market_allocation_log_effect",
            "total_log_effect",
        ],
    ] = 1e308
    currency_source_result.reconciliation.loc[
        0,
        [
            "market_log_effect_sum",
            "active_market_log_return",
            "total_log_effect_sum",
            "active_total_log_return",
        ],
    ] = 1e308
    source = repeat_currency_result(currency_source_result, 2)
    second_period = source.market_detail["from_date"] == pd.Timestamp("2024-02-01")
    source.market_detail.loc[second_period, "market_identifier"] = "Bond"

    with pytest.raises(
        AttributionError,
        match=r"currency roll-up cumulative column .* contains a non-finite value",
    ):
        roll_up_currency_attribution(source)
