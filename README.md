# School Finder

A web application that helps parents find and compare schools in their local council area. It combines catchment area mapping, Ofsted ratings, club availability, private school details, and smart filtering into a single research tool.

Built for UK councils, starting with Milton Keynes.

## Features

- **Council & postcode search** with geocoded catchment lookups
- **Interactive map** (Leaflet/OpenStreetMap) with colour-coded Ofsted pins and catchment radius overlays
- **Constraint-based filtering** by age, gender, school type, faith, Ofsted rating, distance, and club availability
- **Breakfast & after-school clubs** with days, times, and costs per school
- **Private schools section** with fees, transport, hours, and age range
- **Term dates calendar** with side-by-side comparison across schools
- **Ofsted ratings & academic performance** (SATs, GCSEs, Progress 8)
- **Waiting list estimator** using historical admissions data and distance trends
- **School run journey planner** with time-of-day traffic estimates for walking, cycling, driving, and transit
- **Decision support page** with weighted scoring, auto-generated pros/cons, "what if" scenarios, and side-by-side comparison
- **SEND provision** info available behind an opt-in toggle

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Mapping | Leaflet / React-Leaflet (OpenStreetMap) |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | SQLite (default) or PostgreSQL + PostGIS |
| ORM | SQLAlchemy 2.0 |
| Data processing | Polars |
| Scraping | httpx, BeautifulSoup |
| Package manager | uv |
| Build system | Hatch / Hatchling |
| Linting | Ruff (backend), ESLint (frontend) |
| Testing | pytest, pytest-asyncio, Playwright (E2E) |

## Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Getting Started

```bash
# Clone the repository
git clone <repo-url>
cd school-finder

# Backend setup
uv sync --all-extras
uv run python -m src.main          # Starts FastAPI on http://localhost:8000

# Frontend setup (separate terminal)
cd frontend
npm install
npm run dev                         # Starts Vite on http://localhost:5173
```

### Seed the database

The app uses SQLite by default. The database file is created automatically on startup, but starts empty. To populate it with school data:

```bash
uv run python -m src.db.seed --council "Milton Keynes"
```

This imports school records from GIAS (Get Information About Schools) CSV data.

### Run data-collection agents

Agents scrape school websites to gather supplementary data (term dates, clubs, reviews):

```bash
uv run python -m src.agents.term_times --council "Milton Keynes"
uv run python -m src.agents.clubs --council "Milton Keynes"
uv run python -m src.agents.reviews_performance --council "Milton Keynes"
```

Agents cache responses to `./data/cache/` and respect rate limits.

## Configuration

The app reads configuration from environment variables (or a `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_BACKEND` | `sqlite` | `sqlite` or `postgres` |
| `SQLITE_PATH` | `./data/schools.db` | Path to SQLite database file |
| `DATABASE_URL` | — | PostgreSQL connection string (required if `DB_BACKEND=postgres`) |
| `POSTCODES_IO_BASE` | `https://api.postcodes.io` | Postcode geocoding API base URL |
| `CORS_ORIGINS` | `""` | Comma-separated allowed origins |

## Project Structure

```
school-finder/
├── src/
│   ├── main.py                 # FastAPI entrypoint
│   ├── config.py               # Pydantic Settings
│   ├── api/                    # Route handlers
│   │   ├── schools.py          # /api/schools endpoints
│   │   ├── private_schools.py  # /api/private-schools endpoints
│   │   ├── compare.py          # /api/compare
│   │   ├── decision.py         # /api/decision (scoring, pros/cons, what-if)
│   │   ├── journey.py          # /api/journey (school run routing)
│   │   ├── geocode.py          # /api/geocode
│   │   └── councils.py         # /api/councils
│   ├── db/
│   │   ├── base.py             # Abstract repository interfaces
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   ├── sqlite_repo.py      # SQLite implementation (default)
│   │   ├── factory.py          # Returns repo based on DB_BACKEND
│   │   └── seed.py             # GIAS data import script
│   ├── services/
│   │   ├── catchment.py        # Haversine distance calculations
│   │   ├── geocoding.py        # Postcode lookup via postcodes.io
│   │   ├── journey.py          # Route/travel time calculations
│   │   ├── admissions.py       # Waiting list estimation
│   │   └── decision.py         # Weighted scoring & pros/cons engine
│   ├── schemas/                # Pydantic request/response models
│   └── agents/                 # Data-collection scrapers
│       ├── base_agent.py       # Shared base (rate limiting, caching, retry)
│       ├── term_times.py       # Term dates agent
│       ├── clubs.py            # Breakfast/after-school clubs agent
│       ├── reviews_performance.py  # Ratings & academic data agent
│       └── ofsted.py           # Ofsted data agent
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Route definitions
│   │   ├── pages/              # Page components (Home, SchoolList, Compare, etc.)
│   │   ├── components/         # Reusable UI (Map, FilterPanel, SchoolCard, etc.)
│   │   └── api/client.ts       # Backend API client
│   └── e2e/                    # Playwright E2E tests
├── tests/                      # Backend pytest tests
├── data/
│   ├── schools.db              # SQLite database (auto-created)
│   ├── cache/                  # Agent response cache
│   └── seeds/                  # GIAS CSV downloads
├── pyproject.toml
└── uv.lock
```

## Architecture

### Repository pattern

The data layer uses an abstract `SchoolRepository` interface so the app runs self-contained with SQLite but can swap to PostgreSQL without changing business logic:

```python
# Factory returns the correct implementation based on config
def get_school_repository() -> SchoolRepository:
    if settings.DB_BACKEND == "postgres":
        return PostgresSchoolRepository(settings.DATABASE_URL)
    return SQLiteSchoolRepository(settings.SQLITE_PATH)
```

### Spatial queries without PostGIS

In SQLite mode, catchment checks use a Haversine formula registered as a custom SQLite function. No native extensions required.

## API

Key endpoints:

```
GET  /api/schools?council=...&postcode=...&lat=...&lng=...
     &age=&gender=&type=&min_rating=&max_distance_km=
     &has_breakfast_club=&has_afterschool_club=
GET  /api/schools/{id}
GET  /api/schools/{id}/clubs
GET  /api/schools/{id}/performance
GET  /api/schools/{id}/term-dates
GET  /api/schools/{id}/admissions
GET  /api/schools/{id}/admissions/estimate

GET  /api/private-schools?council=...&max_fee=...
GET  /api/private-schools/{id}

GET  /api/compare?ids=1,2,3
GET  /api/decision/score
GET  /api/decision/pros-cons
POST /api/decision/what-if

GET  /api/geocode?postcode=MK9+1AB
GET  /api/councils
GET  /api/journey?from_postcode=...&to_school_id=...&mode=walking
GET  /api/journey/compare
```

## Testing

```bash
# Backend tests
uv run pytest

# Lint
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Frontend E2E tests
cd frontend
npm run test:e2e
```

## Deployment

A `Dockerfile` and `fly.toml` are included for deployment to [Fly.io](https://fly.io). The Docker build produces a single container that serves both the FastAPI backend and the built frontend assets.

## License

This project is not yet licensed. All rights reserved.
