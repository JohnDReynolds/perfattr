"""Tests for mutable currency-result validation at the roll-up boundary."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import cast

import numpy as np
import pandas as pd
import pytest

from perfattr import (
    AttributionError,
    CurrencyAttributionResult,
    roll_up_currency_attribution,
)
from perfattr._currency_rollup_source import validate_source_result


_Mutation = Callable[[CurrencyAttributionResult], None]
_FRAME_NAMES = (
    "market_detail",
    "currency_detail",
    "period_summary",
    "reconciliation",
)


def _timestamp(frame: pd.DataFrame, row: int, column: str) -> pd.Timestamp:
    """Return one explicitly typed timestamp from a heterogeneous result frame."""
    return cast(pd.Timestamp, frame.at[row, column])


def _number(frame: pd.DataFrame, row: int, column: str) -> float:
    """Return one explicitly typed financial value from a result frame."""
    return cast(float, frame.at[row, column])


def _clone_result(result: CurrencyAttributionResult) -> CurrencyAttributionResult:
    """Return an independently owned source-result clone for mutation tests."""
    return deepcopy(result)


def _swap_market_columns(result: CurrencyAttributionResult) -> None:
    """Retain the column set but violate its released order."""
    columns = list(result.market_detail.columns)
    columns[2], columns[3] = columns[3], columns[2]
    result.market_detail = result.market_detail.loc[:, columns]


def _change_summary_dtype(result: CurrencyAttributionResult) -> None:
    """Replace a canonical float64 summary column with float32."""
    result.period_summary["portfolio_market_log_return"] = result.period_summary[
        "portfolio_market_log_return"
    ].astype("float32")


def _empty_reconciliation(result: CurrencyAttributionResult) -> None:
    """Remove the only source reconciliation period without changing its schema."""
    result.reconciliation = result.reconciliation.iloc[0:0].copy()


def _null_market_value(result: CurrencyAttributionResult) -> None:
    """Introduce a forbidden null into a released numerical result column."""
    result.market_detail.loc[0, "portfolio_market_weight"] = float("nan")


def _pad_currency_identifier(result: CurrencyAttributionResult) -> None:
    """Make a source identifier noncanonical without changing its dtype."""
    result.currency_detail.loc[0, "currency_identifier"] = " USD"


def _add_intraday_time(result: CurrencyAttributionResult) -> None:
    """Retain datetime64 dtype while violating normalized-date semantics."""
    result.period_summary.at[0, "from_date"] = _timestamp(
        result.period_summary, 0, "from_date"
    ) + pd.Timedelta(hours=1)


def _duplicate_market_key(result: CurrencyAttributionResult) -> None:
    """Append an otherwise valid duplicate market period key."""
    result.market_detail = pd.concat(
        [result.market_detail, result.market_detail.iloc[[0]]],
        ignore_index=True,
    )


def _reverse_summary_period(result: CurrencyAttributionResult) -> None:
    """Place a period start after its inclusive end date."""
    result.period_summary.loc[0, "from_date"] = pd.Timestamp("2024-02-01")


def _change_reconciliation_period(result: CurrencyAttributionResult) -> None:
    """Make the reconciliation period set disagree with the detail frames."""
    result.reconciliation.at[0, "thru_date"] = _timestamp(
        result.reconciliation, 0, "thru_date"
    ) + pd.Timedelta(days=1)


def _fail_source_reconciliation(result: CurrencyAttributionResult) -> None:
    """Mark one released source calculation identity as failed."""
    result.reconciliation.loc[0, "market_reconciled"] = False


def _break_market_row_components(result: CurrencyAttributionResult) -> None:
    """Make a market row total disagree with its two component channels."""
    result.market_detail.at[0, "total_log_effect"] = _number(
        result.market_detail, 0, "total_log_effect"
    ) + 0.01


def _break_currency_row_components(result: CurrencyAttributionResult) -> None:
    """Make a currency row total disagree with its two component channels."""
    result.currency_detail.at[0, "total_log_effect"] = _number(
        result.currency_detail, 0, "total_log_effect"
    ) + 0.01


def _break_summary_active_market(result: CurrencyAttributionResult) -> None:
    """Make active market return disagree with portfolio minus benchmark."""
    result.period_summary.at[0, "active_market_log_return"] = _number(
        result.period_summary, 0, "active_market_log_return"
    ) + 0.01


def _break_summary_active_currency(result: CurrencyAttributionResult) -> None:
    """Make active currency return disagree with portfolio minus benchmark."""
    result.period_summary.at[0, "active_currency_log_return"] = _number(
        result.period_summary, 0, "active_currency_log_return"
    ) + 0.01


def _break_portfolio_total_components(result: CurrencyAttributionResult) -> None:
    """Preserve active subtraction while breaking portfolio total components."""
    for column in ("portfolio_total_log_return", "active_total_log_return"):
        result.period_summary.at[0, column] = _number(
            result.period_summary, 0, column
        ) + 0.01


def _break_summary_detail_total(result: CurrencyAttributionResult) -> None:
    """Make a summary channel disagree with its market-detail aggregation."""
    result.period_summary.at[0, "market_allocation_log_effect"] = _number(
        result.period_summary, 0, "market_allocation_log_effect"
    ) + 0.01


def _break_summary_total_effect(result: CurrencyAttributionResult) -> None:
    """Make total effect disagree with the four accepted summary channels."""
    result.period_summary.at[0, "total_log_effect"] = _number(
        result.period_summary, 0, "total_log_effect"
    ) + 0.01


def _break_reconciliation_value(result: CurrencyAttributionResult) -> None:
    """Keep flags true while falsifying their recorded numerical evidence."""
    result.reconciliation.at[0, "active_market_log_return"] = _number(
        result.reconciliation, 0, "active_market_log_return"
    ) + 0.01


def _make_effect_nonfinite(result: CurrencyAttributionResult) -> None:
    """Introduce an infinite source effect before any roll-up calculation."""
    result.currency_detail.loc[0, "hedge_selection_log_effect"] = float("inf")


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (_swap_market_columns, "exact released column order"),
        (_change_summary_dtype, "does not use its released dtype"),
        (_empty_reconciliation, "frames must not be empty"),
        (_null_market_value, "contains null values"),
        (_pad_currency_identifier, "contains a noncanonical identity"),
        (_add_intraday_time, "contains a non-normalized date"),
        (_duplicate_market_key, "contains duplicate keys"),
        (_reverse_summary_period, "contains an invalid period"),
        (_change_reconciliation_period, "period sets must match exactly"),
        (_fail_source_reconciliation, "must contain only passes"),
        (_break_market_row_components, "market_detail has invalid effect components"),
        (
            _break_currency_row_components,
            "currency_detail has invalid effect components",
        ),
        (_break_summary_active_market, "invalid active market log returns"),
        (_break_summary_active_currency, "invalid active currency log returns"),
        (_break_portfolio_total_components, "invalid portfolio total components"),
        (_break_summary_detail_total, "does not match market_detail"),
        (_break_summary_total_effect, "invalid total effect components"),
        (_break_reconciliation_value, "does not match source values"),
        (_make_effect_nonfinite, "contains a non-finite value"),
    ),
)
def test_public_rollup_rejects_a_mutated_source_result(
    currency_source_result: CurrencyAttributionResult,
    mutation: _Mutation,
    message: str,
) -> None:
    """Caller-mutable result fields must retain every released source invariant."""
    mutation(currency_source_result)

    with pytest.raises(AttributionError, match=message):
        roll_up_currency_attribution(currency_source_result)


def test_public_rollup_rejects_invalid_source_field_and_metadata_types(
    currency_source_result: CurrencyAttributionResult,
) -> None:
    """Frame-shaped values and string-like metadata must not impersonate exact types."""
    valid_result = _clone_result(currency_source_result)
    currency_source_result.period_summary = cast(pd.DataFrame, [])
    with pytest.raises(
        TypeError,
        match=r"^source result period_summary must be a pandas DataFrame$",
    ):
        roll_up_currency_attribution(currency_source_result)

    second_result = _clone_result(valid_result)
    second_result.base_currency = cast(str, 123)
    with pytest.raises(
        TypeError,
        match=r"^source result base_currency must be a string$",
    ):
        roll_up_currency_attribution(second_result)


@pytest.mark.parametrize("value", ("", " USD", "USD "))
def test_public_rollup_rejects_noncanonical_base_currency(
    currency_source_result: CurrencyAttributionResult,
    value: str,
) -> None:
    """The roll-up preserves rather than trims the released audit identity."""
    currency_source_result.base_currency = value
    with pytest.raises(AttributionError, match="base_currency must be nonempty"):
        roll_up_currency_attribution(currency_source_result)


def test_public_rollup_rejects_overlapping_but_aligned_periods(
    currency_source_result: CurrencyAttributionResult,
    repeat_currency_result: Callable[..., CurrencyAttributionResult],
) -> None:
    """Consistently keyed source frames still may not describe overlapping periods."""
    result = repeat_currency_result(currency_source_result, 2)
    second_start = np.datetime64("2024-01-15", "ns")
    for name in _FRAME_NAMES:
        frame = cast(pd.DataFrame, getattr(result, name))
        frame.loc[frame["from_date"] == pd.Timestamp("2024-02-01"), "from_date"] = (
            second_start
        )

    with pytest.raises(AttributionError, match="contains overlapping periods"):
        roll_up_currency_attribution(result)


def test_source_validation_copies_sorts_and_preserves_gaps(
    currency_source_result: CurrencyAttributionResult,
    repeat_currency_result: Callable[..., CurrencyAttributionResult],
) -> None:
    """Row order is immaterial, gaps remain gaps, and caller frames remain untouched."""
    result = repeat_currency_result(currency_source_result, 4, gaps=True)
    for offset, name in enumerate(_FRAME_NAMES):
        frame = cast(pd.DataFrame, getattr(result, name))
        setattr(
            result,
            name,
            frame.sample(frac=1.0, random_state=offset),
        )
    source_frames = tuple(
        cast(pd.DataFrame, getattr(result, name)) for name in _FRAME_NAMES
    )
    before = tuple(frame.copy(deep=True) for frame in source_frames)

    validated = validate_source_result(result, 1e-12)

    validated_frames = (
        validated.market_detail,
        validated.currency_detail,
        validated.period_summary,
        validated.reconciliation,
    )
    assert validated.base_currency == "USD"
    assert len({id(frame) for frame in (*source_frames, *validated_frames)}) == 8
    assert all(isinstance(frame.index, pd.RangeIndex) for frame in validated_frames)
    assert validated.period_summary["thru_date"].is_monotonic_increasing
    second_start = _timestamp(validated.period_summary, 1, "from_date")
    first_end = _timestamp(validated.period_summary, 0, "thru_date")
    assert second_start > first_end + pd.Timedelta(days=1)
    for frame, expected in zip(source_frames, before, strict=True):
        pd.testing.assert_frame_equal(frame, expected)

    rollup = roll_up_currency_attribution(result)
    assert len(rollup.cumulative) == 4
    assert rollup.base_currency == "USD"


def test_randomly_selected_corruptions_fail_before_the_financial_guard(
    currency_source_result: CurrencyAttributionResult,
    repeat_currency_result: Callable[..., CurrencyAttributionResult],
) -> None:
    """Random period selection must not create a blind spot in active-total checks.

    Twenty-four otherwise valid monthly periods exercise the validation vector over
    a realistic history. A fixed random seed selects twelve period rows and signed
    corruptions independently. Each change breaks ``active total = portfolio total -
    benchmark total`` and must fail before roll-up calculation.
    """
    source = repeat_currency_result(currency_source_result, 24)
    random = np.random.default_rng(20260908)
    for _ in range(12):
        result = _clone_result(source)
        row = int(random.integers(0, len(result.period_summary)))
        direction = float(random.choice((-1.0, 1.0)))
        result.period_summary.at[row, "active_total_log_return"] = _number(
            result.period_summary,
            row,
            "active_total_log_return",
        ) + direction * 0.001
        with pytest.raises(AttributionError, match="invalid active total log returns"):
            roll_up_currency_attribution(result)
