"""Tests for canonical local CSV loading and classification metadata."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from perfattr import (
    PreparationError,
    prepare_attribution,
    read_classification_csv,
    read_mapping_csv,
    read_performance_csv,
    select_portfolio,
)
from perfattr._schemas import PREPARED_REQUIRED_COLUMNS
from perfattr.classification import _normalize_classification


def _write(path: Path, contents: str) -> Path:
    """Write one UTF-8 test fixture and return its path."""
    path.write_text(contents, encoding="utf-8")
    return path


def test_performance_reader_preserves_master_file_identities_and_provenance(
    tmp_path: Path,
) -> None:
    """A normalized multi-portfolio file should retain codes and leading zeroes.

    The same source-period key is valid in two portfolios because each code is a
    separate performance stream. Literal ``NA`` is an identifier, not an inferred
    missing value. The absent contribution column remains absent so later preparation
    records that contribution was derived from weights and returns.
    """
    path = _write(
        tmp_path / "performance.csv",
        "portfolio_code,from_date,thru_date,identifier,weight,return,name,ignored\n"
        "002,2024-01-01,2024-01-31,NA,1.0,0.03,Second,drop me\n"
        "001,2024-01-01,2024-01-31,0007,1.0,0.02,First,drop me\n",
    )

    performance = read_performance_csv(path)

    expected_columns = [
        *PREPARED_REQUIRED_COLUMNS[:-1],
        "portfolio_code",
        "name",
    ]
    assert list(performance.columns) == expected_columns
    assert list(performance["portfolio_code"]) == ["001", "002"]
    assert list(performance["identifier"]) == ["0007", "NA"]
    assert "contribution" not in performance.columns
    assert "quantity_of_days" not in performance.columns
    assert performance["from_date"].dtype == np.dtype("datetime64[ns]")
    assert performance["weight"].dtype == np.dtype("float64")


def test_loaded_master_file_selects_and_prepares_without_losing_derivation(
    tmp_path: Path,
) -> None:
    """Canonical loading should compose with selection and preparation directly."""
    path = _write(
        tmp_path / "master.csv",
        "portfolio_code,from_date,thru_date,identifier,weight,return\n"
        "P,2024-01-01,2024-01-31,ASSET,1.0,0.02\n"
        "B,2024-01-01,2024-01-31,ASSET,1.0,0.01\n",
    )
    master = read_performance_csv(path)

    prepared = prepare_attribution(
        select_portfolio(master, "P"),
        select_portfolio(master, "B"),
    )

    assert prepared.portfolio.loc[0, "contribution"] == 0.02
    assert prepared.benchmark.loc[0, "contribution"] == 0.01
    derived = prepared.reconciliation.loc[
        prepared.reconciliation["check"] == "derived_contribution"
    ]
    assert list(derived["side"]) == ["portfolio", "benchmark"]


def test_performance_reader_preserves_authoritative_fee_contribution(
    tmp_path: Path,
) -> None:
    """Blank return should remain null for a zero-weight authoritative fee row."""
    path = _write(
        tmp_path / "authoritative.csv",
        "from_date,thru_date,identifier,weight,return,contribution\n"
        "2024-02-01,2024-02-29,ASSET,1.0,0.05,0.051\n"
        "2024-02-01,2024-02-29,FEE,0.0,,-0.001\n",
    )

    performance = read_performance_csv(path)
    prepared = prepare_attribution(performance, performance)

    fee = performance.loc[performance["identifier"] == "FEE"].iloc[0]
    assert pd.isna(fee["return"])
    assert fee["contribution"] == -0.001
    assert "derived_contribution" not in set(prepared.reconciliation["check"])


def test_performance_reader_ignores_blank_records(tmp_path: Path) -> None:
    """Empty and whitespace-only CSV records should be harmless."""
    path = _write(
        tmp_path / "blank_rows.csv",
        ",,,,\nfrom_date,thru_date,identifier,weight,return\n , , , , \n"
        "2024-01-01,2024-01-31,A,1.0,0.02\n\n",
    )

    performance = read_performance_csv(path)

    assert len(performance) == 1
    assert performance.loc[0, "identifier"] == "A"


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        pytest.param("", "must contain a header row", id="empty"),
        pytest.param(
            "from_date,thru_date,identifier,weight,weight,return\n"
            "2024-01-01,2024-01-31,A,1.0,1.0,0.02\n",
            "duplicate column labels",
            id="duplicate-header",
        ),
        pytest.param(
            "from_date,thru_date,identifier,weight\n"
            "2024-01-01,2024-01-31,A,1.0\n",
            "missing required columns: return",
            id="missing-required-column",
        ),
        pytest.param(
            "from_date,thru_date,identifier,weight,return\n"
            "2024-01-01,2024-01-31,A,not-a-number,0.02\n",
            "weight.*invalid number",
            id="invalid-number",
        ),
        pytest.param(
            "from_date,thru_date,identifier,weight,return\n"
            "2024-01-01,2024-01-31,A,1.0,0.02,extra\n",
            "row 2 must contain 5 columns; received 6",
            id="extra-field",
        ),
        pytest.param(
            "portfolio_code,from_date,thru_date,identifier,weight,return\n"
            "GOOD,2024-01-01,2024-01-31,A,1.0,0.02\n"
            "BAD,2024-01-01,2024-01-31,A,0.9,0.02\n",
            "portfolio 'BAD'.*weights must sum to 1.0",
            id="invalid-stream-in-master",
        ),
    ],
)
def test_performance_reader_rejects_invalid_csv_contracts(
    tmp_path: Path,
    contents: str,
    message: str,
) -> None:
    """Malformed structure or invalid performance data should fail explicitly."""
    path = _write(tmp_path / "invalid.csv", contents)

    with pytest.raises(PreparationError, match=message):
        read_performance_csv(path)


def test_mapping_reader_trims_deduplicates_and_preserves_leading_zeroes(
    tmp_path: Path,
) -> None:
    """Headerless mapping rows should normalize exactly like in-memory mappings."""
    path = _write(
        tmp_path / "mapping.csv",
        " A , EQ \n"
        "\n"
        "A,EQ\n"
        "001,010\n",
    )

    mapping = read_mapping_csv(path)

    expected = pd.DataFrame(
        {
            "identifier": pd.Series(["001", "A"], dtype="string[python]"),
            "classification_identifier": pd.Series(
                ["010", "EQ"], dtype="string[python]"
            ),
        }
    )
    pd.testing.assert_frame_equal(mapping, expected)


def test_empty_mapping_csv_returns_a_valid_empty_mapping(tmp_path: Path) -> None:
    """A file containing only blank records should represent an identity mapping."""
    path = _write(tmp_path / "empty_mapping.csv", "\n,\n\n")

    mapping = read_mapping_csv(path)

    assert mapping.empty
    assert list(mapping.columns) == ["identifier", "classification_identifier"]
    assert all(str(mapping[column].dtype) == "string" for column in mapping.columns)


def test_mapping_reader_rejects_conflicts_and_wrong_field_counts(
    tmp_path: Path,
) -> None:
    """A source key must have one target and every nonblank row must have two fields."""
    conflict = _write(tmp_path / "conflict.csv", "A,EQ\nA,FI\n")
    too_many = _write(tmp_path / "too_many.csv", "A,EQ,EXTRA\n")
    too_few = _write(tmp_path / "too_few.csv", "A\n")

    with pytest.raises(PreparationError, match="multiple classifications.*A"):
        read_mapping_csv(conflict)
    with pytest.raises(PreparationError, match="exactly two columns; received 3"):
        read_mapping_csv(too_many)
    with pytest.raises(PreparationError, match="exactly two columns; received 1"):
        read_mapping_csv(too_few)


def test_classification_reader_normalizes_metadata_and_quoted_commas(
    tmp_path: Path,
) -> None:
    """Display names may contain CSV-quoted commas and exact duplicates collapse."""
    path = _write(
        tmp_path / "classification.csv",
        ' EQ ,"Equity, US"\nEQ,"Equity, US"\nFI, Fixed Income \n',
    )

    classification = read_classification_csv(path)

    expected = pd.DataFrame(
        {
            "classification_identifier": pd.Series(
                ["EQ", "FI"], dtype="string[python]"
            ),
            "classification_name": pd.Series(
                ["Equity, US", "Fixed Income"], dtype="string[python]"
            ),
        }
    )
    pd.testing.assert_frame_equal(classification, expected)


def test_classification_reader_rejects_conflicting_or_blank_metadata(
    tmp_path: Path,
) -> None:
    """Classification identity and display names must be nonblank and one-to-one."""
    conflict = _write(tmp_path / "conflict.csv", "EQ,Equity\nEQ,Stocks\n")
    blank = _write(tmp_path / "blank.csv", "EQ, \n")

    with pytest.raises(PreparationError, match="multiple names.*EQ"):
        read_classification_csv(conflict)
    with pytest.raises(PreparationError, match="classification_name.*empty string"):
        read_classification_csv(blank)


def test_empty_classification_csv_returns_empty_metadata(tmp_path: Path) -> None:
    """Blank classification records should produce a typed empty metadata frame."""
    path = _write(tmp_path / "empty_classification.csv", "\n,\n")

    classification = read_classification_csv(path)

    assert classification.empty
    assert list(classification.columns) == [
        "classification_identifier",
        "classification_name",
    ]


def test_classification_normalization_requires_exact_dataframe_schema() -> None:
    """The reusable metadata validator should reject wrong types and extra columns."""
    with pytest.raises(TypeError, match="must be a pandas DataFrame"):
        _normalize_classification(cast(pd.DataFrame, []))
    with pytest.raises(PreparationError, match="unexpected columns: extra"):
        _normalize_classification(
            pd.DataFrame(
                {
                    "classification_identifier": ["EQ"],
                    "classification_name": ["Equity"],
                    "extra": [1],
                }
            )
        )


@pytest.mark.parametrize(
    ("path_value", "error_type", "message"),
    [
        pytest.param("", PreparationError, "path must not be blank", id="empty"),
        pytest.param("   ", PreparationError, "path must not be blank", id="blank"),
        pytest.param(
            "missing.csv",
            PreparationError,
            "existing local regular file",
            id="missing",
        ),
        pytest.param(
            "https://example.com/mapping.csv",
            PreparationError,
            "local file, not a URL",
            id="url",
        ),
        pytest.param(
            io.StringIO("A,EQ"),
            TypeError,
            "string or os.PathLike",
            id="file-like",
        ),
        pytest.param(
            b"mapping.csv",
            TypeError,
            "string or os.PathLike",
            id="bytes",
        ),
    ],
)
def test_readers_reject_nonlocal_or_invalid_paths(
    path_value: Any,
    error_type: type[Exception],
    message: str,
) -> None:
    """Readers must accept only string-compatible paths to local regular files."""
    with pytest.raises(error_type, match=message):
        read_mapping_csv(cast(str | os.PathLike[str], path_value))


def test_readers_reject_directories_and_invalid_utf8(tmp_path: Path) -> None:
    """Directories and files outside the UTF-8 contract should fail before parsing."""
    invalid_utf8 = tmp_path / "invalid.csv"
    invalid_utf8.write_bytes(b"A,\xff\n")

    with pytest.raises(PreparationError, match="existing local regular file"):
        read_classification_csv(tmp_path)
    with pytest.raises(PreparationError, match="readable UTF-8 CSV"):
        read_mapping_csv(invalid_utf8)


def test_mapping_reader_rejects_malformed_csv_quoting(tmp_path: Path) -> None:
    """An unterminated quoted field should fail under strict canonical parsing."""
    malformed = _write(tmp_path / "malformed.csv", 'A,"EQ\n')

    with pytest.raises(PreparationError, match="readable UTF-8 CSV"):
        read_mapping_csv(malformed)


def test_reader_returns_owned_data_and_closes_the_file(tmp_path: Path) -> None:
    """Returned data should be independent and the source path reusable immediately."""
    path = _write(tmp_path / "mapping.csv", "A,EQ\n")

    first = read_mapping_csv(path)
    first.loc[0, "classification_identifier"] = "CHANGED"
    path.write_text("A,FI\n", encoding="utf-8")
    second = read_mapping_csv(path)

    assert first.loc[0, "classification_identifier"] == "CHANGED"
    assert second.loc[0, "classification_identifier"] == "FI"
