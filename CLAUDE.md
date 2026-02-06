# School Finder

## Project Overview

A web application that helps parents find and compare schools in their local council area (e.g., Milton Keynes). It combines catchment area mapping, Ofsted ratings, club availability, private school details, and smart filtering to give parents a single place to research schooling options.

## Tech Stack

- **Frontend**: React (Vite), TypeScript, Tailwind CSS
- **Mapping**: Leaflet / React-Leaflet (OpenStreetMap) for catchment radius visualisation
- **Backend**: Python, FastAPI
- **Database (default)**: SQLite with SpatiaLite extension (zero-dependency, self-contained)
- **Database (swappable)**: PostgreSQL + PostGIS via the repository abstraction layer
- **ORM / Query Layer**: SQLAlchemy 2.0 (Core + ORM) with GeoAlchemy2 for spatial queries
- **Data Sources**: GOV.UK Get Information About Schools (GIAS) API, Ofsted data downloads, school websites (scraped by agents)
- **Agent Framework**: Python async agents using httpx + BeautifulSoup/Playwright
- **Testing**: pytest, pytest-asyncio, Playwright (E2E)

---

## Architecture: Database Abstraction

The data layer uses a **repository pattern** so the app runs self-contained with SQLite out of the box but can swap to PostgreSQL (or anything else) without touching business logic.

```
src/
  db/
    base.py              # Abstract repository interfaces (ABCs)
    sqlite_repo.py       # SQLite + SpatiaLite implementation (default)
    postgres_repo.py     # PostgreSQL + PostGIS implementation (optional)
    factory.py           # Returns the correct repo based on config / env var
    models.py            # SQLAlchemy ORM models (shared across backends)
    migrations/          # Alembic migrations
```

### How it works

```python
# base.py - Abstract interface
class SchoolRepository(ABC):
    @abstractmethod
    async def find_schools_in_catchment(self, lat: float, lng: float, council: str) -> list[School]: ...

    @abstractmethod
    async def find_schools_by_filters(self, filters: SchoolFilters) -> list[School]: ...

    @abstractmethod
    async def get_school_by_id(self, school_id: int) -> School | None: ...

# factory.py - Pick implementation based on config
def get_school_repository() -> SchoolRepository:
    backend = settings.DB_BACKEND  # "sqlite" (default) or "postgres"
    if backend == "postgres":
        return PostgresSchoolRepository(settings.DATABASE_URL)
    return SQLiteSchoolRepository(settings.SQLITE_PATH)  # default: ./data/schools.db
```

### Spatial queries without PostGIS

For SQLite mode, geospatial catchment checks use the **Haversine formula** implemented as a Python function registered as a SQLite custom function. This keeps the app fully self-contained with no native extensions required. SpatiaLite is used opportunistically if available (for polygon-based catchment boundaries) but is not required — the app falls back to radius-based distance calculations.

```python
# Haversine fallback for SQLite (no extensions needed)
def haversine_distance(lat1, lng1, lat2, lng2) -> float:
    """Returns distance in kilometres between two coordinates."""
    ...

# Registered as SQLite function so it can be used in queries
connection.create_function("haversine", 4, haversine_distance)

# Query: SELECT * FROM schools WHERE haversine(lat, lng, ?, ?) < catchment_radius_km
```

### Configuration

```env
# .env
DB_BACKEND=sqlite          # "sqlite" (default) or "postgres"
SQLITE_PATH=./data/schools.db
# DATABASE_URL=postgresql://user:pass@localhost:5432/school_finder  # only if postgres
```

---

## Core Features

### 1. Council & Postcode Search

- User selects a council (e.g., Milton Keynes)
- User enters their postcode
- App geocodes the postcode and returns all schools whose catchment area covers that location
- Results shown as a list and on an interactive map

### 2. Interactive Catchment Map

- Each school displays its catchment boundary/radius on the map
- Click a school to see its catchment area highlighted
- **Filter by Ofsted rating** on the map (e.g., show only Outstanding schools and their catchment radii)
- Colour-coded pins/areas by rating: Outstanding (green), Good (blue), Requires Improvement (amber), Inadequate (red)

### 3. Constraint-Based Filtering

Users can set constraints to automatically exclude incompatible schools:

- **Child's age** - only show schools accepting that age group (Reception, Year 1, etc.)
- **Child's gender** - exclude all-boys or all-girls schools as appropriate
- **School type** - state / academy / free school / faith school
- **Ofsted rating** - minimum rating filter
- **Distance** - maximum distance from postcode
- **Religion/faith** - filter faith schools

### 4. Breakfast & After-School Clubs

- Per-school listing of breakfast club availability, hours, and cost
- Per-school listing of after-school club options (sports, arts, homework club, etc.)
- Filter: "only show schools with breakfast club" / "only show schools with after-school club"
- Days of the week and time ranges

### 5. Private Schools (Separate Section)

A dedicated section for independent/private schools with additional data:

- **Fees** - termly and annual fee breakdowns by age group
- **Hours** - school day start/end times, extended day options
- **Transport** - whether the school provides transport, routes, and eligibility
- **Age range** - from what age they accept children
- **Holiday schedules** - term dates, half-terms, holiday length
- **Gender policy** - co-ed, boys only, girls only
- Same map and constraint filtering as state schools

### 6. Term Times & Holiday Schedules

- Calendar view showing term dates for each school
- Compare term dates across schools side by side
- Highlight differences between schools (some academies set their own dates)

### 7. Reviews, Ratings & Performance

- Ofsted rating and inspection date
- Academic performance data (SATs results for primary, GCSE/A-level for secondary)
- Parent reviews (aggregated from public sources)
- School-specific strengths (SEND provision, sports, arts, languages, etc.)
- Progress 8 / Attainment 8 scores where applicable

---

## Specialist Data-Collection Agents

Python async agents that scrape, collect, and normalise school data. They run independently as CLI commands and populate the database via the repository layer.

```
src/agents/
  base_agent.py          # Shared agent base class (rate limiting, caching, error handling)
  term_times.py          # Agent 1
  clubs.py               # Agent 2
  reviews_performance.py # Agent 3
```

All agents:
- Are runnable standalone: `python -m src.agents.term_times --council "Milton Keynes"`
- Use httpx for async HTTP + BeautifulSoup for parsing
- Respect rate limits (configurable delay between requests)
- Cache raw responses to `./data/cache/` to avoid re-fetching
- Write results through the repository abstraction (works with SQLite or Postgres)

### Agent 1: Term Times Agent

**Purpose**: Find and store term dates for every school in the selected council(s).

- Scrapes council websites for published term date PDFs/pages
- Handles academies/free schools that set their own term dates (checks school websites)
- Normalises dates into a consistent format (start/end per term, half-term breaks)
- Stores results in `school_term_dates` table
- Runs periodically to pick up updates (councils publish ~1 year ahead)

### Agent 2: Breakfast & After-School Clubs Agent

**Purpose**: Discover what clubs each school offers, their hours, and costs.

- Scrapes school websites for "wraparound care", "breakfast club", "after-school club" pages
- Extracts: club name, type (breakfast/after-school), days available, time range, cost
- Falls back to checking Ofsted reports for wraparound care mentions
- Stores results in `school_clubs` table

### Agent 3: Reviews, Ratings & Performance Agent

**Purpose**: Aggregate ratings, academic results, and reviews for each school.

- Pulls Ofsted inspection data from the Ofsted data downloads
- Pulls academic performance from DfE school performance tables
- Scrapes parent review snippets from public review sites
- Computes a composite "parent satisfaction" indicator
- Stores results in `school_performance` table

---

## Data Model (SQLAlchemy ORM)

```
schools
  - id (PK), name, urn, type (state/private), council, address, postcode
  - lat, lng, catchment_radius_km (float - used for distance-based catchment)
  - catchment_geometry (optional - WKT polygon for precise boundaries)
  - gender_policy (co-ed/boys/girls), faith, age_range_from, age_range_to
  - ofsted_rating, ofsted_date
  - is_private (boolean)

school_term_dates
  - id (PK), school_id (FK), academic_year
  - term_name, start_date, end_date
  - half_term_start, half_term_end

school_clubs
  - id (PK), school_id (FK)
  - club_type (breakfast/after_school)
  - name, description
  - days_available, start_time, end_time
  - cost_per_session

school_performance
  - id (PK), school_id (FK)
  - metric_type (SATs, GCSE, A-level, Progress8, Attainment8)
  - metric_value, year
  - source_url

school_reviews
  - id (PK), school_id (FK)
  - source, rating, snippet, review_date

private_school_details
  - id (PK), school_id (FK)
  - termly_fee, annual_fee, fee_age_group
  - school_day_start, school_day_end
  - provides_transport, transport_notes
  - holiday_schedule_notes
```

---

## Project Structure

```
school-finder/
  CLAUDE.md
  README.md
  pyproject.toml              # Python project config (dependencies, scripts)
  .env.example
  data/
    schools.db                # SQLite database (created on first run)
    cache/                    # Agent response cache
    seeds/                    # GIAS CSV downloads for seeding
  src/
    __init__.py
    config.py                 # Settings (pydantic-settings, reads .env)
    main.py                   # FastAPI app entrypoint
    api/
      __init__.py
      schools.py              # /api/schools endpoints
      private_schools.py      # /api/private-schools endpoints
      term_dates.py           # /api/term-dates endpoints
      clubs.py                # /api/clubs endpoints
      performance.py          # /api/performance endpoints
      geocode.py              # /api/geocode (postcode lookup proxy)
    db/
      __init__.py
      base.py                 # Abstract repository interfaces
      models.py               # SQLAlchemy ORM models
      sqlite_repo.py          # SQLite implementation
      postgres_repo.py        # PostgreSQL implementation
      factory.py              # Repository factory
      migrations/             # Alembic
    agents/
      __init__.py
      base_agent.py           # Shared base class
      term_times.py           # Agent 1: term dates
      clubs.py                # Agent 2: breakfast/after-school clubs
      reviews_performance.py  # Agent 3: ratings & academic data
    services/
      __init__.py
      catchment.py            # Catchment calculation logic (haversine, polygon)
      filters.py              # Constraint-based filtering logic
      geocoding.py            # Postcode geocoding via postcodes.io
    schemas/
      __init__.py
      school.py               # Pydantic request/response models
      filters.py              # Filter parameter schemas
  frontend/
    package.json
    vite.config.ts
    src/
      App.tsx
      pages/
        Home.tsx              # Council select + postcode input
        SchoolList.tsx        # Results list + map
        SchoolDetail.tsx      # Individual school page
        PrivateSchools.tsx    # Private school browser
        PrivateSchoolDetail.tsx
        Compare.tsx           # Side-by-side comparison
        TermDates.tsx         # Calendar view
      components/
        Map.tsx               # Leaflet map wrapper
        CatchmentOverlay.tsx  # Catchment radius/polygon on map
        FilterPanel.tsx       # Constraint controls
        SchoolCard.tsx        # School summary card
        ClubList.tsx          # Breakfast/after-school club display
        PerformanceChart.tsx  # Academic results visualisation
  tests/
    conftest.py
    test_catchment.py         # Geospatial logic tests
    test_filters.py           # Constraint filtering tests
    test_api/                 # API endpoint tests
    test_agents/              # Agent tests with mocked HTTP
```

---

## API Endpoints

```
GET  /api/schools?council=...&postcode=...&lat=...&lng=...
     &age=&gender=&type=&min_rating=&max_distance_km=&has_breakfast_club=&has_afterschool_club=
GET  /api/schools/{id}
GET  /api/schools/{id}/clubs
GET  /api/schools/{id}/performance
GET  /api/schools/{id}/term-dates
GET  /api/private-schools?council=...&age=&gender=&max_fee=...
GET  /api/private-schools/{id}
GET  /api/geocode?postcode=MK9+1AB
GET  /api/councils                    # List available councils
GET  /api/compare?ids=1,2,3           # Compare multiple schools
```

---

## Implementation Phases

### Phase 1: Foundation

- [ ] Project scaffolding (FastAPI, pyproject.toml, SQLite setup)
- [ ] SQLAlchemy models + repository pattern (base, sqlite, factory)
- [ ] Seed database with GIAS school data for Milton Keynes
- [ ] Postcode geocoding service (postcodes.io - free, no key)
- [ ] Basic `/api/schools` endpoint with distance-from-postcode sorting
- [ ] Minimal React frontend with school list

### Phase 2: Map & Catchment

- [ ] Leaflet map integration with school pins
- [ ] Catchment radius circles rendered on map
- [ ] Haversine-based "in catchment" query for SQLite
- [ ] Ofsted rating colour-coded pins
- [ ] Filter controls (rating, school type, distance)

### Phase 3: Constraints & Filtering

- [ ] Constraint panel (child age, gender, school type, faith)
- [ ] Server-side filtering in repository layer
- [ ] URL-based filter state for shareable links

### Phase 4: Clubs & Wraparound Care

- [ ] Breakfast & after-school clubs agent (Agent 2)
- [ ] Club data display on school detail pages
- [ ] Filter: "has breakfast club" / "has after-school club"

### Phase 5: Private Schools

- [ ] Private school data import
- [ ] Fees, hours, transport, age range display
- [ ] Dedicated private school pages and map section

### Phase 6: Term Times

- [ ] Term times agent (Agent 1)
- [ ] Calendar view component
- [ ] Side-by-side term date comparison

### Phase 7: Reviews & Performance

- [ ] Performance agent (Agent 3)
- [ ] Academic results display (SATs, GCSEs, Progress 8)
- [ ] Parent review aggregation
- [ ] Performance comparison across schools

### Phase 8: PostgreSQL Support & Polish

- [ ] PostgreSQL + PostGIS repository implementation
- [ ] Polygon-based catchment boundaries (when PostGIS available)
- [ ] Alembic migrations for both backends
- [ ] Mobile-responsive design
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] Performance optimisation (map clustering for large datasets)

---

## Running the Project

```bash
# Backend
pip install -e ".[dev]"         # Install with dev dependencies
python -m src.main              # Start FastAPI server (uvicorn)

# Frontend
cd frontend && npm install && npm run dev

# Seed the database
python -m src.db.seed --council "Milton Keynes"

# Run agents
python -m src.agents.term_times --council "Milton Keynes"
python -m src.agents.clubs --council "Milton Keynes"
python -m src.agents.reviews_performance --council "Milton Keynes"

# Tests
pytest
```

---

## Development Guidelines

- Default to SQLite for local dev; no database server needed to get started
- All data-collection agents live in `src/agents/` and are runnable standalone via CLI
- Keep agent scraping respectful: rate-limit requests, cache responses, honour robots.txt
- Validate all user input server-side (postcodes, filter params)
- Use environment variables for API keys and DB connection strings (pydantic-settings)
- Write tests for geospatial queries (catchment containment logic is critical)
- Frontend: use client components only for interactive elements (map, filters)
- Repository pattern: every new query goes through the abstract interface, never directly against a specific DB
