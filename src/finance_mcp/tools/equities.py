"""MCP tools for equities market data, backed by YFinanceClient."""

import asyncio
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from finance_mcp.data.errors import DataUnavailable
from finance_mcp.data.models import PriceHistory, Quote
from finance_mcp.data.yfinance_client import YFinanceClient

Period = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
Interval = Literal["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"]


def register(mcp: FastMCP, client: YFinanceClient) -> None:
    """Register equities tools bound to a YFinanceClient."""

    @mcp.tool
    async def get_quote(
        tickers: Annotated[
            list[str], Field(description="One or more ticker symbols, e.g. ['AAPL', 'MSFT'].")
        ],
    ) -> list[Quote]:
        """Current price snapshot for one or more tickers (price, change, ranges, market cap)."""
        try:
            return await asyncio.to_thread(client.get_quote, tickers)
        except DataUnavailable as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    async def get_price_history(
        ticker: Annotated[str, Field(description="Ticker symbol, e.g. 'AAPL'.")],
        period: Annotated[Period, Field(description="Look-back window.")] = "1mo",
        interval: Annotated[Interval, Field(description="Bar interval.")] = "1d",
    ) -> PriceHistory:
        """Historical OHLCV bars plus a summary; long windows are truncated (summary is full)."""
        try:
            return await asyncio.to_thread(client.get_price_history, ticker, period, interval)
        except DataUnavailable as exc:
            raise ToolError(str(exc)) from exc
