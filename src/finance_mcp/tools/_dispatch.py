"""Helpers that run a data/calculator call and translate domain errors to ToolError.

These take a thunk rather than wrapping the tool function, so each ``@mcp.tool`` keeps
its full annotated signature and FastMCP's schema introspection is unaffected (a
signature-erasing decorator would break it). One home for the data-layer -> ToolError
translation that otherwise repeats in every tool.
"""

import asyncio
from collections.abc import Callable

from fastmcp.exceptions import ToolError

from finance_mcp.data.errors import DataUnavailable, InvalidInput


async def run_data[T](call: Callable[[], T]) -> T:
    """Run a blocking yfinance-backed ``call`` off the event loop.

    Translates DataUnavailable (and its SymbolNotFound subclass) into a ToolError whose
    message is surfaced to the model.
    """
    try:
        return await asyncio.to_thread(call)
    except DataUnavailable as exc:
        raise ToolError(str(exc)) from exc


def run_calc[T](call: Callable[[], T]) -> T:
    """Run a pure calculator ``call``, translating InvalidInput into a ToolError."""
    try:
        return call()
    except InvalidInput as exc:
        raise ToolError(str(exc)) from exc
