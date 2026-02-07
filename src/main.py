from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.bus_routes import router as bus_routes_router
from src.api.compare import router as compare_router
from src.api.councils import router as councils_router
from src.api.decision import router as decision_router
from src.api.geocode import router as geocode_router
from src.api.holiday_clubs import router as holiday_clubs_router
from src.api.journey import router as journey_router
from src.api.parking import router as parking_router
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

_settings = get_settings()
_cors_origins = [o.strip() for o in _settings.CORS_ORIGINS.split(",") if o.strip()] if _settings.CORS_ORIGINS else []
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
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
app.include_router(parking_router)
app.include_router(holiday_clubs_router)
app.include_router(bus_routes_router)

# Serve frontend SPA in production.
# Static assets (JS, CSS, images) are served directly from dist/assets/.
# All other non-API paths fall through to index.html for client-side routing.
if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str) -> FileResponse:
        """Serve index.html for all non-API routes (SPA client-side routing)."""
        file_path = (FRONTEND_DIST / full_path).resolve()
        if full_path and file_path.is_file() and str(file_path).startswith(str(FRONTEND_DIST.resolve())):
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
