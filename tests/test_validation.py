"""Tests for shared low-level validation behavior."""

from __future__ import annotations

import datetime as dt
import warnings

import numpy as np
import pandas as pd
import pytest

from perfattr import AttributionError, PreparationError
from perfattr._validation import normalize_dates, normalize_identity, normalize_numeric


@pytest.mark.parametrize(
    "values",
    [
        pytest.param(pd.Series([20240101]), id="integer-dtype"),
        pytest.param(pd.Series([20240101], dtype=object), id="object-integer"),
        pytest.param(pd.Series([20240101.0], dtype=object), id="object-float"),
        pytest.param(pd.Series([True], dtype=object), id="object-bool"),
        pytest.param(pd.Series([np.bool_(True)], dtype=object), id="numpy-bool"),
        pytest.param(
            pd.Series(["2024-02-01", np.int64(20240101)], dtype=object),
            id="mixed-string-numpy-integer",
        ),
        pytest.param(pd.Series(pd.Categorical([20240101])), id="numeric-category"),
        pytest.param(
            pd.Series(pd.Categorical(["2024-01-01", 20240201])),
            id="mixed-category",
        ),
    ],
)
def test_normalize_dates_rejects_numeric_values_before_epoch_conversion(
    values: pd.Series,
) -> None:
    """Storage must not give numbers an implicit epoch unit or YYYYMMDD meaning."""
    frame = pd.DataFrame({"date": values})
    before = frame.copy(deep=True)

    with pytest.raises(AttributionError, match="probe.*date"):
        normalize_dates(frame, "date", "probe", AttributionError)

    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("error_type", [AttributionError, PreparationError])
@pytest.mark.parametrize(
    "values",
    [
        pytest.param(pd.Series(["not-a-date"]), id="invalid-text"),
        pytest.param(pd.Series(["NaT"]), id="parsed-missing"),
        pytest.param(pd.Series(["1677-09-21"]), id="lower-text"),
        pytest.param(pd.Series(["3000-01-01"]), id="upper-text"),
        pytest.param(pd.Series([dt.date(9999, 12, 31)]), id="upper-python-date"),
        pytest.param(
            pd.Series([pd.Timestamp("3000-01-01")], dtype="datetime64[us]"),
            id="upper-microseconds",
        ),
        pytest.param(
            pd.Series([pd.Timestamp("1677-09-21 01:00")], dtype="datetime64[ns]"),
            id="midnight-underflow",
        ),
    ],
)
def test_normalize_dates_translates_all_invalid_date_stages(
    values: pd.Series,
    error_type: type[ValueError],
) -> None:
    """Parsing, missing results, midnight and ns conversion use the owning error.

    Gregorian 1677-09-21 midnight is -9223372800000000000 ns from 1970,
    below -2**63. Its representable 01:00 timestamp cannot have an ns midnight;
    wrapping to a date in 2262 would change the reporting period.
    """
    frame = pd.DataFrame({"date": values})
    before = frame.copy(deep=True)

    with pytest.raises(error_type, match="probe.*date"):
        normalize_dates(frame, "date", "probe", error_type)

    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "values",
    [
        pytest.param(
            pd.Series(["2024-01-01T00:00+00:00", "2024-01-01T00:00+01:00"]),
            id="mixed-offsets",
        ),
        pytest.param(
            pd.Series([dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)]),
            id="aware-dtype",
        ),
        pytest.param(
            pd.Series(["2024-01-01", "2024-01-02T00:00+01:00"]),
            id="mixed-naive-aware",
        ),
    ],
)
def test_normalize_dates_rejects_timezones_without_parser_warning(
    values: pd.Series,
    strict: bool,
) -> None:
    """Unsupported zones remain domain errors under ordinary and strict callers."""
    frame = pd.DataFrame({"date": values})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if strict:
            warnings.simplefilter("error", FutureWarning)
        filters_before = list(warnings.filters)

        with pytest.raises(PreparationError, match="probe.*date"):
            normalize_dates(frame, "date", "probe", PreparationError)

        assert warnings.filters == filters_before
        assert not caught


@pytest.mark.parametrize(
    ("values", "calendar_dates"),
    [
        pytest.param(
            pd.Series(["2024-01-01 13:00", "February 2, 2024"], dtype=object),
            [(2024, 1, 1), (2024, 2, 2)],
            id="mixed-text-formats",
        ),
        pytest.param(
            pd.Series(
                [dt.date(2024, 1, 1), dt.datetime(2024, 2, 2, 13),
                 np.datetime64("2024-03-03T23:59:59.999999999")],
                dtype=object,
            ),
            [(2024, 1, 1), (2024, 2, 2), (2024, 3, 3)],
            id="mixed-date-scalars",
        ),
        pytest.param(
            pd.Series(pd.Categorical(["2024-01-01"], categories=["2024-01-01", 7])),
            [(2024, 1, 1)],
            id="unused-numeric-category",
        ),
        *[
            pytest.param(
                pd.Series([pd.Timestamp("2024-01-01 23:59:59")], dtype=f"datetime64[{unit}]"),
                [(2024, 1, 1)],
                id=unit,
            )
            for unit in ("s", "ms", "us", "ns")
        ],
        pytest.param(
            pd.Series(["1677-09-22", "2262-04-11"]),
            [(1677, 9, 22), (2262, 4, 11)],
            id="valid-midnight-neighbors",
        ),
        pytest.param(
            pd.Series([pd.Timestamp("2262-04-11 23:59:59")], dtype="datetime64[us]"),
            [(2262, 4, 11)],
            id="normalize-before-ns-conversion",
        ),
        pytest.param(pd.Series([], dtype=object), [], id="empty-object"),
        pytest.param(pd.Series([], dtype="string[python]"), [], id="empty-string"),
    ],
)
def test_normalize_dates_preserves_admitted_calendar_and_series_ownership(
    values: pd.Series,
    calendar_dates: list[tuple[int, int, int]],
) -> None:
    """Date-only conversion keeps labels, ns midnight, parser formats and caller data.

    The upper microsecond timestamp is later than the largest ns timestamp, but its
    midnight fits. Converting to ns before discarding the time would reject it.
    """
    frame = pd.DataFrame({"date": values})
    frame.index = pd.Index([7 - index // 2 for index in range(len(frame))], name="row")
    before = frame.copy(deep=True)
    expected = pd.Series(
        [dt.datetime(*parts) for parts in calendar_dates],
        index=frame.index.copy(deep=True),
        dtype="datetime64[ns]",
        name="date",
    )

    normalized = normalize_dates(frame, "date", "probe", AttributionError)

    pd.testing.assert_series_equal(normalized, expected)
    if not normalized.empty:
        normalized.iloc[0] = pd.Timestamp("2000-01-01")
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize(
    "values",
    [
        pytest.param(pd.Series([" 001 ", "A"], dtype=object), id="object"),
        pytest.param(
            pd.Series([" 001 ", "A"], dtype="string[python]"),
            id="nullable-string",
        ),
        pytest.param(
            pd.Series(pd.Categorical([" 001 ", "A"])),
            id="string-categorical",
        ),
        pytest.param(
            pd.Series(pd.Categorical([" 001 "], categories=[" 001 ", 7])),
            id="string-observation-with-unused-numeric-category",
        ),
        pytest.param(
            pd.Series([np.str_(" 001 "), np.str_("A")], dtype=object),
            id="numpy-strings",
        ),
    ],
)
def test_normalize_identity_accepts_observed_strings(values: pd.Series) -> None:
    """Every observed Python-compatible string should be trimmed without coercion."""
    frame = pd.DataFrame({"identity": values})
    before = frame.copy(deep=True)

    normalized = normalize_identity(frame, "identity", "test input", ValueError)

    expected_values = ["001", "A"] if len(values) == 2 else ["001"]
    expected = pd.Series(expected_values, dtype="string[python]", name="identity")
    pd.testing.assert_series_equal(normalized, expected)
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("dtype", [object, "int64", "float64", "bool"])
def test_normalize_identity_accepts_empty_series_of_any_dtype(
    dtype: type[object] | str,
) -> None:
    """An empty identity column has no non-string value to reject."""
    frame = pd.DataFrame({"identity": pd.Series(dtype=dtype)})

    normalized = normalize_identity(frame, "identity", "test input", ValueError)

    expected = pd.Series(dtype="string[python]", name="identity")
    pd.testing.assert_series_equal(normalized, expected)


@pytest.mark.parametrize(
    "values",
    [
        pytest.param(pd.Series(["A", 7], dtype=object), id="mixed-numeric"),
        pytest.param(pd.Series([b"A"], dtype=object), id="bytes"),
        pytest.param(pd.Series([True], dtype=object), id="boolean"),
        pytest.param(pd.Series([pd.Timestamp("2024-01-01")]), id="datetime"),
        pytest.param(
            pd.Series(pd.Categorical(["A", 7])),
            id="mixed-categorical",
        ),
        pytest.param(
            pd.Series(["A", pd.NA], dtype="string[python]"),
            id="nullable-string-with-null",
        ),
        pytest.param(pd.Series(["A", None], dtype=object), id="object-with-null"),
    ],
)
def test_normalize_identity_rejects_non_strings_and_nulls(values: pd.Series) -> None:
    """Inference must retain the former element-wise rejection contract."""
    frame = pd.DataFrame({"identity": values})

    with pytest.raises(ValueError, match="must contain non-null strings"):
        normalize_identity(frame, "identity", "test input", ValueError)


def test_normalize_identity_rejects_blank_string_after_trimming() -> None:
    """The faster type check must not bypass post-trim blank validation."""
    frame = pd.DataFrame({"identity": ["A", "   "]})

    with pytest.raises(ValueError, match="contains an empty string"):
        normalize_identity(frame, "identity", "test input", ValueError)


def test_normalize_numeric_rejects_complex_values_without_discarding_data() -> None:
    """Financial boundaries must not silently discard an imaginary component.

    Converting ``1 + 2j`` to ``float64`` retains only one and emits a warning. A
    financial value is real-valued, so validation must reject the complex dtype before
    conversion rather than changing the caller's number.
    """
    frame = pd.DataFrame({"weight": pd.Series([1.0 + 2.0j], dtype="complex128")})

    with pytest.raises(ValueError, match="numbers.*real, not complex"):
        normalize_numeric(
            frame,
            "weight",
            "test input",
            ValueError,
            nullable=False,
        )
