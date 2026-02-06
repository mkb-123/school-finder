from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.compare import router as compare_router
from src.api.councils import router as councils_router
from src.api.decision import router as decision_router
from src.api.geocode import router as geocode_router
from src.api.journey import router as journey_router
from src.api.private_schools import router as private_schools_router
from src.api.schools import router as schools_router
from src.config import get_settings

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Ensure the data directory, SQLite database, and tables exist on startup."""
    settings = get_settings()
    db_path = Path(settings.SQLITE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create all tables if they don't exist
    from src.db.models import Base
    from src.db.sqlite_repo import SQLiteSchoolRepository

    repo = SQLiteSchoolRepository(settings.SQLITE_PATH)
    async with repo._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield


app = FastAPI(
    title="School Finder API",
    description="API for finding and comparing schools in UK council areas",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schools_router)
app.include_router(private_schools_router)
app.include_router(geocode_router)
app.include_router(councils_router)
app.include_router(compare_router)
app.include_router(decision_router)
app.include_router(journey_router)

# Serve frontend build (production). The SPA catch-all must come AFTER API routes.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
