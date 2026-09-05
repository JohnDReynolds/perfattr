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


def _frongello(
    portfolio_returns: npt.NDArray[np.float64],
    benchmark_returns: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Calculate full-horizon Frongello factors in chronological order.

    Args:
        portfolio_returns: Total portfolio return for each source period.
        benchmark_returns: Total benchmark return for each source period.

    Returns:
        One factor per period. Each factor compounds earlier portfolio returns and
        later benchmark returns, excluding the current period from both products.

    Notes:
        This prefix-portfolio, suffix-benchmark form is the closed form of
        Frongello's recursive effect-linking algorithm. Empty products equal one.

    References:
        Frongello, A. S. B. “Attribution Linking: Proofed and Clarified.”
        *The Journal of Performance Measurement* 7, no. 1 (2002): 54–67.
    """
    portfolio_prefixes = np.ones_like(portfolio_returns, dtype=np.float64)
    benchmark_suffixes = np.ones_like(benchmark_returns, dtype=np.float64)
    with np.errstate(over="ignore", invalid="ignore"):
        portfolio_prefixes[1:] = np.cumprod(
            1.0 + portfolio_returns[:-1],
            dtype=np.float64,
        )
        benchmark_suffixes[:-1] = np.cumprod(
            1.0 + benchmark_returns[:0:-1],
            dtype=np.float64,
        )[::-1]
        return portfolio_prefixes * benchmark_suffixes
