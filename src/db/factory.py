from __future__ import annotations

from functools import lru_cache

from src.config import get_settings
from src.db.base import SchoolRepository


@lru_cache
def get_school_repository() -> SchoolRepository:
    """Return a cached repository instance based on the configured backend.

    Uses ``lru_cache`` so that the same engine / session factory is reused
    across requests rather than creating a new connection pool each time.
    """
    settings = get_settings()
    if settings.DB_BACKEND == "postgres":
        raise NotImplementedError("PostgreSQL repository not yet implemented")
    from src.db.sqlite_repo import SQLiteSchoolRepository

    return SQLiteSchoolRepository(settings.SQLITE_PATH)
