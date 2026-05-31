"""Server assembly: build the FastMCP instance and register every tool/prompt module."""

from fastmcp import FastMCP

from finance_mcp.data.yfinance_client import YFinanceClient
from finance_mcp.tools import calculators, equities


def create_server(yf_client: YFinanceClient | None = None) -> FastMCP:
    """Create and configure the finance-mcp FastMCP server."""
    mcp: FastMCP = FastMCP("finance-mcp")
    client = yf_client if yf_client is not None else YFinanceClient()
    calculators.register(mcp)
    equities.register(mcp, client)
    return mcp


def main() -> None:
    """Console entry point: run the server over stdio."""
    create_server().run()


if __name__ == "__main__":
    main()
