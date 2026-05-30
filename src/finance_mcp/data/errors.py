"""Typed exceptions for the data layer. Tool wrappers translate these to ToolError."""


class FinanceMCPError(Exception):
    """Base class for all finance-mcp data-layer errors."""


class InvalidInput(FinanceMCPError):
    """Raised when calculator/tool inputs are missing or inconsistent."""
