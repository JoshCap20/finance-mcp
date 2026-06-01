import math
from types import SimpleNamespace
from typing import Any, Literal

import pandas as pd
import pytest
from yfinance.exceptions import YFException

from finance_mcp.data.errors import DataUnavailable, SymbolNotFound
from finance_mcp.data.models import (
    CompanyProfile,
    DividendEvent,
    FinancialStatement,
    KeyMetrics,
    PriceBar,
    PriceHistory,
    PriceSummary,
    Quote,
    SplitEvent,
)
from finance_mcp.data.yfinance_client import YFinanceClient
from tests.conftest import (
    FakeClock,
    fake_ticker_factory,
    make_financials_df,
    make_history_df,
    make_series,
)


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


def test_fundamentals_and_profile_models() -> None:
    stmt = FinancialStatement(
        symbol="AAPL",
        statement="income",
        period="annual",
        period_ends=["2024-09-30", "2023-09-30"],
        line_items={"Total Revenue": [391_035.0, None]},
    )
    assert stmt.statement == "income"
    assert stmt.period == "annual"
    assert stmt.period_ends[0] == "2024-09-30"
    assert stmt.line_items["Total Revenue"] == [391_035.0, None]

    profile = CompanyProfile(
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        market_cap=3.0e12,
        recent_dividends=[DividendEvent(date="2024-08-12", amount=0.25)],
        splits=[SplitEvent(date="2020-08-31", ratio=4.0)],
    )
    assert profile.symbol == "AAPL"
    assert profile.name == "Apple Inc."
    assert profile.recent_dividends[0].amount == 0.25
    assert profile.splits[0].ratio == 4.0

    empty = CompanyProfile(symbol="MSFT")
    assert empty.recent_dividends == []
    assert empty.splits == []
    assert empty.name is None


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
    client = _client(
        factory=fake_ticker_factory(fast_info_error=YFException("yahoo says: rate limited"))
    )
    with pytest.raises(DataUnavailable) as exc:
        client.get_quote(["AAPL"])
    assert "yahoo says: rate limited" in str(exc.value)


def test_get_quote_invalid_symbol_returns_clean_symbol_not_found() -> None:
    client = _client(factory=fake_ticker_factory(fast_info_error=KeyError("exchangeTimezoneName")))
    with pytest.raises(SymbolNotFound) as exc:
        client.get_quote(["BAD"])
    assert "No quote data for 'BAD'" in str(exc.value)
    assert "exchangeTimezoneName" not in str(exc.value)


def test_get_quote_none_price_is_symbol_not_found() -> None:
    client = _client(factory=fake_ticker_factory(fast_info={"last_price": None}))
    with pytest.raises(SymbolNotFound) as exc:
        client.get_quote(["BAD"])
    assert "No quote data for" in str(exc.value)


def test_get_quote_no_second_network_call_on_failure() -> None:
    calls = {"history": 0}

    class _Ticker:
        @property
        def fast_info(self) -> Any:
            raise KeyError("x")

        def history(self, **_kwargs: Any) -> Any:
            calls["history"] += 1
            return None

    def factory(_symbol: str) -> Any:
        return _Ticker()

    client = _client(factory=factory)
    with pytest.raises(SymbolNotFound):
        client.get_quote(["BAD"])
    assert calls["history"] == 0


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
        raise YFException("boom")


def test_get_quote_fast_info_attr_error_becomes_data_unavailable() -> None:
    df = make_history_df([100.0])

    def factory(_symbol: str) -> Any:
        return SimpleNamespace(fast_info=_RaisingCurrencyFastInfo(), history=lambda **_k: df)

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


INCOME = {  # rows: label -> [most-recent, prior]
    "Total Revenue": [400.0, 380.0],
    "Net Income": [100.0, float("nan")],
}


def _fin_client(**kw: Any) -> YFinanceClient:
    factory = kw.pop("factory")
    return YFinanceClient(
        ticker_factory=factory,
        time_fn=FakeClock(),
        quote_ttl=30.0,
        history_ttl=300.0,
        fundamentals_ttl=3600.0,
    )


def test_get_financials_parses_periods_and_line_items() -> None:
    df = make_financials_df(INCOME, ["2024-09-30", "2023-09-30"])
    client = _fin_client(factory=fake_ticker_factory(financials={"income_stmt": df}))
    fs = client.get_financials("AAPL", "income", "annual")
    assert fs.symbol == "AAPL" and fs.statement == "income" and fs.period == "annual"
    assert fs.period_ends == ["2024-09-30", "2023-09-30"]
    assert fs.line_items["Total Revenue"] == [400.0, 380.0]
    assert fs.line_items["Net Income"] == [100.0, None]  # NaN -> None


def test_get_financials_line_items_filter() -> None:
    df = make_financials_df(INCOME, ["2024-09-30", "2023-09-30"])
    client = _fin_client(factory=fake_ticker_factory(financials={"income_stmt": df}))
    fs = client.get_financials("AAPL", "income", "annual", line_items=["Total Revenue", "Nope"])
    assert list(fs.line_items.keys()) == ["Total Revenue"]  # only matching labels, "Nope" dropped


def test_get_financials_quarterly_attr() -> None:
    df = make_financials_df({"Total Revenue": [100.0]}, ["2025-03-31"])
    client = _fin_client(factory=fake_ticker_factory(financials={"quarterly_balance_sheet": df}))
    fs = client.get_financials("AAPL", "balance", "quarterly")
    assert fs.period_ends == ["2025-03-31"]


def test_get_financials_empty_raises_symbol_not_found() -> None:
    client = _fin_client(factory=fake_ticker_factory(financials={"income_stmt": pd.DataFrame()}))
    with pytest.raises(SymbolNotFound):
        client.get_financials("BAD", "income", "annual")


def test_get_financials_fetch_error_is_data_unavailable() -> None:
    client = _fin_client(factory=fake_ticker_factory(financials_error=RuntimeError("yahoo down")))
    with pytest.raises(DataUnavailable) as exc:
        client.get_financials("AAPL", "income", "annual")
    assert "yahoo down" in str(exc.value)


def test_get_financials_parse_error_is_data_unavailable() -> None:
    # Non-datetime columns make `col.date()` raise inside the parse block.
    df = pd.DataFrame({"a": [1.0], "b": [2.0]}, index=["Total Revenue"])
    client = _fin_client(factory=fake_ticker_factory(financials={"income_stmt": df}))
    with pytest.raises(DataUnavailable) as exc:
        client.get_financials("AAPL", "income", "annual")
    assert "AAPL" in str(exc.value)


def test_get_financials_cached_within_ttl() -> None:
    calls = {"n": 0}
    df = make_financials_df(INCOME, ["2024-09-30", "2023-09-30"])

    def counting(symbol: str) -> Any:
        calls["n"] += 1
        return fake_ticker_factory(financials={"income_stmt": df})(symbol)

    clock = FakeClock()
    client = YFinanceClient(
        ticker_factory=counting,
        time_fn=clock,
        quote_ttl=30.0,
        history_ttl=300.0,
        fundamentals_ttl=3600.0,
    )
    client.get_financials("AAPL", "income", "annual")
    client.get_financials("AAPL", "income", "annual")
    assert calls["n"] == 1
    clock.advance(3601.0)
    client.get_financials("AAPL", "income", "annual")
    assert calls["n"] == 2


FULL_INFO = {
    "longName": "Apple Inc.",
    "shortName": "Apple",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "country": "United States",
    "website": "https://www.apple.com",
    "fullTimeEmployees": 166000,
    "longBusinessSummary": "Apple designs phones.",
    "currency": "USD",
    "marketCap": 4.5e12,
    "trailingPE": 37.7,
    "forwardPE": 32.5,
    "dividendYield": 0.35,
    "beta": 1.06,
}


def _profile_client(**kw: Any) -> YFinanceClient:
    factory = kw.pop("factory")
    return YFinanceClient(
        ticker_factory=factory,
        time_fn=FakeClock(),
        quote_ttl=30.0,
        history_ttl=300.0,
        fundamentals_ttl=3600.0,
    )


def test_get_company_profile_maps_fields() -> None:
    client = _profile_client(factory=fake_ticker_factory(info=FULL_INFO))
    p = client.get_company_profile("AAPL")
    assert p.symbol == "AAPL"
    assert p.name == "Apple Inc." and p.sector == "Technology"
    assert p.industry == "Consumer Electronics" and p.country == "United States"
    assert p.employees == 166000 and p.currency == "USD"
    assert p.market_cap == 4.5e12 and p.trailing_pe == 37.7 and p.beta == 1.06
    assert p.summary == "Apple designs phones."


def test_get_company_profile_name_falls_back_to_short_name() -> None:
    info = {"shortName": "Apple", "sector": "Tech"}
    client = _profile_client(factory=fake_ticker_factory(info=info))
    assert client.get_company_profile("AAPL").name == "Apple"


def test_get_company_profile_recent_dividends_capped_at_8() -> None:
    dates = [f"2023-{m:02d}-01" for m in range(1, 13)]  # 12 dividends
    div = make_series(dates, [0.20 + i * 0.01 for i in range(12)])
    client = _profile_client(factory=fake_ticker_factory(info=FULL_INFO, dividends=div))
    p = client.get_company_profile("AAPL")
    assert len(p.recent_dividends) == 8  # only most recent 8
    assert p.recent_dividends[-1].date == "2023-12-01"  # newest last
    assert p.recent_dividends[0].date == "2023-05-01"


def test_get_company_profile_all_splits() -> None:
    spl = make_series(["1987-06-16", "2000-06-21", "2020-08-31"], [2.0, 2.0, 4.0])
    client = _profile_client(factory=fake_ticker_factory(info=FULL_INFO, splits=spl))
    p = client.get_company_profile("AAPL")
    assert len(p.splits) == 3 and p.splits[-1].ratio == 4.0 and p.splits[-1].date == "2020-08-31"


def test_get_company_profile_missing_fields_are_none_and_empty() -> None:
    client = _profile_client(factory=fake_ticker_factory(info={"longName": "X Corp"}))
    p = client.get_company_profile("X")
    assert p.name == "X Corp" and p.sector is None and p.market_cap is None
    assert p.recent_dividends == [] and p.splits == []


def test_get_company_profile_no_name_raises_symbol_not_found() -> None:
    client = _profile_client(factory=fake_ticker_factory(info={"trailingPegRatio": None}))
    with pytest.raises(SymbolNotFound):
        client.get_company_profile("BAD")


def test_get_company_profile_typed_error_is_data_unavailable() -> None:
    client = _profile_client(factory=fake_ticker_factory(info_error=YFException("rate limited")))
    with pytest.raises(DataUnavailable) as exc:
        client.get_company_profile("AAPL")
    assert "rate limited" in str(exc.value)


def test_get_company_profile_raw_error_is_symbol_not_found() -> None:
    client = _profile_client(factory=fake_ticker_factory(info_error=KeyError("boom")))
    with pytest.raises(SymbolNotFound):
        client.get_company_profile("AAPL")


def test_get_company_profile_skips_non_finite_dividends_and_splits() -> None:
    div = make_series(["2023-01-01", "2023-06-01"], [0.20, float("nan")])
    spl = make_series(["2000-06-21", "2020-08-31"], [float("inf"), 4.0])
    client = _profile_client(factory=fake_ticker_factory(info=FULL_INFO, dividends=div, splits=spl))
    p = client.get_company_profile("AAPL")
    assert [d.date for d in p.recent_dividends] == ["2023-01-01"]  # NaN dropped
    assert [s.date for s in p.splits] == ["2020-08-31"]  # inf dropped


def test_get_company_profile_parse_error_is_data_unavailable() -> None:
    # A non-datetime index makes `ts.date()` raise inside the parse block.
    bad_div = pd.Series([0.25], index=["not-a-date"], dtype=float)
    client = _profile_client(factory=fake_ticker_factory(info=FULL_INFO, dividends=bad_div))
    with pytest.raises(DataUnavailable) as exc:
        client.get_company_profile("AAPL")
    assert "AAPL" in str(exc.value)


def test_get_financials_filter_reuses_cached_fetch() -> None:
    calls = {"n": 0}
    df = make_financials_df(INCOME, ["2024-09-30", "2023-09-30"])

    def counting(symbol: str) -> object:
        calls["n"] += 1
        return fake_ticker_factory(financials={"income_stmt": df})(symbol)

    client = YFinanceClient(
        ticker_factory=counting,
        time_fn=FakeClock(),
        quote_ttl=30.0,
        history_ttl=300.0,
        fundamentals_ttl=3600.0,
    )
    full = client.get_financials("AAPL", "income", "annual")
    f1 = client.get_financials("AAPL", "income", "annual", line_items=["Total Revenue"])
    f2 = client.get_financials("AAPL", "income", "annual", line_items=["Net Income"])
    assert calls["n"] == 1  # one fetch; both filters reuse the cached statement
    assert list(f1.line_items) == ["Total Revenue"]
    assert list(f2.line_items) == ["Net Income"]
    assert set(full.line_items) == {"Total Revenue", "Net Income"}  # cached object un-mutated


def test_get_company_profile_nan_employees_nulled_not_fatal() -> None:
    info = {**FULL_INFO, "fullTimeEmployees": float("nan")}
    client = _profile_client(factory=fake_ticker_factory(info=info))
    p = client.get_company_profile("AAPL")
    assert p.employees is None  # junk field nulls; profile still returned
    assert p.name == "Apple Inc."


def test_get_company_profile_float_employees_coerced_to_int() -> None:
    info = {**FULL_INFO, "fullTimeEmployees": 166000.0}
    client = _profile_client(factory=fake_ticker_factory(info=info))
    assert client.get_company_profile("AAPL").employees == 166000


@pytest.mark.parametrize(
    ("statement", "period", "attr"),
    [
        ("income", "annual", "income_stmt"),
        ("income", "quarterly", "quarterly_income_stmt"),
        ("balance", "annual", "balance_sheet"),
        ("balance", "quarterly", "quarterly_balance_sheet"),
        ("cashflow", "annual", "cashflow"),
        ("cashflow", "quarterly", "quarterly_cashflow"),
    ],
)
def test_get_financials_all_statement_period_combos(
    statement: Literal["income", "balance", "cashflow"],
    period: Literal["annual", "quarterly"],
    attr: str,
) -> None:
    df = make_financials_df({"X": [1.0]}, ["2024-12-31"])
    client = _fin_client(factory=fake_ticker_factory(financials={attr: df}))
    fs = client.get_financials("AAPL", statement, period)
    assert fs.statement == statement and fs.period == period
    assert fs.period_ends == ["2024-12-31"] and fs.line_items["X"] == [1.0]


def test_get_quote_zero_previous_close_change_pct_none() -> None:
    fi = {**QUOTE_FI, "previous_close": 0.0}
    [q] = _client(factory=fake_ticker_factory(fast_info=fi)).get_quote(["AAPL"])
    assert q.change == pytest.approx(190.0) and q.change_percent is None and q.previous_close == 0.0


def test_get_price_history_caches_and_keys_on_interval() -> None:
    calls = {"n": 0}
    df = make_history_df([100.0, 101.0])

    def counting(symbol: str) -> object:
        calls["n"] += 1
        return fake_ticker_factory(history_df=df)(symbol)

    clock = FakeClock()
    client = YFinanceClient(
        ticker_factory=counting,
        time_fn=clock,
        quote_ttl=30.0,
        history_ttl=300.0,
        fundamentals_ttl=3600.0,
    )
    client.get_price_history("AAPL", "1mo", "1d")
    client.get_price_history("AAPL", "1mo", "1d")
    assert calls["n"] == 1
    client.get_price_history("AAPL", "1mo", "1wk")  # different interval -> distinct key
    assert calls["n"] == 2
    clock.advance(301.0)
    client.get_price_history("AAPL", "1mo", "1d")  # expired -> refetch
    assert calls["n"] == 3


def test_get_company_profile_caches_within_ttl() -> None:
    calls = {"n": 0}

    def counting(symbol: str) -> object:
        calls["n"] += 1
        return fake_ticker_factory(info=FULL_INFO)(symbol)

    clock = FakeClock()
    client = YFinanceClient(
        ticker_factory=counting,
        time_fn=clock,
        quote_ttl=30.0,
        history_ttl=300.0,
        fundamentals_ttl=3600.0,
    )
    client.get_company_profile("AAPL")
    client.get_company_profile("AAPL")
    assert calls["n"] == 1
    clock.advance(3601.0)
    client.get_company_profile("AAPL")
    assert calls["n"] == 2


def test_get_quote_empty_list_returns_empty() -> None:
    assert _client().get_quote([]) == []


def test_get_quote_batch_fails_if_any_symbol_missing() -> None:
    def factory(symbol: str) -> object:
        if symbol == "AAPL":
            return fake_ticker_factory(fast_info=QUOTE_FI)(symbol)
        return fake_ticker_factory(fast_info_error=KeyError("exchangeTimezoneName"))(symbol)

    with pytest.raises(SymbolNotFound) as exc:
        _client(factory=factory).get_quote(["AAPL", "MSFT"])
    assert "MSFT" in str(exc.value)


def test_get_price_history_single_bar() -> None:
    client = _client(factory=fake_ticker_factory(history_df=make_history_df([100.0])))
    h = client.get_price_history("AAPL", "1d", "1d")
    assert h.summary.bars == 1 and h.summary.total_return_percent == 0.0
    assert h.summary.start_date == h.summary.end_date and h.truncated is False


def test_get_quote_non_price_nan_fields_nulled() -> None:
    fi = {**QUOTE_FI, "market_cap": float("nan"), "last_volume": float("nan")}
    [q] = _client(factory=fake_ticker_factory(fast_info=fi)).get_quote(["AAPL"])
    assert q.price == 190.0 and q.market_cap is None and q.volume is None


def test_get_company_profile_empty_long_name_uses_short_name() -> None:
    factory = fake_ticker_factory(info={"longName": "", "shortName": "Apple"})
    client = _profile_client(factory=factory)
    assert client.get_company_profile("AAPL").name == "Apple"


def test_get_financials_line_items_preserve_order() -> None:
    df = make_financials_df(INCOME, ["2024-09-30", "2023-09-30"])
    client = _fin_client(factory=fake_ticker_factory(financials={"income_stmt": df}))
    fs = client.get_financials(
        "AAPL", "income", "annual", line_items=["Net Income", "Total Revenue"]
    )
    assert list(fs.line_items) == ["Net Income", "Total Revenue"]


def test_get_financials_line_items_all_miss_empty() -> None:
    df = make_financials_df(INCOME, ["2024-09-30", "2023-09-30"])
    client = _fin_client(factory=fake_ticker_factory(financials={"income_stmt": df}))
    fs = client.get_financials("AAPL", "income", "annual", line_items=["Nonexistent"])
    assert fs.line_items == {}


def test_get_company_profile_dividends_below_cap_returns_all() -> None:
    div = make_series(["2023-02-01", "2023-05-01", "2023-08-01"], [0.23, 0.24, 0.25])
    client = _profile_client(factory=fake_ticker_factory(info=FULL_INFO, dividends=div))
    p = client.get_company_profile("AAPL")
    assert [d.date for d in p.recent_dividends] == ["2023-02-01", "2023-05-01", "2023-08-01"]


METRICS_INFO = {
    "longName": "Apple Inc.",
    "trailingPE": 37.73,
    "forwardPE": 32.48,
    "priceToBook": 42.98,
    "priceToSalesTrailing12Months": 10.15,
    "pegRatio": 2.72,
    "enterpriseValue": 4599540350976,
    "enterpriseToEbitda": 28.75,
    "enterpriseToRevenue": 10.19,
    "returnOnEquity": 1.41,
    "returnOnAssets": 0.26,
    "grossMargins": 0.478,
    "operatingMargins": 0.322,
    "profitMargins": 0.271,
    "ebitdaMargins": 0.354,
    "debtToEquity": 79.55,
    "currentRatio": 1.07,
    "quickRatio": 0.906,
    "totalDebt": 84710998016,
    "totalCash": 68507000832,
    "freeCashflow": 101090746368,
    "ebitda": 159975997440,
    "trailingEps": 8.27,
    "forwardEps": 9.61,
    "revenuePerShare": 30.53,
    "bookValue": 7.26,
}


def _metrics_client(**kw: Any) -> YFinanceClient:
    factory = kw.pop("factory")
    return YFinanceClient(
        ticker_factory=factory,
        time_fn=FakeClock(),
        quote_ttl=30.0,
        history_ttl=300.0,
        fundamentals_ttl=3600.0,
    )


def test_get_key_metrics_maps_fields() -> None:
    m = _metrics_client(factory=fake_ticker_factory(info=METRICS_INFO)).get_key_metrics("AAPL")
    assert isinstance(m, KeyMetrics)
    assert m.symbol == "AAPL"
    assert m.trailing_pe == 37.73 and m.forward_pe == 32.48 and m.price_to_book == 42.98
    assert m.price_to_sales == 10.15 and m.peg_ratio == 2.72
    assert m.enterprise_value == 4599540350976 and m.ev_to_ebitda == 28.75
    assert m.ev_to_revenue == 10.19
    assert m.return_on_equity == 1.41 and m.return_on_assets == 0.26
    assert m.gross_margins == 0.478 and m.operating_margins == 0.322
    assert m.profit_margins == 0.271 and m.ebitda_margins == 0.354
    assert m.debt_to_equity == 79.55 and m.current_ratio == 1.07 and m.quick_ratio == 0.906
    assert m.total_debt == 84710998016 and m.total_cash == 68507000832
    assert m.free_cashflow == 101090746368 and m.ebitda == 159975997440
    assert m.trailing_eps == 8.27 and m.forward_eps == 9.61
    assert m.revenue_per_share == 30.53 and m.book_value == 7.26


def test_get_key_metrics_missing_and_nan_are_none() -> None:
    info = {"longName": "X Corp", "trailingPE": float("nan")}
    m = _metrics_client(factory=fake_ticker_factory(info=info)).get_key_metrics("X")
    assert m.symbol == "X" and m.trailing_pe is None
    assert m.ebitda is None and m.profit_margins is None


def test_get_key_metrics_no_name_raises_symbol_not_found() -> None:
    client = _metrics_client(factory=fake_ticker_factory(info={"trailingPegRatio": None}))
    with pytest.raises(SymbolNotFound):
        client.get_key_metrics("BAD")


def test_get_key_metrics_typed_error_is_data_unavailable() -> None:
    client = _metrics_client(factory=fake_ticker_factory(info_error=YFException("rate limited")))
    with pytest.raises(DataUnavailable) as exc:
        client.get_key_metrics("AAPL")
    assert "rate limited" in str(exc.value)


def test_get_key_metrics_raw_error_is_symbol_not_found() -> None:
    client = _metrics_client(factory=fake_ticker_factory(info_error=KeyError("boom")))
    with pytest.raises(SymbolNotFound):
        client.get_key_metrics("AAPL")


def test_get_key_metrics_mapping_failure_is_data_unavailable() -> None:
    # A value that survives the name check but fails float() coercion in mapping.
    info = {"longName": "Apple Inc.", "trailingPE": object()}
    client = _metrics_client(factory=fake_ticker_factory(info=info))
    with pytest.raises(DataUnavailable) as exc:
        client.get_key_metrics("AAPL")
    assert "Failed to parse metrics for 'AAPL'" in str(exc.value)


def test_get_key_metrics_caches_within_ttl() -> None:
    calls = {"n": 0}

    def counting(symbol: str) -> object:
        calls["n"] += 1
        return fake_ticker_factory(info=METRICS_INFO)(symbol)

    clock = FakeClock()
    client = YFinanceClient(
        ticker_factory=counting,
        time_fn=clock,
        quote_ttl=30.0,
        history_ttl=300.0,
        fundamentals_ttl=3600.0,
    )
    client.get_key_metrics("AAPL")
    client.get_key_metrics("AAPL")
    assert calls["n"] == 1
    clock.advance(3601.0)
    client.get_key_metrics("AAPL")
    assert calls["n"] == 2
