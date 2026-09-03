"""Portable portfolio performance-attribution calculations."""

from perfattr.attribution import (
    AttributionError,
    AttributionResult,
    calculate_attribution,
)

__version__ = "0.1.0a1"

__all__ = [
    "AttributionError",
    "AttributionResult",
    "__version__",
    "calculate_attribution",
]
