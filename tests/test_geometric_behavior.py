"""Public behavior and compatibility tests for geometric attribution."""

from __future__ import annotations

from typing import cast

import pandas as pd
import pytest

from perfattr import calculate_attribution, calculate_geometric_attribution
from perfattr._schemas import PREPARED_PERFORMANCE_COLUMNS, PREPARED_REQUIRED_COLUMNS
from perfattr.attribution import AttributionResult
from perfattr.geometric import GeometricAttributionResult


def _authoritative_null_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return opposing unexposed charges that exercise both null-return sides."""
    portfolio = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "Asset", 1.0, 0.10, 0.050, 31),
            ("2024-01-01", "2024-01-31", "B Fee", 0.0, None, 0.000, 31),
            ("2024-01-01", "2024-01-31", "P Fee", 0.0, None, -0.001, 31),
        ],
        columns=PREPARED_PERFORMANCE_COLUMNS,
    )
    benchmark = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "Asset", 1.0, 0.07, 0.040, 31),
            ("2024-01-01", "2024-01-31", "B Fee", 0.0, None, -0.002, 31),
            ("2024-01-01", "2024-01-31", "P Fee", 0.0, None, 0.000, 31),
        ],
        columns=PREPARED_PERFORMANCE_COLUMNS,
    )
    return portfolio, benchmark


def _assert_string_python(series: pd.Series) -> None:
    """Require pandas' explicit Python-backed string extension dtype."""
    assert isinstance(series.dtype, pd.StringDtype)
    assert series.dtype.storage == "python"


def _assert_canonical_dtypes(result: GeometricAttributionResult) -> None:
    """Require every public geometric frame's exact accepted dtype families."""
    for frame in (result.period_detail, result.period_summary, result.cumulative):
        assert str(frame["from_date"].dtype) == "datetime64[ns]"
        assert str(frame["thru_date"].dtype) == "datetime64[ns]"
        assert str(frame["quantity_of_days"].dtype) == "int64"
        for column in frame.columns.difference(
            ["from_date", "thru_date", "quantity_of_days", "identifier"],
            sort=False,
        ):
            assert str(frame[column].dtype) == "float64"
    _assert_string_python(result.period_detail["identifier"])

    reconciliation = result.reconciliation
    assert str(reconciliation["from_date"].dtype) == "datetime64[ns]"
    assert str(reconciliation["thru_date"].dtype) == "datetime64[ns]"
    _assert_string_python(reconciliation["scope"])
    _assert_string_python(reconciliation["check"])
    for column in ("actual", "expected", "difference", "tolerance"):
        assert str(reconciliation[column].dtype) == "float64"
    assert str(reconciliation["passed"].dtype) == "bool"


def test_public_result_has_exact_dtypes_indexes_and_null_placement() -> None:
    """Only mathematically undefined effective and active returns may be null.

    P Fee has an undefined portfolio return and a neutral benchmark return; B Fee has
    the opposite. Both active returns are consequently undefined. Their authoritative
    contributions remain finite in selection or the benchmark allocation residual,
    while all aggregate geometric values and reconciliation evidence remain defined.
    """
    portfolio, benchmark = _authoritative_null_inputs()

    result = calculate_geometric_attribution(portfolio, benchmark)
    detail = result.period_detail.set_index("identifier")

    _assert_canonical_dtypes(result)
    for frame in _geometric_frames(result).values():
        assert frame.index.equals(pd.RangeIndex(len(frame)))
    assert pd.isna(detail.at["P Fee", "portfolio_return"])
    assert detail.at["P Fee", "benchmark_return"] == pytest.approx(0.0)
    assert pd.isna(detail.at["P Fee", "active_return"])
    assert detail.at["P Fee", "selection_effect"] == pytest.approx(-0.001 / 1.04)
    assert detail.at["B Fee", "portfolio_return"] == pytest.approx(0.0)
    assert pd.isna(detail.at["B Fee", "benchmark_return"])
    assert pd.isna(detail.at["B Fee", "active_return"])
    assert detail.at["B Fee", "benchmark_accounting_residual"] == pytest.approx(
        -0.002
    )
    assert detail.at["B Fee", "allocation_effect"] == pytest.approx(0.002 / 1.038)
    assert not result.period_summary.isna().to_numpy().any()
    assert not result.cumulative.isna().to_numpy().any()
    assert not result.reconciliation.isna().to_numpy().any()


def _two_period_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return deliberately unsorted two-period inputs with different universes."""
    portfolio = pd.DataFrame(
        [
            ("2024-02-01", "2024-02-29", "Cash", 0.2, 0.01, 29),
            ("2024-01-01", "2024-01-31", "Equity", 0.7, 0.06, 31),
            ("2024-02-01", "2024-02-29", "Equity", 0.8, -0.02, 29),
            ("2024-01-01", "2024-01-31", "Bonds", 0.3, 0.02, 31),
        ],
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    benchmark = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "Bonds", 0.4, 0.03, 31),
            ("2024-02-01", "2024-02-29", "Equity", 0.7, -0.01, 29),
            ("2024-01-01", "2024-01-31", "Equity", 0.6, 0.04, 31),
            ("2024-02-01", "2024-02-29", "Cash", 0.3, 0.005, 29),
        ],
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    return portfolio, benchmark


def _geometric_frames(result: GeometricAttributionResult) -> dict[str, pd.DataFrame]:
    """Return the public geometric frames by their stable field names."""
    return {
        "period_detail": result.period_detail,
        "period_summary": result.period_summary,
        "cumulative": result.cumulative,
        "reconciliation": result.reconciliation,
    }


def test_public_results_are_deterministic_under_caller_row_order() -> None:
    """Reversing both caller frames must preserve every result value exactly."""
    portfolio, benchmark = _two_period_inputs()

    original = calculate_geometric_attribution(portfolio, benchmark)
    reordered = calculate_geometric_attribution(
        portfolio.iloc[::-1].reset_index(drop=True),
        benchmark.iloc[::-1].reset_index(drop=True),
    )

    for name, frame in _geometric_frames(original).items():
        pd.testing.assert_frame_equal(frame, _geometric_frames(reordered)[name])
    assert list(original.period_detail["identifier"]) == [
        "Bonds",
        "Equity",
        "Cash",
        "Equity",
    ]
    assert list(original.period_summary["thru_date"]) == [
        pd.Timestamp("2024-01-31"),
        pd.Timestamp("2024-02-29"),
    ]


@pytest.mark.parametrize(
    ("frame_name", "column"),
    (
        ("period_detail", "allocation_effect"),
        ("period_summary", "allocation_effect"),
        ("cumulative", "allocation_effect"),
        ("reconciliation", "actual"),
    ),
)
def test_each_returned_frame_is_independently_owned(
    frame_name: str,
    column: str,
) -> None:
    """Mutating one result frame must not affect peers or a later calculation."""
    portfolio, benchmark = _two_period_inputs()
    result = calculate_geometric_attribution(portfolio, benchmark)
    snapshots = {
        name: frame.copy(deep=True) for name, frame in _geometric_frames(result).items()
    }

    target = _geometric_frames(result)[frame_name]
    target.at[0, column] = cast(float, target.at[0, column]) + 100.0

    for name, frame in _geometric_frames(result).items():
        if name != frame_name:
            pd.testing.assert_frame_equal(frame, snapshots[name])
    fresh = calculate_geometric_attribution(portfolio, benchmark)
    for name, frame in _geometric_frames(fresh).items():
        pd.testing.assert_frame_equal(frame, snapshots[name])


def _arithmetic_frames(result: AttributionResult) -> tuple[pd.DataFrame, ...]:
    """Return every stable arithmetic result frame in public order."""
    names = tuple(
        "period_detail period_summary overall_detail cumulative reconciliation".split()
    )
    return tuple(getattr(result, name) for name in names)


def test_geometric_calculation_does_not_change_arithmetic_results() -> None:
    """The separate family must not reinterpret or retain arithmetic state.

    In the governing first period, arithmetic BF allocation for A is
    ``(60% - 50%) * (8% - 6%) = 0.2%`` and portfolio-weighted selection is 2.4%.
    Geometric A allocation instead divides the same numerator by 1.06. Running the
    geometric family between two arithmetic calls must leave every arithmetic frame
    bit-for-bit equal and preserve that intentional methodological distinction.
    """
    portfolio = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "A", 0.6, 0.12, 31),
            ("2024-01-01", "2024-01-31", "B", 0.4, 0.03, 31),
        ],
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    benchmark = pd.DataFrame(
        [
            ("2024-01-01", "2024-01-31", "A", 0.5, 0.08, 31),
            ("2024-01-01", "2024-01-31", "B", 0.5, 0.04, 31),
        ],
        columns=PREPARED_REQUIRED_COLUMNS,
    )
    before = calculate_attribution(portfolio, benchmark)

    geometric = calculate_geometric_attribution(portfolio, benchmark)
    after = calculate_attribution(portfolio, benchmark)

    for before_frame, after_frame in zip(
        _arithmetic_frames(before),
        _arithmetic_frames(after),
        strict=True,
    ):
        pd.testing.assert_frame_equal(before_frame, after_frame)
    arithmetic_a = cast(
        pd.Series,
        before.period_detail.set_index("identifier").loc["A"],
    )
    geometric_a = cast(
        pd.Series,
        geometric.period_detail.set_index("identifier").loc["A"],
    )
    assert cast(float, arithmetic_a["allocation_effect"]) == pytest.approx(0.002)
    assert cast(float, arithmetic_a["selection_effect"]) == pytest.approx(0.024)
    assert cast(float, geometric_a["allocation_effect"]) == pytest.approx(
        0.002 / 1.06
    )
