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
    idx = pd.to_datetime(pd.date_range("2024-01-01", periods=len(closes), freq="D"))
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


def make_financials_df(rows: dict[str, list[float]], period_ends: list[str]) -> pd.DataFrame:
    """rows = {line_item_label: [values most-recent-first]}; columns are the period-end dates."""
    return pd.DataFrame.from_dict(rows, orient="index", columns=pd.to_datetime(period_ends))


def make_series(dates: list[str], values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.to_datetime(dates), dtype=float)


def fake_ticker_factory(
    fast_info: dict[str, Any] | None = None,
    history_df: pd.DataFrame | None = None,
    error: Exception | None = None,
    fast_info_error: Exception | None = None,
    history_error: Exception | None = None,
    financials: dict[str, Any] | None = None,
    financials_error: Exception | None = None,
    info: dict[str, Any] | None = None,
    dividends: pd.Series | None = None,
    splits: pd.Series | None = None,
    info_error: Exception | None = None,
    recommendations: pd.DataFrame | None = None,
) -> Callable[[str], Any]:
    """Build a ticker factory returning a stub Ticker for any symbol.

    The legacy ``error`` makes BOTH ``.fast_info`` access and ``.history()`` raise it.
    ``fast_info_error`` makes only ``.fast_info`` access raise; ``history_error`` makes
    only ``.history()`` raise. These compose so combined scenarios can be expressed.

    ``financials`` maps a yfinance financials attribute name (e.g. ``"income_stmt"``,
    ``"quarterly_balance_sheet"``) to the DataFrame the stub returns for that attribute.
    ``financials_error`` makes access to any of those financials attributes raise it.
    """
    fi_exc = fast_info_error or error
    hist_exc = history_error or error
    financials_map = financials or {}
    _FINANCIALS_ATTRS = frozenset(
        {
            "income_stmt",
            "quarterly_income_stmt",
            "balance_sheet",
            "quarterly_balance_sheet",
            "cashflow",
            "quarterly_cashflow",
        }
    )

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

        @property
        def info(self) -> Any:
            if info_error is not None:
                raise info_error
            return info if info is not None else {}

        @property
        def dividends(self) -> Any:
            return dividends if dividends is not None else pd.Series(dtype=float)

        @property
        def splits(self) -> Any:
            return splits if splits is not None else pd.Series(dtype=float)

        @property
        def recommendations(self) -> Any:
            return recommendations if recommendations is not None else pd.DataFrame()

        def __getattr__(self, name: str) -> Any:
            if name in _FINANCIALS_ATTRS:
                if financials_error is not None:
                    raise financials_error
                return financials_map.get(name, pd.DataFrame())
            raise AttributeError(name)

    def factory(_symbol: str) -> Any:
        return _Ticker()

    return factory


def make_recommendations_df(
    rows: list[tuple[str, int, int, int, int, int]],
) -> pd.DataFrame:
    """Build a yfinance-shaped recommendations frame.

    Each row is (period, strongBuy, buy, hold, sell, strongSell).
    """
    return pd.DataFrame(rows, columns=["period", "strongBuy", "buy", "hold", "sell", "strongSell"])


def fake_search_factory(
    quotes: list[dict[str, Any]] | None = None,
    error: Exception | None = None,
) -> Callable[[str], Any]:
    """Return a callable that mimics ``yf.Search``.

    The returned callable accepts ``(query, **kwargs)``; if ``error`` is set it
    raises it, otherwise it returns an object whose ``.quotes`` attribute is
    ``quotes or []``.
    """

    def _search(query: str, **kwargs: Any) -> Any:
        if error is not None:
            raise error
        return SimpleNamespace(quotes=quotes or [])

    return _search


def make_client(**kw: Any) -> YFinanceClient:
    factory = kw.pop("factory")
    search = kw.pop("search_factory", None)
    extra: dict[str, Any] = {}
    if search is not None:
        extra["search_factory"] = search
    return YFinanceClient(
        ticker_factory=factory, time_fn=FakeClock(), quote_ttl=30.0, history_ttl=300.0, **extra
    )
