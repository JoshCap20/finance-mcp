"""MCP tools for computed analytics, backed by YFinanceClient."""

import asyncio
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from finance_mcp.data.errors import DataUnavailable
from finance_mcp.data.models import KeyMetrics, PerformanceStats
from finance_mcp.data.yfinance_client import YFinanceClient
from finance_mcp.tools.equities import Period  # reuse the period Literal


def register(mcp: FastMCP, client: YFinanceClient) -> None:
    """Register analytics tools bound to a YFinanceClient."""

    @mcp.tool
    async def get_key_metrics(
        ticker: Annotated[str, Field(description="Ticker symbol, e.g. 'AAPL'.")],
    ) -> KeyMetrics:
        """Valuation, profitability, and leverage ratios (as reported by Yahoo).

        Note units differ by field: P/E, P/B, P/S, EV/EBITDA, PEG are plain ratios;
        margins and ROE/ROA are fractions (0.27 = 27%); debt_to_equity is a percent
        (79.5 = 79.5%); EV, total debt/cash, FCF, EBITDA are absolute amounts.
        """
        try:
            return await asyncio.to_thread(client.get_key_metrics, ticker)
        except DataUnavailable as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    async def analyze_performance(
        ticker: Annotated[str, Field(description="Ticker symbol, e.g. 'AAPL'.")],
        period: Annotated[Period, Field(description="Look-back window for the statistics.")] = "1y",
    ) -> PerformanceStats:
        """Return and risk stats from daily auto-adjusted closes over the window.

        Includes total and annualized return, annualized volatility, max drawdown
        (negative percent), and 50/200-day SMAs (null if insufficient history).
        Annualized at 252 trading days/year.
        """
        try:
            return await asyncio.to_thread(client.analyze_performance, ticker, period)
        except DataUnavailable as exc:
            raise ToolError(str(exc)) from exc
