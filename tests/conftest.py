"""Shared pytest fixtures."""

from collections.abc import AsyncIterator, Callable
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport

from finance_mcp.data.yfinance_client import YFinanceClient
from finance_mcp.server import create_server


@pytest.fixture
async def client() -> AsyncIterator[Client[FastMCPTransport]]:
    """An in-memory MCP client connected to a fresh finance-mcp server."""
    async with Client(create_server()) as connected:
        yield connected


class FakeClock:
    """Mutable monotonic clock for deterministic TTL tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_history_df(closes: list[float]) -> pd.DataFrame:
    idx = pd.to_datetime([f"2024-01-{i + 1:02d}" for i in range(len(closes))])
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 1 for c in closes],
            "Low": [c - 1 for c in closes],
            "Close": closes,
            "Volume": [1000 * (i + 1) for i in range(len(closes))],
        },
        index=idx,
    )


def fake_ticker_factory(
    fast_info: dict[str, Any] | None = None,
    history_df: pd.DataFrame | None = None,
    error: Exception | None = None,
    fast_info_error: Exception | None = None,
    history_error: Exception | None = None,
) -> Callable[[str], Any]:
    """Build a ticker factory returning a stub Ticker for any symbol.

    The legacy ``error`` makes BOTH ``.fast_info`` access and ``.history()`` raise it.
    ``fast_info_error`` makes only ``.fast_info`` access raise; ``history_error`` makes
    only ``.history()`` raise. These compose so combined scenarios can be expressed.
    """
    fi_exc = fast_info_error or error
    hist_exc = history_error or error

    class _Ticker:
        @property
        def fast_info(self) -> Any:
            if fi_exc is not None:
                raise fi_exc
            return SimpleNamespace(**(fast_info or {}))

        def history(self, **_kwargs: Any) -> Any:
            if hist_exc is not None:
                raise hist_exc
            return history_df if history_df is not None else pd.DataFrame()

    def factory(_symbol: str) -> Any:
        return _Ticker()

    return factory


def make_client(**kw: Any) -> YFinanceClient:
    factory = kw.pop("factory")
    return YFinanceClient(
        ticker_factory=factory, time_fn=FakeClock(), quote_ttl=30.0, history_ttl=300.0
    )
