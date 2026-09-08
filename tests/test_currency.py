"""Tests for the currency-attribution public boundary and result identity."""

from __future__ import annotations

from dataclasses import fields
from typing import cast

import pandas as pd
import pytest

import perfattr
from perfattr import (
    AttributionError,
    AttributionResult,
    CurrencyAttributionResult,
    calculate_currency_attribution,
)
from perfattr._schemas import (
    CURRENCY_DETAIL_COLUMNS,
    CURRENCY_EXPOSURE_INPUT_COLUMNS,
    CURRENCY_MARKET_DETAIL_COLUMNS,
    CURRENCY_MARKET_INPUT_COLUMNS,
    CURRENCY_PERIOD_SUMMARY_COLUMNS,
    CURRENCY_RECONCILIATION_COLUMNS,
)
from perfattr.currency import __all__ as currency_all


_MARKET_INPUT_COLUMNS = tuple(
    """from_date thru_date market_identifier market_weight local_asset_return
    local_cash_return""".split()
)
_CURRENCY_INPUT_COLUMNS = tuple(
    """from_date thru_date currency_identifier currency_weight
    base_currency_cash_return""".split()
)
_MARKET_DETAIL_COLUMNS = tuple(
    """from_date thru_date market_identifier portfolio_market_weight
    portfolio_local_asset_return benchmark_market_weight
    benchmark_local_asset_return local_cash_return
    portfolio_local_log_return_premium benchmark_local_log_return_premium
    active_market_weight active_local_log_return_premium
    market_allocation_log_effect security_selection_log_effect
    total_log_effect""".split()
)
_CURRENCY_DETAIL_COLUMNS = tuple(
    """from_date thru_date currency_identifier portfolio_currency_weight
    portfolio_base_currency_cash_return benchmark_currency_weight
    benchmark_base_currency_cash_return portfolio_base_currency_cash_log_return
    benchmark_base_currency_cash_log_return active_currency_weight
    active_base_currency_cash_log_return currency_allocation_log_effect
    hedge_selection_log_effect total_log_effect""".split()
)
_PERIOD_SUMMARY_COLUMNS = tuple(
    """from_date thru_date portfolio_market_log_return
    benchmark_market_log_return active_market_log_return
    portfolio_currency_log_return benchmark_currency_log_return
    active_currency_log_return portfolio_total_log_return
    benchmark_total_log_return active_total_log_return
    market_allocation_log_effect security_selection_log_effect
    currency_allocation_log_effect hedge_selection_log_effect
    total_log_effect""".split()
)
_RECONCILIATION_COLUMNS = tuple(
    """from_date thru_date market_log_effect_sum active_market_log_return
    market_reconciled currency_log_effect_sum active_currency_log_return
    currency_reconciled total_log_effect_sum active_total_log_return
    total_reconciled""".split()
)
_DATE_COLUMNS = frozenset({"from_date", "thru_date"})
_STRING_COLUMNS = frozenset({"market_identifier", "currency_identifier"})
_BOOLEAN_COLUMNS = frozenset(
    {"market_reconciled", "currency_reconciled", "total_reconciled"}
)
_CurrencyInputs = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]


def _market_input(asset_return: float) -> pd.DataFrame:
    """Return one valid market frame for exercising the public boundary."""
    return pd.DataFrame(
        [("2024-01-01", "2024-01-31", "Equity", 1.0, asset_return, 0.002)],
        columns=CURRENCY_MARKET_INPUT_COLUMNS,
    )


def _currency_input(cash_return: float) -> pd.DataFrame:
    """Return one valid currency frame for exercising the public boundary."""
    return pd.DataFrame(
        [("2024-01-01", "2024-01-31", "USD", 1.0, cash_return)],
        columns=CURRENCY_EXPOSURE_INPUT_COLUMNS,
    )


def _empty_canonical_frame(columns: tuple[str, ...]) -> pd.DataFrame:
    """Construct an empty result frame with the exact accepted schema dtypes."""
    dtype_by_column = {
        **dict.fromkeys(_DATE_COLUMNS, "datetime64[ns]"),
        **dict.fromkeys(_STRING_COLUMNS, "string[python]"),
        **dict.fromkeys(_BOOLEAN_COLUMNS, "bool"),
    }
    return pd.DataFrame(
        {
            column: pd.Series(dtype=dtype_by_column.get(column, "float64"))
            for column in columns
        }
    )


def _currency_call(
    inputs: _CurrencyInputs,
    *,
    base_currency: str = "USD",
    reconciliation_tolerance: float = 1e-12,
) -> CurrencyAttributionResult:
    """Call the calculation without obscuring its complete public signature."""
    portfolio_markets, benchmark_markets, portfolio_currencies, benchmark_currencies = (
        inputs
    )
    return calculate_currency_attribution(
        portfolio_markets,
        benchmark_markets,
        portfolio_currencies,
        benchmark_currencies,
        base_currency=base_currency,
        reconciliation_tolerance=reconciliation_tolerance,
    )


def test_currency_api_is_exported_from_module_and_package_root() -> None:
    """Both accepted public identities should be importable from either boundary."""
    assert currency_all == [
        "CurrencyAttributionResult",
        "calculate_currency_attribution",
    ]
    assert perfattr.CurrencyAttributionResult is CurrencyAttributionResult
    assert perfattr.calculate_currency_attribution is calculate_currency_attribution


def test_currency_result_has_the_exact_accepted_field_order() -> None:
    """The currency result must remain separate from domestic attribution results."""
    assert [field.name for field in fields(CurrencyAttributionResult)] == [
        "market_detail",
        "currency_detail",
        "period_summary",
        "reconciliation",
        "base_currency",
    ]
    assert not issubclass(CurrencyAttributionResult, AttributionResult)


def test_currency_input_schemas_match_the_accepted_contract() -> None:
    """Input schema constants should preserve four side-separated frames."""
    assert CURRENCY_MARKET_INPUT_COLUMNS == _MARKET_INPUT_COLUMNS
    assert CURRENCY_EXPOSURE_INPUT_COLUMNS == _CURRENCY_INPUT_COLUMNS
    assert "quantity_of_days" not in CURRENCY_MARKET_INPUT_COLUMNS
    assert "quantity_of_days" not in CURRENCY_EXPOSURE_INPUT_COLUMNS
    assert not any(column.startswith("portfolio_") for column in _MARKET_INPUT_COLUMNS)
    assert not any(column.startswith("benchmark_") for column in _MARKET_INPUT_COLUMNS)


def test_currency_result_schemas_match_the_accepted_contract() -> None:
    """Result schema constants should fix every accepted column in exact order."""
    assert CURRENCY_MARKET_DETAIL_COLUMNS == _MARKET_DETAIL_COLUMNS
    assert CURRENCY_DETAIL_COLUMNS == _CURRENCY_DETAIL_COLUMNS
    assert CURRENCY_PERIOD_SUMMARY_COLUMNS == _PERIOD_SUMMARY_COLUMNS
    assert CURRENCY_RECONCILIATION_COLUMNS == _RECONCILIATION_COLUMNS
    for columns in (
        CURRENCY_MARKET_DETAIL_COLUMNS,
        CURRENCY_DETAIL_COLUMNS,
        CURRENCY_PERIOD_SUMMARY_COLUMNS,
        CURRENCY_RECONCILIATION_COLUMNS,
    ):
        assert "quantity_of_days" not in columns
    effect_columns = {
        column
        for columns in (
            CURRENCY_MARKET_DETAIL_COLUMNS,
            CURRENCY_DETAIL_COLUMNS,
            CURRENCY_PERIOD_SUMMARY_COLUMNS,
        )
        for column in columns
        if "effect" in column
    }
    assert effect_columns
    assert all(column.endswith("_log_effect") for column in effect_columns)


def test_direct_currency_result_construction_retains_supplied_values() -> None:
    """Ordinary dataclass construction should retain four distinct frames and metadata.

    This records the accepted empty-frame dtypes without implying that direct
    construction validates, copies, or freezes supplied values.
    """
    market_detail = _empty_canonical_frame(CURRENCY_MARKET_DETAIL_COLUMNS)
    currency_detail = _empty_canonical_frame(CURRENCY_DETAIL_COLUMNS)
    period_summary = _empty_canonical_frame(CURRENCY_PERIOD_SUMMARY_COLUMNS)
    reconciliation = _empty_canonical_frame(CURRENCY_RECONCILIATION_COLUMNS)

    result = CurrencyAttributionResult(
        market_detail=market_detail,
        currency_detail=currency_detail,
        period_summary=period_summary,
        reconciliation=reconciliation,
        base_currency="usd",
    )

    assert result.market_detail is market_detail
    assert result.currency_detail is currency_detail
    assert result.period_summary is period_summary
    assert result.reconciliation is reconciliation
    assert result.base_currency == "usd"
    assert len({id(frame) for frame in _result_frames(result)}) == 4
    for frame, columns in zip(
        _result_frames(result),
        (
            CURRENCY_MARKET_DETAIL_COLUMNS,
            CURRENCY_DETAIL_COLUMNS,
            CURRENCY_PERIOD_SUMMARY_COLUMNS,
            CURRENCY_RECONCILIATION_COLUMNS,
        ),
        strict=True,
    ):
        assert tuple(frame.columns) == columns
        assert isinstance(frame.index, pd.RangeIndex)


def _result_frames(result: CurrencyAttributionResult) -> tuple[pd.DataFrame, ...]:
    """Return result frames in the accepted public field order."""
    return (
        result.market_detail,
        result.currency_detail,
        result.period_summary,
        result.reconciliation,
    )


@pytest.mark.parametrize(
    "input_name",
    (
        "portfolio_markets",
        "benchmark_markets",
        "portfolio_currencies",
        "benchmark_currencies",
    ),
)
def test_currency_boundary_requires_four_pandas_inputs(input_name: str) -> None:
    """Each input lookalike should fail by type before financial calculation."""
    inputs = {
        "portfolio_markets": _market_input(0.02),
        "benchmark_markets": _market_input(0.01),
        "portfolio_currencies": _currency_input(0.002),
        "benchmark_currencies": _currency_input(0.002),
    }
    inputs[input_name] = cast(pd.DataFrame, object())

    with pytest.raises(
        TypeError,
        match=rf"^{input_name} must be a pandas DataFrame$",
    ):
        _currency_call(
            (
                inputs["portfolio_markets"],
                inputs["benchmark_markets"],
                inputs["portfolio_currencies"],
                inputs["benchmark_currencies"],
            )
        )


@pytest.mark.parametrize("value", (True, 123, None, object()))
def test_currency_boundary_rejects_nonstring_base_currency(value: object) -> None:
    """The base-currency audit identity must be supplied explicitly as text."""
    with pytest.raises(TypeError, match=r"^base_currency must be a string$"):
        _currency_call(
            (
                _market_input(0.02),
                _market_input(0.01),
                _currency_input(0.002),
                _currency_input(0.002),
            ),
            base_currency=cast(str, value),
        )


@pytest.mark.parametrize("value", ("", " ", " USD", "USD ", "\tUSD"))
def test_currency_boundary_rejects_invalid_base_currency(value: str) -> None:
    """Empty or padded identities must not be silently normalized."""
    with pytest.raises(
        AttributionError,
        match=(
            "^base_currency must be nonempty with no leading or trailing "
            "whitespace$"
        ),
    ):
        _currency_call(
            (
                _market_input(0.02),
                _market_input(0.01),
                _currency_input(0.002),
                _currency_input(0.002),
            ),
            base_currency=value,
        )


@pytest.mark.parametrize("value", (True, "1e-12", None, object()))
def test_currency_boundary_rejects_nonnumeric_tolerances(value: object) -> None:
    """The accepted tolerance boundary excludes booleans and numeric lookalikes."""
    with pytest.raises(
        TypeError,
        match=r"^reconciliation_tolerance must be a real number$",
    ):
        _currency_call(
            (
                _market_input(0.02),
                _market_input(0.01),
                _currency_input(0.002),
                _currency_input(0.002),
            ),
            reconciliation_tolerance=cast(float, value),
        )


@pytest.mark.parametrize("value", (0.0, -1.0, float("nan"), float("inf")))
def test_currency_boundary_rejects_invalid_numeric_tolerances(value: float) -> None:
    """Zero, negative, and nonfinite tolerances must not reach calculation."""
    with pytest.raises(
        AttributionError,
        match=r"^reconciliation_tolerance must be finite and greater than zero$",
    ):
        _currency_call(
            (
                _market_input(0.02),
                _market_input(0.01),
                _currency_input(0.002),
                _currency_input(0.002),
            ),
            reconciliation_tolerance=value,
        )


def test_valid_currency_call_returns_owned_frames_without_mutation() -> None:
    """A complete valid call should return owned frames without caller mutation."""
    inputs = (
        _market_input(0.02),
        _market_input(0.01),
        _currency_input(0.002),
        _currency_input(0.002),
    )
    before = tuple(frame.copy(deep=True) for frame in inputs)

    result = _currency_call(inputs, base_currency="usd")

    for frame, expected in zip(inputs, before, strict=True):
        pd.testing.assert_frame_equal(frame, expected)
    assert result.base_currency == "usd"
    assert len({id(frame) for frame in _result_frames(result)}) == 4
    assert bool(result.reconciliation["total_reconciled"].all())


def test_malformed_currency_content_is_rejected_before_calculation() -> None:
    """Invalid content must fail before any financial calculation."""
    malformed = pd.DataFrame({"unexpected": [object()]})

    with pytest.raises(
        AttributionError,
        match=r"^portfolio_markets input must contain exactly the required columns",
    ):
        _currency_call((malformed, malformed, malformed, malformed))
