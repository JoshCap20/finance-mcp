"""MCP tool wrappers for the pure financial calculators. Thin: validate + translate."""

from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from finance_mcp.data import calculators
from finance_mcp.data.errors import InvalidInput
from finance_mcp.data.models import LoanSchedule, TVMResult


def register(mcp: FastMCP) -> None:
    """Register calculator tools on the given server instance."""

    @mcp.tool
    def time_value_of_money(
        solve_for: Annotated[
            Literal["pv", "fv", "pmt", "rate", "nper"],
            Field(description="Which unknown to solve for. Provide all other variables."),
        ],
        pv: Annotated[
            float | None,
            Field(
                description=(
                    "Present value. Sign convention: cash received is positive, "
                    "cash paid is negative."
                )
            ),
        ] = None,
        fv: Annotated[float | None, Field(description="Future value.")] = None,
        pmt: Annotated[
            float | None,
            Field(description="Payment per period (defaults to 0 if omitted)."),
        ] = None,
        rate: Annotated[
            float | None,
            Field(description="Interest rate per period as a decimal, e.g. 0.05 for 5%."),
        ] = None,
        nper: Annotated[
            float | None,
            Field(description="Number of periods."),
        ] = None,
    ) -> TVMResult:
        """Solve compound interest / present & future value / annuity payment / period count / CAGR.

        Covers most personal-finance math via one equation. Examples: future value of a
        deposit (solve_for='fv'), a loan/mortgage payment (solve_for='pmt'), or a CAGR
        between two values with no interim payments (solve_for='rate', pmt=0).
        """
        try:
            return calculators.time_value_of_money(
                solve_for=solve_for, pv=pv, fv=fv, pmt=pmt, rate=rate, nper=nper
            )
        except InvalidInput as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    def loan_schedule(
        principal: Annotated[float, Field(gt=0, description="Loan amount borrowed.")],
        annual_rate: Annotated[
            float,
            Field(ge=0, description="Annual interest rate as a decimal, e.g. 0.06 for 6%."),
        ],
        term_months: Annotated[
            int,
            Field(gt=0, description="Loan term in months, e.g. 360 for 30 years."),
        ],
        extra_payment: Annotated[
            float,
            Field(ge=0, description="Extra principal paid each month; shortens the term."),
        ] = 0.0,
    ) -> LoanSchedule:
        """Compute the monthly payment, total interest, and amortization schedule for a loan."""
        try:
            return calculators.loan_schedule(
                principal=principal,
                annual_rate=annual_rate,
                term_months=term_months,
                extra_payment=extra_payment,
            )
        except InvalidInput as exc:
            raise ToolError(str(exc)) from exc
