import math
from types import SimpleNamespace
from typing import Any

import pytest

from finance_mcp.data.errors import DataUnavailable, SymbolNotFound
from finance_mcp.data.models import PriceBar, PriceHistory, PriceSummary, Quote
from finance_mcp.data.yfinance_client import YFinanceClient
from tests.conftest import FakeClock, fake_ticker_factory, make_history_df


def test_models_and_errors_exist() -> None:
    q = Quote(
        symbol="AAPL",
        currency="USD",
        price=190.0,
        previous_close=188.0,
        change=2.0,
        change_percent=1.06,
        day_high=191.0,
        day_low=187.0,
        year_high=200.0,
        year_low=150.0,
        market_cap=3.0e12,
        volume=50_000_000,
    )
    assert q.symbol == "AAPL"
    bar = PriceBar(date="2024-01-02", open=1.0, high=2.0, low=0.5, close=1.5, volume=100)
    summary = PriceSummary(
        start_date="2024-01-02",
        end_date="2024-01-03",
        start_close=1.5,
        end_close=1.6,
        total_return_percent=6.67,
        period_high=2.0,
        period_low=0.5,
        bars=2,
    )
    hist = PriceHistory(
        symbol="AAPL", period="1mo", interval="1d", bars=[bar], summary=summary, truncated=False
    )
    assert hist.summary.bars == 2
    assert issubclass(SymbolNotFound, DataUnavailable)
    assert str(DataUnavailable("boom")) == "boom"


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


def _client(**kw: Any) -> YFinanceClient:
    clock = kw.pop("clock", FakeClock())
    factory = kw.pop("factory", fake_ticker_factory(fast_info=QUOTE_FI))
    return YFinanceClient(ticker_factory=factory, time_fn=clock, quote_ttl=30.0, history_ttl=300.0)


def test_get_quote_parses_and_computes_change() -> None:
    [q] = _client().get_quote(["AAPL"])
    assert q.symbol == "AAPL"
    assert q.price == 190.0
    assert q.change == pytest.approx(2.0)
    assert q.change_percent == pytest.approx(2.0 / 188.0 * 100.0)
    assert q.currency == "USD"


def test_get_quote_caches_within_ttl() -> None:
    calls = {"n": 0}

    def counting_factory(symbol: str) -> object:
        calls["n"] += 1
        return fake_ticker_factory(fast_info=QUOTE_FI)(symbol)

    clock = FakeClock()
    client = YFinanceClient(
        ticker_factory=counting_factory, time_fn=clock, quote_ttl=30.0, history_ttl=300.0
    )
    client.get_quote(["AAPL"])
    client.get_quote(["AAPL"])
    assert calls["n"] == 1
    clock.advance(31.0)
    client.get_quote(["AAPL"])
    assert calls["n"] == 2


def test_get_quote_missing_price_raises_symbol_not_found() -> None:
    client = _client(factory=fake_ticker_factory(fast_info={"last_price": None}))
    with pytest.raises(SymbolNotFound):
        client.get_quote(["BADSYM"])


def test_get_quote_surfaces_yfinance_error_message() -> None:
    client = _client(factory=fake_ticker_factory(error=RuntimeError("yahoo says: rate limited")))
    with pytest.raises(DataUnavailable) as exc:
        client.get_quote(["AAPL"])
    assert "yahoo says: rate limited" in str(exc.value)


def test_get_price_history_parses_bars_and_summary() -> None:
    df = make_history_df([100.0, 101.0, 102.0, 103.0])
    client = _client(factory=fake_ticker_factory(history_df=df))
    hist = client.get_price_history("AAPL", period="1mo", interval="1d")
    assert hist.summary.bars == 4
    assert hist.summary.start_close == 100.0
    assert hist.summary.end_close == 103.0
    assert hist.summary.total_return_percent == pytest.approx(3.0)
    assert hist.summary.period_high == 104.0
    assert hist.bars[-1].close == 103.0
    assert hist.truncated is False


def test_get_price_history_empty_raises_symbol_not_found() -> None:
    client = _client(factory=fake_ticker_factory(history_df=make_history_df([])))
    with pytest.raises(SymbolNotFound):
        client.get_price_history("BADSYM", period="1mo", interval="1d")


def test_get_price_history_truncates_to_max_bars() -> None:
    df = make_history_df([float(i) for i in range(1, 11)])
    client = YFinanceClient(
        ticker_factory=fake_ticker_factory(history_df=df),
        time_fn=FakeClock(),
        quote_ttl=30.0,
        history_ttl=300.0,
        max_bars=5,
    )
    hist = client.get_price_history("AAPL", period="1mo", interval="1d")
    assert len(hist.bars) == 5
    assert hist.truncated is True
    assert hist.summary.bars == 10


def test_get_quote_nan_price_raises_symbol_not_found() -> None:
    client = _client(
        factory=fake_ticker_factory(fast_info={"last_price": float("nan"), "previous_close": 188.0})
    )
    with pytest.raises(SymbolNotFound):
        client.get_quote(["AAPL"])


def test_get_quote_nan_previous_close_yields_none_change() -> None:
    fi = {**QUOTE_FI, "previous_close": float("nan")}
    client = _client(factory=fake_ticker_factory(fast_info=fi))
    [q] = client.get_quote(["AAPL"])
    assert q.price == 190.0
    assert q.change is None
    assert q.change_percent is None


def test_get_price_history_drops_nan_rows() -> None:
    df = make_history_df([100.0, 101.0, 102.0])
    df.loc[df.index[1], "Close"] = float("nan")
    client = _client(factory=fake_ticker_factory(history_df=df))
    hist = client.get_price_history("AAPL", period="1mo", interval="1d")
    assert hist.summary.bars == 2
    assert all(math.isfinite(b.close) for b in hist.bars)


def test_get_price_history_all_nan_raises() -> None:
    df = make_history_df([100.0])
    df.loc[df.index[0], "Close"] = float("nan")
    client = _client(factory=fake_ticker_factory(history_df=df))
    with pytest.raises(SymbolNotFound):
        client.get_price_history("AAPL", period="1mo", interval="1d")


def test_get_price_history_zero_start_close_no_crash() -> None:
    df = make_history_df([0.0, 5.0])
    client = _client(factory=fake_ticker_factory(history_df=df))
    hist = client.get_price_history("AAPL", period="1mo", interval="1d")
    assert hist.summary.total_return_percent == 0.0


def test_get_quote_inf_price_raises_symbol_not_found() -> None:
    client = _client(
        factory=fake_ticker_factory(fast_info={"last_price": float("inf"), "previous_close": 188.0})
    )
    with pytest.raises(SymbolNotFound):
        client.get_quote(["X"])


def test_get_price_history_drops_inf_rows() -> None:
    df = make_history_df([100.0, 101.0, 102.0])
    df.loc[df.index[1], "Close"] = float("inf")
    client = _client(factory=fake_ticker_factory(history_df=df))
    hist = client.get_price_history("AAPL", period="1mo", interval="1d")
    assert hist.summary.bars == 2


def test_get_price_history_all_inf_raises() -> None:
    df = make_history_df([100.0])
    df.loc[df.index[0], "Close"] = float("inf")
    client = _client(factory=fake_ticker_factory(history_df=df))
    with pytest.raises(SymbolNotFound):
        client.get_price_history("AAPL", period="1mo", interval="1d")


class _RaisingCurrencyFastInfo:
    """fast_info stub whose `currency` property raises, last_price is fine."""

    last_price = 190.0
    previous_close = 188.0

    @property
    def currency(self) -> str:
        raise RuntimeError("boom")


def test_get_quote_fast_info_attr_error_becomes_data_unavailable() -> None:
    def factory(_symbol: str) -> Any:
        return SimpleNamespace(fast_info=_RaisingCurrencyFastInfo())

    client = _client(factory=factory)
    with pytest.raises(DataUnavailable) as exc:
        client.get_quote(["X"])
    assert "boom" in str(exc.value)


def test_get_price_history_parse_error_becomes_data_unavailable() -> None:
    df = make_history_df([100.0, 101.0]).drop(columns=["Volume"])
    client = _client(factory=fake_ticker_factory(history_df=df))
    with pytest.raises(DataUnavailable) as exc:
        client.get_price_history("AAPL", period="1mo", interval="1d")
    assert "AAPL" in str(exc.value)


def test_get_quote_distinct_symbols_cached_independently() -> None:
    calls = {"n": 0}

    def counting_factory(symbol: str) -> object:
        calls["n"] += 1
        return fake_ticker_factory(fast_info=QUOTE_FI)(symbol)

    client = YFinanceClient(
        ticker_factory=counting_factory, time_fn=FakeClock(), quote_ttl=30.0, history_ttl=300.0
    )
    results = client.get_quote(["AAPL", "MSFT"])
    assert [r.symbol for r in results] == ["AAPL", "MSFT"]
    assert calls["n"] == 2
