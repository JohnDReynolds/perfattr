"""Portable portfolio performance-attribution calculations."""

from perfattr.attribution import (
    AttributionError,
    AttributionResult,
    calculate_attribution,
)
from perfattr.preparation import (
    PreparationError,
    PreparationWarning,
    select_portfolio,
)

__version__ = "0.1.0"

__all__ = [
    "AttributionError",
    "AttributionResult",
    "PreparationError",
    "PreparationWarning",
    "__version__",
    "calculate_attribution",
    "select_portfolio",
]
