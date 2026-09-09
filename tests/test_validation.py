"""Tests for shared low-level validation behavior."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from perfattr._validation import normalize_identity, normalize_numeric


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
