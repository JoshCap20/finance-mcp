"""MCP tools for equities market data, backed by YFinanceClient."""

import asyncio
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from finance_mcp.data.errors import DataUnavailable
from finance_mcp.data.models import (
    AnalystData,
    CompanyProfile,
    FinancialStatement,
    HistoryInterval,
    HistoryPeriod,
    PriceHistory,
    Quote,
    Statement,
    StatementPeriod,
    SymbolSearchResult,
)
from finance_mcp.data.yfinance_client import YFinanceClient


def register(mcp: FastMCP, client: YFinanceClient) -> None:
    """Register equities tools bound to a YFinanceClient."""

    @mcp.tool
    async def get_quote(
        tickers: Annotated[
            list[str], Field(description="One or more ticker symbols, e.g. ['AAPL', 'MSFT'].")
        ],
    ) -> list[Quote]:
        """Current price snapshot for one or more tickers (price, change, ranges, market cap).

        Fails (with a message naming the offending ticker) if ANY ticker has no data; on
        failure the caller should retry without the offending symbol.
        """
        try:
            return await asyncio.to_thread(client.get_quote, tickers)
        except DataUnavailable as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    async def get_price_history(
        ticker: Annotated[str, Field(description="Ticker symbol, e.g. 'AAPL'.")],
        period: Annotated[HistoryPeriod, Field(description="Look-back window.")] = "1mo",
        interval: Annotated[
            HistoryInterval,
            Field(
                description=(
                    "Bar interval. Intraday intervals (1m-1h) only support short look-backs "
                    "(1m ~ 7 days, sub-daily ~ 60 days); use 1d+ for long periods."
                )
            ),
        ] = "1d",
    ) -> PriceHistory:
        """Historical OHLCV bars plus a summary; long windows are truncated (summary is full)."""
        try:
            return await asyncio.to_thread(client.get_price_history, ticker, period, interval)
        except DataUnavailable as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    async def get_financials(
        ticker: Annotated[str, Field(description="Ticker symbol, e.g. 'AAPL'.")],
        statement: Annotated[
            Statement, Field(description="Which statement: 'income', 'balance', or 'cashflow'.")
        ],
        period: Annotated[
            StatementPeriod, Field(description="Reporting period granularity.")
        ] = "annual",
        line_items: Annotated[
            list[str] | None,
            Field(
                description="Specific line-item labels to return (exactly as they appear in the "
                "statement, e.g. 'Total Revenue'); omit for the full statement."
            ),
        ] = None,
    ) -> FinancialStatement:
        """Income statement, balance sheet, or cash flow.

        Returns line items by period (most recent first); values are in the company's reporting
        currency in absolute units (e.g. 416161000000 = 416.161 billion), null where not reported.
        """
        try:
            return await asyncio.to_thread(
                client.get_financials, ticker, statement, period, line_items
            )
        except DataUnavailable as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    async def get_company_profile(
        ticker: Annotated[str, Field(description="Ticker symbol, e.g. 'AAPL'.")],
    ) -> CompanyProfile:
        """Company profile and key stats.

        Includes sector, industry, market cap and P/E, with recent dividends and splits.
        Note: dividend_yield is a percent (e.g. 5.92 means 5.92%).
        """
        try:
            return await asyncio.to_thread(client.get_company_profile, ticker)
        except DataUnavailable as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    async def get_analyst_data(
        ticker: Annotated[str, Field(description="Ticker symbol, e.g. 'AAPL'.")],
    ) -> AnalystData:
        """Sell-side analyst consensus: price targets, the consensus recommendation, and the
        recent rating trend (analyst counts over the last four months).

        recommendation_mean runs 1.0 (strong buy) to 5.0 (strong sell). Price targets and
        current_price are in the result's currency. ETFs, indices, and crypto have no
        analyst coverage and return an error.
        """
        try:
            return await asyncio.to_thread(client.get_analyst_data, ticker)
        except DataUnavailable as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    async def search_symbols(
        query: Annotated[
            str, Field(description="Company or instrument name to resolve, e.g. 'Apple'.")
        ],
        max_results: Annotated[
            int, Field(ge=1, le=20, description="Maximum number of matches to return.")
        ] = 8,
    ) -> SymbolSearchResult:
        """Resolve a company or instrument name to ticker symbol(s), best match first.

        Returns all instrument types (EQUITY, ETF, CRYPTOCURRENCY, FUTURE, INDEX, …); use each
        match's quote_type to choose. Use this to find a symbol before calling the other tools.
        An unmatched query returns an empty match list (not an error).
        """
        try:
            return await asyncio.to_thread(client.search_symbols, query, max_results)
        except DataUnavailable as exc:
            raise ToolError(str(exc)) from exc
