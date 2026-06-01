"""Pydantic return models. Every tool returns one of these (never a bare dict)."""

import datetime
from typing import Literal

from pydantic import BaseModel, Field

TVMVariable = Literal["pv", "fv", "pmt", "rate", "nper"]


class TVMResult(BaseModel):
    """Result of a time-value-of-money computation."""

    solved_for: TVMVariable = Field(description="Which variable was solved for.")
    solved_value: float = Field(description="The computed value of the solved-for variable.")
    pv: float = Field(description="Present value (cash convention: inflow positive).")
    fv: float = Field(description="Future value.")
    pmt: float = Field(description="Payment per period.")
    rate: float = Field(description="Interest rate per period (decimal, e.g. 0.05).")
    nper: float = Field(description="Number of periods.")


class AmortizationRow(BaseModel):
    """One period of a loan amortization schedule."""

    period: int = Field(description="1-based period index.")
    payment: float = Field(description="Total payment made this period.")
    principal: float = Field(description="Portion applied to principal.")
    interest: float = Field(description="Portion applied to interest.")
    balance: float = Field(description="Remaining principal after this period.")


class LoanSchedule(BaseModel):
    """Amortization summary and full schedule for a loan or mortgage."""

    monthly_payment: float = Field(description="Scheduled monthly payment (excl. extra).")
    n_payments: int = Field(description="Number of payments until payoff.")
    total_paid: float = Field(description="Sum of all payments made.")
    total_interest: float = Field(description="Total interest paid over the loan.")
    schedule: list[AmortizationRow] = Field(description="Per-period amortization rows.")


class NPVResult(BaseModel):
    """Net present value at a given discount rate."""

    rate: float = Field(description="Discount rate used (per period, or annual for dated).")
    npv: float = Field(description="Net present value.")


class IRRResult(BaseModel):
    """Internal rate of return of a cashflow series.

    Non-conventional cashflows (more than one sign change) can have several IRRs;
    in that case ``is_unique`` is False and ``irr`` is only a representative value.
    """

    irr: float = Field(
        description="Representative IRR (per period, or annual for dated). When not unique "
        "this is the smallest non-negative root (or the root nearest zero if all are "
        "negative); inspect all_irrs and is_unique, or use mirr() for a single value."
    )
    all_irrs: list[float] = Field(
        default_factory=list,
        description="Every real IRR found in (-100%, 1000%], ascending.",
    )
    is_unique: bool = Field(
        default=True,
        description="True when exactly one IRR exists; when False, irr is one of several.",
    )


class MIRRResult(BaseModel):
    """Modified internal rate of return (always unique given the two rates)."""

    mirr: float = Field(description="Modified IRR per period (annualize externally if needed).")
    finance_rate: float = Field(description="Rate used to discount negative cashflows.")
    reinvest_rate: float = Field(description="Rate used to compound positive cashflows.")


class DatedCashflow(BaseModel):
    """A single cashflow on a calendar date (for XNPV/XIRR)."""

    date: datetime.date = Field(description="Cashflow date (ISO 8601, e.g. 2024-01-31).")
    amount: float = Field(description="Cashflow amount; outflows negative, inflows positive.")


class RateConversionResult(BaseModel):
    """Result of a nominal<->effective annual rate conversion."""

    input_rate: float = Field(description="The rate provided, as a decimal.")
    periods_per_year: int = Field(description="Compounding periods per year used.")
    direction: Literal["nominal_to_effective", "effective_to_nominal"] = Field(
        description="Conversion performed."
    )
    compounding: Literal["discrete", "continuous"] = Field(
        default="discrete", description="Compounding convention used for the conversion."
    )
    converted_rate: float = Field(description="The resulting rate, as a decimal.")


class BondAnalytics(BaseModel):
    """Price and interest-rate risk metrics for a fixed-coupon bond."""

    price: float = Field(description="Present value (clean price) of the bond.")
    current_yield: float = Field(description="Annual coupon divided by price.")
    macaulay_duration: float = Field(description="Macaulay duration in years.")
    modified_duration: float = Field(description="Modified duration in years (price sensitivity).")
    convexity: float = Field(description="Convexity in years^2.")


class BondYTM(BaseModel):
    """Yield to maturity solved from a bond's market price."""

    yield_to_maturity: float = Field(description="Annual yield to maturity, as a decimal.")


class Quote(BaseModel):
    """A current price snapshot for one ticker."""

    symbol: str = Field(description="Ticker symbol.")
    currency: str | None = Field(default=None, description="Quote currency, e.g. USD.")
    price: float = Field(description="Latest price.")
    previous_close: float | None = Field(default=None, description="Previous close.")
    change: float | None = Field(default=None, description="Price change vs previous close.")
    change_percent: float | None = Field(
        default=None, description="Percent change vs previous close."
    )
    day_high: float | None = Field(default=None, description="Intraday high.")
    day_low: float | None = Field(default=None, description="Intraday low.")
    year_high: float | None = Field(default=None, description="52-week high.")
    year_low: float | None = Field(default=None, description="52-week low.")
    market_cap: float | None = Field(default=None, description="Market capitalization.")
    volume: float | None = Field(default=None, description="Latest/last volume.")


class PriceBar(BaseModel):
    """One OHLCV bar."""

    date: str = Field(description="Bar date (ISO 8601).")
    open: float = Field(description="Open price.")
    high: float = Field(description="High price.")
    low: float = Field(description="Low price.")
    close: float = Field(description="Close price.")
    volume: float = Field(description="Volume.")


class PriceSummary(BaseModel):
    """Compact summary over the requested history window."""

    start_date: str = Field(description="First bar date.")
    end_date: str = Field(description="Last bar date.")
    start_close: float = Field(description="Close of the first bar.")
    end_close: float = Field(description="Close of the last bar.")
    total_return_percent: float = Field(description="Percent change from first to last close.")
    period_high: float = Field(description="Highest high over the window.")
    period_low: float = Field(description="Lowest low over the window.")
    bars: int = Field(description="Number of bars in the full window.")


class PriceHistory(BaseModel):
    """OHLCV history plus a computed summary."""

    symbol: str = Field(description="Ticker symbol.")
    period: str = Field(description="Requested period, e.g. '1mo'.")
    interval: str = Field(description="Requested interval, e.g. '1d'.")
    bars: list[PriceBar] = Field(description="OHLCV bars (most recent, may be truncated).")
    summary: PriceSummary = Field(description="Summary computed over the full window.")
    truncated: bool = Field(
        description="True if bars were capped; summary still covers the full window."
    )


class FinancialStatement(BaseModel):
    """A financial statement (income/balance/cashflow) as a label -> per-period values table."""

    symbol: str = Field(description="Ticker symbol.")
    statement: Literal["income", "balance", "cashflow"] = Field(description="Which statement.")
    period: Literal["annual", "quarterly"] = Field(description="Reporting period granularity.")
    period_ends: list[str] = Field(
        description="Period-end dates (ISO 8601), most recent first; values align to this order."
    )
    line_items: dict[str, list[float | None]] = Field(
        description="Line item label -> values aligned to period_ends (null where not reported)."
    )


class DividendEvent(BaseModel):
    """A single cash dividend."""

    date: str = Field(description="Ex-dividend date (ISO 8601).")
    amount: float = Field(description="Dividend amount per share.")


class SplitEvent(BaseModel):
    """A single stock split."""

    date: str = Field(description="Split date (ISO 8601).")
    ratio: float = Field(description="Split ratio (e.g. 4.0 = 4-for-1).")


class CompanyProfile(BaseModel):
    """Company profile and key stats, with recent corporate actions."""

    symbol: str = Field(description="Ticker symbol.")
    name: str | None = Field(default=None, description="Company name.")
    sector: str | None = Field(default=None, description="Sector.")
    industry: str | None = Field(default=None, description="Industry.")
    country: str | None = Field(default=None, description="Country.")
    website: str | None = Field(default=None, description="Website URL.")
    employees: int | None = Field(default=None, description="Full-time employees.")
    summary: str | None = Field(default=None, description="Business summary.")
    currency: str | None = Field(default=None, description="Reporting/quote currency.")
    market_cap: float | None = Field(default=None, description="Market capitalization.")
    trailing_pe: float | None = Field(default=None, description="Trailing P/E ratio.")
    forward_pe: float | None = Field(default=None, description="Forward P/E ratio.")
    dividend_yield: float | None = Field(default=None, description="Dividend yield.")
    beta: float | None = Field(default=None, description="Beta vs the market.")
    recent_dividends: list[DividendEvent] = Field(
        default_factory=list, description="Most recent dividends (newest last)."
    )
    splits: list[SplitEvent] = Field(default_factory=list, description="Stock split history.")
