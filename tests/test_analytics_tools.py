import pandas as pd
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from finance_mcp.server import create_server
from tests.conftest import fake_ticker_factory, make_client, make_history_df

METRICS_INFO = {
    "longName": "Apple Inc.",
    "trailingPE": 37.73,
    "profitMargins": 0.271,
    "returnOnEquity": 1.41,
    "debtToEquity": 79.55,
    "freeCashflow": 101090746368,
}


async def test_analytics_tools_registered() -> None:
    server = create_server(yf_client=make_client(factory=fake_ticker_factory(info=METRICS_INFO)))
    async with Client(server) as client:
        names = {t.name for t in await client.list_tools()}
        assert {"get_key_metrics", "analyze_performance"} <= names
        assert len(names) == 19  # 18 prior + get_news


async def test_get_key_metrics_tool() -> None:
    server = create_server(yf_client=make_client(factory=fake_ticker_factory(info=METRICS_INFO)))
    async with Client(server) as client:
        result = await client.call_tool("get_key_metrics", {"ticker": "AAPL"})
        assert result.data.trailing_pe == 37.73 and result.data.profit_margins == 0.271


async def test_analyze_performance_tool() -> None:
    df = make_history_df([100.0, 110.0, 99.0])
    server = create_server(yf_client=make_client(factory=fake_ticker_factory(history_df=df)))
    async with Client(server) as client:
        result = await client.call_tool("analyze_performance", {"ticker": "AAPL", "period": "1mo"})
        assert result.data.bars == 3
        assert result.data.total_return_percent == pytest.approx(-1.0)


async def test_get_key_metrics_tool_invalid_errors() -> None:
    server = create_server(yf_client=make_client(factory=fake_ticker_factory(info={"x": 1})))
    async with Client(server) as client:
        with pytest.raises(ToolError):
            await client.call_tool("get_key_metrics", {"ticker": "BAD"})


async def test_analyze_performance_tool_invalid_errors() -> None:
    server = create_server(
        yf_client=make_client(factory=fake_ticker_factory(history_df=pd.DataFrame()))
    )
    async with Client(server) as client:
        with pytest.raises(ToolError):
            await client.call_tool("analyze_performance", {"ticker": "BAD", "period": "1y"})
