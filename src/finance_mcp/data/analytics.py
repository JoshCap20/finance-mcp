"""Pure return/risk math over a series of closing prices. No MCP/network imports.

Assumes strictly positive closes (real adjusted prices); a zero close would divide by zero.
"""

import math
import statistics

from finance_mcp.data.errors import InvalidInput


def total_return(closes: list[float]) -> float:
    """Total percent return from the first to the last close (e.g. 12.3 = 12.3%)."""
    if len(closes) < 2:
        raise InvalidInput("need at least two closes")
    return (closes[-1] / closes[0] - 1) * 100


def annualized_return(closes: list[float], periods_per_year: float = 252.0) -> float:
    """Annualized return (CAGR) over the window, in percent, at ``periods_per_year`` intervals."""
    if len(closes) < 2:
        raise InvalidInput("need at least two closes")
    growth: float = (closes[-1] / closes[0]) ** (periods_per_year / (len(closes) - 1))
    return (growth - 1) * 100


def annualized_volatility(closes: list[float], periods_per_year: float = 252.0) -> float:
    """Annualized volatility of daily simple returns, in percent; 0.0 with fewer than 2 returns."""
    returns = [closes[t] / closes[t - 1] - 1 for t in range(1, len(closes))]
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns) * math.sqrt(periods_per_year) * 100


def max_drawdown(closes: list[float]) -> float:
    """Largest peak-to-trough decline, as a non-positive percent (e.g. -23.4 = -23.4%)."""
    if len(closes) < 1:
        raise InvalidInput("need at least one close")
    peak = closes[0]
    worst = 0.0
    for close in closes:
        if close > peak:
            peak = close
        drawdown = (close / peak - 1) * 100
        if drawdown < worst:
            worst = drawdown
    return worst


def sma(closes: list[float], window: int) -> float | None:
    """Simple moving average of the last ``window`` closes; None if fewer than ``window`` closes."""
    if window <= 0:
        raise InvalidInput("window must be a positive integer.")
    if len(closes) < window:
        return None
    return statistics.fmean(closes[-window:])
