"""Tests for the multi-period currency roll-up public boundary."""

from __future__ import annotations

from dataclasses import fields
from inspect import Parameter, signature
from typing import cast

import pandas as pd
import pytest

import perfattr
from perfattr import (
    AttributionError,
    CurrencyAttributionResult,
    CurrencyAttributionRollupResult,
    roll_up_currency_attribution,
)
from perfattr._schemas import (
    CURRENCY_PERIOD_SUMMARY_COLUMNS,
    CURRENCY_ROLLUP_CUMULATIVE_CHECKS,
    CURRENCY_ROLLUP_CUMULATIVE_COLUMNS,
    CURRENCY_ROLLUP_CURRENCY_OVERALL_COLUMNS,
    CURRENCY_ROLLUP_MARKET_OVERALL_COLUMNS,
    CURRENCY_ROLLUP_OVERALL_CHECKS,
    CURRENCY_ROLLUP_RECONCILIATION_COLUMNS,
)
from perfattr.currency_rollup import __all__ as currency_rollup_all


_MARKET_OVERALL_COLUMNS = tuple(
    """from_date thru_date market_identifier market_allocation_log_effect
    security_selection_log_effect total_log_effect""".split()
)
_CURRENCY_OVERALL_COLUMNS = tuple(
    """from_date thru_date currency_identifier currency_allocation_log_effect
    hedge_selection_log_effect total_log_effect""".split()
)
_RECONCILIATION_COLUMNS = tuple(
    """scope from_date thru_date check actual expected difference tolerance
    passed""".split()
)
_CUMULATIVE_CHECKS = tuple(
    """portfolio_market_rollup benchmark_market_rollup active_market_identity
    market_effect_identity portfolio_currency_rollup benchmark_currency_rollup
    active_currency_identity currency_effect_identity portfolio_total_rollup
    benchmark_total_rollup portfolio_total_components benchmark_total_components
    active_total_identity active_total_components total_effect_identity""".split()
)
_OVERALL_CHECKS = tuple(
    """market_allocation_detail security_selection_detail market_total_detail
    currency_allocation_detail hedge_selection_detail currency_total_detail""".split()
)
_DATE_COLUMNS = frozenset({"from_date", "thru_date"})
_STRING_COLUMNS = frozenset(
    {"market_identifier", "currency_identifier", "scope", "check"}
)


def _empty_canonical_frame(columns: tuple[str, ...]) -> pd.DataFrame:
    """Construct an empty roll-up frame with the accepted canonical dtypes."""
    dtype_by_column = {
        **dict.fromkeys(_DATE_COLUMNS, "datetime64[ns]"),
        **dict.fromkeys(_STRING_COLUMNS, "string[python]"),
        "passed": "bool",
    }
    return pd.DataFrame(
        {
            column: pd.Series(dtype=dtype_by_column.get(column, "float64"))
            for column in columns
        }
    )


def test_currency_rollup_api_is_exported_from_module_and_package_root() -> None:
    """Both approved identities should be importable from either boundary."""
    assert currency_rollup_all == [
        "CurrencyAttributionRollupResult",
        "roll_up_currency_attribution",
    ]
    assert (
        perfattr.CurrencyAttributionRollupResult
        is CurrencyAttributionRollupResult
    )
    assert perfattr.roll_up_currency_attribution is roll_up_currency_attribution


def test_currency_rollup_result_has_the_exact_approved_field_order() -> None:
    """The roll-up result must remain separate from its source result family."""
    assert [field.name for field in fields(CurrencyAttributionRollupResult)] == [
        "market_overall_detail",
        "currency_overall_detail",
        "cumulative",
        "reconciliation",
        "base_currency",
    ]
    assert not issubclass(CurrencyAttributionRollupResult, CurrencyAttributionResult)


def test_currency_rollup_function_has_the_exact_approved_signature() -> None:
    """The boundary has one source argument and one keyword-only policy."""
    parameters = signature(roll_up_currency_attribution).parameters
    assert list(parameters) == ["result", "reconciliation_tolerance"]
    assert parameters["result"].kind is Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["reconciliation_tolerance"].kind is Parameter.KEYWORD_ONLY
    assert parameters["reconciliation_tolerance"].default == 1e-12


def test_currency_rollup_schemas_and_check_order_match_the_contract() -> None:
    """Schema constants should fix every approved column and check in order."""
    assert CURRENCY_ROLLUP_MARKET_OVERALL_COLUMNS == _MARKET_OVERALL_COLUMNS
    assert CURRENCY_ROLLUP_CURRENCY_OVERALL_COLUMNS == _CURRENCY_OVERALL_COLUMNS
    assert CURRENCY_ROLLUP_CUMULATIVE_COLUMNS == CURRENCY_PERIOD_SUMMARY_COLUMNS
    assert CURRENCY_ROLLUP_RECONCILIATION_COLUMNS == _RECONCILIATION_COLUMNS
    assert CURRENCY_ROLLUP_CUMULATIVE_CHECKS == _CUMULATIVE_CHECKS
    assert CURRENCY_ROLLUP_OVERALL_CHECKS == _OVERALL_CHECKS


def test_direct_currency_rollup_result_construction_retains_supplied_values() -> None:
    """Ordinary construction retains canonical frames without validating or copying."""
    frames = (
        _empty_canonical_frame(CURRENCY_ROLLUP_MARKET_OVERALL_COLUMNS),
        _empty_canonical_frame(CURRENCY_ROLLUP_CURRENCY_OVERALL_COLUMNS),
        _empty_canonical_frame(CURRENCY_ROLLUP_CUMULATIVE_COLUMNS),
        _empty_canonical_frame(CURRENCY_ROLLUP_RECONCILIATION_COLUMNS),
    )
    result = CurrencyAttributionRollupResult(
        market_overall_detail=frames[0],
        currency_overall_detail=frames[1],
        cumulative=frames[2],
        reconciliation=frames[3],
        base_currency="usd",
    )
    result_frames = (
        result.market_overall_detail,
        result.currency_overall_detail,
        result.cumulative,
        result.reconciliation,
    )

    assert all(
        result_frame is source_frame
        for result_frame, source_frame in zip(result_frames, frames, strict=True)
    )
    assert result.base_currency == "usd"
    assert len({id(frame) for frame in result_frames}) == 4
    for frame, columns in zip(
        result_frames,
        (
            CURRENCY_ROLLUP_MARKET_OVERALL_COLUMNS,
            CURRENCY_ROLLUP_CURRENCY_OVERALL_COLUMNS,
            CURRENCY_ROLLUP_CUMULATIVE_COLUMNS,
            CURRENCY_ROLLUP_RECONCILIATION_COLUMNS,
        ),
        strict=True,
    ):
        assert tuple(frame.columns) == columns
        assert isinstance(frame.index, pd.RangeIndex)


def test_currency_rollup_boundary_rejects_a_source_lookalike() -> None:
    """Only the dedicated currency-attribution source type may cross the boundary."""
    with pytest.raises(
        TypeError,
        match=r"^result must be a CurrencyAttributionResult$",
    ):
        roll_up_currency_attribution(cast(CurrencyAttributionResult, object()))


@pytest.mark.parametrize("value", (True, "1e-12", None, object()))
def test_currency_rollup_boundary_rejects_nonnumeric_tolerances(
    value: object,
    currency_source_result: CurrencyAttributionResult,
) -> None:
    """The approved tolerance boundary excludes booleans and numeric lookalikes."""
    with pytest.raises(
        TypeError,
        match=r"^reconciliation_tolerance must be a real number$",
    ):
        roll_up_currency_attribution(
            currency_source_result,
            reconciliation_tolerance=cast(float, value),
        )


@pytest.mark.parametrize("value", (0.0, -1.0, float("nan"), float("inf")))
def test_currency_rollup_boundary_rejects_invalid_numeric_tolerances(
    value: float,
    currency_source_result: CurrencyAttributionResult,
) -> None:
    """Zero, negative, and non-finite tolerances must not reach calculation."""
    with pytest.raises(
        AttributionError,
        match=r"^reconciliation_tolerance must be finite and greater than zero$",
    ):
        roll_up_currency_attribution(
            currency_source_result,
            reconciliation_tolerance=value,
        )


def test_valid_currency_rollup_call_returns_complete_owned_result(
    currency_source_result: CurrencyAttributionResult,
) -> None:
    """A valid boundary call returns all frames without source mutation."""
    source = currency_source_result
    source_frames = (
        source.market_detail,
        source.currency_detail,
        source.period_summary,
        source.reconciliation,
    )
    before = tuple(frame.copy(deep=True) for frame in source_frames)

    result = roll_up_currency_attribution(source)

    for frame, expected in zip(
        source_frames,
        before,
        strict=True,
    ):
        pd.testing.assert_frame_equal(frame, expected)
    assert isinstance(result, CurrencyAttributionRollupResult)
    assert tuple(result.market_overall_detail.columns) == (
        CURRENCY_ROLLUP_MARKET_OVERALL_COLUMNS
    )
    assert tuple(result.currency_overall_detail.columns) == (
        CURRENCY_ROLLUP_CURRENCY_OVERALL_COLUMNS
    )
    assert tuple(result.cumulative.columns) == CURRENCY_ROLLUP_CUMULATIVE_COLUMNS
    assert tuple(result.reconciliation.columns) == (
        CURRENCY_ROLLUP_RECONCILIATION_COLUMNS
    )
    assert result.base_currency == "USD"
    assert bool(result.reconciliation["passed"].all())
