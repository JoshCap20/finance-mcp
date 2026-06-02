"""MCP tools for computed analytics, backed by YFinanceClient."""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from finance_mcp.data.models import HistoryPeriod, KeyMetrics, PerformanceStats
from finance_mcp.data.yfinance_client import YFinanceClient
from finance_mcp.tools._dispatch import run_data


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
        return await run_data(lambda: client.get_key_metrics(ticker))

    @mcp.tool
    async def analyze_performance(
        ticker: Annotated[str, Field(description="Ticker symbol, e.g. 'AAPL'.")],
        period: Annotated[
            HistoryPeriod, Field(description="Look-back window for the statistics.")
        ] = "1y",
    ) -> PerformanceStats:
        """Return and risk stats from daily auto-adjusted closes over the window.

        Includes total and annualized return, annualized volatility, max drawdown
        (negative percent), and 50/200-day SMAs (null if insufficient history).
        Annualized at 252 trading days/year.
        """
        return await run_data(lambda: client.analyze_performance(ticker, period))
