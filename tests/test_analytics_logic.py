"""Unit tests for the pure analytics math (no MCP/network)."""

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
