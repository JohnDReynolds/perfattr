"""Define diagnostics shared by the portable preparation stages."""


class PreparationError(ValueError):
    """Report invalid preparation input or a failed preparation invariant."""


class PreparationWarning(RuntimeWarning):
    """Report valid preparation input truncated before an incomplete bucket."""


__all__ = ["PreparationError", "PreparationWarning"]
