# Finance MCP

An MCP server of finance tools: a `yfinance` market-data wrapper plus deterministic
financial calculators. (Computed analytics and analysis prompts are planned.)

Immediate roadmap:

1. Additional yfinance wrappers - financial statements, news, etc.
2. Public free data requiring keys - add optional extensions for fed data for interest rates, etc.
3. Portfolio tools - add tools for portfolio analysis to extend specific stock functionality

## Tools

**Market data (yfinance)**

- `get_quote` — current price snapshot for one or more tickers: price, change, day/52-week ranges, market cap (batched; cached briefly).
- `get_price_history` — OHLCV bars plus a computed summary for a ticker, by period and interval (long windows are truncated; the summary covers the full window).

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

The calculators are pure and deterministic; the market-data tools fetch live data
(briefly cached) and surface source errors clearly. All tools return typed,
structured results and report invalid inputs as clear errors.

## Run

```bash
uv run finance-mcp        # stdio MCP server
```

Add to an MCP client (e.g. Claude) as:

```json
{ "mcpServers": { "finance": { "command": "uvx", "args": ["finance-mcp"] } } }
```
