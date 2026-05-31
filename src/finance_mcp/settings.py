"""Runtime configuration loaded from environment variables (prefix FINANCE_MCP_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server configuration. All fields have safe defaults so zero-config works."""

    model_config = SettingsConfigDict(env_prefix="FINANCE_MCP_", env_file=".env")

    quote_cache_ttl_seconds: int = 30
    history_cache_ttl_seconds: int = 300
    fundamentals_cache_ttl_seconds: int = 3600


def get_settings() -> Settings:
    """Return the loaded settings instance."""
    return Settings()
