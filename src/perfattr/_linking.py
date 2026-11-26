"""Numerically stable helpers for multi-period attribution linking."""

from __future__ import annotations

from decimal import Context, Decimal, DecimalException, DivisionByZero, InvalidOperation
from decimal import MAX_EMAX, MIN_EMIN, Overflow, ROUND_HALF_EVEN
from decimal import localcontext
import math
import sys

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


def _menchero_wealth(returns: npt.NDArray[np.float64]) -> tuple[int, int]:
    """Retain a source wealth product as an exact integer and binary exponent.

    Args:
        returns: Finite simple period returns greater than -1.

    Returns:
        Numerator and exponent representing ``product(1 + returns)`` exactly.

    Notes:
        Binary floats are dyadic rationals. Add one before rounding each factor,
        remove its powers of two, then multiply the odd numerators. Integer width
        grows with history length. Exact products are necessary because subtracting
        rounded wealth or log ratios can erase a material active difference.
    """
    product, exponent = 1, 0
    for value in returns:
        numerator, denominator = float(value).as_integer_ratio()
        factor = numerator + denominator
        power = (factor & -factor).bit_length() - 1
        product *= factor >> power
        exponent += power - (denominator.bit_length() - 1)
    return product, exponent


def _menchero_source_scales(
    portfolio_returns: npt.NDArray[np.float64],
    benchmark_returns: npt.NDArray[np.float64],
) -> tuple[Decimal, Decimal]:
    """Evaluate the continuous common scale and exact-source active wealth.

    Args:
        portfolio_returns: Admitted portfolio period returns.
        benchmark_returns: Corresponding benchmark period returns.

    Returns:
        Common scale M and source wealth difference D in the caller's local
        high-precision context.

    Notes:
        With source wealth roots x and y, the difference-of-powers identity gives
        ``M = sum(x**(T-1-j) * y**j) / T``. A positive-term recurrence evaluates
        that sum in O(T) arithmetic operations without subtracting nearby roots.
        Subtract the dyadic source products before converting to Decimal, retaining
        D even when the two roots round to the same high-precision value.

    References:
        Menchero, J. G. "An Optimized Approach to Linking Attribution Effects over
        Time." *The Journal of Performance Measurement* 5, no. 1 (2000): 36-42.
    """
    count = portfolio_returns.size
    wealths = [_menchero_wealth(values) for values in (portfolio_returns, benchmark_returns)]
    exponent = min(power for _, power in wealths)
    difference = (wealths[0][0] << (wealths[0][1] - exponent)) - (
        wealths[1][0] << (wealths[1][1] - exponent)
    )
    growths = [Decimal(value) * Decimal(2) ** power for value, power in wealths]
    roots = [growth ** (Decimal(1) / int(count)) for growth in growths]
    ratio = roots[1] / roots[0]
    term = roots[0] ** (int(count) - 1)
    common_scale = Decimal(0)
    for _ in range(count):
        common_scale += term
        term *= ratio
    return common_scale / int(count), Decimal(difference) * Decimal(2) ** exponent


def _menchero_projection(
    common_scale: Decimal,
    wealth_difference: Decimal,
    portfolio_returns: npt.NDArray[np.float64],
    benchmark_returns: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Complete the minimum-norm projection before rounding each coefficient.

    Args:
        common_scale: Continuous Menchero scale M in the local Decimal context.
        wealth_difference: Source wealth difference D in that same context.
        portfolio_returns: Admitted portfolio period returns, with some activity.
        benchmark_returns: Corresponding benchmark period returns.

    Returns:
        Float64 coefficients ``[M*(Q-S*d[t]) + D*d[t]] / Q``.

    Notes:
        Express both source vectors in one exact binary unit before subtracting.
        For d=n/U, S=sum(n)/U and Q=sum(n**2)/U**2, the coefficient is
        ``[M*(q-s*n) + D*n*U] / q``. Integer projection numerators preserve tiny
        departures from a unit projection. Keep both terms in the local Decimal
        context through their cancellation and division, then convert once.
        A small final coefficient can multiply large authoritative offsetting
        charges, so accurate aggregate reconciliation alone is insufficient.
    """
    ratios = [
        (float(left).as_integer_ratio(), float(right).as_integer_ratio())
        for left, right in zip(portfolio_returns, benchmark_returns)
    ]
    unit = max(denominator for pair in ratios for _, denominator in pair)
    integers = [
        left * (unit // left_unit) - right * (unit // right_unit)
        for (left, left_unit), (right, right_unit) in ratios
    ]
    active_sum = sum(integers)
    squared_norm = sum(value * value for value in integers)
    return np.asarray(
        [
            float(
                (common_scale * Decimal(squared_norm - active_sum * value)
                 + wealth_difference * Decimal(value * unit)) / Decimal(squared_norm)
            )
            for value in integers
        ],
        dtype=np.float64,
    )


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

    Raises:
        AttributionError: If a common scale, residual, correction or coefficient
            is not finite under the released admission rules.

    Notes:
        The existing minimum-norm formula uses exact dyadic source products and
        projection numerators, then a uniform local Decimal evaluation. Precision
        spans binary64's largest exponent through its smallest subnormal, with
        guard digits for period accumulation and root evaluation. Thus cancellation
        between finite projected terms is retained through the smallest float64
        coefficient. Precision grows only logarithmically with the period count;
        it does not select a different formula or a financial equality tolerance.
        The private context owns its settings independently of mutable process
        defaults. Caller Decimal settings and flags are preserved.

        A single period is the identity. When every period active return is exactly
        zero, the minimum-norm correction is exactly zero. Equal horizon wealth
        with a nonzero active vector still requires its optimized correction.
        Horizon and contribution calculations and production audits remain separate.

    References:
        Menchero, J. G. "An Optimized Approach to Linking Attribution Effects over
        Time." *The Journal of Performance Measurement* 5, no. 1 (2000): 36-42.
    """
    active_returns = portfolio_returns - benchmark_returns
    maximum_active_return = float(np.max(np.abs(active_returns)))
    if not np.isfinite(active_returns).all() or not np.isfinite(maximum_active_return):
        raise AttributionError("Menchero linking values must be finite")
    if portfolio_returns.size == 1:
        return np.ones(1, dtype=np.float64)

    # Carry cancellation across the full output exponent range. Two count
    # factors cover recurrence and accumulation; 32 extra decimal digits
    # separate root/rounding error from the smallest float64 output unit.
    precision = math.ceil(
        (sys.float_info.max_exp - sys.float_info.min_exp + sys.float_info.mant_dig)
        * math.log10(2)
    ) + 32 + 2 * len(str(portfolio_returns.size))
    try:
        with localcontext(Context(
            prec=precision, rounding=ROUND_HALF_EVEN, Emax=MAX_EMAX, Emin=MIN_EMIN,
            capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow],
        )):
            common_scale, wealth_difference = _menchero_source_scales(
                portfolio_returns, benchmark_returns,
            )
            common_value = float(common_scale)
            if not np.isfinite(common_value):
                raise AttributionError("Menchero linking values must be finite")
            if maximum_active_return == 0.0:
                return np.full(portfolio_returns.size, common_value, dtype=np.float64)
            coefficients = _menchero_projection(
                common_scale, wealth_difference, portfolio_returns, benchmark_returns,
            )
    except (DecimalException, OverflowError, ValueError) as error:
        raise AttributionError("Menchero linking values must be finite") from error

    # Preserve finite-residual admission using the released rounded horizons, while
    # the coefficients above retain the independent source-wealth calculation.
    residual = (
        portfolio_horizon_return - benchmark_horizon_return
        - common_value * float(np.sum(active_returns, dtype=np.float64))
    )
    with np.errstate(over="ignore", invalid="ignore"):
        corrections = coefficients - common_value
    if (not np.isfinite(residual) or not np.isfinite(coefficients).all()
            or not np.isfinite(corrections).all()):
        raise AttributionError("Menchero linking values must be finite")
    return coefficients
