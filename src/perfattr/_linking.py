"""Numerically stable helpers for multi-period attribution linking."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def _compound_returns(returns: npt.NDArray[np.float64]) -> float:
    """Compound period returns with stable logarithmic arithmetic."""
    with np.errstate(over="ignore", invalid="ignore"):
        return float(np.expm1(np.log1p(returns).sum(dtype=np.float64)))


def _smoothing(returns: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Evaluate logarithmic smoothing with its exact zero-return limit."""
    coefficients = np.ones_like(returns, dtype=np.float64)
    nonzero = returns != 0.0
    np.divide(
        np.log1p(returns),
        returns,
        out=coefficients,
        where=nonzero,
    )
    return coefficients


def _carino(
    portfolio_returns: npt.NDArray[np.float64],
    benchmark_returns: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Evaluate Carino coefficients stably for equal and near-equal returns."""
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        relative_difference = (
            portfolio_returns - benchmark_returns
        ) / (1.0 + benchmark_returns)
        return _smoothing(relative_difference) / (1.0 + benchmark_returns)
