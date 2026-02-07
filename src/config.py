from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    DB_BACKEND: str = "sqlite"
    SQLITE_PATH: str = "./data/schools.db"
    DATABASE_URL: str | None = None
    POSTCODES_IO_BASE: str = "https://api.postcodes.io"
    CORS_ORIGINS: str = ""  # Comma-separated origins, empty = same-origin only

    # Government data source settings
    GIAS_CSV_URL_TEMPLATE: str = (
        "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/edubasealldata{date}.csv"
    )
    GIAS_CACHE_TTL_HOURS: int = 24

    OFSTED_MI_LANDING_URL: str = (
        "https://www.gov.uk/government/statistical-data-sets/"
        "monthly-management-information-ofsteds-school-inspections-outcomes"
    )
    OFSTED_CACHE_TTL_HOURS: int = 168  # 1 week (data updates monthly)

    EES_API_BASE: str = "https://api.education.gov.uk/statistics/v1"
    EES_SUBSCRIPTION_KEY: str | None = None  # Optional; CSV download works without

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
