import datetime
import math

import pytest

from finance_mcp.data.calculators import (
    irr,
    loan_schedule,
    npv,
    time_value_of_money,
    xirr,
    xnpv,
)
from finance_mcp.data.errors import InvalidInput
from finance_mcp.data.models import DatedCashflow


def test_future_value_compound_interest() -> None:
    # $1000 invested (outflow, so pv negative) at 5%/yr for 10 yrs, no payments.
    result = time_value_of_money(solve_for="fv", pv=-1000.0, pmt=0.0, rate=0.05, nper=10.0)
    assert result.solved_for == "fv"
    assert result.solved_value == pytest.approx(1628.894627, rel=1e-6)


def test_present_value() -> None:
    # What deposit grows to $1628.894627 at 5% over 10 yrs? -> 1000 (outflow).
    result = time_value_of_money(solve_for="pv", fv=1628.894627, pmt=0.0, rate=0.05, nper=10.0)
    assert result.solved_value == pytest.approx(-1000.0, rel=1e-6)


def test_payment_annuity() -> None:
    # Loan of 200000 (inflow) at 0.5%/mo for 360 mo, fv 0 -> payment ~ -1199.10 (outflow).
    result = time_value_of_money(solve_for="pmt", pv=200000.0, fv=0.0, rate=0.005, nper=360.0)
    assert result.solved_value == pytest.approx(-1199.101, rel=1e-5)


def test_rate_is_cagr_when_no_payments() -> None:
    # Solve rate: 1000 -> 2000 over 10 yrs, no payments -> CAGR 7.1773%.
    result = time_value_of_money(solve_for="rate", pv=-1000.0, fv=2000.0, pmt=0.0, nper=10.0)
    assert result.solved_value == pytest.approx(0.0717734625, rel=1e-6)


def test_nper() -> None:
    # Periods to grow 1000 -> 2000 at 5%: ln(2)/ln(1.05) ~ 14.2067.
    result = time_value_of_money(solve_for="nper", pv=-1000.0, fv=2000.0, pmt=0.0, rate=0.05)
    assert result.solved_value == pytest.approx(14.2067, rel=1e-4)


def test_zero_rate_payment() -> None:
    # r = 0: pv + pmt*n + fv = 0. pv=-1200, n=12, fv=0 -> pmt = 100.
    result = time_value_of_money(solve_for="pmt", pv=-1200.0, fv=0.0, rate=0.0, nper=12.0)
    assert result.solved_value == pytest.approx(100.0, rel=1e-9)


def test_missing_required_input_raises() -> None:
    # Solving for fv requires pv, pmt, rate, nper; omit rate.
    with pytest.raises(InvalidInput):
        time_value_of_money(solve_for="fv", pv=-1000.0, pmt=0.0, nper=10.0)


def test_result_echoes_all_fields() -> None:
    result = time_value_of_money(solve_for="fv", pv=-1000.0, pmt=0.0, rate=0.05, nper=10.0)
    assert result.rate == 0.05
    assert result.nper == 10.0
    assert math.isclose(result.fv, result.solved_value)


def test_loan_payment_30yr() -> None:
    # 200k at 6% annual, 360 months -> payment ~ 1199.10.
    result = loan_schedule(
        principal=200000.0, annual_rate=0.06, term_months=360, include_schedule=True
    )
    assert result.monthly_payment == pytest.approx(1199.101, rel=1e-5)
    assert result.n_payments == 360
    assert result.total_interest == pytest.approx(result.total_paid - 200000.0, rel=1e-9)
    assert result.schedule[-1].balance == pytest.approx(0.0, abs=1e-2)


def test_loan_zero_interest() -> None:
    # 12000 at 0% over 12 months -> 1000/mo, no interest.
    result = loan_schedule(principal=12000.0, annual_rate=0.0, term_months=12)
    assert result.monthly_payment == pytest.approx(1000.0, rel=1e-9)
    assert result.total_interest == pytest.approx(0.0, abs=1e-6)
    assert result.n_payments == 12


def test_loan_extra_payment_shortens_term() -> None:
    base = loan_schedule(principal=200000.0, annual_rate=0.06, term_months=360)
    faster = loan_schedule(
        principal=200000.0, annual_rate=0.06, term_months=360, extra_payment=200.0
    )
    assert faster.n_payments < base.n_payments
    assert faster.total_interest < base.total_interest


def test_loan_invalid_term_raises() -> None:
    with pytest.raises(InvalidInput):
        loan_schedule(principal=1000.0, annual_rate=0.05, term_months=0)


def test_fv_zero_rate_with_payments() -> None:
    # r = 0: fv = -(pv + pmt*n). pv=-1000, pmt=-50, n=12 -> 1600.
    result = time_value_of_money(solve_for="fv", pv=-1000.0, pmt=-50.0, rate=0.0, nper=12.0)
    assert result.solved_value == pytest.approx(1600.0, rel=1e-9)


def test_pv_zero_rate_with_payments() -> None:
    result = time_value_of_money(solve_for="pv", fv=1600.0, pmt=-50.0, rate=0.0, nper=12.0)
    assert result.solved_value == pytest.approx(-1000.0, rel=1e-9)


def test_nper_zero_rate_with_payments() -> None:
    # r = 0: nper = -(pv + fv)/pmt. pv=-1200, fv=0, pmt=100 -> 12.
    result = time_value_of_money(solve_for="nper", pv=-1200.0, fv=0.0, pmt=100.0, rate=0.0)
    assert result.solved_value == pytest.approx(12.0, rel=1e-9)


def test_nper_general_with_payments() -> None:
    # 12-month annuity at 1%/mo, payment that amortizes 1000 -> nper ~ 12.
    result = time_value_of_money(solve_for="nper", pv=1000.0, fv=0.0, pmt=-88.84879, rate=0.01)
    assert result.solved_value == pytest.approx(12.0, rel=1e-3)


def test_rate_general_with_payments() -> None:
    # Solve the periodic rate of a 12-month annuity amortizing 1000 -> ~1%/mo.
    result = time_value_of_money(solve_for="rate", pv=1000.0, fv=0.0, pmt=-88.84879, nper=12.0)
    assert result.solved_value == pytest.approx(0.01, rel=1e-4)


def test_nper_zero_rate_and_zero_pmt_raises() -> None:
    with pytest.raises(InvalidInput):
        time_value_of_money(solve_for="nper", pv=-1000.0, fv=2000.0, pmt=0.0, rate=0.0)


def test_rate_zero_pv_and_pmt_raises() -> None:
    with pytest.raises(InvalidInput):
        time_value_of_money(solve_for="rate", pv=0.0, fv=100.0, pmt=0.0, nper=10.0)


def test_rate_no_real_solution_raises() -> None:
    # pv and fv same sign with no payments -> no real positive growth factor.
    with pytest.raises(InvalidInput):
        time_value_of_money(solve_for="rate", pv=-1000.0, fv=-500.0, pmt=0.0, nper=10.0)


def test_loan_invalid_principal_raises() -> None:
    with pytest.raises(InvalidInput):
        loan_schedule(principal=0.0, annual_rate=0.05, term_months=12)


def test_loan_negative_rate_raises() -> None:
    with pytest.raises(InvalidInput):
        loan_schedule(principal=1000.0, annual_rate=-0.01, term_months=12)


def test_loan_schedule_summary_only_by_default() -> None:
    result = loan_schedule(principal=200000.0, annual_rate=0.06, term_months=360)
    assert result.monthly_payment == pytest.approx(1199.101, rel=1e-5)
    assert result.n_payments == 360
    assert result.total_interest == pytest.approx(result.total_paid - 200000.0, rel=1e-9)
    assert result.schedule == []  # full rows omitted by default


def test_loan_schedule_includes_rows_when_requested() -> None:
    result = loan_schedule(
        principal=200000.0, annual_rate=0.06, term_months=360, include_schedule=True
    )
    assert len(result.schedule) == 360
    assert result.schedule[-1].balance == pytest.approx(0.0, abs=1e-2)


def test_loan_negative_extra_payment_raises() -> None:
    with pytest.raises(InvalidInput):
        loan_schedule(principal=1000.0, annual_rate=0.05, term_months=12, extra_payment=-10.0)


def test_npv_basic() -> None:
    assert npv(0.10, [-1000.0, 500.0, 500.0, 500.0]).npv == pytest.approx(243.426, rel=1e-4)


def test_npv_zero_rate_is_sum() -> None:
    assert npv(0.0, [-1000.0, 600.0, 600.0]).npv == pytest.approx(200.0, rel=1e-9)


def test_npv_empty_raises() -> None:
    with pytest.raises(InvalidInput):
        npv(0.1, [])


def test_npv_invalid_rate_raises() -> None:
    with pytest.raises(InvalidInput):
        npv(-1.0, [-100.0, 110.0])


def test_irr_simple_exact() -> None:
    assert irr([-100.0, 110.0]).irr == pytest.approx(0.10, rel=1e-9)


def test_irr_roundtrips_through_npv() -> None:
    cashflows = [-1000.0, 500.0, 500.0, 500.0]
    r = irr(cashflows).irr
    assert npv(r, cashflows).npv == pytest.approx(0.0, abs=1e-6)


def test_irr_no_sign_change_raises() -> None:
    with pytest.raises(InvalidInput):
        irr([100.0, 200.0, 300.0])


def test_irr_single_cashflow_raises() -> None:
    with pytest.raises(InvalidInput):
        irr([-100.0])


def _cf(year: int, amount: float) -> DatedCashflow:
    return DatedCashflow(date=datetime.date(year, 1, 1), amount=amount)


def test_xnpv_zero_at_irr_rate() -> None:
    flows = [_cf(2021, -1000.0), _cf(2022, 1100.0)]  # 365-day span (non-leap)
    assert xnpv(0.10, flows).npv == pytest.approx(0.0, abs=1e-6)


def test_xirr_simple_annual() -> None:
    flows = [_cf(2021, -1000.0), _cf(2022, 1100.0)]
    assert xirr(flows).irr == pytest.approx(0.10, rel=1e-6)


def test_xirr_order_independent() -> None:
    flows = [_cf(2022, 1100.0), _cf(2021, -1000.0)]  # reversed input
    assert xirr(flows).irr == pytest.approx(0.10, rel=1e-6)


def test_xnpv_empty_raises() -> None:
    with pytest.raises(InvalidInput):
        xnpv(0.1, [])


def test_xnpv_invalid_rate_raises() -> None:
    with pytest.raises(InvalidInput):
        xnpv(-1.0, [_cf(2021, -100.0), _cf(2022, 110.0)])


def test_xirr_no_sign_change_raises() -> None:
    with pytest.raises(InvalidInput):
        xirr([_cf(2021, 100.0), _cf(2022, 200.0)])


def test_xirr_single_cashflow_raises() -> None:
    with pytest.raises(InvalidInput):
        xirr([_cf(2021, -100.0)])
