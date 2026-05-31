"""Typed exceptions for the data layer. Tool wrappers translate these to ToolError."""


class FinanceMCPError(Exception):
    """Base class for all finance-mcp data-layer errors."""


class InvalidInput(FinanceMCPError):
    """Raised when calculator/tool inputs are missing or inconsistent."""


class DataUnavailable(FinanceMCPError):
    """Raised when a data source returns no usable data or an error; message is surfaced."""


class SymbolNotFound(DataUnavailable):
    """Raised when a ticker symbol has no data."""
