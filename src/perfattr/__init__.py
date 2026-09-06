"""Portable portfolio performance-attribution calculations."""

from perfattr.attribution import (
    AttributionError,
    AttributionResult,
    calculate_attribution,
)
from perfattr._exceptions import PreparationError, PreparationWarning
from perfattr.classification import normalize_classification
from perfattr.frequency import Frequency
from perfattr.hierarchy import HierarchicalRollupResult, roll_up_attribution
from perfattr.io import (
    read_classification_csv,
    read_mapping_csv,
    read_performance_csv,
)
from perfattr.prepare import PreparationResult, prepare_attribution
from perfattr.mapping import normalize_mapping
from perfattr.method import AttributionMethod, EffectLinkingMethod
from perfattr.preparation import (
    select_portfolio,
)

__version__ = "0.9.0a1"

__all__ = [
    "AttributionError",
    "AttributionMethod",
    "AttributionResult",
    "EffectLinkingMethod",
    "Frequency",
    "HierarchicalRollupResult",
    "PreparationError",
    "PreparationResult",
    "PreparationWarning",
    "__version__",
    "calculate_attribution",
    "normalize_classification",
    "normalize_mapping",
    "prepare_attribution",
    "read_classification_csv",
    "read_mapping_csv",
    "read_performance_csv",
    "roll_up_attribution",
    "select_portfolio",
]
