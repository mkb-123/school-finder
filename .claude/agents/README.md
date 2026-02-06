# Claude AI Specialist Agents

This directory contains specialist agent configurations for Claude AI to intelligently find and extract school data from various UK government and public sources.

## Available Agents

### 1. Ofsted Specialist (`ofsted-specialist.md`)
**Purpose**: Find official Ofsted inspection ratings and reports

**Data Sources**:
- Ofsted Data View (reports.ofsted.gov.uk)
- Ofsted Management Information CSV
- Individual school Ofsted reports

**Use Cases**:
- Find current Ofsted rating for a specific school
- Download latest inspection data for all schools in a council
- Verify Ofsted ratings in database against official sources
- Extract detailed inspection judgements from reports

**Example Prompt**:
```
You are an Ofsted Specialist Agent. Find the current Ofsted rating for Caroline Haslett Primary School (URN 110394) in Milton Keynes. Use the Ofsted Data View at reports.ofsted.gov.uk and provide the rating, inspection date, and report URL.
```

---

### 2. Clubs Specialist (`clubs-specialist.md`)
**Purpose**: Find breakfast clubs, after-school clubs, and wraparound care

**Data Sources**:
- School websites (wraparound care pages)
- Council childcare directories
- Third-party childcare provider websites
- School prospectuses and handbooks

**Use Cases**:
- Find all clubs offered at a specific school
- Extract club times, costs, and booking methods
- Compare club offerings across multiple schools
- Identify schools with early breakfast clubs for working parents

**Example Prompt**:
```
You are a Clubs Specialist Agent. Find all breakfast and after-school clubs at Caroline Haslett Primary School, Milton Keynes. Extract club names, times, costs, and how parents can book. Search the school website and council childcare directory.
```

---

### 3. Term Times Specialist (`term-times-specialist.md`)
**Purpose**: Extract school term dates and holiday schedules

**Data Sources**:
- Council term dates pages (for maintained schools)
- Individual school websites (for academies)
- Academy trust websites
- School calendar downloads (ICS files)

**Use Cases**:
- Get term dates for a specific school
- Extract council-wide standard term dates
- Compare holiday lengths between schools
- Identify INSET days when schools are closed

**Example Prompt**:
```
You are a Term Times Specialist Agent. Find the term dates for all Milton Keynes maintained schools for the 2025/2026 academic year. Get the dates from the Milton Keynes Council website and list all terms, half-terms, and INSET days.
```

---

### 4. Performance & Reviews Specialist (`performance-specialist.md`)
**Purpose**: Find academic performance data and parent reviews

**Data Sources**:
- DfE Performance Tables (compare-school-performance.service.gov.uk)
- Ofsted detailed inspection reports
- Parent review sites (SchoolGuide, Mumsnet)
- Council family information services

**Use Cases**:
- Get latest SATs/GCSE results for a school
- Extract Progress 8 scores for secondary schools
- Compare performance across multiple schools
- Find parent reviews and ratings
- Analyze historical performance trends

**Example Prompt**:
```
You are a Performance & Reviews Specialist Agent. Get the latest Key Stage 2 SATs results for Caroline Haslett Primary School (URN 110394). Include reading, writing, maths results and compare to national averages. Also find any parent reviews for this school.
```

---

### 5. UX Design Specialist (`ux-design-specialist.md`)
**Purpose**: World-class user experience design — make every page intuitive, beautiful, and effortless

**Expertise**:
- Progressive disclosure and visual hierarchy
- Mobile-first responsive design
- Micro-interactions and transitions
- Accessibility (WCAG 2.1 AA)
- Empty states, error states, and loading states
- Copy and microcopy review
- Comparison workflow optimisation
- Map UX (pin density, zoom, info panels)

**Use Cases**:
- Review a page for visual hierarchy, information density, and mobile responsiveness
- Audit a component for accessibility compliance
- Walk through a user flow and identify friction points
- Critique copy and microcopy for parent-friendliness

**Example Prompt**:
```
You are the UX Design Specialist Agent (see .claude/agents/ux-design-specialist.md). Review the SchoolDetail.tsx page for visual hierarchy, information density, and mobile responsiveness. Identify the top 5 UX issues and provide specific fixes.
```

---

### 6. Admissions Specialist (`admissions-specialist.md`)
**Purpose**: Extract admissions policies, oversubscription criteria, and application requirements

**Data Sources**:
- School admissions policies on school websites
- Council admissions booklets (PDF)
- DfE admissions data
- School Adjudicator determinations

**Use Cases**:
- Extract oversubscription priority order for a school
- Find supplementary information form (SIF) requirements and deadlines
- Identify faith school religious practice requirements
- Get historical last distance offered data

**Example Prompt**:
```
You are an Admissions Specialist Agent. Extract the full oversubscription criteria for Caroline Haslett Primary School. List the priority order, any faith requirements, whether a SIF is needed, and the last distance offered for the past 3 years.
```

---

### 7. Transport & Journey Specialist (`transport-specialist.md`)
**Purpose**: Find school transport options, bus routes, walking safety, and parking information

**Data Sources**:
- Council school transport pages
- School websites (transport sections)
- Local authority transport policies
- Road safety reports

**Use Cases**:
- Find school bus routes and stop locations
- Check free transport eligibility thresholds
- Assess walking route safety
- Gather parking and drop-off intel

**Example Prompt**:
```
You are a Transport Specialist Agent. Find all school bus routes serving schools in Milton Keynes. Include stop locations, pick-up times, eligibility criteria, and costs. Also check free transport distance thresholds.
```

---

### 8. Private School Specialist (`private-school-specialist.md`)
**Purpose**: Extract detailed information from independent/private school websites

**Data Sources**:
- Independent school websites
- ISC (Independent Schools Council) directory
- ISI (Independent Schools Inspectorate) reports
- Good Schools Guide

**Use Cases**:
- Extract full fee breakdown including hidden costs
- Find bursary and scholarship availability
- Get entry assessment process details
- Check boarding options and Saturday school policies

**Example Prompt**:
```
You are a Private School Specialist Agent. Find the complete fee structure for [School Name] including hidden costs (lunches, trips, uniform, exam fees). Also check for bursary availability and the entrance assessment process.
```

---

### 9. Uniform & Prospectus Specialist (`uniform-prospectus-specialist.md`)
**Purpose**: Find school uniform details, costs, and prospectus/welcome pack links

**Data Sources**:
- School websites (uniform policy pages)
- School prospectus PDFs
- Uniform supplier websites
- PTA/parent group pages

**Use Cases**:
- Extract uniform requirements and approximate costs
- Find prospectus PDF links for school detail pages
- Check if generic/supermarket uniforms are accepted
- Locate school ethos statements

**Example Prompt**:
```
You are a Uniform & Prospectus Specialist Agent. Find the uniform requirements for Caroline Haslett Primary School including colours, required items, supplier, and approximate cost for a full set. Also locate the school prospectus PDF.
```

---

### 10. Demographics & Census Specialist (`demographics-specialist.md`)
**Purpose**: Extract and interpret DfE school census data

**Data Sources**:
- DfE School Census data (explore-education-statistics.service.gov.uk)
- DfE Performance Tables
- GIAS dataset
- Ofsted Data View

**Use Cases**:
- Get ethnic diversity and EAL percentages for a school
- Find FSM eligibility rates (socioeconomic proxy)
- Extract attendance and exclusion rates
- Track class size and pupil-teacher ratio trends

**Example Prompt**:
```
You are a Demographics Specialist Agent. Get the latest census data for all primary schools in Milton Keynes. Include ethnic diversity breakdown, FSM percentage, EAL percentage, attendance rate, and average class size.
```

---

### 11. Catchment & Boundary Specialist (`catchment-specialist.md`)
**Purpose**: Extract school catchment area boundaries and admission zones

**Data Sources**:
- Council admissions maps (interactive or PDF)
- Council GIS data portals
- School admissions policies (text descriptions)
- Historical last distance offered data

**Use Cases**:
- Extract catchment boundary polygons from council maps
- Estimate effective catchment radius from historical data
- Identify catchment overlaps between schools
- Track catchment changes over time

**Example Prompt**:
```
You are a Catchment Specialist Agent. Find the catchment area boundaries for all primary schools in Milton Keynes. Extract polygon data where available, or estimate catchment radius from last distance offered data.
```

---

### 12. Python Backend Specialist (`python-backend-specialist.md`)
**Purpose**: Expert Python developer for FastAPI, SQLAlchemy 2.0, async Python, and Pydantic v2

**Expertise**:
- FastAPI route design, dependency injection, middleware
- SQLAlchemy 2.0 async sessions, query optimisation
- Repository pattern implementation
- Pydantic v2 request/response models
- Python 3.11+, uv, Ruff

**Use Cases**:
- Build new API endpoints with proper schemas and validation
- Optimise database queries
- Refactor services to use the repository pattern correctly
- Add error handling to existing endpoints

**Example Prompt**:
```
You are the Python Backend Specialist Agent. Build a new /api/schools/{id}/demographics endpoint that returns census data from the demographics table. Use the repository pattern, create Pydantic response models, and add proper error handling.
```

---

### 13. React & TypeScript Frontend Specialist (`react-frontend-specialist.md`)
**Purpose**: Expert frontend developer for React 18+, TypeScript, Tailwind CSS, and React-Leaflet

**Expertise**:
- React 18+ with hooks, context, suspense
- TypeScript strict mode, generics
- Tailwind CSS responsive design
- React-Leaflet map components
- Accessibility and performance optimisation

**Use Cases**:
- Build new pages with data fetching, loading, and error states
- Create reusable components following the design system
- Integrate new API endpoints with proper TypeScript types
- Optimise map performance with marker clustering

**Example Prompt**:
```
You are the React Frontend Specialist Agent. Build the SchoolDemographics component that displays census data from the /api/schools/{id}/demographics endpoint. Use Tailwind CSS, include loading and empty states, and ensure mobile responsiveness.
```

---

### 14. Database & Migration Specialist (`database-migration-specialist.md`)
**Purpose**: Expert in SQLAlchemy ORM models, Alembic migrations, and dual-backend support

**Expertise**:
- SQLAlchemy 2.0 ORM model design
- Alembic migration authoring
- SQLite quirks and PostgreSQL/PostGIS
- Schema evolution and data migrations

**Use Cases**:
- Add new tables with proper relationships and indexes
- Write migrations that work for both SQLite and PostgreSQL
- Add spatial columns with PostGIS fallback
- Optimise queries with proper indexing

**Example Prompt**:
```
You are the Database Specialist Agent. Add a school_demographics table to the data model with columns for ethnic_diversity_json, fsm_percentage, eal_percentage, attendance_rate, and exclusion_rate. Write the SQLAlchemy model and Alembic migration for both backends.
```

---

### 15. Data Pipeline Specialist (`data-pipeline-specialist.md`)
**Purpose**: Expert in Polars, CSV parsing, data normalisation, and GIAS dataset processing

**Expertise**:
- Polars (NOT pandas) for all data manipulation
- GIAS CSV schema and government data quirks
- ETL pipeline design
- Data validation and cleaning

**Use Cases**:
- Parse GIAS CSV and map to School model
- Build seed scripts for new data tables
- Clean and normalise messy government data
- Build incremental update pipelines

**Example Prompt**:
```
You are the Data Pipeline Specialist Agent. Build a seed script using Polars to parse the DfE school census CSV and populate the school_demographics table. Handle encoding issues, missing data, and validate percentages are in range.
```

---

### 16. Testing & QA Specialist (`testing-qa-specialist.md`)
**Purpose**: Expert in pytest, pytest-asyncio, Playwright E2E, and test fixture design

**Expertise**:
- pytest fixtures, parametrize, conftest patterns
- pytest-asyncio for async tests
- Playwright for E2E browser tests
- Geospatial test cases with verified coordinates
- Mocking external HTTP calls

**Use Cases**:
- Write comprehensive tests for new API endpoints
- Build geospatial tests with known coordinate pairs
- Create mock HTTP fixtures for agent tests
- Write E2E tests for user flows

**Example Prompt**:
```
You are the Testing Specialist Agent. Write tests for the /api/schools/{id}/demographics endpoint. Include happy path, missing school, empty data, and invalid ID cases. Use realistic fixture data and pytest-asyncio.
```

---

### 17. Security & Validation Specialist (`security-validation-specialist.md`)
**Purpose**: Expert in input validation, OWASP top 10 prevention, and secure API design

**Expertise**:
- Input validation and sanitisation
- OWASP Top 10 prevention
- Rate limiting and CORS configuration
- Dependency auditing and data privacy

**Use Cases**:
- Audit API endpoints for injection vulnerabilities
- Add proper input validation to new endpoints
- Review security headers configuration
- Check dependencies for known CVEs

**Example Prompt**:
```
You are the Security Specialist Agent. Audit the /api/schools endpoint for injection vulnerabilities, parameter tampering, and rate limiting. Check that all query params are validated via Pydantic and that SQLAlchemy parameterised queries are used throughout.
```

---

## How to Use These Agents

### Method 1: Direct Task Tool Usage

In a Claude Code conversation, use the Task tool to invoke a specialist agent:

```
Use the Task tool with subagent_type="general-purpose" and provide the agent's specialty and task.
```

Example:
```
/task "You are an Ofsted Specialist Agent (see .claude/agents/ofsted-specialist.md). Find the current Ofsted rating for Caroline Haslett Primary School URN 110394."
```

### Method 2: Ralph Wiggum Loop

Add to `.claude/ralph-wiggum/USE_CASES.md`:

```bash
/ralph-loop "You are an Ofsted Specialist Agent. Download the latest Ofsted MI CSV, extract ratings for all Milton Keynes schools, and update the database ofsted_rating and ofsted_date fields. Verify all updates." --completion-promise "OFSTED_UPDATED" --max-iterations 20
```

### Method 3: Natural Language Request

Simply ask Claude Code in natural language, and it will recognize the task and use the appropriate specialist agent:

```
"Can you find the Ofsted rating for Caroline Haslett Primary School?"
```

Claude will automatically reference the Ofsted specialist agent configuration and search accordingly.

---

## Agent Design Principles

All specialist agents follow these principles:

1. **Authoritative Sources First**: Always use official UK government sources (Ofsted, DfE, GIAS) as primary sources
2. **URN-Based Matching**: Use Unique Reference Numbers (URN) for reliable school identification
3. **Data Validation**: Cross-reference multiple sources and flag outdated or suspicious data
4. **Structured Output**: Return data in JSON format for easy database integration
5. **Source Attribution**: Always include source URLs for verification
6. **Graceful Fallbacks**: If primary source fails, try secondary sources or manual search strategies

---

## Integration with School Finder Database

Each agent is designed to output data that maps directly to the School Finder database schema:

**Data Specialist Agents:**
- **Ofsted Agent** → `schools.ofsted_rating`, `schools.ofsted_date`
- **Clubs Agent** → `school_clubs` table
- **Term Times Agent** → `school_term_dates` table
- **Performance Agent** → `school_performance`, `school_reviews` tables
- **Admissions Agent** → `admissions_history` table
- **Transport Agent** → journey planner and school bus route data
- **Private School Agent** → `private_school_details` table
- **Uniform & Prospectus Agent** → uniform costs and prospectus URLs per school
- **Demographics Agent** → DfE census data (FSM, EAL, attendance, exclusions)
- **Catchment Agent** → `schools.catchment_geometry`, `schools.catchment_radius_km`

**Design & Review Agents:**
- **UX Design Agent** → `frontend/src/pages/*.tsx`, `frontend/src/components/*.tsx` (reviews, not data)

**Coding Specialist Agents:**
- **Python Backend Agent** → `src/api/`, `src/services/`, `src/db/`
- **React Frontend Agent** → `frontend/src/pages/`, `frontend/src/components/`
- **Database Agent** → `src/db/models.py`, `src/db/migrations/`
- **Data Pipeline Agent** → `src/db/seed.py`, `data/seeds/`
- **Testing Agent** → `tests/`
- **Security Agent** → cross-cutting audit of all `src/api/` endpoints

The agents provide structured JSON output that can be directly inserted or used to update the SQLite database via the repository layer.

---

## Tips for Best Results

1. **Always provide URN when known** - it's the most reliable identifier
2. **Specify the council/location** - helps narrow searches and validate results
3. **Request specific data fields** - the more specific your prompt, the better the output
4. **Ask for source URLs** - enables verification and manual checking
5. **Use for verification** - great for checking database data against official sources
6. **Combine agents** - e.g., "Find Ofsted rating AND performance data AND clubs for school X"

---

## Future Agent Ideas

Potential additional specialist agents:
- **SEND Specialist** - Find special educational needs provisions
- **League Table Specialist** - Create custom rankings based on multiple criteria

---

## Contributing

To add a new specialist agent:

1. Create a new `.md` file in this directory
2. Follow the template structure used by existing agents
3. Define: Purpose, Data Sources, Capabilities, Search Strategies, Output Format
4. Add usage examples and integration notes
5. Update this README with the new agent
6. Test with real prompts to ensure Claude can use it effectively
