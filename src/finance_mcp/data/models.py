"""Pydantic return models. Every tool returns one of these (never a bare dict)."""

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
