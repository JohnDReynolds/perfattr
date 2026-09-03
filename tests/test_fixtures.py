"""Validate the independent attribution fixture data."""

from __future__ import annotations

import math
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt
import pandas as pd


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_FIXTURE_NAMES = (
    "single_period_derived",
    "single_period_authoritative",
    "multi_period_linking",
    "linking_boundaries",
)
_EXPECTED_DETAIL_COLUMNS = """
from_date thru_date quantity_of_days identifier portfolio_weight portfolio_return
portfolio_contribution benchmark_weight benchmark_return benchmark_contribution
active_weight active_return active_contribution allocation_effect selection_effect
total_effect linked_portfolio_contribution linked_benchmark_contribution
linked_active_contribution linked_allocation_effect linked_selection_effect
linked_total_effect
""".split()
_TOLERANCE = 1e-12


def _assert_close(actual: float, expected: float) -> None:
    """Assert the specification's relative and absolute tolerance."""
    assert math.isclose(actual, expected, rel_tol=_TOLERANCE, abs_tol=_TOLERANCE)


def _smoothing(return_value: float) -> float:
    """Evaluate the logarithmic contribution-smoothing function."""
    if return_value == 0.0:
        return 1.0
    return math.log1p(return_value) / return_value


def _carino(portfolio_return: float, benchmark_return: float) -> float:
    """Evaluate the Carino coefficient, including its equal-return limit."""
    if portfolio_return == benchmark_return:
        return 1.0 / (1.0 + portfolio_return)
    return (
        math.log1p(portfolio_return) - math.log1p(benchmark_return)
    ) / (portfolio_return - benchmark_return)


def _read_case(case_name: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read one fixture's portfolio, benchmark, and expected detail."""
    case_path = _FIXTURE_ROOT / case_name
    portfolio = pd.read_csv(case_path / "portfolio.csv")
    benchmark = pd.read_csv(case_path / "benchmark.csv")
    detail = pd.read_csv(case_path / "expected_period_detail.csv")
    return portfolio, benchmark, detail


def _float_array(frame: pd.DataFrame, column: str) -> npt.NDArray[np.float64]:
    """Return one fixture column as a typed float64 array."""
    return np.asarray(frame[column], dtype=np.float64)


def _column_sum(frame: pd.DataFrame, column: str) -> float:
    """Return a fixture column's sum as an ordinary float."""
    return float(_float_array(frame, column).sum())


def test_fixture_files_have_stable_shapes_and_cover_the_roadmap_cases() -> None:
    """Fixture inputs should be readable and exercise every promised edge case."""
    for case_name in _FIXTURE_NAMES:
        portfolio, benchmark, detail = _read_case(case_name)
        assert list(detail.columns) == _EXPECTED_DETAIL_COLUMNS
        assert not portfolio.empty
        assert not benchmark.empty
        assert not detail.empty

    portfolio, benchmark, _ = _read_case("single_period_derived")
    assert (portfolio["weight"] < 0.0).any()
    assert ((portfolio["weight"] == 0.0) & portfolio["return"].isna()).any()
    assert set(portfolio["identifier"]) != set(benchmark["identifier"])

    portfolio, benchmark, _ = _read_case("single_period_authoritative")
    assert "contribution" in portfolio.columns
    assert "contribution" not in benchmark.columns
    assert (
        (portfolio["weight"] == 0.0)
        & portfolio["return"].isna()
        & (portfolio["contribution"] != 0.0)
    ).any()

    portfolio, benchmark, _ = _read_case("linking_boundaries")
    assert portfolio["thru_date"].nunique() > 1
    assert portfolio["return"].min() < -0.99999
    assert benchmark["return"].min() < -0.99999


def test_expected_period_detail_obeys_single_period_identities() -> None:
    """Literal expected rows should satisfy the specified effect identities."""
    for case_name in _FIXTURE_NAMES:
        _, _, detail = _read_case(case_name)
        periods = detail.groupby(["from_date", "thru_date"], sort=False)

        for _, period in periods:
            portfolio_return = _column_sum(period, "portfolio_contribution")
            benchmark_return = _column_sum(period, "benchmark_contribution")
            _assert_close(_column_sum(period, "portfolio_weight"), 1.0)
            _assert_close(_column_sum(period, "benchmark_weight"), 1.0)

            active_weight = _float_array(period, "portfolio_weight") - _float_array(
                period, "benchmark_weight"
            )
            active_contribution = _float_array(
                period, "portfolio_contribution"
            ) - _float_array(period, "benchmark_contribution")
            benchmark_group_return = _float_array(period, "benchmark_return")
            allocation = np.where(
                np.isnan(benchmark_group_return),
                0.0,
                active_weight * (benchmark_group_return - benchmark_return),
            )
            total = active_contribution - active_weight * benchmark_return
            selection = total - allocation

            np.testing.assert_allclose(
                _float_array(period, "active_weight"),
                active_weight,
                rtol=_TOLERANCE,
                atol=_TOLERANCE,
            )
            np.testing.assert_allclose(
                _float_array(period, "active_contribution"),
                active_contribution,
                rtol=_TOLERANCE,
                atol=_TOLERANCE,
            )
            np.testing.assert_allclose(
                _float_array(period, "allocation_effect"),
                allocation,
                rtol=_TOLERANCE,
                atol=_TOLERANCE,
            )
            np.testing.assert_allclose(
                _float_array(period, "selection_effect"),
                selection,
                rtol=_TOLERANCE,
                atol=_TOLERANCE,
            )
            np.testing.assert_allclose(
                _float_array(period, "total_effect"),
                total,
                rtol=_TOLERANCE,
                atol=_TOLERANCE,
            )

            _assert_close(
                _column_sum(period, "total_effect"),
                portfolio_return - benchmark_return,
            )


def _read_horizon(case_name: str, detail: pd.DataFrame) -> pd.DataFrame:
    """Read multi-period coefficients or supply identity coefficients."""
    horizon_path = _FIXTURE_ROOT / case_name / "expected_horizon.csv"
    if horizon_path.exists():
        return pd.read_csv(horizon_path)

    return pd.DataFrame(
        {
            "from_date": [detail.at[0, "from_date"]],
            "thru_date": [detail.at[0, "thru_date"]],
            "portfolio_period_return": [
                _column_sum(detail, "portfolio_contribution")
            ],
            "benchmark_period_return": [
                _column_sum(detail, "benchmark_contribution")
            ],
            "portfolio_linking_coefficient": [1.0],
            "benchmark_linking_coefficient": [1.0],
            "active_effect_linking_coefficient": [1.0],
        }
    )


def _compound(values: npt.NDArray[np.float64]) -> float:
    """Compound an array of decimal period returns."""
    return math.prod(1.0 + float(value) for value in values) - 1.0


def _expected_linking_coefficients(
    portfolio_period_return: float,
    benchmark_period_return: float,
    portfolio_horizon_return: float,
    benchmark_horizon_return: float,
) -> tuple[float, float, float]:
    """Evaluate the three specified linking coefficients for one period."""
    portfolio_coefficient = _smoothing(portfolio_period_return) / _smoothing(
        portfolio_horizon_return
    )
    benchmark_coefficient = _smoothing(benchmark_period_return) / _smoothing(
        benchmark_horizon_return
    )
    active_coefficient = _carino(
        portfolio_period_return, benchmark_period_return
    ) / _carino(portfolio_horizon_return, benchmark_horizon_return)
    return portfolio_coefficient, benchmark_coefficient, active_coefficient


def _assert_linked_rows(
    rows: pd.DataFrame,
    portfolio_coefficient: float,
    benchmark_coefficient: float,
    active_coefficient: float,
) -> None:
    """Check the linked values for one period against its coefficients."""
    np.testing.assert_allclose(
        _float_array(rows, "linked_portfolio_contribution"),
        _float_array(rows, "portfolio_contribution") * portfolio_coefficient,
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    np.testing.assert_allclose(
        _float_array(rows, "linked_benchmark_contribution"),
        _float_array(rows, "benchmark_contribution") * benchmark_coefficient,
        rtol=_TOLERANCE,
        atol=_TOLERANCE,
    )
    for linked_column, simple_column in (
        ("linked_allocation_effect", "allocation_effect"),
        ("linked_selection_effect", "selection_effect"),
        ("linked_total_effect", "total_effect"),
    ):
        np.testing.assert_allclose(
            _float_array(rows, linked_column),
            _float_array(rows, simple_column) * active_coefficient,
            rtol=_TOLERANCE,
            atol=_TOLERANCE,
        )


def _assert_linked_case(detail: pd.DataFrame, horizon: pd.DataFrame) -> None:
    """Check coefficients, linked rows, and full-horizon reconciliation."""
    portfolio_period_returns = _float_array(horizon, "portfolio_period_return")
    benchmark_period_returns = _float_array(horizon, "benchmark_period_return")
    portfolio_horizon_return = _compound(portfolio_period_returns)
    benchmark_horizon_return = _compound(benchmark_period_returns)

    for index in range(len(horizon)):
        coefficients = _expected_linking_coefficients(
            float(portfolio_period_returns[index]),
            float(benchmark_period_returns[index]),
            portfolio_horizon_return,
            benchmark_horizon_return,
        )
        stored_coefficients = (
            float(_float_array(horizon, "portfolio_linking_coefficient")[index]),
            float(_float_array(horizon, "benchmark_linking_coefficient")[index]),
            float(_float_array(horizon, "active_effect_linking_coefficient")[index]),
        )
        for stored, expected in zip(stored_coefficients, coefficients, strict=True):
            _assert_close(stored, expected)

        matches = (detail["from_date"] == horizon.at[index, "from_date"]) & (
            detail["thru_date"] == horizon.at[index, "thru_date"]
        )
        matching_rows = cast(pd.DataFrame, detail.loc[matches])
        _assert_linked_rows(matching_rows, *coefficients)

    _assert_close(
        _column_sum(detail, "linked_portfolio_contribution"),
        portfolio_horizon_return,
    )
    _assert_close(
        _column_sum(detail, "linked_benchmark_contribution"),
        benchmark_horizon_return,
    )
    _assert_close(
        _column_sum(detail, "linked_total_effect"),
        portfolio_horizon_return - benchmark_horizon_return,
    )


def test_expected_linked_values_obey_horizon_formulas() -> None:
    """Literal linked values should reconcile to independently evaluated formulas."""
    for case_name in _FIXTURE_NAMES:
        _, _, detail = _read_case(case_name)
        _assert_linked_case(detail, _read_horizon(case_name, detail))
