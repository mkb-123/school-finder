# School Finder

## Project Overview

A web application that helps parents find and compare schools in their local council area (e.g., Milton Keynes). It combines catchment area mapping, Ofsted ratings, club availability, private school details, and smart filtering to give parents a single place to research schooling options.

## Tech Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS
- **Mapping**: Leaflet / React-Leaflet (OpenStreetMap) for catchment radius visualisation
- **Backend**: Next.js API routes
- **Database**: PostgreSQL with PostGIS (for geospatial catchment queries)
- **ORM**: Drizzle ORM
- **Data Sources**: GOV.UK Get Information About Schools (GIAS) API, Ofsted Data downloads, school websites (scraped by agents)
- **Agent Framework**: Custom Node.js worker agents for data collection
- **Testing**: Vitest, Playwright (E2E)

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

These are background worker agents that scrape, collect, and normalise school data. They run independently and populate the database.

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

## Data Model (Key Tables)

```
schools
  - id, name, urn, type (state/private), council, address, postcode
  - lat, lng, catchment_geometry (PostGIS)
  - gender_policy (co-ed/boys/girls), faith, age_range_from, age_range_to
  - ofsted_rating, ofsted_date
  - is_private (boolean)

school_term_dates
  - id, school_id, academic_year
  - term_name, start_date, end_date
  - half_term_start, half_term_end

school_clubs
  - id, school_id
  - club_type (breakfast/after_school)
  - name, description
  - days_available, start_time, end_time
  - cost_per_session

school_performance
  - id, school_id
  - metric_type (SATs, GCSE, A-level, Progress8, Attainment8)
  - metric_value, year
  - source_url

school_reviews
  - id, school_id
  - source, rating, snippet, review_date

private_school_details
  - id, school_id
  - termly_fee, annual_fee, fee_age_group
  - school_day_start, school_day_end
  - provides_transport, transport_notes
  - holiday_schedule_notes
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
```

---

## Implementation Phases

### Phase 1: Foundation

- [ ] Project scaffolding (Next.js, Tailwind, DB setup)
- [ ] Seed database with GIAS school data for Milton Keynes
- [ ] Postcode geocoding (postcodes.io API - free)
- [ ] Basic school list page with distance from postcode

### Phase 2: Map & Catchment

- [ ] Leaflet map integration with school pins
- [ ] Catchment area polygons/radii rendered on map
- [ ] Ofsted rating colour-coded pins
- [ ] Filter controls (rating, school type, distance)

### Phase 3: Constraints & Filtering

- [ ] Constraint panel (child age, gender, school type, faith)
- [ ] Server-side filtering with PostGIS spatial queries
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

### Phase 8: Polish

- [ ] Mobile-responsive design
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] SEO (per-school pages)
- [ ] Performance optimisation (map clustering for large datasets)

---

## Development Guidelines

- Use server components by default; client components only for interactive elements (map, filters)
- All data-collection agents live in `src/agents/` and are runnable standalone via CLI
- Keep agent scraping respectful: rate-limit requests, cache responses, honour robots.txt
- Validate all user input server-side (postcodes, filter params)
- Use environment variables for API keys and DB connection strings
- Write tests for geospatial queries (catchment containment logic is critical)
