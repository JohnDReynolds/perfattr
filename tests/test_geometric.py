"""Tests for the geometric-attribution public boundary and result identity."""

from __future__ import annotations

from dataclasses import fields
from typing import cast

import pandas as pd
import pytest

import perfattr
from perfattr import (
    AttributionError,
    AttributionResult,
    GeometricAttributionResult,
    calculate_geometric_attribution,
)
from perfattr._schemas import (
    GEOMETRIC_CUMULATIVE_COLUMNS,
    GEOMETRIC_PERIOD_DETAIL_COLUMNS,
    GEOMETRIC_PERIOD_SUMMARY_COLUMNS,
    GEOMETRIC_RECONCILIATION_COLUMNS,
    PREPARED_REQUIRED_COLUMNS,
)
from perfattr.geometric import __all__ as geometric_all


_GEOMETRIC_PERIOD_DETAIL_COLUMNS = tuple(
    """from_date thru_date quantity_of_days identifier portfolio_weight
    portfolio_return portfolio_contribution benchmark_weight benchmark_return
    benchmark_contribution active_weight active_return active_contribution
    semi_notional_contribution benchmark_accounting_residual allocation_effect
    selection_effect""".split()
)
_GEOMETRIC_PERIOD_TOTAL_COLUMNS = tuple(
    """from_date thru_date quantity_of_days portfolio_return benchmark_return
    semi_notional_return geometric_excess_return allocation_effect selection_effect
    total_effect""".split()
)
_GEOMETRIC_RECONCILIATION_COLUMNS = tuple(
    """scope from_date thru_date check actual expected difference tolerance
    passed""".split()
)
_DATE_COLUMNS = frozenset({"from_date", "thru_date"})
_STRING_COLUMNS = frozenset({"identifier", "scope", "check"})


def _prepared_input(period_return: float) -> pd.DataFrame:
    """Return one valid-looking prepared performance frame for the staged guard."""
    return pd.DataFrame(
        [("2024-01-01", "2024-01-31", "Asset", 1.0, period_return, 31)],
        columns=PREPARED_REQUIRED_COLUMNS,
    )


def _empty_canonical_frame(columns: tuple[str, ...]) -> pd.DataFrame:
    """Construct an empty frame with the exact accepted schema dtypes."""
    values: dict[str, pd.Series] = {}
    for column in columns:
        if column in _DATE_COLUMNS:
            dtype = "datetime64[ns]"
        elif column in _STRING_COLUMNS:
            dtype = "string[python]"
        elif column == "quantity_of_days":
            dtype = "int64"
        elif column == "passed":
            dtype = "bool"
        else:
            dtype = "float64"
        values[column] = pd.Series(dtype=dtype)
    return pd.DataFrame(values)


def test_geometric_api_is_exported_from_module_and_package_root() -> None:
    """Both approved public identities should be importable from either boundary."""
    assert geometric_all == [
        "GeometricAttributionResult",
        "calculate_geometric_attribution",
    ]
    assert perfattr.GeometricAttributionResult is GeometricAttributionResult
    assert perfattr.calculate_geometric_attribution is calculate_geometric_attribution


def test_geometric_result_has_the_exact_approved_field_order() -> None:
    """The separate result must not masquerade as the arithmetic result family."""
    assert [field.name for field in fields(GeometricAttributionResult)] == [
        "period_detail",
        "period_summary",
        "cumulative",
        "reconciliation",
    ]
    assert not issubclass(GeometricAttributionResult, AttributionResult)


def test_geometric_schemas_match_the_accepted_contract() -> None:
    """Schema constants should fix every approved column in exact order."""
    assert GEOMETRIC_PERIOD_DETAIL_COLUMNS == _GEOMETRIC_PERIOD_DETAIL_COLUMNS
    assert GEOMETRIC_PERIOD_SUMMARY_COLUMNS == _GEOMETRIC_PERIOD_TOTAL_COLUMNS
    assert GEOMETRIC_CUMULATIVE_COLUMNS == _GEOMETRIC_PERIOD_TOTAL_COLUMNS
    assert GEOMETRIC_RECONCILIATION_COLUMNS == _GEOMETRIC_RECONCILIATION_COLUMNS
    assert "total_effect" not in GEOMETRIC_PERIOD_DETAIL_COLUMNS
    assert "overall_detail" not in {
        field.name for field in fields(GeometricAttributionResult)
    }


def test_direct_result_construction_retains_canonical_frames() -> None:
    """Ordinary dataclass construction should preserve its four distinct frames.

    This test records the approved empty-frame dtypes without implying that direct
    construction validates, copies, or freezes its inputs.
    """
    period_detail = _empty_canonical_frame(GEOMETRIC_PERIOD_DETAIL_COLUMNS)
    period_summary = _empty_canonical_frame(GEOMETRIC_PERIOD_SUMMARY_COLUMNS)
    cumulative = _empty_canonical_frame(GEOMETRIC_CUMULATIVE_COLUMNS)
    reconciliation = _empty_canonical_frame(GEOMETRIC_RECONCILIATION_COLUMNS)

    result = GeometricAttributionResult(
        period_detail=period_detail,
        period_summary=period_summary,
        cumulative=cumulative,
        reconciliation=reconciliation,
    )

    assert result.period_detail is period_detail
    assert result.period_summary is period_summary
    assert result.cumulative is cumulative
    assert result.reconciliation is reconciliation
    assert len({id(frame) for frame in _result_frames(result)}) == 4
    for frame, columns in (
        (result.period_detail, GEOMETRIC_PERIOD_DETAIL_COLUMNS),
        (result.period_summary, GEOMETRIC_PERIOD_SUMMARY_COLUMNS),
        (result.cumulative, GEOMETRIC_CUMULATIVE_COLUMNS),
        (result.reconciliation, GEOMETRIC_RECONCILIATION_COLUMNS),
    ):
        assert tuple(frame.columns) == columns
        assert isinstance(frame.index, pd.RangeIndex)


def _result_frames(result: GeometricAttributionResult) -> tuple[pd.DataFrame, ...]:
    """Return result frames in the accepted public field order."""
    return (
        result.period_detail,
        result.period_summary,
        result.cumulative,
        result.reconciliation,
    )


@pytest.mark.parametrize("side", ("portfolio", "benchmark"))
def test_geometric_boundary_requires_pandas_inputs(side: str) -> None:
    """Input lookalikes should fail by type before the temporary financial guard."""
    portfolio = _prepared_input(0.02)
    benchmark = _prepared_input(0.01)
    invalid = cast(pd.DataFrame, object())
    if side == "portfolio":
        portfolio = invalid
    else:
        benchmark = invalid

    with pytest.raises(TypeError, match=rf"^{side} must be a pandas DataFrame$"):
        calculate_geometric_attribution(portfolio, benchmark)


@pytest.mark.parametrize("value", (True, "1e-12", None, object()))
def test_geometric_boundary_rejects_nonnumeric_tolerances(value: object) -> None:
    """The approved strict non-boolean real-number boundary should be shared."""
    with pytest.raises(
        TypeError,
        match=r"^reconciliation_tolerance must be a real number$",
    ):
        calculate_geometric_attribution(
            _prepared_input(0.02),
            _prepared_input(0.01),
            reconciliation_tolerance=cast(float, value),
        )


@pytest.mark.parametrize("value", (0.0, -1.0, float("nan"), float("inf")))
def test_geometric_boundary_rejects_invalid_numeric_tolerances(value: float) -> None:
    """Zero, negative, and non-finite tolerances must not reach implementation."""
    with pytest.raises(
        AttributionError,
        match=r"^reconciliation_tolerance must be finite and greater than zero$",
    ):
        calculate_geometric_attribution(
            _prepared_input(0.02),
            _prepared_input(0.01),
            reconciliation_tolerance=value,
        )


def test_valid_geometric_call_returns_complete_result_without_mutating_inputs() -> None:
    """The public boundary should return all four independently owned frames."""
    portfolio = _prepared_input(0.02)
    benchmark = _prepared_input(0.01)
    portfolio_before = portfolio.copy(deep=True)
    benchmark_before = benchmark.copy(deep=True)

    result = calculate_geometric_attribution(
        portfolio,
        benchmark,
        reconciliation_tolerance=1e-10,
    )

    assert isinstance(result, GeometricAttributionResult)
    assert tuple(result.period_detail.columns) == GEOMETRIC_PERIOD_DETAIL_COLUMNS
    assert tuple(result.period_summary.columns) == GEOMETRIC_PERIOD_SUMMARY_COLUMNS
    assert tuple(result.cumulative.columns) == GEOMETRIC_CUMULATIVE_COLUMNS
    assert tuple(result.reconciliation.columns) == GEOMETRIC_RECONCILIATION_COLUMNS
    assert bool(result.reconciliation["passed"].to_numpy().all())
    assert len({id(frame) for frame in _result_frames(result)}) == 4
    pd.testing.assert_frame_equal(portfolio, portfolio_before)
    pd.testing.assert_frame_equal(benchmark, benchmark_before)
