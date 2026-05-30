"""Server assembly: build the FastMCP instance and register every tool/prompt module."""

from fastmcp import FastMCP

from finance_mcp.tools import calculators


def create_server() -> FastMCP:
    """Create and configure the finance-mcp FastMCP server."""
    mcp: FastMCP = FastMCP("finance-mcp")
    calculators.register(mcp)
    return mcp


def main() -> None:
    """Console entry point: run the server over stdio."""
    create_server().run()


if __name__ == "__main__":
    main()
