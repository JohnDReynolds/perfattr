"""Read the canonical local CSV inputs accepted by portable preparation."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from perfattr._exceptions import PreparationError
from perfattr._schemas import PREPARED_REQUIRED_COLUMNS
from perfattr._validation import normalize_identity, normalize_reconciliation_tolerance
from perfattr.classification import _normalize_classification
from perfattr.mapping import _normalize_mapping
from perfattr.preparation import _NormalizedPerformance, _normalize_performance


_PERFORMANCE_REQUIRED_COLUMNS = PREPARED_REQUIRED_COLUMNS[:-1]
_PERFORMANCE_OPTIONAL_COLUMNS = (
    "contribution",
    "portfolio_code",
    "name",
)
_MAPPING_COLUMNS_BY_WIDTH = {
    2: ("identifier", "classification_identifier"),
    4: ("from_date", "thru_date", "identifier", "classification_identifier"),
}
_CLASSIFICATION_COLUMNS = (
    "classification_identifier",
    "classification_name",
)


def _local_csv_path(
    path: str | os.PathLike[str],
    context: str,
) -> Path:
    """Require a nonblank path to an existing local regular file.

    Args:
        path: String or string-returning path-like object.
        context: Reader label included in errors.

    Returns:
        A validated local path.

    Raises:
        TypeError: If ``path`` is not string-compatible path data.
        PreparationError: If it is blank or does not identify a regular file.
    """
    if isinstance(path, bytes) or not isinstance(path, str | os.PathLike):
        raise TypeError(f"{context} path must be a string or os.PathLike[str]")
    try:
        raw_path = os.fspath(path)
    except TypeError as error:
        raise TypeError(
            f"{context} path must be a string or os.PathLike[str]"
        ) from error
    if not isinstance(raw_path, str):
        raise TypeError(f"{context} path must resolve to a string")
    if not raw_path.strip():
        raise PreparationError(f"{context} path must not be blank")
    if "://" in raw_path:
        raise PreparationError(f"{context} path must identify a local file, not a URL")

    local_path = Path(raw_path)
    try:
        is_file = local_path.is_file()
    except OSError as error:
        raise PreparationError(
            f"{context} path must identify an existing local regular file"
        ) from error
    if not is_file:
        raise PreparationError(
            f"{context} path must identify an existing local regular file"
        )
    return local_path


def _read_nonblank_rows(path: Path, context: str) -> list[list[str]]:
    """Read nonblank UTF-8 CSV records with strict quote handling."""
    try:
        with path.open("r", encoding="utf-8", newline="") as source:
            reader = csv.reader(source, strict=True)
            return [
                row
                for row in reader
                if row and any(value.strip() for value in row)
            ]
    except (csv.Error, OSError, UnicodeError) as error:
        raise PreparationError(f"{context} is not a readable UTF-8 CSV file") from error


def _read_pair_csv(
    path: str | os.PathLike[str],
    columns: tuple[str, str],
    context: str,
) -> pd.DataFrame:
    """Read one headerless two-column canonical CSV.

    Args:
        path: Existing local UTF-8 CSV path.
        columns: Canonical names assigned to the two fields.
        context: Reader label included in errors.

    Returns:
        String-valued pairs with blank records removed.

    Raises:
        TypeError: If ``path`` is not path-like string data.
        PreparationError: If the file cannot be read or a nonblank record does not
            contain exactly two fields.
    """
    local_path = _local_csv_path(path, context)
    rows = _read_nonblank_rows(local_path, context)
    for line_number, row in enumerate(rows, start=1):
        if len(row) != 2:
            raise PreparationError(
                f"{context} row {line_number} must contain exactly two columns; "
                f"received {len(row)}"
            )
    return pd.DataFrame(rows, columns=columns, dtype="string[python]")


def _read_mapping_frame(path: str | os.PathLike[str]) -> pd.DataFrame:
    """Read one uniformly static or effective-dated headerless mapping CSV."""
    context = "mapping CSV"
    local_path = _local_csv_path(path, context)
    rows = _read_nonblank_rows(local_path, context)
    if not rows:
        return pd.DataFrame(
            columns=_MAPPING_COLUMNS_BY_WIDTH[2], dtype="string[python]"
        )

    width = len(rows[0])
    columns = _MAPPING_COLUMNS_BY_WIDTH.get(width)
    if columns is None:
        raise PreparationError(
            f"{context} row 1 must contain exactly two or four columns; "
            f"received {width}"
        )

    for line_number, row in enumerate(rows, start=1):
        if len(row) != width:
            raise PreparationError(
                f"{context} uses mixed column counts; row {line_number} has "
                f"{len(row)} columns but row 1 has {width}"
            )
        if tuple(value.strip() for value in row) == columns:
            raise PreparationError(f"{context} must be headerless")

    return pd.DataFrame(rows, columns=columns, dtype="string[python]")


def _performance_header(path: Path) -> tuple[list[str], int]:
    """Validate widths and return the first nonblank record and its physical line."""
    try:
        with path.open("r", encoding="utf-8", newline="") as source:
            header: list[str] | None = None
            header_line_number = 0
            reader = csv.reader(source, strict=True)
            for row in reader:
                if not row or not any(value.strip() for value in row):
                    continue
                if header is None:
                    header = row
                    header_line_number = reader.line_num
                    continue
                if len(row) != len(header):
                    raise PreparationError(
                        f"performance CSV row {reader.line_num} must contain "
                        f"{len(header)} columns; received {len(row)}"
                    )
    except (csv.Error, OSError, UnicodeError) as error:
        raise PreparationError(
            "performance CSV is not a readable UTF-8 CSV file"
        ) from error
    if header is None:
        raise PreparationError("performance CSV must contain a header row")
    if len(header) != len(set(header)):
        raise PreparationError("performance CSV contains duplicate column labels")
    return header, header_line_number


def _read_performance_frame(
    path: Path,
    header: list[str],
    header_line_number: int,
) -> pd.DataFrame:
    """Parse performance fields while preserving source identity text."""
    try:
        frame = pd.read_csv(
            path,
            encoding="utf-8",
            dtype=str,
            keep_default_na=False,
            skiprows=header_line_number - 1,
        )
    except (OSError, UnicodeError, pd.errors.ParserError) as error:
        raise PreparationError(
            "performance CSV is not a readable canonical UTF-8 CSV file"
        ) from error
    nonblank = pd.Series(False, index=frame.index, dtype="bool")
    for column in frame.columns:
        values = cast(pd.Series, frame[column])
        nonblank = cast(pd.Series, nonblank | values.str.strip().ne(""))
    frame = cast(pd.DataFrame, frame.loc[nonblank].copy(deep=True))
    for column in ("weight", "return", "contribution"):
        if column not in header:
            continue
        values = cast(pd.Series, frame[column]).mask(frame[column].eq(""), np.nan)
        try:
            frame[column] = pd.to_numeric(values, errors="raise")
        except (TypeError, ValueError) as error:
            raise PreparationError(
                f"performance CSV column {column!r} contains an invalid number"
            ) from error
    return frame


def _normalize_performance_streams(
    frame: pd.DataFrame,
    reconciliation_tolerance: float,
) -> _NormalizedPerformance:
    """Normalize one ordinary stream or every code in a master performance frame."""
    if "portfolio_code" not in frame.columns:
        return _normalize_performance(
            frame,
            "performance CSV",
            reconciliation_tolerance,
        )

    source = frame.copy(deep=True)
    source["portfolio_code"] = normalize_identity(
        source,
        "portfolio_code",
        "performance CSV",
        PreparationError,
    )
    streams = [
        _normalize_performance(
            group,
            f"performance CSV portfolio {code!r}",
            reconciliation_tolerance,
        )
        for code, group in source.groupby(
            "portfolio_code", sort=True, observed=True, dropna=False
        )
    ]
    if not streams:
        raise PreparationError("performance CSV must contain performance rows")
    contribution_was_supplied = streams[0].contribution_was_supplied
    normalized = pd.concat(
        [stream.frame for stream in streams], ignore_index=True
    )
    return _NormalizedPerformance(normalized, contribution_was_supplied)


def _performance_reader_output(
    normalized: _NormalizedPerformance,
) -> pd.DataFrame:
    """Return normalized source columns while preserving contribution provenance."""
    columns = [*_PERFORMANCE_REQUIRED_COLUMNS]
    if normalized.contribution_was_supplied:
        columns.append("contribution")
    columns.extend(
        column
        for column in ("portfolio_code", "name")
        if column in normalized.frame.columns
    )
    result = cast(
        pd.DataFrame,
        normalized.frame.loc[:, columns].copy(deep=True),
    )
    order = ["thru_date", "identifier"]
    if "portfolio_code" in result.columns:
        order.insert(0, "portfolio_code")
    return result.sort_values(order, kind="stable").reset_index(drop=True)


def read_performance_csv(
    path: str | os.PathLike[str],
    *,
    reconciliation_tolerance: float = 1e-12,
) -> pd.DataFrame:
    """Read and validate canonical source-period performance CSV data.

    Args:
        path: Path to an existing local UTF-8 CSV with a header row.
        reconciliation_tolerance: Positive relative and absolute tolerance for each
            source-period weight total.

    Returns:
        Independently owned normalized source columns. A source contribution column is
        retained only when it existed in the file, preserving returns-only provenance
        for ``prepare_attribution``. Multi-portfolio files retain ``portfolio_code``
        for subsequent ``select_portfolio`` calls.

    Raises:
        TypeError: If ``path`` is not string-compatible path data or the tolerance is
            not a real number.
        PreparationError: If the path, CSV structure, schema, values, or financial
            invariants violate the canonical performance contract.

    Notes:
        The reader validates each portfolio code as its own performance stream. It
        never chooses a code, applies a date window, or interprets vendor columns.
    """
    tolerance = normalize_reconciliation_tolerance(
        reconciliation_tolerance,
        PreparationError,
    )
    local_path = _local_csv_path(path, "performance CSV")
    header, header_line_number = _performance_header(local_path)
    frame = _read_performance_frame(local_path, header, header_line_number)
    return _performance_reader_output(_normalize_performance_streams(frame, tolerance))


def read_mapping_csv(path: str | os.PathLike[str]) -> pd.DataFrame:
    """Read and validate a canonical headerless mapping CSV.

    Args:
        path: Path to an existing local UTF-8 CSV. Every nonblank row must use
            either the static ``identifier, classification_identifier`` form or the
            effective-dated ``from_date, thru_date, identifier,
            classification_identifier`` form.

    Returns:
        An independently owned normalized static or effective-dated mapping frame,
        with the schema selected by the uniform row width.

    Raises:
        TypeError: If ``path`` is not string-compatible path data.
        PreparationError: If the path, row structure, headerless contract, or mapping
            values are invalid.

    Notes:
        Blank records are ignored. Mixing the two supported forms in one file is not
        allowed. Effective dates are closed and inclusive.
    """
    mapping = _read_mapping_frame(path)
    return _normalize_mapping(mapping, "mapping CSV")


def read_classification_csv(path: str | os.PathLike[str]) -> pd.DataFrame:
    """Read and validate canonical headerless classification metadata.

    Args:
        path: Path to an existing local UTF-8 two-column CSV.

    Returns:
        Independently owned normalized classification identifiers and display names.

    Raises:
        TypeError: If ``path`` is not string-compatible path data.
        PreparationError: If the path, row structure, or metadata values are invalid.

    Notes:
        Classification names are display metadata and never enter financial
        preparation calculations.
    """
    classification = _read_pair_csv(
        path, _CLASSIFICATION_COLUMNS, "classification CSV"
    )
    return _normalize_classification(classification, "classification CSV")


__all__ = [
    "read_classification_csv",
    "read_mapping_csv",
    "read_performance_csv",
]
