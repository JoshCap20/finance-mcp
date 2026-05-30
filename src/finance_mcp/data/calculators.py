"""Pure financial calculators. No MCP imports, no I/O — deterministic math only.

Time-value-of-money uses the standard end-of-period (ordinary annuity) equation
with the Excel cash-flow sign convention (money received is positive, money paid
is negative):

    PV*(1+r)^n + PMT*((1+r)^n - 1)/r + FV = 0      (r != 0)
    PV + PMT*n + FV = 0                            (r == 0)
"""

import math

from finance_mcp.data.errors import InvalidInput
from finance_mcp.data.models import TVMResult, TVMVariable


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

    # General case: bisection on f(r) = fv(pv, pmt, r, nper) - fv_target = 0.
    def f(r: float) -> float:
        return _fv(pv, pmt, r, nper) - fv

    low, high = -0.9999, 1.0
    f_low, f_high = f(low), f(high)
    # Expand the upper bracket until a sign change is found (capped).
    attempts = 0
    while f_low * f_high > 0.0 and attempts < 60:
        high *= 1.5
        f_high = f(high)
        attempts += 1
    if f_low * f_high > 0.0:
        raise InvalidInput("Could not bracket a rate solution for the given inputs.")
    for _ in range(200):
        mid = (low + high) / 2.0
        f_mid = f(mid)
        if abs(f_mid) < 1e-9:
            return mid
        if f_low * f_mid < 0.0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2.0


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
