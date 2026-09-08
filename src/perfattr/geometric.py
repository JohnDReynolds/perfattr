"""Public boundary for geometric excess-return attribution.

The financial calculation remains deliberately guarded until Roadmap 11's
single-period formulas have independent fixtures and complete reconciliation tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import numpy.typing as npt
import pandas as pd

from perfattr._exceptions import AttributionError
from perfattr._reconciliation import _validate_result_values
from perfattr._schemas import (
    GEOMETRIC_CUMULATIVE_COLUMNS,
    GEOMETRIC_CUMULATIVE_RECONCILIATION_CHECKS,
    GEOMETRIC_PERIOD_DETAIL_COLUMNS,
    GEOMETRIC_PERIOD_RECONCILIATION_CHECKS,
    GEOMETRIC_PERIOD_SUMMARY_COLUMNS,
    GEOMETRIC_RECONCILIATION_COLUMNS,
)
from perfattr._validation import float_array as _float_array
from perfattr._validation import is_close as _is_close
from perfattr._validation import normalize_reconciliation_tolerance
from perfattr.attribution import (
    _equalize_universe,
    _normalize_input,
    _validate_matched_periods,
)


@dataclass
class GeometricAttributionResult:
    """Hold geometric attribution result frames.

    Attributes:
        period_detail: Geometric allocation and selection for each period and
            identifier.
        period_summary: Geometric return and effect-channel totals for each period.
        cumulative: Chronological compounded return and effect-channel prefixes.
        reconciliation: Passing multiplicative reconciliation evidence.

    Notes:
        Direct construction is ordinary dataclass construction and does not validate
        or copy frames. The calculator returns independently owned frames without
        mutating caller inputs.
    """

    period_detail: pd.DataFrame
    period_summary: pd.DataFrame
    cumulative: pd.DataFrame
    reconciliation: pd.DataFrame


_FloatArray = npt.NDArray[np.float64]
_INPUT_VALUE_COLUMNS = {
    "portfolio_weight": "weight_portfolio",
    "benchmark_weight": "weight_benchmark",
    "portfolio_return": "effective_return_portfolio",
    "benchmark_return": "effective_return_benchmark",
    "portfolio_contribution": "contribution_portfolio",
    "benchmark_contribution": "contribution_benchmark",
}


def _geometric_input_values(equalized: pd.DataFrame) -> dict[str, _FloatArray]:
    """Return named float64 arrays used by the geometric period calculation."""
    return {
        result_column: _float_array(equalized, source_column)
        for result_column, source_column in _INPUT_VALUE_COLUMNS.items()
    }


def _semi_notional_terms(
    equalized: pd.DataFrame,
    values: dict[str, _FloatArray],
) -> tuple[_FloatArray, _FloatArray]:
    """Calculate semi-notional contributions and benchmark residuals.

    Args:
        equalized: Normalized rows used to report an invalid period and identifier.
        values: Named normalized input arrays.

    Returns:
        Semi-notional contributions and authoritative benchmark accounting residuals.

    Raises:
        AttributionError: If a nonzero portfolio exposure has no benchmark effective
            return.
    """
    benchmark_return = values["benchmark_return"]
    benchmark_return_defined = ~np.isnan(benchmark_return)
    undefined = (values["portfolio_weight"] != 0.0) & ~benchmark_return_defined
    if np.any(undefined):
        invalid = equalized.loc[undefined].iloc[0]
        raise AttributionError(
            "geometric semi-notional return is undefined for nonzero portfolio "
            f"weight at {invalid['thru_date']:%Y-%m-%d} identifier "
            f"{invalid['identifier']!r}"
        )

    semi_notional = np.zeros(len(equalized), dtype=np.float64)
    np.multiply(
        values["portfolio_weight"],
        benchmark_return,
        out=semi_notional,
        where=benchmark_return_defined,
    )
    benchmark_modeled = np.zeros(len(equalized), dtype=np.float64)
    np.multiply(
        values["benchmark_weight"],
        benchmark_return,
        out=benchmark_modeled,
        where=benchmark_return_defined,
    )
    benchmark_residual = values["benchmark_contribution"] - benchmark_modeled
    return semi_notional, benchmark_residual


def _geometric_period_totals(
    equalized: pd.DataFrame,
    semi_notional: _FloatArray,
) -> tuple[_FloatArray, _FloatArray]:
    """Return benchmark and semi-notional totals repeated on their period rows."""
    working = equalized.assign(_semi_notional_contribution=semi_notional)
    grouped = working.groupby(
        ["from_date", "thru_date"],
        sort=False,
        observed=True,
    )
    benchmark_total = np.asarray(
        grouped["contribution_benchmark"].transform("sum"),
        dtype=np.float64,
    )
    semi_notional_total = np.asarray(
        grouped["_semi_notional_contribution"].transform("sum"),
        dtype=np.float64,
    )
    if not np.isfinite(semi_notional_total).all():
        raise AttributionError("geometric semi-notional period return must be finite")
    if np.any(semi_notional_total <= -1.0):
        raise AttributionError(
            "geometric semi-notional period return must be greater than -1.0"
        )
    return benchmark_total, semi_notional_total


def _geometric_effect_values(
    values: dict[str, _FloatArray],
    semi_notional: _FloatArray,
    benchmark_residual: _FloatArray,
    benchmark_total: _FloatArray,
    semi_notional_total: _FloatArray,
) -> dict[str, _FloatArray]:
    """Calculate active facts and the two identifier effect channels."""
    active_weight = values["portfolio_weight"] - values["benchmark_weight"]
    active_return = np.full(len(active_weight), np.nan, dtype=np.float64)
    benchmark_defined = ~np.isnan(values["benchmark_return"])
    active_return_defined = ~np.isnan(values["portfolio_return"]) & benchmark_defined
    np.subtract(
        values["portfolio_return"],
        values["benchmark_return"],
        out=active_return,
        where=active_return_defined,
    )
    allocation_numerator = -benchmark_residual
    np.add(
        allocation_numerator,
        active_weight * (values["benchmark_return"] - benchmark_total),
        out=allocation_numerator,
        where=benchmark_defined,
    )
    return {
        "active_weight": active_weight,
        "active_return": active_return,
        "active_contribution": (
            values["portfolio_contribution"] - values["benchmark_contribution"]
        ),
        "allocation_effect": allocation_numerator / (1.0 + benchmark_total),
        "selection_effect": (
            (values["portfolio_contribution"] - semi_notional)
            / (1.0 + semi_notional_total)
        ),
    }


def _build_geometric_period_detail(equalized: pd.DataFrame) -> pd.DataFrame:
    """Calculate geometric allocation and selection for equalized period rows.

    Args:
        equalized: Released normalized portfolio and benchmark rows over one common
            period-and-identifier universe.

    Returns:
        A new canonical period-detail frame containing semi-notional contributions
        and two geometric effect channels.

    Raises:
        AttributionError: If a nonzero portfolio exposure has no benchmark effective
            return, a semi-notional period wealth base is nonpositive, or a calculated
            value is non-finite.

    Notes:
        Allocation uses the geometric Brinson-Fachler expression plus the explicit
        benchmark accounting residual specified by Roadmap 11. Selection uses
        authoritative portfolio contribution and absorbs interaction.

    References:
        Bacon, Carl R. *Practical Portfolio Performance Measurement and Attribution*,
        2nd ed. Wiley, 2008, ch. 6.
    """
    values = _geometric_input_values(equalized)
    semi_notional, benchmark_residual = _semi_notional_terms(equalized, values)
    benchmark_total, semi_notional_total = _geometric_period_totals(
        equalized,
        semi_notional,
    )
    effects = _geometric_effect_values(
        values,
        semi_notional,
        benchmark_residual,
        benchmark_total,
        semi_notional_total,
    )

    detail_values: dict[str, object] = dict(values)
    detail_values.update(effects)
    detail_values.update(
        {
            "from_date": equalized["from_date"],
            "thru_date": equalized["thru_date"],
            "quantity_of_days": equalized["quantity_of_days"].astype("int64"),
            "identifier": equalized["identifier"].astype("string[python]"),
            "semi_notional_contribution": semi_notional,
            "benchmark_accounting_residual": benchmark_residual,
        }
    )
    detail = pd.DataFrame(
        detail_values,
        columns=GEOMETRIC_PERIOD_DETAIL_COLUMNS,
    ).reset_index(drop=True)
    _validate_result_values(
        "geometric period_detail",
        detail,
        ("portfolio_return", "benchmark_return", "active_return"),
    )
    return detail


def _build_geometric_period_summary(detail: pd.DataFrame) -> pd.DataFrame:
    """Aggregate identifier effects and successive-notional period returns.

    Args:
        detail: Canonical geometric identifier-period detail.

    Returns:
        One new chronological summary row per source period.

    Raises:
        AttributionError: If a calculated geometric return is non-finite.
    """
    period_keys = ["from_date", "thru_date", "quantity_of_days"]
    value_columns = [
        "portfolio_contribution",
        "benchmark_contribution",
        "semi_notional_contribution",
        "allocation_effect",
        "selection_effect",
    ]
    period_values = detail.set_index(period_keys).loc[:, value_columns]
    summary = cast(
        pd.DataFrame,
        period_values.groupby(level=period_keys, sort=False).sum(),
    ).reset_index()
    portfolio_return = _float_array(summary, "portfolio_contribution")
    benchmark_return = _float_array(summary, "benchmark_contribution")
    geometric_excess_return = (
        (1.0 + portfolio_return) / (1.0 + benchmark_return) - 1.0
    )
    summary["portfolio_return"] = portfolio_return
    summary["benchmark_return"] = benchmark_return
    summary["semi_notional_return"] = _float_array(
        summary,
        "semi_notional_contribution",
    )
    summary["geometric_excess_return"] = geometric_excess_return
    summary["total_effect"] = geometric_excess_return.copy()
    result = cast(
        pd.DataFrame,
        summary.loc[:, GEOMETRIC_PERIOD_SUMMARY_COLUMNS],
    ).reset_index(drop=True)
    _validate_result_values("geometric period_summary", result)
    return result


def _calculate_geometric_period_frames(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    reconciliation_tolerance: float = 1e-12,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize prepared inputs and calculate private geometric period frames.

    Args:
        portfolio: Prepared portfolio performance rows.
        benchmark: Prepared benchmark performance rows.
        reconciliation_tolerance: Validated input weight-total tolerance.

    Returns:
        Independently owned period-detail and period-summary frames.

    Notes:
        This private vertical slice supports independent Step 3 verification while
        the public function remains guarded pending cumulative reconciliation.
    """
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        normalized_portfolio, normalized_benchmark = tuple(
            _normalize_input(frame, side)
            for frame, side in ((portfolio, "portfolio"), (benchmark, "benchmark"))
        )
        _validate_matched_periods(
            normalized_portfolio,
            normalized_benchmark,
            reconciliation_tolerance,
        )
        equalized = _equalize_universe(normalized_portfolio, normalized_benchmark)
        detail = _build_geometric_period_detail(equalized)
        summary = _build_geometric_period_summary(detail)
    return detail, summary


def _compound_prefix(returns: _FloatArray) -> _FloatArray:
    """Compound every chronological return prefix with stable log arithmetic."""
    return np.expm1(
        np.cumsum(
            np.log1p(returns),
            dtype=np.float64,
        )
    )


def _build_geometric_cumulative(summary: pd.DataFrame) -> pd.DataFrame:
    """Build chronological compounded geometric return and effect prefixes.

    Args:
        summary: Canonical geometric period totals in chronological order.

    Returns:
        One new cumulative row per source period.

    Raises:
        AttributionError: If a cumulative day count or compounded value is invalid.
    """
    period_columns = (
        "portfolio_return",
        "benchmark_return",
        "semi_notional_return",
        "allocation_effect",
        "selection_effect",
    )
    cumulative_values = {
        column: _compound_prefix(_float_array(summary, column))
        for column in period_columns
    }
    geometric_excess = (
        (1.0 + cumulative_values["portfolio_return"])
        / (1.0 + cumulative_values["benchmark_return"])
        - 1.0
    )
    cumulative_days = np.cumsum(
        np.asarray(summary["quantity_of_days"], dtype=np.int64),
        dtype=np.int64,
    )
    if np.any(cumulative_days <= 0):
        raise AttributionError(
            "geometric cumulative quantity_of_days must remain positive"
        )
    result_values: dict[str, object] = dict(cumulative_values)
    result_values.update(
        {
            "from_date": summary.at[0, "from_date"],
            "thru_date": summary["thru_date"],
            "quantity_of_days": cumulative_days,
            "geometric_excess_return": geometric_excess,
            "total_effect": geometric_excess.copy(),
        }
    )
    cumulative = pd.DataFrame(
        result_values,
        columns=GEOMETRIC_CUMULATIVE_COLUMNS,
    ).reset_index(drop=True)
    _validate_result_values("geometric cumulative", cumulative)
    return cumulative


def _repeat_reconciliation_keys(
    frame: pd.DataFrame,
    scope: str,
    checks: tuple[str, ...],
) -> dict[str, object]:
    """Repeat frame period keys for one ordered set of reconciliation checks."""
    check_count = len(checks)
    return {
        "scope": scope,
        "from_date": np.repeat(
            np.asarray(frame["from_date"], dtype="datetime64[ns]"),
            check_count,
        ),
        "thru_date": np.repeat(
            np.asarray(frame["thru_date"], dtype="datetime64[ns]"),
            check_count,
        ),
        "check": np.tile(checks, len(frame)),
    }


def _build_geometric_period_reconciliation(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    """Build unfinished identifier and successive-notional period checks."""
    period_keys = ["from_date", "thru_date"]
    effect_columns = ["allocation_effect", "selection_effect"]
    period_values = detail.set_index(period_keys).loc[:, effect_columns]
    period_totals = cast(
        pd.DataFrame,
        period_values.groupby(level=period_keys, sort=False).sum(),
    ).reset_index()
    portfolio = _float_array(summary, "portfolio_return")
    benchmark = _float_array(summary, "benchmark_return")
    semi_notional = _float_array(summary, "semi_notional_return")
    allocation = _float_array(summary, "allocation_effect")
    selection = _float_array(summary, "selection_effect")
    total = _float_array(summary, "total_effect")
    actual = np.column_stack(
        (
            _float_array(period_totals, "allocation_effect"),
            _float_array(period_totals, "selection_effect"),
            allocation,
            selection,
            total,
            (1.0 + allocation) * (1.0 + selection) - 1.0,
        )
    )
    expected = np.column_stack(
        (
            allocation,
            selection,
            (1.0 + semi_notional) / (1.0 + benchmark) - 1.0,
            (1.0 + portfolio) / (1.0 + semi_notional) - 1.0,
            (1.0 + portfolio) / (1.0 + benchmark) - 1.0,
            total,
        )
    )
    return pd.DataFrame(
        {
            **_repeat_reconciliation_keys(
                summary,
                "period",
                GEOMETRIC_PERIOD_RECONCILIATION_CHECKS,
            ),
            "actual": actual.ravel(),
            "expected": expected.ravel(),
        }
    )


def _direct_compound_prefix(returns: _FloatArray) -> _FloatArray:
    """Compound prefixes directly for independent production reconciliation."""
    return np.cumprod(1.0 + returns, dtype=np.float64) - 1.0


def _build_geometric_cumulative_reconciliation(
    summary: pd.DataFrame,
    cumulative: pd.DataFrame,
) -> pd.DataFrame:
    """Build unfinished cumulative compounding and wealth-ratio checks."""
    columns = (
        "portfolio_return",
        "benchmark_return",
        "semi_notional_return",
        "allocation_effect",
        "selection_effect",
    )
    values = {column: _float_array(cumulative, column) for column in columns}
    total = _float_array(cumulative, "total_effect")
    actual = np.column_stack(
        (
            *(values[column] for column in columns),
            total,
            values["allocation_effect"],
            values["selection_effect"],
            (1.0 + values["allocation_effect"])
            * (1.0 + values["selection_effect"])
            - 1.0,
        )
    )
    expected = np.column_stack(
        (
            *(
                _direct_compound_prefix(_float_array(summary, column))
                for column in columns
            ),
            (1.0 + values["portfolio_return"])
            / (1.0 + values["benchmark_return"])
            - 1.0,
            (1.0 + values["semi_notional_return"])
            / (1.0 + values["benchmark_return"])
            - 1.0,
            (1.0 + values["portfolio_return"])
            / (1.0 + values["semi_notional_return"])
            - 1.0,
            total,
        )
    )
    return pd.DataFrame(
        {
            **_repeat_reconciliation_keys(
                cumulative,
                "cumulative",
                GEOMETRIC_CUMULATIVE_RECONCILIATION_CHECKS,
            ),
            "actual": actual.ravel(),
            "expected": expected.ravel(),
        }
    )


def _build_geometric_reconciliation(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    cumulative: pd.DataFrame,
    reconciliation_tolerance: float,
) -> pd.DataFrame:
    """Build and require passing geometric period and cumulative evidence.

    Args:
        detail: Canonical identifier-period geometric effects.
        summary: Canonical period effect-channel totals.
        cumulative: Canonical compounded-prefix totals.
        reconciliation_tolerance: Positive relative and absolute comparison tolerance.

    Returns:
        A new deterministic reconciliation frame containing only passing checks.

    Raises:
        AttributionError: If any geometric identity fails or evidence is non-finite.
    """
    reconciliation = pd.concat(
        [
            _build_geometric_period_reconciliation(detail, summary),
            _build_geometric_cumulative_reconciliation(summary, cumulative),
        ],
        ignore_index=True,
    )
    actual = _float_array(reconciliation, "actual")
    expected = _float_array(reconciliation, "expected")
    reconciliation["difference"] = np.subtract(actual, expected)
    reconciliation["tolerance"] = reconciliation_tolerance
    reconciliation["passed"] = _is_close(actual, expected, reconciliation_tolerance)
    reconciliation = cast(
        pd.DataFrame,
        reconciliation.loc[:, GEOMETRIC_RECONCILIATION_COLUMNS],
    )
    reconciliation["scope"] = reconciliation["scope"].astype("string[python]")
    reconciliation["check"] = reconciliation["check"].astype("string[python]")
    reconciliation["passed"] = reconciliation["passed"].astype("bool")
    if not np.asarray(reconciliation["passed"], dtype=np.bool_).all():
        failed = reconciliation.loc[~reconciliation["passed"]].iloc[0]
        raise AttributionError(
            "geometric reconciliation failed for "
            f"{failed['scope']} {failed['thru_date']:%Y-%m-%d} "
            f"{failed['check']}"
        )
    _validate_result_values("geometric reconciliation", reconciliation)
    return reconciliation.reset_index(drop=True)


def calculate_geometric_attribution(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    reconciliation_tolerance: float = 1e-12,
) -> GeometricAttributionResult:
    """Calculate Bacon/Burnie geometric excess-return attribution.

    Args:
        portfolio: Prepared portfolio rows satisfying the portable input contract.
        benchmark: Prepared benchmark rows for the same reporting periods.
        reconciliation_tolerance: Positive finite relative and absolute tolerance for
            geometric input validation and reconciliation evidence.

    Returns:
        Four new caller-owned frames containing identifier-period effects, period
        totals, compounded prefixes, and passing multiplicative reconciliation.

    Raises:
        TypeError: If either input is not a pandas DataFrame or the tolerance is not a
            non-boolean real number.
        AttributionError: If the tolerance, prepared financial input, calculated
            values, or geometric reconciliation violates the governing contract.

    Notes:
        Allocation and portfolio-weighted selection combine multiplicatively, with
        interaction absorbed into selection. Supplied contribution is authoritative.
        No identifier-level horizon result is created because allocating compounding
        cross-terms requires another methodology.

    References:
        Bacon, Carl R. *Practical Portfolio Performance Measurement and Attribution*,
        2nd ed. Wiley, 2008, ch. 6.
    """
    if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        portfolio,
        pd.DataFrame,
    ):
        raise TypeError("portfolio must be a pandas DataFrame")
    if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        benchmark,
        pd.DataFrame,
    ):
        raise TypeError("benchmark must be a pandas DataFrame")
    tolerance = normalize_reconciliation_tolerance(
        reconciliation_tolerance,
        AttributionError,
    )
    detail, summary = _calculate_geometric_period_frames(
        portfolio,
        benchmark,
        tolerance,
    )
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        cumulative = _build_geometric_cumulative(summary)
        reconciliation = _build_geometric_reconciliation(
            detail,
            summary,
            cumulative,
            tolerance,
        )
    return GeometricAttributionResult(
        period_detail=detail,
        period_summary=summary,
        cumulative=cumulative,
        reconciliation=reconciliation,
    )


__all__ = ["GeometricAttributionResult", "calculate_geometric_attribution"]
