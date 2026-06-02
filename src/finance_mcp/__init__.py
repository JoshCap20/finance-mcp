"""finance-mcp: an MCP server for finance tools, market data, and calculators."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mcp-finance")
except PackageNotFoundError:  # pragma: no cover - source checkout without an install
    __version__ = "0.0.0+unknown"
