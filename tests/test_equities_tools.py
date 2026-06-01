import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from yfinance.exceptions import YFException

from finance_mcp.server import create_server
from tests.conftest import (
    fake_ticker_factory,
    make_client,
    make_financials_df,
    make_history_df,
    make_series,
)

INCOME = {"Total Revenue": [400.0, 380.0], "Net Income": [100.0, 90.0]}
FULL_INFO = {
    "longName": "Apple Inc.",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "country": "United States",
    "currency": "USD",
    "marketCap": 4.5e12,
    "trailingPE": 37.7,
}

QUOTE_FI = {
    "last_price": 190.0,
    "previous_close": 188.0,
    "day_high": 191.0,
    "day_low": 187.0,
    "year_high": 200.0,
    "year_low": 150.0,
    "market_cap": 3.0e12,
    "currency": "USD",
    "last_volume": 50_000_000,
}


async def test_get_quote_tool() -> None:
    server = create_server(yf_client=make_client(factory=fake_ticker_factory(fast_info=QUOTE_FI)))
    async with Client(server) as client:
        names = {t.name for t in await client.list_tools()}
        assert {"get_quote", "get_price_history"} <= names
        result = await client.call_tool("get_quote", {"tickers": ["AAPL"]})
        assert result.data[0].price == 190.0


async def test_get_quote_tool_multiple_tickers() -> None:
    server = create_server(yf_client=make_client(factory=fake_ticker_factory(fast_info=QUOTE_FI)))
    async with Client(server) as client:
        result = await client.call_tool("get_quote", {"tickers": ["AAPL", "MSFT"]})
        assert [q.symbol for q in result.data] == ["AAPL", "MSFT"]


async def test_get_price_history_tool() -> None:
    df = make_history_df([100.0, 101.0, 102.0])
    server = create_server(yf_client=make_client(factory=fake_ticker_factory(history_df=df)))
    async with Client(server) as client:
        result = await client.call_tool(
            "get_price_history", {"ticker": "AAPL", "period": "1mo", "interval": "1d"}
        )
        assert result.data.summary.bars == 3


async def test_get_quote_tool_surfaces_yfinance_message() -> None:
    server = create_server(
        yf_client=make_client(
            factory=fake_ticker_factory(fast_info_error=YFException("yahoo: blocked"))
        )
    )
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc:
            await client.call_tool("get_quote", {"tickers": ["AAPL"]})
        assert "yahoo: blocked" in str(exc.value)


async def test_get_price_history_tool_surfaces_yfinance_message() -> None:
    server = create_server(
        yf_client=make_client(factory=fake_ticker_factory(error=RuntimeError("yahoo: down")))
    )
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc:
            await client.call_tool(
                "get_price_history", {"ticker": "AAPL", "period": "1mo", "interval": "1d"}
            )
        assert "yahoo: down" in str(exc.value)


async def test_fundamentals_tools_registered() -> None:
    server = create_server(yf_client=make_client(factory=fake_ticker_factory(info=FULL_INFO)))
    async with Client(server) as client:
        names = {t.name for t in await client.list_tools()}
        assert {"get_financials", "get_company_profile"} <= names
        assert len(names) == 14  # 12 prior + these 2


async def test_get_financials_tool() -> None:
    df = make_financials_df(INCOME, ["2024-09-30", "2023-09-30"])
    server = create_server(
        yf_client=make_client(factory=fake_ticker_factory(financials={"income_stmt": df}))
    )
    async with Client(server) as client:
        result = await client.call_tool(
            "get_financials", {"ticker": "AAPL", "statement": "income", "period": "annual"}
        )
        assert result.data.period_ends == ["2024-09-30", "2023-09-30"]
        assert result.data.line_items["Total Revenue"] == [400.0, 380.0]


async def test_get_financials_tool_line_items_filter() -> None:
    df = make_financials_df(INCOME, ["2024-09-30", "2023-09-30"])
    server = create_server(
        yf_client=make_client(factory=fake_ticker_factory(financials={"income_stmt": df}))
    )
    async with Client(server) as client:
        result = await client.call_tool(
            "get_financials",
            {
                "ticker": "AAPL",
                "statement": "income",
                "period": "annual",
                "line_items": ["Net Income"],
            },
        )
        assert list(result.data.line_items.keys()) == ["Net Income"]


async def test_get_company_profile_tool() -> None:
    div = make_series(["2024-02-01", "2024-05-01"], [0.24, 0.25])
    spl = make_series(["2020-08-31"], [4.0])
    server = create_server(
        yf_client=make_client(
            factory=fake_ticker_factory(info=FULL_INFO, dividends=div, splits=spl)
        )
    )
    async with Client(server) as client:
        result = await client.call_tool("get_company_profile", {"ticker": "AAPL"})
        assert result.data.sector == "Technology"
        assert len(result.data.recent_dividends) == 2 and result.data.splits[0].ratio == 4.0


async def test_get_financials_tool_invalid_errors() -> None:
    import pandas as pd

    server = create_server(
        yf_client=make_client(
            factory=fake_ticker_factory(financials={"income_stmt": pd.DataFrame()})
        )
    )
    async with Client(server) as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "get_financials", {"ticker": "BAD", "statement": "income", "period": "annual"}
            )


async def test_get_company_profile_tool_invalid_errors() -> None:
    from finance_mcp.data.errors import DataUnavailable

    def _factory(_symbol: str) -> object:
        raise DataUnavailable("no profile")

    server = create_server(yf_client=make_client(factory=_factory))
    async with Client(server) as client:
        with pytest.raises(ToolError):
            await client.call_tool("get_company_profile", {"ticker": "BAD"})
