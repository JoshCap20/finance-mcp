"""Tests for server assembly and settings."""

import pytest
from fastmcp import FastMCP

from finance_mcp.server import create_server, main
from finance_mcp.settings import get_settings


def test_settings_defaults() -> None:
    settings = get_settings()
    assert settings.quote_cache_ttl_seconds == 30
    assert settings.fundamentals_cache_ttl_seconds == 3600


def test_quote_ttl_default_is_30() -> None:
    settings = get_settings()
    assert settings.quote_cache_ttl_seconds == 30
    assert settings.history_cache_ttl_seconds == 300
    assert settings.fundamentals_cache_ttl_seconds == 3600


def test_create_server_returns_fastmcp() -> None:
    assert isinstance(create_server(), FastMCP)


def test_main_invokes_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def fake_run(self: FastMCP, *args: object, **kwargs: object) -> None:
        calls.append(True)

    monkeypatch.setattr(FastMCP, "run", fake_run)
    main()
    assert calls == [True]
