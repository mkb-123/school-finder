from __future__ import annotations

import os

from src.db.base import SchoolRepository
from src.db.sqlite_repo import SQLiteSchoolRepository


def get_school_repository() -> SchoolRepository:
    """Return the appropriate :class:`SchoolRepository` implementation.

    The backend is selected by the ``DB_BACKEND`` environment variable:

    * ``"sqlite"`` (default) -- uses :class:`SQLiteSchoolRepository`
    * ``"postgres"``         -- reserved for future PostgreSQL + PostGIS support

    Raises:
        NotImplementedError: If the requested backend is not yet implemented.
    """
    backend = os.environ.get("DB_BACKEND", "sqlite").lower()

    if backend == "sqlite":
        sqlite_path = os.environ.get("SQLITE_PATH", "./data/schools.db")
        return SQLiteSchoolRepository(sqlite_path)

    if backend == "postgres":
        raise NotImplementedError(
            "PostgreSQL backend is not yet implemented. "
            "Set DB_BACKEND=sqlite or omit the variable to use the default SQLite backend."
        )

    raise ValueError(f"Unknown DB_BACKEND: {backend!r}. Supported values: 'sqlite', 'postgres'.")
