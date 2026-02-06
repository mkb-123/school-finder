# Parking Chaos Rating Feature Implementation

## Overview

Implemented a comprehensive parking and drop-off chaos rating system that allows parents to submit and view ratings about the school gate situation. This feature provides critical real-world intel about daily logistics that significantly impact family routines.

## Feature Components

### 1. Database Model (`src/db/models.py`)

Added `ParkingRating` model with the following fields:
- **Rating dimensions** (1-5 scale, 5 = worst/most chaotic):
  - `dropoff_chaos` - Morning drop-off congestion and stress level
  - `pickup_chaos` - Afternoon pick-up congestion and wait times
  - `parking_availability` - Difficulty finding parking nearby
  - `road_congestion` - Traffic congestion on surrounding roads
  - `restrictions_hazards` - Parking restrictions, safety concerns, hazards
- **Optional feedback**:
  - `comments` - Free-text parent insights and tips
  - `parent_email` - Optional contact for follow-up
- **Metadata**:
  - `submitted_at` - Timestamp of submission
  - `school_id` - Foreign key to schools table

### 2. Repository Layer (`src/db/base.py`, `src/db/sqlite_repo.py`)

Following the established repository pattern:
- **Abstract interface** (`SchoolRepository`):
  - `get_parking_ratings_for_school(school_id)` - Retrieve all ratings
  - `create_parking_rating(rating)` - Submit new rating
- **SQLite implementation** with proper async/await pattern

### 3. API Endpoints (`src/api/parking.py`)

Three RESTful endpoints:

#### GET `/api/schools/{school_id}/parking-ratings`
Returns all parking ratings for a school (most recent first).

**Response**: `List[ParkingRatingResponse]`

#### GET `/api/schools/{school_id}/parking-summary`
Returns aggregated statistics:
- Total number of ratings
- Average score for each dimension (drop-off, pick-up, parking, congestion, hazards)
- Overall chaos score (average of all dimensions)

**Response**: `ParkingRatingSummary`

#### POST `/api/parking-ratings`
Submit a new parking rating.

**Request body**: `ParkingRatingSubmitRequest`
```json
{
  "school_id": 123,
  "dropoff_chaos": 4,
  "pickup_chaos": 5,
  "parking_availability": 3,
  "road_congestion": 4,
  "restrictions_hazards": 2,
  "comments": "Very busy at drop-off time. Arrive 15 minutes early for easier parking.",
  "parent_email": "parent@example.com"
}
```

**Validation**:
- School must exist (404 if not)
- Rating values must be 1-5 (400 if invalid)
- All rating fields optional (parents can rate subset of dimensions)

### 4. Pydantic Schemas (`src/schemas/school.py`)

- `ParkingRatingResponse` - Individual rating with all fields
- `ParkingRatingSubmitRequest` - Request payload for submissions
- `ParkingRatingSummary` - Aggregated statistics
- Updated `SchoolDetailResponse` to include `parking_summary`

### 5. Frontend Components

#### `ParkingRatingDisplay.tsx`
Visual component displaying parking ratings with:
- **Compact mode**: One-line summary with overall chaos score and rating count
- **Full mode**:
  - Large overall chaos score with color coding (green/amber/red)
  - Breakdown of each dimension with progress bars
  - Color-coded indicators (1-2 = green/low, 2-3.5 = amber/moderate, 3.5-5 = red/high)
  - Rating count and explanatory text

#### `ParkingRatingForm.tsx`
Interactive submission form with:
- 5 circular buttons per dimension (1-5 rating)
- Dynamic color coding based on selected value
- Optional comments textarea
- Optional email field for follow-up
- Success confirmation screen
- Error handling and validation

### 6. School Detail Page Integration (`frontend/src/pages/SchoolDetail.tsx`)

Added "Parking" tab showing:
1. `ParkingRatingDisplay` - Current ratings and statistics
2. `ParkingRatingForm` - Submission interface
3. Auto-refresh after successful submission

### 7. Seed Data (`src/db/seed.py`)

Added `_generate_test_parking_ratings()` function that creates realistic test data:
- 0-10 ratings per school (15% have none, simulating new feature adoption)
- Higher chaos scores for secondary schools (more students = more chaos)
- Variation in each rating dimension
- 30% of ratings include comments with realistic templates
- Random submission timestamps over past 6 months
- 10% include email addresses (most submit anonymously)

**Integration**: Added as step 12/12 in seed process, runs after uniform generation.

### 8. Tests (`tests/test_parking_ratings.py`)

Comprehensive test coverage:
- Repository layer: Create and retrieve ratings
- API endpoints: Submit, fetch, summary
- Validation: Invalid rating values (>5), non-existent schools
- Integration: Full request/response cycle

## Design Decisions

### Rating Scale: 1-5 (5 = Worst)

Chosen because:
- Industry standard (matches app store ratings, surveys)
- Intuitive: higher number = worse chaos
- Sufficient granularity without overwhelming users
- Easy to visualize with progress bars and colors

### Five Rating Dimensions

Separating concerns allows parents to provide nuanced feedback:
- Drop-off and pick-up are distinct (often different chaos levels)
- Parking availability vs. road congestion are separate issues
- Restrictions/hazards captures safety concerns

### Optional Ratings

Parents can rate any subset of dimensions:
- Some may only experience drop-off (e.g., work from home parents)
- Some may only experience pick-up (e.g., grandparents)
- Flexibility increases participation

### Aggregated Summary in School Detail

Computing averages on-the-fly:
- No denormalized fields to maintain
- Always reflects current data
- Low overhead (simple average calculation)
- Follows existing pattern (admissions estimation)

### Anonymous by Default

Email field is optional:
- Reduces friction for submissions
- Parents may fear school retaliation for negative feedback
- 90% submit anonymously in seed data (realistic behavior)

### Color Coding: Green/Amber/Red

Visual indicators for quick scanning:
- **Green (1-2)**: Low chaos, easy drop-off/parking
- **Amber (2-3.5)**: Moderate issues, manageable with planning
- **Red (3.5-5)**: High chaos, significant daily stress factor

## Integration with Existing Features

### Repository Pattern
Follows established abstraction:
- New methods in `SchoolRepository` base class
- Implementation in `SQLiteSchoolRepository`
- Ready for PostgreSQL implementation (future)

### API Design
Consistent with existing endpoints:
- RESTful conventions
- Pydantic validation
- HTTPException error handling
- Dependency injection for repository

### Frontend Structure
Matches existing component patterns:
- Functional React components with hooks
- TypeScript interfaces for type safety
- Tailwind CSS for styling
- Async data fetching with error handling

### Seed Script
Follows established conventions:
- Deterministic random seed (reproducible)
- Idempotent (deletes existing before creating)
- Progress reporting
- Summary statistics

## Future Enhancements

### Potential Additions (Not Yet Implemented)

1. **Moderation**: Flag/review system for inappropriate comments
2. **Voting**: Helpful/not helpful on existing ratings
3. **Time-based filtering**: "Ratings from last 6 months" vs. "All time"
4. **School responses**: Allow schools to comment or provide updates
5. **Map integration**: Show parking areas on school detail map
6. **Decision support integration**: Add parking chaos as weighting slider
7. **Trend tracking**: Show if situation is improving or worsening over time

## Database Schema

```sql
CREATE TABLE parking_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id),
    dropoff_chaos INTEGER,  -- 1-5 scale
    pickup_chaos INTEGER,
    parking_availability INTEGER,
    road_congestion INTEGER,
    restrictions_hazards INTEGER,
    comments TEXT,
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    parent_email VARCHAR(255)
);

CREATE INDEX idx_parking_ratings_school_id ON parking_ratings(school_id);
CREATE INDEX idx_parking_ratings_submitted_at ON parking_ratings(submitted_at);
```

## API Examples

### Submit Rating
```bash
curl -X POST http://localhost:8000/api/parking-ratings \
  -H "Content-Type: application/json" \
  -d '{
    "school_id": 42,
    "dropoff_chaos": 4,
    "pickup_chaos": 5,
    "parking_availability": 3,
    "comments": "Very busy. Double parking is common. Allow extra time."
  }'
```

### Get Summary
```bash
curl http://localhost:8000/api/schools/42/parking-summary
```

**Response**:
```json
{
  "school_id": 42,
  "total_ratings": 7,
  "avg_dropoff_chaos": 3.8,
  "avg_pickup_chaos": 4.2,
  "avg_parking_availability": 3.1,
  "avg_road_congestion": 3.5,
  "avg_restrictions_hazards": 2.4,
  "overall_chaos_score": 3.4
}
```

## User Journey

### Viewing Ratings
1. Parent navigates to school detail page
2. Clicks "Parking" tab
3. Sees aggregated summary (overall score + dimension breakdown)
4. Reviews individual parent comments for specific insights

### Submitting Rating
1. Parent scrolls to "Submit Your Rating" section
2. Rates each dimension by clicking 1-5 circles
3. Optionally adds comments with specific details/tips
4. Optionally provides email
5. Clicks "Submit Rating"
6. Sees success confirmation
7. Page reloads to show updated statistics

## Files Changed

### Backend
- `src/db/models.py` - Added `ParkingRating` model
- `src/db/base.py` - Added repository interface methods
- `src/db/sqlite_repo.py` - Implemented SQLite methods
- `src/api/parking.py` - NEW: API endpoints
- `src/schemas/school.py` - Added Pydantic schemas
- `src/main.py` - Registered parking router
- `src/db/seed.py` - Added parking rating generation

### Frontend
- `frontend/src/components/ParkingRatingDisplay.tsx` - NEW: Display component
- `frontend/src/components/ParkingRatingForm.tsx` - NEW: Submission form
- `frontend/src/pages/SchoolDetail.tsx` - Added Parking tab

### Tests
- `tests/test_parking_ratings.py` - NEW: Test coverage

## Testing

### Manual Testing
```bash
# Start backend
uv run python -m src.main

# Re-seed database with parking ratings
uv run python -m src.db.seed --council "Milton Keynes"

# Start frontend
cd frontend && npm run dev

# Navigate to any school detail page and click "Parking" tab
```

### Automated Testing
```bash
uv run pytest tests/test_parking_ratings.py -v
```

## Architecture Compliance

This feature strictly follows the architecture patterns defined in `CLAUDE.md`:
- ✅ Repository pattern with abstract interface
- ✅ SQLite implementation (ready for PostgreSQL extension)
- ✅ FastAPI with Pydantic validation
- ✅ React + TypeScript + Tailwind CSS
- ✅ Polars for seed data (if CSV processing needed)
- ✅ Async/await throughout
- ✅ No raw SQL (SQLAlchemy ORM only)
- ✅ Comprehensive test coverage
