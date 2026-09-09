"""Numerically stable helpers for multi-period attribution linking."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from perfattr._exceptions import AttributionError


def _compound_returns(returns: npt.NDArray[np.float64]) -> float:
    """Compound a chronological series of simple returns.

    Args:
        returns: Finite simple period returns greater than ``-1``.

    Returns:
        The full-horizon simple return.

    Notes:
        This evaluates ``expm1(sum(log1p(return)))`` instead of multiplying wealth
        relatives directly. The caller validates the return domain and the finite
        result.
    """
    with np.errstate(over="ignore", invalid="ignore"):
        return float(np.expm1(np.log1p(returns).sum(dtype=np.float64)))


def _smoothing(returns: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Evaluate the logarithmic contribution-smoothing coefficient.

    Args:
        returns: Finite simple period returns greater than ``-1``.

    Returns:
        One ``log1p(return) / return`` coefficient per period.

    Notes:
        The coefficient's exact continuous limit at a zero return is one. This makes
        period contribution times the coefficient additive on a log-return basis.
    """
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
    """Evaluate unnormalized Carino active-effect coefficients.

    Args:
        portfolio_returns: Total portfolio simple return for each period.
        benchmark_returns: Total benchmark simple return for each period.

    Returns:
        One stable Carino coefficient per period.

    Notes:
        For unequal returns, the coefficient is the difference of portfolio and
        benchmark log returns divided by their simple-return difference. Expressing
        it through their relative difference avoids cancellation for near-equal
        returns. At equality, the exact limit is ``1 / (1 + benchmark_return)``.

    References:
        Carino, D. R. “Combining Attribution Effects Over Time.”
        *The Journal of Performance Measurement* 3, no. 4 (1999): 5–14.
    """
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


def _menchero(
    portfolio_returns: npt.NDArray[np.float64],
    benchmark_returns: npt.NDArray[np.float64],
    portfolio_horizon_return: float,
    benchmark_horizon_return: float,
) -> npt.NDArray[np.float64]:
    """Calculate Menchero optimized full-horizon effect coefficients.

    Args:
        portfolio_returns: Total portfolio return for each source period.
        benchmark_returns: Total benchmark return for each source period.
        portfolio_horizon_return: Compounded portfolio return for the horizon.
        benchmark_horizon_return: Compounded benchmark return for the horizon.

    Returns:
        One Menchero coefficient per period, in source-period order.

    Notes:
        The common scale is the mean of the positive terms in the
        difference-of-powers identity. This remains continuous when the compounded
        horizon returns are equal and avoids subtracting nearly equal roots.

        Corrections use a scaled Euclidean norm. If every active period return is
        exactly zero, the minimum-norm correction is exactly zero. No tolerance
        selects either financial formula.

    References:
        Menchero, J. G. "An Optimized Approach to Linking Attribution Effects over
        Time." *The Journal of Performance Measurement* 5, no. 1 (2000): 36-42.
    """
    period_count = portfolio_returns.size
    horizon_log_growths = np.log1p(
        np.asarray(
            [portfolio_horizon_return, benchmark_horizon_return],
            dtype=np.float64,
        )
    )

    # These are the logs of x**(T-1-j) * y**j. Scaling their exponentials keeps
    # the continuous divided-difference mean well conditioned.
    benchmark_powers = np.arange(period_count, dtype=np.float64)
    term_logs = (
        (period_count - 1.0 - benchmark_powers) * horizon_log_growths[0]
        + benchmark_powers * horizon_log_growths[1]
    ) / period_count
    common_scale = float(
        np.exp(np.logaddexp.reduce(term_logs) - np.log(period_count))
    )
    if not np.isfinite(term_logs).all() or not np.isfinite(common_scale):
        raise AttributionError("Menchero linking values must be finite")

    active_returns = portfolio_returns - benchmark_returns
    maximum_active_return = float(np.max(np.abs(active_returns)))
    if not np.isfinite(active_returns).all() or not np.isfinite(maximum_active_return):
        raise AttributionError("Menchero linking values must be finite")
    # A one-period horizon is the identity by definition. Returning it explicitly
    # prevents expm1(log1p(return)) reconstruction noise from creating a spurious
    # least-squares correction on platforms with different math libraries.
    if period_count == 1:
        return np.ones(1, dtype=np.float64)
    if maximum_active_return == 0.0:
        return np.full(period_count, common_scale, dtype=np.float64)

    scaled_active_returns = active_returns / maximum_active_return
    scaled_squared_norm = float(np.dot(scaled_active_returns, scaled_active_returns))
    residual = (
        portfolio_horizon_return
        - benchmark_horizon_return
        - common_scale
        * float(np.sum(active_returns, dtype=np.float64))
    )
    if not np.isfinite(scaled_squared_norm) or not np.isfinite(residual):
        raise AttributionError("Menchero linking values must be finite")
    correction_scale = residual / maximum_active_return / scaled_squared_norm
    scaled_active_returns = common_scale + correction_scale * scaled_active_returns
    if not np.isfinite(correction_scale) or not np.isfinite(scaled_active_returns).all():
        raise AttributionError("Menchero linking values must be finite")
    return scaled_active_returns
