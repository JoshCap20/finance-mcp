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
