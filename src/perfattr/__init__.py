"""Portable portfolio performance-attribution calculations."""

from perfattr.attribution import (
    AttributionError,
    AttributionResult,
    calculate_attribution,
)
from perfattr._exceptions import PreparationError, PreparationWarning
from perfattr.frequency import Frequency
from perfattr.prepare import PreparationResult, prepare_attribution
from perfattr.preparation import (
    select_portfolio,
)

__version__ = "0.1.0"

__all__ = [
    "AttributionError",
    "AttributionResult",
    "Frequency",
    "PreparationError",
    "PreparationResult",
    "PreparationWarning",
    "__version__",
    "calculate_attribution",
    "prepare_attribution",
    "select_portfolio",
]
