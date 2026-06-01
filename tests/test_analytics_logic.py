"""Unit tests for the pure analytics math (no MCP/network)."""

import math
import statistics

import pytest

from finance_mcp.data.analytics import (
    annualized_return,
    annualized_volatility,
    max_drawdown,
    sma,
    total_return,
)
from finance_mcp.data.errors import InvalidInput

SERIES = [100.0, 110.0, 99.0]  # returns: +0.10, then 99/110-1 = -0.10


def test_total_return() -> None:
    assert total_return(SERIES) == pytest.approx(-1.0)  # 99/100 - 1


def test_total_return_needs_two() -> None:
    with pytest.raises(InvalidInput):
        total_return([100.0])


def test_annualized_return_equals_total_when_252_intervals() -> None:
    # 253 closes => 252 intervals => exponent 252/252 = 1 => annualized == total return.
    closes = [100.0 + i for i in range(253)]  # 100 .. 352
    assert annualized_return(closes) == pytest.approx(total_return(closes), rel=1e-9)


def test_annualized_return_needs_two() -> None:
    with pytest.raises(InvalidInput):
        annualized_return([100.0])


def test_annualized_volatility() -> None:
    # stdev([0.10, -0.10], ddof=1) = sqrt(0.02) = 0.1414214; * sqrt(252) * 100 ~= 224.499
    assert annualized_volatility(SERIES) == pytest.approx(224.499, rel=1e-4)


def test_annualized_volatility_too_few_returns_is_zero() -> None:
    assert annualized_volatility([100.0, 110.0]) == 0.0  # only 1 return


def test_max_drawdown() -> None:
    assert max_drawdown(SERIES) == pytest.approx(-10.0)  # 99/110 - 1


def test_max_drawdown_monotonic_up_is_zero() -> None:
    assert max_drawdown([100.0, 101.0, 102.0]) == pytest.approx(0.0)


def test_max_drawdown_single_element_is_zero() -> None:
    assert max_drawdown([100.0]) == pytest.approx(0.0)


def test_max_drawdown_needs_one() -> None:
    with pytest.raises(InvalidInput):
        max_drawdown([])


def test_sma() -> None:
    assert sma(SERIES, 2) == pytest.approx(104.5)  # (110+99)/2
    assert sma(SERIES, 5) is None


def test_max_drawdown_uses_running_peak() -> None:
    # Peak 120 (bar 1), trough 90 (bar 2), recovers to 130 (last bar):
    # running-peak gives -25% (120->90); a naive first-to-min would wrongly give -10%.
    assert max_drawdown([100.0, 120.0, 90.0, 130.0]) == pytest.approx(-25.0)


def test_annualized_return_declining() -> None:
    assert annualized_return([100.0, 90.0], periods_per_year=252.0) == pytest.approx(
        (0.9**252 - 1) * 100
    )


def test_annualized_return_nontrivial_exponent() -> None:
    # 2 closes, ppy=2 -> exponent 2/(2-1)=2 -> (1.21)**2 - 1 = 0.4641 -> 46.41%
    assert annualized_return([100.0, 121.0], periods_per_year=2.0) == pytest.approx(46.41, rel=1e-4)


def test_annualized_volatility_multiple_returns() -> None:
    closes = [100.0, 110.0, 99.0, 108.9]
    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    expected = statistics.stdev(rets) * math.sqrt(252.0) * 100
    assert annualized_volatility(closes) == pytest.approx(expected)


def test_sma_at_window_boundary() -> None:
    assert sma([100.0, 110.0, 99.0], 3) == pytest.approx(103.0)  # mean of all three, not None


def test_sma_nonpositive_window_raises() -> None:
    with pytest.raises(InvalidInput):
        sma([100.0, 110.0, 99.0], 0)
