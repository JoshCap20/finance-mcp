import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from yfinance.exceptions import YFException

from finance_mcp.server import create_server
from tests.conftest import fake_ticker_factory, make_client, make_history_df

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
