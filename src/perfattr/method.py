"""Define the supported portable attribution calculation methods."""

from enum import Enum


class AttributionMethod(str, Enum):
    """Identify the requested Brinson-Fachler effect convention.

    Attributes:
        BRINSON_FACHLER_TWO_EFFECT: Preserve the released convention in which
            portfolio-weighted selection absorbs interaction.
        BRINSON_FACHLER_THREE_EFFECT: Report benchmark-weighted selection and
            interaction as separate effect channels.
    """

    BRINSON_FACHLER_TWO_EFFECT = "Brinson-Fachler Two-Effect"
    BRINSON_FACHLER_THREE_EFFECT = "Brinson-Fachler Three-Effect"


__all__ = ["AttributionMethod"]
