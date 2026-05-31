"""In-memory MCP protocol tests for the calculator tools."""

import pytest
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport
from fastmcp.exceptions import ToolError


async def test_tools_are_registered(client: Client[FastMCPTransport]) -> None:
    names = {tool.name for tool in await client.list_tools()}
    assert {"time_value_of_money", "loan_schedule"} <= names


async def test_time_value_of_money_tool(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "time_value_of_money",
        {"solve_for": "fv", "pv": -1000.0, "pmt": 0.0, "rate": 0.05, "nper": 10.0},
    )
    assert result.data.solved_for == "fv"
    assert result.data.solved_value == pytest.approx(1628.894627, rel=1e-6)


async def test_loan_schedule_tool(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "loan_schedule",
        {"principal": 200000.0, "annual_rate": 0.06, "term_months": 360},
    )
    assert result.data.monthly_payment == pytest.approx(1199.101, rel=1e-5)
    assert result.data.n_payments == 360


async def test_invalid_input_surfaces_as_tool_error(client: Client[FastMCPTransport]) -> None:
    with pytest.raises(ToolError):
        await client.call_tool(
            "time_value_of_money",
            {"solve_for": "fv", "pv": -1000.0, "pmt": 0.0, "nper": 10.0},  # missing rate
        )


async def test_loan_schedule_invalid_input_surfaces_as_tool_error(
    client: Client[FastMCPTransport],
) -> None:
    with pytest.raises(ToolError):
        await client.call_tool(
            "loan_schedule",
            {"principal": 1000.0, "annual_rate": 0.05, "term_months": 0},
        )


async def test_new_tools_registered(client: Client[FastMCPTransport]) -> None:
    names = {t.name for t in await client.list_tools()}
    assert {"npv", "irr", "xnpv", "xirr", "convert_rate"} <= names


async def test_npv_tool(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "npv", {"rate": 0.10, "cashflows": [-1000.0, 500.0, 500.0, 500.0]}
    )
    assert result.data.npv == pytest.approx(243.426, rel=1e-4)


async def test_irr_tool(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool("irr", {"cashflows": [-100.0, 110.0]})
    assert result.data.irr == pytest.approx(0.10, rel=1e-9)


async def test_xirr_tool(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "xirr",
        {
            "cashflows": [
                {"date": "2021-01-01", "amount": -1000.0},
                {"date": "2022-01-01", "amount": 1100.0},
            ]
        },
    )
    assert result.data.irr == pytest.approx(0.10, rel=1e-6)


async def test_convert_rate_tool(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "convert_rate",
        {"rate": 0.12, "periods_per_year": 12, "direction": "nominal_to_effective"},
    )
    assert result.data.converted_rate == pytest.approx(0.12682503, rel=1e-7)


async def test_loan_schedule_tool_summary_default(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "loan_schedule", {"principal": 200000.0, "annual_rate": 0.06, "term_months": 360}
    )
    assert result.data.schedule == []
    assert result.data.n_payments == 360


async def test_loan_schedule_tool_with_rows(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "loan_schedule",
        {
            "principal": 200000.0,
            "annual_rate": 0.06,
            "term_months": 360,
            "include_schedule": True,
        },
    )
    assert len(result.data.schedule) == 360


async def test_irr_tool_no_sign_change_errors(client: Client[FastMCPTransport]) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("irr", {"cashflows": [100.0, 200.0]})


async def test_npv_tool_empty_errors(client: Client[FastMCPTransport]) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("npv", {"rate": 0.1, "cashflows": []})


async def test_xnpv_tool_empty_errors(client: Client[FastMCPTransport]) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("xnpv", {"rate": 0.1, "cashflows": []})


async def test_xirr_tool_no_sign_change_errors(client: Client[FastMCPTransport]) -> None:
    with pytest.raises(ToolError):
        await client.call_tool(
            "xirr",
            {
                "cashflows": [
                    {"date": "2021-01-01", "amount": 100.0},
                    {"date": "2022-01-01", "amount": 200.0},
                ]
            },
        )


async def test_convert_rate_tool_invalid_nominal_errors(client: Client[FastMCPTransport]) -> None:
    with pytest.raises(ToolError):
        await client.call_tool(
            "convert_rate",
            {"rate": -20.0, "periods_per_year": 12, "direction": "nominal_to_effective"},
        )


async def test_bond_tools_registered(client: Client[FastMCPTransport]) -> None:
    names = {t.name for t in await client.list_tools()}
    assert {"bond_price", "bond_ytm"} <= names


async def test_bond_price_tool(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "bond_price",
        {
            "face": 1000.0,
            "coupon_rate": 0.06,
            "years_to_maturity": 10.0,
            "ytm": 0.06,
            "frequency": 2,
        },
    )
    assert result.data.price == pytest.approx(1000.0, rel=1e-6)


async def test_bond_ytm_tool(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "bond_ytm",
        {
            "face": 1000.0,
            "coupon_rate": 0.06,
            "years_to_maturity": 10.0,
            "price": 1000.0,
            "frequency": 2,
        },
    )
    assert result.data.yield_to_maturity == pytest.approx(0.06, rel=1e-6)


async def test_tvm_when_begin_tool(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "time_value_of_money",
        {"solve_for": "fv", "pv": 0.0, "pmt": -100.0, "rate": 0.05, "nper": 10.0, "when": "begin"},
    )
    assert result.data.solved_value == pytest.approx(1320.679, rel=1e-5)


async def test_bond_price_tool_invalid_errors(client: Client[FastMCPTransport]) -> None:
    # ytm <= -1 is not schema-blocked, so it reaches the data layer and surfaces as ToolError.
    with pytest.raises(ToolError):
        await client.call_tool(
            "bond_price",
            {
                "face": 1000.0,
                "coupon_rate": 0.05,
                "years_to_maturity": 10.0,
                "ytm": -2.0,
                "frequency": 2,
            },
        )


async def test_convert_rate_tool_continuous(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "convert_rate",
        {
            "rate": 0.12,
            "periods_per_year": 1,
            "direction": "nominal_to_effective",
            "compounding": "continuous",
        },
    )
    assert result.data.converted_rate == pytest.approx(0.12749685, rel=1e-7)
    assert result.data.compounding == "continuous"


async def test_bond_ytm_tool_non_integer_periods_errors(client: Client[FastMCPTransport]) -> None:
    with pytest.raises(ToolError):
        await client.call_tool(
            "bond_ytm",
            {
                "face": 1000.0,
                "coupon_rate": 0.05,
                "years_to_maturity": 2.5,
                "price": 950.0,
                "frequency": 1,
            },
        )


async def test_mirr_tool_registered(client: Client[FastMCPTransport]) -> None:
    names = {t.name for t in await client.list_tools()}
    assert "mirr" in names


async def test_mirr_tool(client: Client[FastMCPTransport]) -> None:
    result = await client.call_tool(
        "mirr",
        {
            "cashflows": [-1000.0, 500.0, 400.0, 300.0, 100.0],
            "finance_rate": 0.10,
            "reinvest_rate": 0.12,
        },
    )
    assert result.data.mirr == pytest.approx(0.13168560, rel=1e-6)


async def test_mirr_tool_invalid_errors(client: Client[FastMCPTransport]) -> None:
    with pytest.raises(ToolError):
        await client.call_tool(
            "mirr",
            {"cashflows": [-100.0, -50.0], "finance_rate": 0.1, "reinvest_rate": 0.1},
        )
