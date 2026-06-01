# Finance MCP

An MCP server of finance tools: a `yfinance` market-data wrapper, computed analytics,
and deterministic financial calculators. (Analysis prompts are planned.)

Immediate roadmap:

1. Additional yfinance wrappers - get_news (recent headlines for a ticker)

2. More computed analytics

- compare_peers (rank a set of tickers across key metrics)

3. analyze_stock + compare_stocks — user-invoked slash commands that orchestrate the existing 14 tools into a methodology
4. Public free data requiring keys - add optional extensions for fed data for interest rates, etc.
5. Portfolio tools - add tools for portfolio analysis to extend specific stock functionality

## Tools

**Market data (yfinance)**

- `get_quote` — current price snapshot for one or more tickers: price, change, day/52-week ranges, market cap (batched; cached briefly).
- `get_price_history` — OHLCV bars plus a computed summary for a ticker, by period and interval (long windows are truncated; the summary covers the full window).
- `get_financials` — income statement, balance sheet, or cash flow (annual or quarterly) as line items by period; values in the company's reporting currency, with an optional line-item filter.
- `get_company_profile` — sector, industry, market cap, P/E, beta, business summary, plus recent dividends and stock splits.
- `get_analyst_data` — sell-side analyst consensus: price targets, consensus recommendation, and the recent rating trend (analyst counts over the last four months).
- `search_symbols` — resolve a company or instrument name to ticker symbol(s), best match first, across all instrument types (equity, ETF, crypto, …).

**Analytics**

- `get_key_metrics` — valuation/profitability/leverage ratios (P/E, EV/EBITDA, margins, ROE, debt/equity, FCF, EPS, …) as reported by Yahoo; units noted per field.
- `analyze_performance` — total & annualized return, annualized volatility, max drawdown, and 50/200-day SMAs computed from the daily price series.

**Time value & loans**

- `time_value_of_money` — solve any one of present/future value, payment, rate, or periods (compound interest, annuities, CAGR); supports begin-of-period (annuity-due).
- `loan_schedule` — monthly payment, total interest, and optional amortization schedule for a fixed-rate loan/mortgage (nominal APR compounded monthly).

**Cashflow valuation**

- `npv` — net present value of equally-spaced cashflows (cashflow[0] at t=0).
- `irr` — internal rate of return; returns all real roots and flags non-uniqueness.
- `mirr` — modified IRR; single-valued given finance and reinvestment rates.
- `xnpv` / `xirr` — NPV/IRR of cashflows on actual calendar dates (Actual/365).

**Rates & fixed income**

- `convert_rate` — nominal ↔ effective annual rate (discrete or continuous compounding).
- `bond_price` — price plus Macaulay/modified duration and convexity at a given yield (priced on a coupon date).
- `bond_ytm` — yield to maturity from a bond's market price.

The calculators are pure and deterministic; the market-data and analytics tools fetch
live data (briefly cached) and surface source errors clearly. All tools return typed,
structured results and report invalid inputs as clear errors.

## Run

```bash
uv run mcp-finance        # stdio MCP server
```

Add to an MCP client (e.g. Claude) as:

```json
{ "mcpServers": { "finance": { "command": "uvx", "args": ["mcp-finance"] } } }
```
