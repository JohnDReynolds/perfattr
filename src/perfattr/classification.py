"""Validate source-neutral classification display metadata."""

from __future__ import annotations

import pandas as pd

from perfattr._exceptions import PreparationError
from perfattr._validation import normalize_identity_pairs


_CLASSIFICATION_COLUMNS = (
    "classification_identifier",
    "classification_name",
)


def _normalize_classification(
    classification: pd.DataFrame,
    context: str = "classification input",
) -> pd.DataFrame:
    """Validate and normalize classification display metadata.

    Args:
        classification: Source-neutral classification identifiers and display names.
        context: Human-readable boundary included in errors.

    Returns:
        Independently owned, deduplicated metadata ordered by classification
        identifier and name.

    Raises:
        TypeError: If ``classification`` is not a pandas DataFrame.
        PreparationError: If its schema, identities, or one-to-one naming contract is
            invalid.

    Notes:
        Display names are metadata only. They do not enter preparation calculations or
        propagate into portable result frames.
    """
    return normalize_identity_pairs(
        classification,
        _CLASSIFICATION_COLUMNS,
        context,
        PreparationError,
        "assigns multiple names to classification identifiers",
    )


def normalize_classification(classification: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize source-neutral classification display metadata.

    Args:
        classification: DataFrame containing exactly ``classification_identifier``
            and ``classification_name`` columns.

    Returns:
        An independently owned, deduplicated metadata frame in deterministic order.

    Raises:
        TypeError: If ``classification`` is not a pandas DataFrame.
        PreparationError: If its schema, identities, or one-to-one naming contract is
            invalid.

    Notes:
        Display names remain host metadata and do not enter preparation calculations.
    """
    return _normalize_classification(classification)


__all__ = ["normalize_classification"]
