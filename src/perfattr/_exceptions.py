"""Define diagnostics raised by portable attribution and preparation stages."""


class AttributionError(ValueError):
    """Report invalid attribution input or a failed calculation invariant."""


class PreparationError(ValueError):
    """Report invalid preparation input or a failed preparation invariant."""


class PreparationWarning(RuntimeWarning):
    """Report valid preparation input truncated before an incomplete bucket."""


__all__ = ["AttributionError", "PreparationError", "PreparationWarning"]
