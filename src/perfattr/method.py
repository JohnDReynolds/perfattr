"""Define the supported portable attribution calculation methods."""

from enum import Enum


class AttributionMethod(str, Enum):
    """Identify the requested attribution effect convention.

    Attributes:
        BRINSON_FACHLER_TWO_EFFECT: Preserve the released convention in which
            portfolio-weighted selection absorbs interaction.
        BRINSON_FACHLER_THREE_EFFECT: Report benchmark-weighted selection and
            interaction as separate effect channels.
        BRINSON_HOOD_BEEBOWER_THREE_EFFECT: Report BHB allocation,
            benchmark-weighted selection, and interaction as separate channels.
    """

    BRINSON_FACHLER_TWO_EFFECT = "Brinson-Fachler Two-Effect"
    BRINSON_FACHLER_THREE_EFFECT = "Brinson-Fachler Three-Effect"
    BRINSON_HOOD_BEEBOWER_THREE_EFFECT = "Brinson-Hood-Beebower Three-Effect"


def uses_explicit_interaction(method: AttributionMethod) -> bool:
    """Return whether a method uses the released explicit-interaction schemas."""
    return method in (
        AttributionMethod.BRINSON_FACHLER_THREE_EFFECT,
        AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT,
    )


__all__ = ["AttributionMethod"]
