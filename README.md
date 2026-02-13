# School Finder

A web application that helps parents find and compare schools in their local council area. It combines catchment area mapping, Ofsted ratings, club availability, private school details, and smart filtering into a single place to research schooling options.

**Live site:** [https://mkb-123.github.io/school-finder/](https://mkb-123.github.io/school-finder/)

## Features

- **Council & postcode search** -- enter a postcode and see all schools whose catchment covers that location
- **Interactive map** -- Leaflet/OpenStreetMap with catchment radius overlays, colour-coded by Ofsted rating
- **Constraint-based filtering** -- filter by child's age, gender, school type, faith, Ofsted rating, and distance
- **Breakfast & after-school clubs** -- per-school club listings with hours and costs
- **Private schools** -- dedicated section with fees, transport, hours, and age range
- **Term dates** -- calendar view with side-by-side comparison across schools
- **Waiting list estimator** -- historical admissions data and likelihood indicators
- **Journey planner** -- travel times by walking, cycling, driving, or public transport at realistic drop-off/pick-up times
- **Decision support** -- weighted scoring, pros/cons, side-by-side comparison, and "what if" scenarios
- **Fee comparison** -- compare private school fees across age groups
- **SEND provision** -- special educational needs information, available behind a toggle

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Mapping | Leaflet / React-Leaflet (OpenStreetMap) |
| Backend | Python 3.11+, FastAPI |
| Database | SQLite (default), PostgreSQL + PostGIS (optional) |
| ORM | SQLAlchemy 2.0 |
| Data sources | GOV.UK GIAS API, Ofsted data downloads |
| Package management | uv (Python), npm (frontend) |

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Backend

```bash
# Install Python dependencies
uv sync --all-extras

# Seed the database with school data
uv run python -m src.db.seed --council "Milton Keynes"

# Start the API server
uv run python -m src.main
```

The API server runs at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server runs at `http://localhost:5173` and proxies API requests to the backend.

### Running Data Agents

The project includes agents that collect real school data from official sources:

```bash
uv run python -m src.agents.term_times --council "Milton Keynes"
uv run python -m src.agents.clubs --council "Milton Keynes"
uv run python -m src.agents.reviews_performance --council "Milton Keynes"
```

## Development

```bash
# Lint (backend)
uv run ruff check src/ tests/

# Lint (frontend)
cd frontend && npm run lint

# Type check (frontend)
cd frontend && npm run type-check

# Tests (backend)
uv run pytest

# E2E tests (frontend)
cd frontend && npm run test:e2e
```

## Deployment

### GitHub Pages (frontend only)

The frontend is automatically deployed to GitHub Pages on every push to `main` via the `.github/workflows/deploy.yml` workflow. The static site is available at `https://mkb-123.github.io/school-finder/`.

Note: The GitHub Pages deployment serves the frontend as a static site. API-dependent features require the backend to be running separately.

### Full Stack (Fly.io)

The project includes a `fly.toml` and `Dockerfile` for full-stack deployment on Fly.io.

## Project Structure

```
school-finder/
  frontend/          # React + TypeScript + Vite
    src/
      api/           # API client
      components/    # Reusable UI components
      pages/         # Route-level page components
  src/               # Python backend
    api/             # FastAPI route handlers
    db/              # Repository pattern (SQLite / PostgreSQL)
    agents/          # Data collection agents
    services/        # Business logic
    schemas/         # Pydantic models
  tests/             # Backend tests
  data/              # SQLite database + agent cache + seed data
```

## License

This project is private and not licensed for redistribution.
