"""Validate mutable attribution results before hierarchical roll-up."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from perfattr._exceptions import AttributionError
from perfattr._reconciliation import _validate_result_values
from perfattr._schemas import (
    CUMULATIVE_COLUMNS,
    OVERALL_DETAIL_COLUMNS,
    OVERALL_RECONCILIATION_CHECKS,
    PERIOD_DETAIL_COLUMNS,
    PERIOD_RECONCILIATION_CHECKS,
    PERIOD_SUMMARY_COLUMNS,
    RECONCILIATION_COLUMNS,
    THREE_EFFECT_CUMULATIVE_COLUMNS,
    THREE_EFFECT_OVERALL_DETAIL_COLUMNS,
    THREE_EFFECT_OVERALL_RECONCILIATION_CHECKS,
    THREE_EFFECT_PERIOD_DETAIL_COLUMNS,
    THREE_EFFECT_PERIOD_RECONCILIATION_CHECKS,
    THREE_EFFECT_PERIOD_SUMMARY_COLUMNS,
)
from perfattr._validation import float_array as _float_array
from perfattr._validation import is_close as _is_close
from perfattr.attribution import AttributionResult
from perfattr.method import (
    AttributionMethod,
    EffectLinkingMethod,
    uses_explicit_interaction,
)

_DATE_COLUMNS = frozenset({"from_date", "thru_date"})
_STRING_COLUMNS = frozenset({"identifier", "scope", "check"})
_NULLABLE_RESULT_COLUMNS = frozenset(
    {"portfolio_return", "benchmark_return", "active_return"}
)


def _source_result_schemas(
    method: AttributionMethod,
) -> dict[str, tuple[str, ...]]:
    """Return every exact released frame schema for one attribution method."""
    if uses_explicit_interaction(method):
        return {
            "period_detail": THREE_EFFECT_PERIOD_DETAIL_COLUMNS,
            "period_summary": THREE_EFFECT_PERIOD_SUMMARY_COLUMNS,
            "overall_detail": THREE_EFFECT_OVERALL_DETAIL_COLUMNS,
            "cumulative": THREE_EFFECT_CUMULATIVE_COLUMNS,
            "reconciliation": RECONCILIATION_COLUMNS,
        }
    return {
        "period_detail": PERIOD_DETAIL_COLUMNS,
        "period_summary": PERIOD_SUMMARY_COLUMNS,
        "overall_detail": OVERALL_DETAIL_COLUMNS,
        "cumulative": CUMULATIVE_COLUMNS,
        "reconciliation": RECONCILIATION_COLUMNS,
    }


def _has_canonical_dtype(column: str, values: pd.Series) -> bool:
    """Return whether one released result column has its exact canonical dtype."""
    if column in _DATE_COLUMNS:
        return values.dtype == np.dtype("datetime64[ns]")
    if column in _STRING_COLUMNS:
        dtype = values.dtype
        return isinstance(dtype, pd.StringDtype) and dtype.storage == "python"
    if column == "quantity_of_days":
        return values.dtype == np.dtype("int64")
    if column == "passed":
        return values.dtype == np.dtype("bool")
    return values.dtype == np.dtype("float64")


def _validate_source_frame(
    name: str,
    frame: pd.DataFrame,
    columns: tuple[str, ...],
) -> None:
    """Require one source result frame to retain its released contract."""
    context = f"source result {name}"
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{context} must be a pandas DataFrame")
    if tuple(frame.columns) != columns:
        raise AttributionError(f"{context} must use the exact released column order")
    if not (
        isinstance(frame.index, pd.RangeIndex)
        and frame.index.start == 0
        and frame.index.stop == len(frame)
        and frame.index.step == 1
    ):
        raise AttributionError(f"{context} must use a zero-based RangeIndex")

    nullable_columns = tuple(
        column for column in columns if column in _NULLABLE_RESULT_COLUMNS
    )
    for column in columns:
        values = cast(pd.Series, frame[column])
        if not _has_canonical_dtype(column, values):
            raise AttributionError(
                f"{context} column {column!r} does not use its released dtype"
            )
        if column not in nullable_columns and bool(values.isna().any()):
            raise AttributionError(f"{context} column {column!r} contains null values")
        if column in _STRING_COLUMNS:
            stripped = cast(pd.Series, values.str.strip())
            if bool(stripped.eq("").any()) or not stripped.equals(values):
                raise AttributionError(
                    f"{context} column {column!r} contains a noncanonical identity"
                )
    _validate_result_values(name, frame, nullable_columns)


def _validate_sorted_keys(
    name: str,
    frame: pd.DataFrame,
    keys: tuple[str, ...],
) -> None:
    """Require unique keys in the released deterministic order."""
    if bool(frame.duplicated(list(keys)).any()):
        raise AttributionError(f"source result {name} contains duplicate keys")
    expected = frame.sort_values(list(keys), kind="stable").reset_index(drop=True)
    if not frame.loc[:, list(keys)].equals(expected.loc[:, list(keys)]):
        raise AttributionError(f"source result {name} is not deterministically sorted")


def effective_returns(
    weights: np.ndarray,
    contributions: np.ndarray,
) -> np.ndarray:
    """Derive effective returns under the authoritative-contribution rule."""
    returns = np.zeros(len(weights), dtype=np.float64)
    nonzero_weights = weights != 0.0
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        np.divide(
            contributions,
            weights,
            out=returns,
            where=nonzero_weights,
        )
    returns[(weights == 0.0) & (contributions != 0.0)] = np.nan
    return returns


def _validate_period_return_pair(
    period_detail: pd.DataFrame,
    side: str,
    tolerance: float,
) -> None:
    """Require one side's effective returns to match weight and contribution."""
    weights = _float_array(period_detail, f"{side}_weight")
    contributions = _float_array(period_detail, f"{side}_contribution")
    actual = _float_array(period_detail, f"{side}_return")
    expected = effective_returns(weights, contributions)
    if not np.array_equal(np.isnan(actual), np.isnan(expected)):
        raise AttributionError(
            f"source result period_detail has invalid {side} return null placement"
        )
    defined = ~np.isnan(expected)
    if not _is_close(actual[defined], expected[defined], tolerance).all():
        raise AttributionError(
            f"source result period_detail has invalid {side} effective returns"
        )


def _validate_active_returns(
    name: str,
    frame: pd.DataFrame,
    tolerance: float,
) -> None:
    """Require active-return nulls and values to follow the difference rule."""
    portfolio_returns = _float_array(frame, "portfolio_return")
    benchmark_returns = _float_array(frame, "benchmark_return")
    actual = _float_array(frame, "active_return")
    expected = np.full(len(frame), np.nan, dtype=np.float64)
    defined = ~np.isnan(portfolio_returns) & ~np.isnan(benchmark_returns)
    np.subtract(
        portfolio_returns,
        benchmark_returns,
        out=expected,
        where=defined,
    )
    if not np.array_equal(np.isnan(actual), np.isnan(expected)):
        raise AttributionError(
            f"source result {name} has invalid active return null placement"
        )
    if not _is_close(actual[defined], expected[defined], tolerance).all():
        raise AttributionError(f"source result {name} has invalid active returns")


def _validate_period_structure(result: AttributionResult) -> None:
    """Require consistent source periods, day counts, dates, and identifiers."""
    detail = result.period_detail
    summary = result.period_summary
    overall = result.overall_detail
    cumulative = result.cumulative
    detail_periods = detail.loc[
        :, ["from_date", "thru_date", "quantity_of_days"]
    ].drop_duplicates(ignore_index=True)
    detail_periods = detail_periods.sort_values(
        ["thru_date", "from_date"], kind="stable"
    ).reset_index(drop=True)
    if bool(detail_periods.duplicated(["from_date", "thru_date"]).any()):
        raise AttributionError(
            "source result period_detail has inconsistent quantity_of_days"
        )
    summary_periods = summary.loc[
        :, ["from_date", "thru_date", "quantity_of_days"]
    ]
    if not detail_periods.equals(summary_periods):
        raise AttributionError(
            "source result period_detail and period_summary periods do not match"
        )
    if not detail_periods.loc[:, ["from_date", "thru_date"]].equals(
        cumulative.loc[:, ["from_date", "thru_date"]]
    ):
        raise AttributionError(
            "source result period_detail and cumulative periods do not match"
        )

    expected_horizon = (
        cast(pd.Timestamp, detail_periods.iloc[0]["from_date"]),
        cast(pd.Timestamp, detail_periods.iloc[-1]["thru_date"]),
    )
    horizon_keys = overall.loc[:, ["from_date", "thru_date"]].drop_duplicates()
    if len(horizon_keys) != 1 or tuple(horizon_keys.iloc[0]) != expected_horizon:
        raise AttributionError("source result overall_detail horizon dates do not match")

    detail_identifiers = frozenset(str(value) for value in detail["identifier"])
    overall_identifiers = frozenset(str(value) for value in overall["identifier"])
    if detail_identifiers != overall_identifiers:
        raise AttributionError(
            "source result period_detail and overall_detail identifiers do not match"
        )


def _expected_reconciliation_keys(
    result: AttributionResult,
) -> pd.DataFrame:
    """Build released scope, date, and check order without recalculating values."""
    period_checks = PERIOD_RECONCILIATION_CHECKS
    overall_checks = OVERALL_RECONCILIATION_CHECKS
    if uses_explicit_interaction(result.method):
        period_checks = THREE_EFFECT_PERIOD_RECONCILIATION_CHECKS
        overall_checks = THREE_EFFECT_OVERALL_RECONCILIATION_CHECKS

    rows: list[tuple[str, pd.Timestamp, pd.Timestamp, str]] = []
    for from_date, thru_date in result.period_summary[
        ["from_date", "thru_date"]
    ].itertuples(index=False, name=None):
        rows.extend(
            ("period", from_date, thru_date, check) for check in period_checks
        )
    horizon = result.overall_detail.iloc[0]
    rows.extend(
        ("overall", horizon["from_date"], horizon["thru_date"], check)
        for check in overall_checks
    )
    expected = pd.DataFrame(
        rows,
        columns=("scope", "from_date", "thru_date", "check"),
    )
    expected["scope"] = expected["scope"].astype("string[python]")
    expected["from_date"] = expected["from_date"].astype("datetime64[ns]")
    expected["thru_date"] = expected["thru_date"].astype("datetime64[ns]")
    expected["check"] = expected["check"].astype("string[python]")
    return expected


def validate_source_result(
    result: AttributionResult,
    tolerance: float,
) -> frozenset[str]:
    """Validate the released result boundary needed by hierarchical roll-up.

    Args:
        result: Candidate caller-owned attribution result.
        tolerance: Positive finite comparison tolerance already validated publicly.

    Returns:
        The complete canonical source leaf identifier set.

    Raises:
        TypeError: If result metadata or a frame has the wrong dedicated type.
        AttributionError: If a mutable result frame no longer satisfies its released
            structural, numerical, or reconciliation contract.

    Notes:
        This protects the post-calculation boundary without re-running preparation,
        Brinson formulas, linking, or source reconciliation mathematics.
    """
    if not isinstance(result.method, AttributionMethod):
        raise TypeError("result.method must be an AttributionMethod")
    if not isinstance(result.effect_linking_method, EffectLinkingMethod):
        raise TypeError(
            "result.effect_linking_method must be an EffectLinkingMethod"
        )

    schemas = _source_result_schemas(result.method)
    for name, columns in schemas.items():
        _validate_source_frame(name, getattr(result, name), columns)
    if result.period_detail.empty or result.overall_detail.empty:
        raise AttributionError("source result detail frames must not be empty")

    _validate_sorted_keys(
        "period_detail",
        result.period_detail,
        ("thru_date", "from_date", "identifier"),
    )
    _validate_sorted_keys(
        "overall_detail",
        result.overall_detail,
        ("identifier",),
    )
    _validate_period_structure(result)
    _validate_period_return_pair(result.period_detail, "portfolio", tolerance)
    _validate_period_return_pair(result.period_detail, "benchmark", tolerance)
    _validate_active_returns("period_detail", result.period_detail, tolerance)
    _validate_active_returns("overall_detail", result.overall_detail, tolerance)

    passed = cast(pd.Series, result.reconciliation["passed"])
    if result.reconciliation.empty or not bool(np.asarray(passed, dtype=np.bool_).all()):
        raise AttributionError("source result reconciliation must contain only passes")
    reconciliation_keys = result.reconciliation.loc[
        :, ["scope", "from_date", "thru_date", "check"]
    ]
    if not reconciliation_keys.equals(_expected_reconciliation_keys(result)):
        raise AttributionError(
            "source result reconciliation does not use its released check order"
        )
    return frozenset(str(value) for value in result.overall_detail["identifier"])
