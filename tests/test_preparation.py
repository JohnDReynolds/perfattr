"""Tests for source-period normalization and portfolio selection."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from perfattr import PreparationError, PreparationWarning, select_portfolio
from perfattr.preparation import _NormalizedPerformance, _normalize_performance


def _basic_source() -> pd.DataFrame:
    """Return one valid source period with two ordinary holdings."""
    return pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-01-01"],
            "thru_date": ["2024-01-31", "2024-01-31"],
            "identifier": ["A", "B"],
            "weight": [0.6, 0.4],
            "return": [0.1, -0.05],
        }
    )


def _changed_source(change: Callable[[pd.DataFrame], None]) -> pd.DataFrame:
    """Return a basic source after applying one test-specific mutation."""
    source = _basic_source()
    change(source)
    return source


def _duplicate_column_source() -> pd.DataFrame:
    """Return a source whose two weight columns have the same label."""
    return pd.DataFrame(
        [["2024-01-01", "2024-01-31", "A", 1.0, 1.0, 0.1]],
        columns=[
            "from_date",
            "thru_date",
            "identifier",
            "weight",
            "weight",
            "return",
        ],
    )


def test_returns_only_normalization_derives_contribution_and_days() -> None:
    """Returns-only input should derive auditable contribution and inclusive days."""
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 3,
            "thru_date": ["2024-01-31"] * 3,
            "identifier": [" ZERO ", "SHORT", "LONG"],
            # Signed exposures are valid because their net weight is exactly one.
            "weight": [0.0, -0.2, 1.2],
            "return": [np.nan, 0.05, 0.1],
            "portfolio_code": [" 001 "] * 3,
            "name": ["Zero", "Short", "Long"],
            "ignored": [1, 2, 3],
        }
    )
    source_before = source.copy(deep=True)

    normalized = _normalize_performance(source, "portfolio input")

    assert isinstance(normalized, _NormalizedPerformance)
    assert not normalized.contribution_was_supplied
    expected_columns = """from_date thru_date quantity_of_days identifier weight
    return contribution portfolio_code name""".split()
    assert list(normalized.frame.columns) == expected_columns
    assert list(normalized.frame["identifier"]) == ["LONG", "SHORT", "ZERO"]
    assert list(normalized.frame["portfolio_code"]) == ["001", "001", "001"]
    assert list(normalized.frame["quantity_of_days"]) == [31, 31, 31]
    # LONG contributes 1.2 * 10% = 12%; SHORT contributes -0.2 * 5% = -1%;
    # the undefined zero-weight row contributes exactly zero.
    np.testing.assert_allclose(
        normalized.frame["contribution"],
        [0.12, -0.01, 0.0],
        rtol=1e-12,
        atol=1e-12,
    )
    assert pd.isna(normalized.frame.loc[2, "return"])
    assert str(normalized.frame["identifier"].dtype) == "string"
    assert normalized.frame["weight"].dtype == np.dtype("float64")
    assert normalized.frame["quantity_of_days"].dtype == np.dtype("int64")
    pd.testing.assert_frame_equal(source, source_before)


@pytest.mark.parametrize("charge_identifier", ["FEE", "FINANCING"])
def test_authoritative_normalization_preserves_unexposed_charge(
    charge_identifier: str,
) -> None:
    """A fee or financing charge should retain contribution without exposure."""
    source = pd.DataFrame(
        {
            "from_date": ["2024-02-01", "2024-02-01"],
            "thru_date": ["2024-02-29", "2024-02-29"],
            "identifier": ["ASSET", charge_identifier],
            "weight": [1.0, 0.0],
            "return": [0.05, np.nan],
            # The 5.1% asset contribution less a 0.1% charge reconciles to 5.0%.
            "contribution": [0.051, -0.001],
        }
    )

    normalized = _normalize_performance(source, "portfolio input")

    assert normalized.contribution_was_supplied
    np.testing.assert_allclose(
        normalized.frame["contribution"],
        [0.051, -0.001],
        rtol=1e-12,
        atol=1e-12,
    )
    assert normalized.frame["contribution"].sum() == pytest.approx(0.05)
    assert pd.isna(normalized.frame.loc[1, "return"])
    assert list(normalized.frame["quantity_of_days"]) == [29, 29]


def test_normalization_accepts_date_objects_and_removes_times() -> None:
    """Accepted date-like values should become naive midnight timestamps."""
    source = _basic_source()
    source["from_date"] = [dt.date(2024, 1, 1), dt.date(2024, 1, 1)]
    source["thru_date"] = [
        pd.Timestamp("2024-01-31 15:30"),
        pd.Timestamp("2024-01-31 23:59"),
    ]

    normalized = _normalize_performance(source, "portfolio input")

    from_dates_match = normalized.frame["from_date"].eq(pd.Timestamp("2024-01-01"))
    thru_dates_match = normalized.frame["thru_date"].eq(pd.Timestamp("2024-01-31"))
    assert bool(np.asarray(from_dates_match, dtype=np.bool_).all())
    assert bool(np.asarray(thru_dates_match, dtype=np.bool_).all())
    assert list(normalized.frame["quantity_of_days"]) == [31, 31]


def test_normalization_uses_the_requested_weight_tolerance() -> None:
    """A host compatibility tolerance should affect acceptance, not source values."""
    source = _basic_source()
    source.loc[1, "weight"] = 0.400000004

    with pytest.raises(PreparationError, match="weights must sum to 1.0"):
        _normalize_performance(source, "portfolio input")

    normalized = _normalize_performance(
        source,
        "portfolio input",
        reconciliation_tolerance=5e-9,
    )

    # The accepted host value remains authoritative; tolerance never rounds it to one.
    assert normalized.frame["weight"].sum() == pytest.approx(1.000000004)


@pytest.mark.parametrize("value", [True, "1e-12", 0.0, -1.0, np.inf, np.nan])
def test_normalization_rejects_invalid_tolerances(value: Any) -> None:
    """The reconciliation tolerance should be a finite positive real number."""
    expected_error = TypeError if isinstance(value, str | bool) else PreparationError
    with pytest.raises(expected_error):
        _normalize_performance(
            _basic_source(),
            "portfolio input",
            reconciliation_tolerance=cast(float, value),
        )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        pytest.param(
            _basic_source().iloc[0:0],
            "must not be empty",
            id="empty",
        ),
        pytest.param(
            _basic_source().drop(columns="return"),
            "missing required columns: return",
            id="missing-column",
        ),
        pytest.param(
            _duplicate_column_source(),
            "duplicate column labels",
            id="duplicate-column",
        ),
    ],
)
def test_normalization_rejects_invalid_frame_shapes(
    source: pd.DataFrame,
    message: str,
) -> None:
    """Empty, incomplete, and duplicate-column schemas should fail explicitly."""
    with pytest.raises(PreparationError, match=message):
        _normalize_performance(source, "portfolio input")


def test_normalization_requires_a_dataframe() -> None:
    """The normalized boundary should reject lookalike non-DataFrame inputs."""
    with pytest.raises(TypeError, match="must be a pandas DataFrame"):
        _normalize_performance(cast(pd.DataFrame, []), "portfolio input")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        pytest.param(
            lambda frame: frame.__setitem__("identifier", ["A", "  "]),
            "identifier.*empty string",
            id="blank-identifier",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("identifier", ["A", 2]),
            "identifier.*non-null strings",
            id="non-string-identifier",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("from_date", [None, "2024-01-01"]),
            "from_date.*null",
            id="null-date",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("thru_date", ["bad", "2024-01-31"]),
            "thru_date.*invalid date",
            id="invalid-date",
        ),
        pytest.param(
            lambda frame: frame.__setitem__(
                "thru_date",
                [pd.Timestamp("2024-01-31", tz="UTC")] * 2,
            ),
            "thru_date.*timezone-naive",
            id="timezone-aware-date",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("from_date", [1, 1]),
            "from_date.*contain dates",
            id="numeric-date",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("from_date", ["2024-02-01"] * 2),
            "from_date after",
            id="reversed-period",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("weight", ["0.6", "0.4"]),
            "weight.*numbers",
            id="numeric-string",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("return", [True, False]),
            "return.*numbers",
            id="boolean-return",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("weight", [np.nan, 1.0]),
            "weight.*null",
            id="null-weight",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("weight", [np.inf, -np.inf]),
            "weight.*finite",
            id="infinite-weight",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("return", [np.inf, -0.05]),
            "return.*finite",
            id="infinite-return",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("return", [-1.0, -0.05]),
            "return.*greater than -1.0",
            id="minus-one-return",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("return", [np.nan, -0.05]),
            "nonzero weight with a null return",
            id="undefined-nonzero-weight-return",
        ),
        pytest.param(
            lambda frame: frame.__setitem__("weight", [0.7, 0.4]),
            "weights must sum to 1.0",
            id="invalid-weight-total",
        ),
    ],
)
def test_normalization_rejects_invalid_identity_date_and_financial_values(
    change: Callable[[pd.DataFrame], None],
    message: str,
) -> None:
    """Invalid source identities, periods, returns, and weights should not be guessed."""
    with pytest.raises(PreparationError, match=message):
        _normalize_performance(_changed_source(change), "portfolio input")


@pytest.mark.parametrize(
    ("source", "message"),
    [
        pytest.param(
            pd.concat([_basic_source(), _basic_source().iloc[[0]]], ignore_index=True),
            "duplicate period and identifier",
            id="duplicate-key",
        ),
        pytest.param(
            pd.DataFrame(
                {
                    "from_date": ["2024-01-01", "2024-01-02"],
                    "thru_date": ["2024-01-31", "2024-01-31"],
                    "identifier": ["A", "B"],
                    "weight": [1.0, 1.0],
                    "return": [0.1, 0.2],
                }
            ),
            "maps one thru_date to more than one source period",
            id="ambiguous-thru-date",
        ),
        pytest.param(
            pd.DataFrame(
                {
                    "from_date": ["2024-01-01", "2024-01-15"],
                    "thru_date": ["2024-01-31", "2024-02-15"],
                    "identifier": ["A", "A"],
                    "weight": [1.0, 1.0],
                    "return": [0.1, 0.2],
                }
            ),
            "overlapping source periods",
            id="overlap",
        ),
    ],
)
def test_normalization_rejects_ambiguous_period_structures(
    source: pd.DataFrame,
    message: str,
) -> None:
    """Duplicate or overlapping period structures should fail before calculation."""
    with pytest.raises(PreparationError, match=message):
        _normalize_performance(source, "portfolio input")


@pytest.mark.parametrize(
    ("weights", "contribution", "returns", "message"),
    [
        pytest.param(
            [0.6, 0.4],
            [0.06, np.nan],
            [0.1, -0.05],
            "contribution.*null",
            id="null",
        ),
        pytest.param(
            [0.6, 0.4],
            [0.06, np.inf],
            [0.1, -0.05],
            "contribution.*finite",
            id="infinite",
        ),
        pytest.param(
            [1.0, 0.0],
            [0.06, -0.02],
            [0.1, 0.0],
            "requires a null return",
            id="defined-zero-weight-return",
        ),
    ],
)
def test_authoritative_contribution_rejects_invalid_values(
    weights: list[float],
    contribution: list[float],
    returns: list[float],
    message: str,
) -> None:
    """Authoritative contribution should remain complete, finite, and coherent."""
    source = _basic_source()
    source["weight"] = weights
    source["return"] = returns
    source["contribution"] = contribution

    with pytest.raises(PreparationError, match=message):
        _normalize_performance(source, "portfolio input")


def test_normalization_rejects_nonfinite_effective_return() -> None:
    """Contribution divided by a tiny nonzero exposure must remain finite."""
    source = _basic_source()
    source["weight"] = [1e-320, 1.0]
    source["return"] = [0.0, 0.0]
    source["contribution"] = [1e308, 0.0]

    with pytest.raises(PreparationError, match="non-finite effective return"):
        _normalize_performance(source, "portfolio input")


def test_normalization_rejects_overflowed_derived_contribution() -> None:
    """Finite weights and returns must not be allowed to multiply to infinity."""
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 3,
            "thru_date": ["2024-01-31"] * 3,
            "identifier": ["LARGE", "OFFSET", "UNIT"],
            # The signed weights cancel exactly before the unit exposure is added.
            "weight": [1e308, -1e308, 1.0],
            "return": [1e308, 0.0, 0.0],
        }
    )

    with pytest.raises(PreparationError, match="derives a non-finite contribution"):
        _normalize_performance(source, "portfolio input")


def test_normalization_rejects_nonfinite_contribution_total() -> None:
    """Finite row contributions must not be allowed to overflow their period total."""
    source = _basic_source()
    # Signed weights 2 and -1 still net to one. Each effective return remains finite,
    # while adding the two 1e308 authoritative contributions overflows float64.
    source["weight"] = [2.0, -1.0]
    source["return"] = [0.0, 0.0]
    source["contribution"] = [1e308, 1e308]

    with pytest.raises(PreparationError, match="non-finite source-period contribution"):
        _normalize_performance(source, "portfolio input")


def test_normalization_requires_selection_for_multiple_portfolio_codes() -> None:
    """Normalization should prevent two portfolios from being mixed accidentally."""
    source = _basic_source()
    source["portfolio_code"] = ["PORT", "BENCH"]

    with pytest.raises(PreparationError, match="call select_portfolio first"):
        _normalize_performance(source, "portfolio input")


def test_select_portfolio_is_exact_deterministic_and_nonmutating() -> None:
    """Selection should trim identities, preserve order, and copy matching rows."""
    source = pd.DataFrame(
        {
            "portfolio_code": [" 001 ", "001", "ABC", "abc"],
            "identifier": ["B", "A", "C", "D"],
            "weight": [0.4, 0.6, 1.0, 1.0],
        },
        index=[8, 6, 4, 2],
    )
    source_before = source.copy(deep=True)

    selected = select_portfolio(source, " 001 ")

    assert list(selected["portfolio_code"]) == ["001", "001"]
    assert list(selected["identifier"]) == ["B", "A"]
    assert isinstance(selected.index, pd.RangeIndex)
    selected.loc[0, "identifier"] = "CHANGED"
    pd.testing.assert_frame_equal(source, source_before)


@pytest.mark.parametrize(
    ("source", "code", "error_type", "message"),
    [
        pytest.param(
            pd.DataFrame({"identifier": ["A"]}),
            "P",
            PreparationError,
            "missing required column",
            id="missing-column",
        ),
        pytest.param(
            pd.DataFrame({"portfolio_code": [" "]}),
            "P",
            PreparationError,
            "empty string",
            id="blank-source-code",
        ),
        pytest.param(
            pd.DataFrame({"portfolio_code": [1]}),
            "1",
            PreparationError,
            "non-null strings",
            id="non-string-source-code",
        ),
        pytest.param(
            pd.DataFrame({"portfolio_code": ["P"]}),
            "Q",
            PreparationError,
            "no performance rows",
            id="no-match",
        ),
        pytest.param(
            pd.DataFrame({"portfolio_code": ["P"]}),
            " ",
            PreparationError,
            "must not be blank",
            id="blank-request",
        ),
    ],
)
def test_select_portfolio_rejects_ambiguous_or_missing_codes(
    source: pd.DataFrame,
    code: str,
    error_type: type[Exception],
    message: str,
) -> None:
    """Selection should reject invalid identities instead of coercing or guessing."""
    with pytest.raises(error_type, match=message):
        select_portfolio(source, code)


def test_select_portfolio_rejects_non_dataframe_and_non_string_inputs() -> None:
    """Selection should enforce its DataFrame and string boundary types."""
    with pytest.raises(TypeError, match="pandas DataFrame"):
        select_portfolio(cast(pd.DataFrame, []), "P")
    with pytest.raises(TypeError, match="must be a string"):
        select_portfolio(
            pd.DataFrame({"portfolio_code": ["P"]}),
            cast(str, 1),
        )


def test_preparation_errors_and_warnings_are_public() -> None:
    """Callers should be able to catch the documented preparation diagnostics."""
    assert issubclass(PreparationError, ValueError)
    assert issubclass(PreparationWarning, RuntimeWarning)
