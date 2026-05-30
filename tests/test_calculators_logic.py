import math

import pytest

from finance_mcp.data.calculators import loan_schedule, time_value_of_money
from finance_mcp.data.errors import InvalidInput


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
    result = loan_schedule(principal=200000.0, annual_rate=0.06, term_months=360)
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
