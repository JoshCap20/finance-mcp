"""Pure financial calculators. No MCP imports, no I/O — deterministic math only.

Time-value-of-money uses the standard end-of-period (ordinary annuity) equation
with the Excel cash-flow sign convention (money received is positive, money paid
is negative):

    PV*(1+r)^n + PMT*((1+r)^n - 1)/r + FV = 0      (r != 0)
    PV + PMT*n + FV = 0                            (r == 0)
"""

import math
from collections.abc import Callable

from finance_mcp.data.errors import InvalidInput
from finance_mcp.data.models import (
    AmortizationRow,
    DatedCashflow,
    IRRResult,
    LoanSchedule,
    NPVResult,
    TVMResult,
    TVMVariable,
)


def _bisect(f: Callable[[float], float], low: float = -0.999999, high: float = 10.0) -> float:
    """Find a root of ``f`` in (low, high), expanding ``high`` to bracket a sign change.

    Uses interval-width convergence (scale-independent), not a raw ``|f|`` tolerance.
    Raises InvalidInput if no sign change can be bracketed within the search range.
    """
    f_low = f(low)
    f_high = f(high)
    attempts = 0
    while f_low * f_high > 0.0 and attempts < 100:
        high *= 2.0
        f_high = f(high)
        attempts += 1
    if f_low * f_high > 0.0:
        raise InvalidInput("Could not bracket a root in the searched range.")
    for _ in range(500):
        mid = (low + high) / 2.0
        if (high - low) / 2.0 < 1e-12:
            return mid
        f_mid = f(mid)
        if f_low * f_mid <= 0.0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2.0


def _require(name: str, value: float | None) -> float:
    if value is None:
        raise InvalidInput(f"'{name}' is required when it is not the variable being solved for.")
    return value


def _fv(pv: float, pmt: float, rate: float, nper: float) -> float:
    if rate == 0.0:
        return -(pv + pmt * nper)
    growth: float = (1.0 + rate) ** nper
    return -(pv * growth + pmt * (growth - 1.0) / rate)


def _pv(fv: float, pmt: float, rate: float, nper: float) -> float:
    if rate == 0.0:
        return -(fv + pmt * nper)
    growth: float = (1.0 + rate) ** nper
    return -(fv + pmt * (growth - 1.0) / rate) / growth


def _pmt(pv: float, fv: float, rate: float, nper: float) -> float:
    if rate == 0.0:
        return -(pv + fv) / nper
    growth: float = (1.0 + rate) ** nper
    return -(pv * growth + fv) * rate / (growth - 1.0)


def _nper(pv: float, fv: float, pmt: float, rate: float) -> float:
    if rate == 0.0:
        if pmt == 0.0:
            raise InvalidInput("Cannot solve for nper when both rate and pmt are zero.")
        return -(pv + fv) / pmt
    if pmt == 0.0:
        # pv*(1+r)^n + fv = 0  ->  (1+r)^n = -fv/pv
        ratio = -fv / pv
        if ratio <= 0.0:
            raise InvalidInput("No real solution for nper with the given pv/fv signs.")
        return math.log(ratio) / math.log(1.0 + rate)
    k = pmt / rate
    numerator = k - fv
    denominator = k + pv
    if denominator == 0.0 or numerator / denominator <= 0.0:
        raise InvalidInput("No real solution for nper with the given inputs.")
    return math.log(numerator / denominator) / math.log(1.0 + rate)


def _rate(pv: float, fv: float, pmt: float, nper: float) -> float:
    # Closed form when there are no periodic payments (CAGR).
    if pmt == 0.0:
        if pv == 0.0:
            raise InvalidInput("Cannot solve for rate when pv and pmt are both zero.")
        ratio = -fv / pv
        if ratio <= 0.0:
            raise InvalidInput("No real rate solution for the given pv/fv signs.")
        growth_factor: float = ratio ** (1.0 / nper)
        return growth_factor - 1.0

    # General case: solve f(r) = fv(pv, pmt, r, nper) - fv_target = 0 numerically.
    return _bisect(lambda r: _fv(pv, pmt, r, nper) - fv)


def time_value_of_money(
    solve_for: TVMVariable,
    pv: float | None = None,
    fv: float | None = None,
    pmt: float | None = None,
    rate: float | None = None,
    nper: float | None = None,
) -> TVMResult:
    """Solve a time-value-of-money problem for one unknown variable.

    Provide every variable except the one named by ``solve_for``. ``pmt`` defaults
    to 0 when omitted and not being solved for. Covers compound interest, present/
    future value, annuity payments, period count, and CAGR (solve for ``rate`` with
    ``pmt=0``).
    """
    pmt_known = 0.0 if (pmt is None and solve_for != "pmt") else pmt

    if solve_for == "fv":
        value = _fv(
            _require("pv", pv),
            _require("pmt", pmt_known),
            _require("rate", rate),
            _require("nper", nper),
        )
    elif solve_for == "pv":
        value = _pv(
            _require("fv", fv),
            _require("pmt", pmt_known),
            _require("rate", rate),
            _require("nper", nper),
        )
    elif solve_for == "pmt":
        value = _pmt(
            _require("pv", pv),
            _require("fv", fv),
            _require("rate", rate),
            _require("nper", nper),
        )
    elif solve_for == "nper":
        value = _nper(
            _require("pv", pv),
            _require("fv", fv),
            _require("pmt", pmt_known),
            _require("rate", rate),
        )
    else:  # rate
        value = _rate(
            _require("pv", pv),
            _require("fv", fv),
            _require("pmt", pmt_known),
            _require("nper", nper),
        )

    resolved: dict[str, float | None] = {
        "pv": pv,
        "fv": fv,
        "pmt": pmt_known,
        "rate": rate,
        "nper": nper,
    }
    resolved[solve_for] = value
    return TVMResult(
        solved_for=solve_for,
        solved_value=value,
        pv=resolved["pv"] if resolved["pv"] is not None else 0.0,
        fv=resolved["fv"] if resolved["fv"] is not None else 0.0,
        pmt=resolved["pmt"] if resolved["pmt"] is not None else 0.0,
        rate=resolved["rate"] if resolved["rate"] is not None else 0.0,
        nper=resolved["nper"] if resolved["nper"] is not None else 0.0,
    )


def loan_schedule(
    principal: float,
    annual_rate: float,
    term_months: int,
    extra_payment: float = 0.0,
    include_schedule: bool = False,
) -> LoanSchedule:
    """Build an amortization summary for a fixed-rate loan or mortgage.

    ``annual_rate`` is a decimal (e.g. 0.06 for 6%). ``extra_payment`` is an
    additional amount applied to principal each month; it shortens the term.
    The summary (payment, totals, payoff count) is always computed; the full
    per-period rows are returned only when ``include_schedule`` is True.
    """
    if principal <= 0.0:
        raise InvalidInput("principal must be positive.")
    if term_months <= 0:
        raise InvalidInput("term_months must be a positive integer.")
    if annual_rate < 0.0:
        raise InvalidInput("annual_rate cannot be negative.")
    if extra_payment < 0.0:
        raise InvalidInput("extra_payment cannot be negative.")

    monthly_rate = annual_rate / 12.0
    if monthly_rate == 0.0:
        payment = principal / term_months
    else:
        growth: float = (1.0 + monthly_rate) ** term_months
        payment = principal * monthly_rate * growth / (growth - 1.0)

    rows: list[AmortizationRow] = []
    balance = principal
    total_paid = 0.0
    total_interest = 0.0
    period = 0
    # Guard against non-terminating loops; term_months is the natural upper bound.
    while balance > 1e-9 and period < term_months:
        period += 1
        interest = balance * monthly_rate
        scheduled = payment + extra_payment
        principal_paid = scheduled - interest
        if principal_paid >= balance:  # final (partial) payment
            principal_paid = balance
            scheduled = principal_paid + interest
        balance -= principal_paid
        total_paid += scheduled
        total_interest += interest
        if include_schedule:
            rows.append(
                AmortizationRow(
                    period=period,
                    payment=round(scheduled, 2),
                    principal=round(principal_paid, 2),
                    interest=round(interest, 2),
                    balance=round(max(balance, 0.0), 2),
                )
            )

    return LoanSchedule(
        monthly_payment=round(payment, 2),
        n_payments=period,
        total_paid=round(total_paid, 2),
        total_interest=round(total_interest, 2),
        schedule=rows,
    )


def npv(rate: float, cashflows: list[float]) -> NPVResult:
    """Net present value of equally-spaced cashflows, with cashflows[0] at t=0 (undiscounted).

    NPV = sum(cashflows[t] / (1 + rate)**t for t in 0..n). Note this differs from
    Excel's NPV(), which assumes the first cashflow is one period in the future.
    """
    if not cashflows:
        raise InvalidInput("cashflows must not be empty.")
    if rate <= -1.0:
        raise InvalidInput("rate must be greater than -1 (-100%).")
    total = 0.0
    for period, cash in enumerate(cashflows):
        total += cash / (1.0 + rate) ** period
    return NPVResult(rate=rate, npv=total)


def _has_sign_change(values: list[float]) -> bool:
    signs = {value > 0.0 for value in values if value != 0.0}
    return len(signs) > 1


def irr(cashflows: list[float]) -> IRRResult:
    """Internal rate of return of equally-spaced cashflows; needs >=1 sign change."""
    if len(cashflows) < 2:
        raise InvalidInput("irr needs at least two cashflows.")
    if not _has_sign_change(cashflows):
        raise InvalidInput("irr needs at least one sign change in the cashflows.")
    rate = _bisect(lambda r: npv(r, cashflows).npv)
    return IRRResult(irr=rate)


def xnpv(rate: float, cashflows: list[DatedCashflow]) -> NPVResult:
    """Net present value of dated cashflows; base date is the earliest, 365-day basis.

    XNPV = sum(amount / (1 + rate)**((date - base_date).days / 365)). The annual
    ``rate`` discounts by actual elapsed days, so irregular spacing is handled.
    """
    if not cashflows:
        raise InvalidInput("cashflows must not be empty.")
    if rate <= -1.0:
        raise InvalidInput("rate must be greater than -1 (-100%).")
    base = min(cf.date for cf in cashflows)
    total = 0.0
    for cf in cashflows:
        years = (cf.date - base).days / 365.0
        total += cf.amount / (1.0 + rate) ** years
    return NPVResult(rate=rate, npv=total)


def xirr(cashflows: list[DatedCashflow]) -> IRRResult:
    """Annualized internal rate of return of dated cashflows; needs >=1 sign change."""
    if len(cashflows) < 2:
        raise InvalidInput("xirr needs at least two cashflows.")
    if not _has_sign_change([cf.amount for cf in cashflows]):
        raise InvalidInput("xirr needs at least one sign change in the cashflows.")
    rate = _bisect(lambda r: xnpv(r, cashflows).npv)
    return IRRResult(irr=rate)
