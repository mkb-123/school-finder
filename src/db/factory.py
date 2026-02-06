from __future__ import annotations

from typing import Any

from src.config import get_settings


def get_school_repository() -> Any:
    """Return the appropriate school repository based on configuration.

    Actual implementations (SQLiteSchoolRepository, PostgresSchoolRepository)
    will be registered in the database layer build phase.
    """
    settings = get_settings()
    if settings.DB_BACKEND == "postgres":
        raise NotImplementedError("PostgreSQL repository not yet implemented")
    raise NotImplementedError("SQLite repository not yet implemented")
