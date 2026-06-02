"""Tests for analysis prompts (in-memory Client; no network)."""

from fastmcp import Client

from finance_mcp.server import create_server


async def test_analyze_stock_is_registered_with_expected_arguments() -> None:
    async with Client(create_server()) as client:
        prompts = await client.list_prompts()
        by_name = {p.name: p for p in prompts}
        assert "analyze_stock" in by_name
        args = {a.name: a for a in (by_name["analyze_stock"].arguments or [])}
        assert set(args) == {"ticker", "horizon"}
        assert args["ticker"].required is True
        assert args["horizon"].required is False
