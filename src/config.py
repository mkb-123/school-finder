from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    DB_BACKEND: str = "sqlite"
    SQLITE_PATH: str = "./data/schools.db"
    DATABASE_URL: str | None = None
    POSTCODES_IO_BASE: str = "https://api.postcodes.io"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
