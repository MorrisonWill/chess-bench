from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(default="sqlite+aiosqlite:///./chessbench.db")
    openrouter_api_key: str | None = None
    openrouter_base_url: AnyHttpUrl = Field(default="https://openrouter.ai/api/v1")
    stockfish_path: str = Field(default="stockfish")
    dashboard_refresh_seconds: int = Field(default=10)
    scheduler_interval_seconds: float = Field(default=5.0)
    debug: bool = False
    test_mode: bool = False
    log_level: str = Field(default="INFO")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
