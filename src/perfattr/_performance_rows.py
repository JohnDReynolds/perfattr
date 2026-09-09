"""Normalize shared contribution and effective-return row semantics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd

from perfattr._validation import float_array, normalize_numeric, raise_invalid


@dataclass(frozen=True)
class _PerformanceRowValues:
    """Hold normalized financial values shared by preparation and calculation.

    Attributes:
        contribution_was_supplied: Whether contribution was caller-supplied and
            authoritative rather than derived.
        input_returns: Caller-supplied returns, including permitted nulls.
        effective_returns: Returns implied by contribution and weight.
    """

    contribution_was_supplied: bool
    input_returns: npt.NDArray[np.float64]
    effective_returns: npt.NDArray[np.float64]


def _normalize_performance_row_values(
    frame: pd.DataFrame,
    context: str,
    error_type: type[ValueError],
    *,
    nonfinite_derived_message: str,
) -> _PerformanceRowValues:
    """Apply shared contribution and effective-return rules to normalized rows.

    Args:
        frame: Independently owned frame whose weight and return columns are already
            normalized to float64. Contribution may be present but unnormalized.
        context: Human-readable boundary included in validation errors.
        error_type: Domain error raised for invalid financial values.
        nonfinite_derived_message: Boundary-specific error text used when finite
            weights and returns overflow while deriving contribution.

    Returns:
        Normalized input returns, effective returns, and contribution provenance.

    Raises:
        ValueError: Using ``error_type`` when row values violate the financial
            contract.

    Notes:
        Supplied contribution is authoritative. A nonzero weight requires a defined
        return. A zero-weight, nonzero-contribution row instead requires a null return
        and has a null effective return. Zero weight and zero contribution imply a
        zero effective return, whether the input return is zero or null. The helper
        writes normalized or derived contribution only to the independently owned
        frame received from its caller.
    """
    weights = float_array(frame, "weight")
    input_returns = float_array(frame, "return")
    present_returns = ~np.isnan(input_returns)
    if np.any(input_returns[present_returns] <= -1.0):
        raise_invalid(
            error_type,
            context,
            "column 'return' must be greater than -1.0 when present",
        )
    if np.any((weights != 0.0) & ~present_returns):
        raise_invalid(error_type, context, "contains a nonzero weight with a null return")

    contribution_was_supplied = "contribution" in frame.columns
    if contribution_was_supplied:
        frame["contribution"] = normalize_numeric(
            frame,
            "contribution",
            context,
            error_type,
            nullable=False,
        )
        contributions = float_array(frame, "contribution")
        invalid_undefined_returns = (
            (weights == 0.0) & (contributions != 0.0) & present_returns
        )
        if np.any(invalid_undefined_returns):
            raise_invalid(
                error_type,
                context,
                "requires a null return when weight is zero and contribution is nonzero",
            )
    else:
        contributions = np.zeros(len(frame), dtype=np.float64)
        # A missing return is valid only at zero weight. The output remains zero there,
        # so no undefined multiplication is evaluated.
        with np.errstate(over="ignore", invalid="ignore"):
            np.multiply(
                weights,
                input_returns,
                out=contributions,
                where=present_returns,
            )
        if not np.isfinite(contributions).all():
            raise_invalid(error_type, context, nonfinite_derived_message)
        frame["contribution"] = contributions

    effective_returns = np.zeros(len(frame), dtype=np.float64)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        np.divide(
            contributions,
            weights,
            out=effective_returns,
            where=weights != 0.0,
        )
    effective_returns[(weights == 0.0) & (contributions != 0.0)] = np.nan
    if not np.isfinite(effective_returns[~np.isnan(effective_returns)]).all():
        raise_invalid(error_type, context, "produces a non-finite effective return")

    return _PerformanceRowValues(
        contribution_was_supplied=contribution_was_supplied,
        input_returns=input_returns,
        effective_returns=effective_returns,
    )
