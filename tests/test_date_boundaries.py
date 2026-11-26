"""Public consumers of the shared date-only admission and normalization contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields
import datetime as dt
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import pytest

from perfattr import (
    AttributionError,
    AttributionResult,
    PreparationError,
    calculate_attribution,
    calculate_currency_attribution,
    calculate_geometric_attribution,
    normalize_mapping,
    prepare_attribution,
    read_performance_csv,
)


def _source(dates: pd.Series) -> pd.DataFrame:
    """Build independently dated, unit-weight rows for date-boundary tests."""
    return pd.DataFrame(
        {
            "from_date": dates,
            "thru_date": dates,
            "identifier": [f"A{index}" for index in range(len(dates))],
            "weight": [1.0] * len(dates),
            "return": [0.05] * len(dates),
            "quantity_of_days": [1] * len(dates),
        }
    )


def _invalid_date_call(
    operation: str,
    source: pd.DataFrame,
    tmp_path: Path,
) -> tuple[Callable[[], object], tuple[pd.DataFrame, ...]]:
    """Return the actual public call and its independently inspectable inputs."""
    if operation == "calculation":
        return lambda: calculate_attribution(source, source), (source,)
    if operation == "geometric":
        return lambda: calculate_geometric_attribution(source, source), (source,)
    if operation == "preparation":
        return lambda: prepare_attribution(source, source), (source,)
    if operation == "effective-mapping":
        mapping = source.loc[:, ["from_date", "thru_date", "identifier"]].copy()
        mapping["classification_identifier"] = "Risk"
        return lambda: normalize_mapping(mapping), (mapping,)
    if operation == "performance-csv":
        path = tmp_path / "performance.csv"
        source.drop(columns="quantity_of_days").to_csv(path, index=False)
        return lambda: read_performance_csv(path), ()
    market = source.loc[:, ["from_date", "thru_date"]].copy()
    market["market_identifier"] = source["identifier"]
    market["market_weight"] = 1.0
    market["local_asset_return"] = 0.05
    market["local_cash_return"] = 0.0
    currency = source.loc[:, ["from_date", "thru_date"]].copy()
    currency["currency_identifier"] = "USD"
    currency["currency_weight"] = 1.0
    currency["base_currency_cash_return"] = 0.0
    return (
        lambda: calculate_currency_attribution(
            market, market, currency, currency, base_currency="USD"
        ),
        (market, currency),
    )


@pytest.mark.parametrize(
    "operation",
    ["calculation", "geometric", "preparation", "effective-mapping",
     "performance-csv", "currency"],
)
@pytest.mark.parametrize(
    "dates",
    [
        pytest.param(pd.Series(["3000-01-01"]), id="unrepresentable-ns"),
        pytest.param(
            pd.Series([pd.Timestamp("1677-09-21 01:00")], dtype="datetime64[ns]"),
            id="unrepresentable-midnight",
        ),
        pytest.param(
            pd.Series(["2024-01-01T00:00+00:00", "2024-01-01T00:00+01:00"]),
            id="mixed-timezones",
        ),
    ],
)
def test_public_date_errors_preserve_the_owning_boundary_and_callers(
    operation: str,
    dates: pd.Series,
    tmp_path: Path,
) -> None:
    """Every distinct date consumer rejects corruption before financial work.

    The 1677 timestamp itself fits ns, but its midnight does not. A parser that
    postpones ns conversion must still translate the later failure. Mixed offsets
    exercise pandas 2.2's parser diagnostic under a strict caller warning policy.
    """
    call, inputs = _invalid_date_call(operation, _source(dates), tmp_path)
    snapshots = tuple(frame.copy(deep=True) for frame in inputs)
    file_before = {path: path.read_bytes() for path in tmp_path.iterdir()}
    error_type = (
        AttributionError if operation in {"calculation", "geometric", "currency"}
        else PreparationError
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("error", FutureWarning)
        with pytest.raises(error_type, match="date"):
            call()
        assert not caught

    for frame, snapshot in zip(inputs, snapshots, strict=True):
        pd.testing.assert_frame_equal(frame, snapshot)
    assert {path: path.read_bytes() for path in tmp_path.iterdir()} == file_before


def test_numeric_source_dates_cannot_silently_remove_a_selected_period() -> None:
    """Invalid numeric January dates must fail before February-only alignment.

    January's supplied P/B contributions are 10%/3%, February's 2%/1%. Implicit
    epoch conversion loses January and reports only February despite valid weights.
    A number has no admitted date unit, so the complete task must reject it.
    """
    portfolio = pd.DataFrame(
        {
            "from_date": pd.Series([20240101, "2024-02-01"], dtype=object),
            "thru_date": pd.Series([20240131, "2024-02-29"], dtype=object),
            "identifier": ["A", "A"],
            "weight": [1.0, 1.0],
            "return": [0.10, 0.02],
            "contribution": [0.10, 0.02],
        }
    )
    benchmark = portfolio.copy(deep=True)
    benchmark["from_date"] = ["2024-01-01", "2024-02-01"]
    benchmark["thru_date"] = ["2024-01-31", "2024-02-29"]
    benchmark["return"] = [0.03, 0.01]
    benchmark["contribution"] = [0.03, 0.01]
    snapshots = (portfolio.copy(deep=True), benchmark.copy(deep=True))

    with pytest.raises(PreparationError, match="portfolio input.*from_date.*dates"):
        prepare_attribution(portfolio, benchmark)

    pd.testing.assert_frame_equal(portfolio, snapshots[0])
    pd.testing.assert_frame_equal(benchmark, snapshots[1])


@pytest.mark.parametrize("bound", ["3000-01-01", "1677-09-21", "NaT"])
def test_date_window_errors_do_not_escape_preparation(bound: str) -> None:
    """Optional date-window bounds obey the same valid, representable-date rule."""
    source = _source(pd.Series(["2024-01-01"]))
    with pytest.raises(PreparationError, match="date window.*from_date"):
        prepare_attribution(source, source, from_date=bound)


@pytest.mark.parametrize("calendar_date", [dt.date(1677, 9, 22), dt.date(2262, 4, 11)])
def test_valid_boundary_dates_preserve_the_complete_financial_result(
    calendar_date: dt.date,
) -> None:
    """Neighboring valid midnights preserve every result, including a zero-weight fee.

    P contributes .051 - .001 = .05, independently of its supplied .10 asset return;
    B contributes .03. One-period selection is .021 - .001 = .02, allocation is zero.
    Replacing a one-day calendar label cannot change any financial or audit value.
    """
    portfolio = pd.DataFrame(
        {
            "from_date": pd.Series([calendar_date, calendar_date], dtype=object),
            "thru_date": pd.Series([calendar_date, calendar_date], dtype=object),
            "identifier": ["A", "FEE"],
            "weight": [1.0, 0.0],
            "return": [0.10, np.nan],
            "contribution": [0.051, -0.001],
            "quantity_of_days": [1, 1],
        }
    )
    benchmark = portfolio.iloc[[0]].copy(deep=True)
    benchmark["return"] = 0.03
    benchmark["contribution"] = 0.03
    snapshots = (portfolio.copy(deep=True), benchmark.copy(deep=True))
    ordinary = [frame.copy(deep=True) for frame in (portfolio, benchmark)]
    for frame in ordinary:
        frame["from_date"] = "2024-01-01"
        frame["thru_date"] = "2024-01-01"
    expected = calculate_attribution(*ordinary)
    for field in fields(AttributionResult):
        frame = getattr(expected, field.name)
        if not isinstance(frame, pd.DataFrame):
            continue
        for column in ("from_date", "thru_date"):
            frame[column] = pd.Series(
                [calendar_date] * len(frame), dtype="datetime64[ns]", index=frame.index
            )

    prepared = prepare_attribution(portfolio, benchmark)
    result = calculate_attribution(prepared.portfolio, prepared.benchmark)

    for field in fields(AttributionResult):
        actual_frame = getattr(result, field.name)
        expected_frame = getattr(expected, field.name)
        if isinstance(actual_frame, pd.DataFrame):
            pd.testing.assert_frame_equal(actual_frame, expected_frame)
        else:
            assert actual_frame == expected_frame
    np.testing.assert_allclose(
        result.period_summary[["portfolio_return", "benchmark_return", "active_return"]],
        [[0.05, 0.03, 0.02]], rtol=1e-12, atol=1e-12,
    )
    fee = result.period_detail.loc[result.period_detail["identifier"] == "FEE"].iloc[0]
    assert pd.isna(fee["portfolio_return"])
    assert fee["portfolio_contribution"] == -0.001
    assert prepared.reconciliation["passed"].all()
    pd.testing.assert_frame_equal(portfolio, snapshots[0])
    pd.testing.assert_frame_equal(benchmark, snapshots[1])
