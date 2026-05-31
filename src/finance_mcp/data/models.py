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
    """Internal rate of return of a cashflow series."""

    irr: float = Field(description="Internal rate of return (per period, or annual for dated).")


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
