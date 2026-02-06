# School Finder

## Project Overview

A web application that helps parents find and compare schools in their local council area (e.g., Milton Keynes). It combines catchment area mapping, Ofsted ratings, club availability, private school details, and smart filtering to give parents a single place to research schooling options.

## Tech Stack

- **Frontend**: React (Vite), TypeScript, Tailwind CSS
- **Mapping**: Leaflet / React-Leaflet (OpenStreetMap) for catchment radius visualisation
- **Backend**: Python 3.11+, FastAPI
- **Package Manager**: uv (fast Python package manager)
- **Build System**: Hatch / Hatchling
- **Database (default)**: SQLite with Haversine distance queries (zero-dependency, self-contained)
- **Database (swappable)**: PostgreSQL + PostGIS via the repository abstraction layer
- **ORM / Query Layer**: SQLAlchemy 2.0 (Core + ORM) with GeoAlchemy2 for spatial queries (Postgres only)
- **Data Sources**: GOV.UK Get Information About Schools (GIAS) API, Ofsted data downloads, school websites (scraped by agents)
- **Agent Framework**: Python async agents using httpx + BeautifulSoup/Playwright
- **Linting**: Ruff
- **Testing**: pytest, pytest-asyncio, Playwright (E2E)

---

## Architecture: Database Abstraction

The data layer uses a **repository pattern** so the app runs self-contained with SQLite out of the box but can swap to PostgreSQL (or anything else) without touching business logic.

```
src/
  db/
    base.py              # Abstract repository interfaces (ABCs)
    sqlite_repo.py       # SQLite implementation (default)
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

For SQLite mode, geospatial catchment checks use the **Haversine formula** implemented as a Python function registered as a SQLite custom function. This keeps the app fully self-contained with no native extensions required.

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
- Progress 8 / Attainment 8 scores where applicable

### 8. Waiting List Estimator

Uses historical admissions data to estimate how likely a child is to get a place:

- **Last distance offered** - how far from the school the furthest admitted child lived, per year
- **Trend analysis** - is the catchment shrinking or growing over recent years?
- **Waiting list movement** - historical data on how many places freed up after initial offers
- **Likelihood indicator** - "Very likely" / "Likely" / "Unlikely" based on the user's postcode distance vs historical cutoffs
- **Appeals success rate** - what percentage of appeals succeed at each school (where data is available)

### 9. School Run Journey Planner

Calculates realistic travel times to each school factoring in actual drop-off and pick-up times:

- **Time-of-day routing** - estimates use traffic data for **8:00-8:45am** (drop-off) and **5:00-5:30pm** (pick-up after work), not generic travel times
- **Multiple transport modes** - walking, cycling, driving, public transport
- **Route display on map** - overlay the route from your postcode to the school
- **Multi-school comparison** - "School A is 8 min walk, School B is 22 min walk at drop-off time"
- **Parking/drop-off notes** - flag schools with known parking difficulties or drop-off restrictions

### 10. Decision Support Page

A **dedicated separate page** that helps parents weigh up their options holistically:

- **Weighted scoring** - user sets what matters most to them (distance, rating, clubs, fees, etc.) and schools get ranked by a personalised composite score
- **Pros/cons summary** - auto-generated bullet points for each school (e.g., "Outstanding Ofsted but no breakfast club", "10 min walk but Requires Improvement")
- **Side-by-side comparison** - pick 2-4 schools and see every metric in columns
- **"What if" scenarios** - "What if I'm OK with a 15 min drive?" / "What if I drop my minimum Ofsted to Good?"
- **Shortlist** - save schools to a shortlist that persists across sessions (local storage)
- **Export** - download comparison as PDF or share via link

### 11. SEND Provision (Hidden by Default)

SEND (Special Educational Needs & Disabilities) information is available but **hidden by default** behind a toggle:

- Enable via a "Show SEND information" toggle in settings/filters
- When enabled: SEND provision detail, EHCP-friendly flags, accessibility info, specialist unit availability
- Hidden by default to reduce clutter for users who don't need it

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
- Are runnable standalone: `uv run python -m src.agents.term_times --council "Milton Keynes"`
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
  - catchment_geometry (optional - WKT polygon for precise boundaries, Postgres only)
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

admissions_history
  - id (PK), school_id (FK), academic_year
  - places_offered, applications_received
  - last_distance_offered_km
  - waiting_list_offers (how many came off the list)
  - appeals_heard, appeals_upheld

user_shortlists
  - Stored client-side in localStorage (no server table needed)
```

---

## Page Structure

```
/                           - Landing page: select council, enter postcode
/schools                    - Results list + map (state schools in catchment)
/schools/[id]               - Individual school detail page
/schools/map                - Full-screen map with filters (Ofsted, type, clubs)
/private-schools            - Private school browser with fees, transport, hours
/private-schools/[id]       - Individual private school detail page
/compare                    - Side-by-side school comparison
/term-dates                 - Calendar view of term dates across schools
/decision-support           - Weighted scoring, pros/cons, "what if" scenarios
/journey                    - School run planner (drop-off & pick-up time routing)
```

---

## Project Structure

```
school-finder/
  CLAUDE.md
  README.md
  pyproject.toml              # Hatch build config + dependencies
  uv.lock                    # uv lockfile (committed)
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
      journey.py              # /api/journey (school run routing)
      admissions.py           # /api/admissions (waiting list data)
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
      journey.py              # School run route calculations
      admissions.py           # Waiting list estimation logic
      decision.py             # Weighted scoring & pros/cons generation
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
        DecisionSupport.tsx   # Weighted scoring & what-if scenarios
        Journey.tsx           # School run planner
      components/
        Map.tsx               # Leaflet map wrapper
        CatchmentOverlay.tsx  # Catchment radius/polygon on map
        FilterPanel.tsx       # Constraint controls
        SchoolCard.tsx        # School summary card
        ClubList.tsx          # Breakfast/after-school club display
        PerformanceChart.tsx  # Academic results visualisation
        WaitingListGauge.tsx  # Likelihood indicator for admissions
        JourneyCard.tsx       # Travel time comparison card
        SendToggle.tsx        # SEND info toggle (hidden by default)
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
GET  /api/schools/{id}/admissions          # Waiting list / historical admissions
GET  /api/private-schools?council=...&age=&gender=&max_fee=...
GET  /api/private-schools/{id}
GET  /api/geocode?postcode=MK9+1AB
GET  /api/councils                         # List available councils
GET  /api/compare?ids=1,2,3               # Compare multiple schools
GET  /api/journey?from_postcode=...&to_school_id=...&mode=walking|driving|cycling|transit
```

---

## Implementation Phases

### Phase 1: Foundation

- [ ] Project scaffolding (FastAPI, pyproject.toml, uv, SQLite setup)
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

### Phase 8: Waiting List Estimator

- [ ] Historical admissions data model and seeding
- [ ] Waiting list estimation service
- [ ] Likelihood indicator UI component
- [ ] Trend visualisation (catchment distance over years)

### Phase 9: School Run Journey Planner

- [ ] Journey calculation service (using routing API with time-of-day traffic)
- [ ] Journey API endpoint
- [ ] Route overlay on map
- [ ] Multi-school travel time comparison UI

### Phase 10: Decision Support Page

- [ ] Weighted scoring engine in backend
- [ ] Pros/cons auto-generation logic
- [ ] Decision support frontend page
- [ ] "What if" scenario controls
- [ ] Shortlist (localStorage) + PDF export

### Phase 11: PostgreSQL Support & Polish

- [ ] PostgreSQL + PostGIS repository implementation
- [ ] Polygon-based catchment boundaries (when PostGIS available)
- [ ] Alembic migrations for both backends
- [ ] SEND toggle and data (hidden by default)
- [ ] Mobile-responsive design
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] Performance optimisation (map clustering for large datasets)

---

## Running the Project

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Backend
uv sync --all-extras               # Install all dependencies (including dev)
uv run python -m src.main          # Start FastAPI server (uvicorn)

# Frontend
cd frontend && npm install && npm run dev

# Seed the database
uv run python -m src.db.seed --council "Milton Keynes"

# Run agents
uv run python -m src.agents.term_times --council "Milton Keynes"
uv run python -m src.agents.clubs --council "Milton Keynes"
uv run python -m src.agents.reviews_performance --council "Milton Keynes"

# Lint
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Tests
uv run pytest
```

---

## Development Agents (Claude Subagents)

These are Claude Code subagents used during development to parallelise work across different parts of the codebase. They are invoked via the Task tool during implementation sessions.

### Coordinator Agent

**Focus**: Orchestrates the other agents, ensures consistency, and commits regularly.

This is the main agent (you, running in the primary conversation). Its responsibilities:

- **Dispatch work** to specialist agents via the Task tool, running them in parallel where possible
- **Check agent output** after each batch completes: verify imports resolve, lint passes, tests pass
- **Reconcile conflicts** when multiple agents touch related code (e.g., frontend API calls must match backend routes, schemas must match models)
- **Commit and push regularly** - after each batch of agent work lands, stage, commit with a descriptive message, and push. Don't let untracked files accumulate
- **Track progress** via the TodoWrite tool, marking tasks complete as agents finish
- **Re-dispatch on failure** - if an agent's output has lint errors or broken imports, either fix inline or re-dispatch a focused fix agent
- **Sequence dependencies** - agents that depend on each other's output (e.g., frontend needs API contract finalised first) should be dispatched sequentially, not in parallel

Workflow per phase:
1. Plan which agents to dispatch and identify dependencies
2. Launch independent agents in parallel (via Task with run_in_background=true)
3. Monitor progress (check output files, git status)
4. When agents complete: review changes, run lint + tests, fix issues
5. Commit and push with a clear message describing what was built
6. Repeat for next batch

### GIAS Data Agent

**Focus**: GIAS dataset research, download, parsing, and seed script.

- Understands the GIAS CSV schema (hundreds of columns, inconsistent encoding)
- Maps GIAS columns to the School model fields
- Builds and maintains `src/db/seed.py`
- Handles edge cases: missing lat/lng, closed schools, merged schools

### Geospatial Agent

**Focus**: All coordinate, distance, and mapping logic.

- Implements and tests the Haversine formula in `src/services/catchment.py`
- Builds the SQLite custom function registration
- Handles coordinate system gotchas (WGS84 vs OSGB36)
- Builds and tests catchment polygon rendering for the frontend map
- Validates distance calculations against known reference points

### Scraping Agent Builder

**Focus**: Building and testing the 3+ data-collection agents.

- Builds `src/agents/base_agent.py` with retry, rate-limit, and caching logic
- Builds each specific scraper (term times, clubs, reviews/performance)
- Handles PDFs (term dates are often published as PDFs), broken HTML, JS-rendered pages
- Tests agents against real school websites with mocked HTTP in tests

### API & Schema Agent

**Focus**: FastAPI endpoints, Pydantic schemas, request validation.

- Designs and builds all API routes in `src/api/`
- Builds Pydantic v2 request/response models in `src/schemas/`
- Ensures consistent error handling, pagination, and filter parsing
- Gets the API contract right between backend and frontend

### Frontend Map Agent

**Focus**: Leaflet + React map integration.

- Builds map components: pins, catchment overlays, colour-coded Ofsted markers
- Implements click-to-highlight catchment areas
- Handles performance with marker clustering for large datasets
- Builds filter-driven map re-rendering

### Decision Engine Agent

**Focus**: Weighted scoring, pros/cons, and "what if" scenarios.

- Builds `src/services/decision.py` with the composite scoring algorithm
- Normalises heterogeneous data (Ofsted rating, distance in km, fee in pounds, booleans) into comparable scores
- Implements pros/cons auto-generation logic
- Builds the "what if" scenario engine

### Test Agent

**Focus**: Comprehensive test coverage for critical logic.

- Writes geospatial tests with known coordinate pairs and verified distances
- Tests filter edge cases (e.g., co-ed primary but single-sex sixth form)
- Builds API integration tests with realistic fixture data
- Tests agent scraping with mocked HTTP responses

---

## Development Guidelines

- Default to SQLite for local dev; no database server needed to get started
- Use `uv` for all Python dependency management; commit `uv.lock`
- All data-collection agents live in `src/agents/` and are runnable standalone via CLI
- Keep agent scraping respectful: rate-limit requests, cache responses, honour robots.txt
- Validate all user input server-side (postcodes, filter params)
- Use environment variables for API keys and DB connection strings (pydantic-settings)
- Write tests for geospatial queries (catchment containment logic is critical)
- Frontend: use client components only for interactive elements (map, filters)
- Repository pattern: every new query goes through the abstract interface, never directly against a specific DB
- SEND features are behind a toggle; never show SEND data unless explicitly enabled
- **Prefer Polars over pandas** for all data manipulation (CSV parsing, GIAS data processing, agent data normalisation, seed scripts). Polars is faster and more memory-efficient. Only use pandas if a third-party library requires it
