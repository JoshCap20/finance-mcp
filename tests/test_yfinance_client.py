from finance_mcp.data.errors import DataUnavailable, SymbolNotFound
from finance_mcp.data.models import PriceBar, PriceHistory, PriceSummary, Quote


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
