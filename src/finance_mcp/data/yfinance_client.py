"""Cached, error-surfacing wrapper over yfinance. No MCP imports.

Network access is isolated here. yfinance errors and empty results become
DataUnavailable/SymbolNotFound whose message is surfaced to the caller verbatim,
because we cannot enumerate every Yahoo failure mode.
"""

import math
import time
from collections.abc import Callable
from typing import Any, Literal, cast

import yfinance as yf
from yfinance.exceptions import YFException

from finance_mcp.data.errors import DataUnavailable, SymbolNotFound
from finance_mcp.data.models import (
    FinancialStatement,
    PriceBar,
    PriceHistory,
    PriceSummary,
    Quote,
)

DEFAULT_MAX_BARS = 260

_FINANCIALS_ATTR = {
    ("income", "annual"): "income_stmt",
    ("income", "quarterly"): "quarterly_income_stmt",
    ("balance", "annual"): "balance_sheet",
    ("balance", "quarterly"): "quarterly_balance_sheet",
    ("cashflow", "annual"): "cashflow",
    ("cashflow", "quarterly"): "quarterly_cashflow",
}


class YFinanceClient:
    """Thin yfinance facade with a per-key TTL cache."""

    def __init__(
        self,
        ticker_factory: Callable[[str], Any] = yf.Ticker,
        time_fn: Callable[[], float] = time.monotonic,
        quote_ttl: float = 30.0,
        history_ttl: float = 300.0,
        fundamentals_ttl: float = 3600.0,
        max_bars: int = DEFAULT_MAX_BARS,
    ) -> None:
        self._ticker = ticker_factory
        self._now = time_fn
        self._quote_ttl = quote_ttl
        self._history_ttl = history_ttl
        self._fundamentals_ttl = fundamentals_ttl
        self._max_bars = max_bars
        self._cache: dict[tuple[str, ...], tuple[float, Any]] = {}

    def _cached(self, key: tuple[str, ...], ttl: float, fetch: Callable[[], Any]) -> Any:
        hit = self._cache.get(key)
        now = self._now()
        if hit is not None and now - hit[0] < ttl:
            return hit[1]
        value = fetch()
        self._cache[key] = (now, value)
        return value

    def get_quote(self, symbols: list[str]) -> list[Quote]:
        def fetch(sym: str) -> Callable[[], Quote]:
            return lambda: self._fetch_quote(sym)

        return [cast(Quote, self._cached(("quote", s), self._quote_ttl, fetch(s))) for s in symbols]

    def _fetch_quote(self, symbol: str) -> Quote:
        try:
            fi = self._ticker(symbol).fast_info
            price = _opt(getattr(fi, "last_price", None))
            prev = _opt(getattr(fi, "previous_close", None))
            currency = getattr(fi, "currency", None)
            day_high = _opt(getattr(fi, "day_high", None))
            day_low = _opt(getattr(fi, "day_low", None))
            year_high = _opt(getattr(fi, "year_high", None))
            year_low = _opt(getattr(fi, "year_low", None))
            market_cap = _opt(getattr(fi, "market_cap", None))
            volume = _opt(getattr(fi, "last_volume", None))
        except YFException as exc:
            # yfinance's own typed errors (rate limit, etc.) — surface verbatim.
            raise DataUnavailable(f"Failed to fetch quote for '{symbol}': {exc}") from exc
        except Exception as exc:
            # fast_info leaks raw errors (e.g. KeyError) for symbols with no data.
            raise SymbolNotFound(
                f"No quote data for '{symbol}'. The symbol may be invalid or delisted."
            ) from exc
        if price is None:
            raise SymbolNotFound(
                f"No quote data for '{symbol}'. The symbol may be invalid or delisted."
            )
        change = (price - prev) if prev is not None else None
        change_pct = (change / prev * 100.0) if (change is not None and prev) else None
        return Quote(
            symbol=symbol,
            currency=currency,
            price=price,
            previous_close=prev,
            change=change,
            change_percent=change_pct,
            day_high=day_high,
            day_low=day_low,
            year_high=year_high,
            year_low=year_low,
            market_cap=market_cap,
            volume=volume,
        )

    def get_price_history(self, symbol: str, period: str, interval: str) -> PriceHistory:
        return cast(
            PriceHistory,
            self._cached(
                ("history", symbol, period, interval),
                self._history_ttl,
                lambda: self._fetch_history(symbol, period, interval),
            ),
        )

    def _fetch_history(self, symbol: str, period: str, interval: str) -> PriceHistory:
        try:
            df = self._ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
        except Exception as exc:  # surface any yfinance failure verbatim
            raise DataUnavailable(f"Failed to fetch history for '{symbol}': {exc}") from exc
        if df is None or df.empty:
            raise SymbolNotFound(
                f"No price history for '{symbol}'. Check the symbol/period/interval."
            )
        try:
            all_bars: list[PriceBar] = []
            for idx, row in df.iterrows():
                o, h, low, c, v = (
                    float(row["Open"]),
                    float(row["High"]),
                    float(row["Low"]),
                    float(row["Close"]),
                    float(row["Volume"]),
                )
                if any(not math.isfinite(x) for x in (o, h, low, c, v)):
                    continue
                all_bars.append(
                    PriceBar(
                        date=idx.date().isoformat(), open=o, high=h, low=low, close=c, volume=v
                    )
                )
            if not all_bars:
                raise SymbolNotFound(
                    f"No price history for '{symbol}'. Check the symbol/period/interval."
                )
            start_close = all_bars[0].close
            total_return = (
                ((all_bars[-1].close / start_close - 1.0) * 100.0) if start_close else 0.0
            )
            summary = PriceSummary(
                start_date=all_bars[0].date,
                end_date=all_bars[-1].date,
                start_close=start_close,
                end_close=all_bars[-1].close,
                total_return_percent=total_return,
                period_high=max(b.high for b in all_bars),
                period_low=min(b.low for b in all_bars),
                bars=len(all_bars),
            )
            truncated = len(all_bars) > self._max_bars
            bars = all_bars[-self._max_bars :] if truncated else all_bars
            return PriceHistory(
                symbol=symbol,
                period=period,
                interval=interval,
                bars=bars,
                summary=summary,
                truncated=truncated,
            )
        except SymbolNotFound:
            raise
        except Exception as exc:  # surface any parsing failure verbatim
            raise DataUnavailable(f"Failed to parse history for '{symbol}': {exc}") from exc

    def get_financials(
        self,
        symbol: str,
        statement: Literal["income", "balance", "cashflow"],
        period: Literal["annual", "quarterly"],
        line_items: list[str] | None = None,
    ) -> FinancialStatement:
        full = cast(
            FinancialStatement,
            self._cached(
                ("financials", symbol, statement, period),
                self._fundamentals_ttl,
                lambda: self._fetch_financials(symbol, statement, period),
            ),
        )
        if line_items is None:
            return full
        wanted = {li: full.line_items[li] for li in line_items if li in full.line_items}
        return full.model_copy(update={"line_items": wanted})

    def _fetch_financials(
        self,
        symbol: str,
        statement: Literal["income", "balance", "cashflow"],
        period: Literal["annual", "quarterly"],
    ) -> FinancialStatement:
        attr = _FINANCIALS_ATTR[(statement, period)]
        try:
            df = getattr(self._ticker(symbol), attr)
        except Exception as exc:  # surface any yfinance failure verbatim
            raise DataUnavailable(
                f"Failed to fetch {statement} statement for '{symbol}': {exc}"
            ) from exc
        if df is None or df.empty:
            raise SymbolNotFound(
                f"No {statement} statement for '{symbol}'. Check the ticker symbol."
            )
        try:
            period_ends = [col.date().isoformat() for col in df.columns]
            line_items: dict[str, list[float | None]] = {
                str(idx): [_opt(v) for v in row] for idx, row in df.iterrows()
            }
            return FinancialStatement(
                symbol=symbol,
                statement=statement,
                period=period,
                period_ends=period_ends,
                line_items=line_items,
            )
        except Exception as exc:  # surface any parsing failure verbatim
            raise DataUnavailable(
                f"Failed to parse {statement} statement for '{symbol}': {exc}"
            ) from exc


def _opt(value: Any) -> float | None:
    if value is None:
        return None
    f = float(value)
    return f if math.isfinite(f) else None
