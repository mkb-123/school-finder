# Holiday Club Availability Feature Implementation

## Summary

Implemented the "Holiday Club Availability" feature from FEATURE_REQUESTS.md. This feature extends the existing clubs system to include holiday clubs - childcare provision during school breaks.

## Changes Made

### 1. Database Models (`src/db/models.py`)

Added new `HolidayClub` model with the following fields:
- `provider_name`: Name of the holiday club provider
- `is_school_run`: Boolean indicating if school-run or external provider
- `description`: Description of activities offered
- `age_from`/`age_to`: Age range covered by the club
- `start_time`/`end_time`: Operating hours
- `cost_per_day`/`cost_per_week`: Pricing information
- `available_weeks`: Which holiday periods are covered (Easter, Summer, etc.)
- `booking_url`: Optional URL for online booking

Added relationship to `School` model: `holiday_clubs`

### 2. Repository Layer (`src/db/base.py`, `src/db/sqlite_repo.py`)

- Added `HolidayClub` import to repository interface
- Added abstract method `get_holiday_clubs_for_school()` to `SchoolRepository` base class
- Implemented `get_holiday_clubs_for_school()` in `SQLiteSchoolRepository`

### 3. API Schemas (`src/schemas/holiday_club.py`)

Created new schema file with:
- `HolidayClubResponse`: Pydantic response model for holiday club data

Updated `src/schemas/school.py`:
- Added import of `HolidayClubResponse`
- Added `holiday_clubs` field to `SchoolDetailResponse`

### 4. API Endpoints (`src/api/holiday_clubs.py`)

Created new router with endpoint:
- `GET /api/schools/{school_id}/holiday-clubs`: Returns list of holiday clubs for a school

Updated `src/api/schools.py`:
- Added `HolidayClubResponse` import
- Modified `get_school()` to fetch and include holiday clubs in school detail response

Updated `src/main.py`:
- Added holiday_clubs router to FastAPI app

### 5. Seed Data (`src/db/seed_holiday_clubs.py`)

Created comprehensive seed data generation module with:
- `generate_holiday_clubs()`: Generates realistic holiday club data
  - Mix of school-run and external providers
  - Realistic age ranges, hours, and pricing
  - Various holiday periods covered (Easter, Summer, half-terms)
  - Optional booking URLs
- `upsert_holiday_clubs()`: Inserts holiday clubs without duplicates

Holiday club data includes:
- 10 realistic provider names (both school-run and external)
- 60% of schools have at least one holiday club
- Varied operating hours (typically 7:30-18:00)
- Realistic pricing (£5-8 per hour, with weekly discounts)
- Multiple holiday periods (Easter, Summer, October half-term, etc.)

### 6. Frontend Components

Created two React components:

**`frontend/src/components/HolidayClubCard.tsx`**:
- Displays individual holiday club information
- Shows provider name, age range, hours, costs
- Indicates if school-run or external
- Displays available weeks and booking link
- Responsive card design with hover effects

**`frontend/src/components/HolidayClubsList.tsx`**:
- Displays list of holiday clubs with filtering
- Filter toggle: All / School-run / External providers
- Empty state handling
- Info box explaining the difference between school-run and external
- Grid layout for multiple clubs

### 7. Tests (`tests/test_api/test_holiday_clubs.py`)

Created comprehensive API tests:
- `test_get_holiday_clubs_empty()`: Tests empty state
- `test_get_holiday_clubs_with_data()`: Tests fetching holiday clubs
- `test_holiday_clubs_in_school_detail()`: Tests inclusion in school detail endpoint

## Integration with Existing Features

### School Detail Page
Holiday clubs can be displayed on the school detail page by:
1. Importing `HolidayClubsList` component
2. Passing `school.holiday_clubs` data to the component
3. Adding as a new tab or section alongside existing clubs data

Example integration:
```tsx
import HolidayClubsList from '../components/HolidayClubsList';

// In SchoolDetail component:
<div>
  <h2>Term-time Clubs</h2>
  {/* Existing breakfast and after-school clubs */}

  <h2>Holiday Clubs</h2>
  <HolidayClubsList clubs={school.holiday_clubs} schoolName={school.name} />
</div>
```

### Decision Support
Holiday club availability can be factored into decision scoring by:
- Checking if school has any holiday clubs (`has_holiday_club` boolean)
- Preferring school-run clubs over external providers
- Considering cost and hours coverage

## Database Migration

The `HolidayClub` table will be created automatically on next app startup through the lifespan handler in `src/main.py`, which calls `Base.metadata.create_all()`.

## Seed Data Integration

To integrate holiday club generation into the main seed script:

1. Add import in `src/db/seed.py`:
```python
from src.db.seed_holiday_clubs import generate_holiday_clubs, upsert_holiday_clubs
```

2. Add generation step after club seeding (around line 1880):
```python
print("[X/Y] Generating holiday club data ...")
holiday_clubs = generate_holiday_clubs(all_schools)
holiday_clubs_inserted = upsert_holiday_clubs(session, holiday_clubs)
total_holiday_clubs = session.query(HolidayClub).count()
print(f"  Holiday clubs generated: {len(holiday_clubs)}")
print(f"  Holiday clubs inserted: {holiday_clubs_inserted}")
print(f"  Total holiday clubs in DB: {total_holiday_clubs}")
```

## API Examples

### Get Holiday Clubs for a School
```bash
GET /api/schools/123/holiday-clubs
```

Response:
```json
[
  {
    "id": 1,
    "school_id": 123,
    "provider_name": "School Holiday Club",
    "is_school_run": true,
    "description": "Fun-filled days with sports, arts, crafts, and games during school holidays",
    "age_from": 4,
    "age_to": 11,
    "start_time": "08:00:00",
    "end_time": "18:00:00",
    "cost_per_day": 35.50,
    "cost_per_week": 150.00,
    "available_weeks": "Easter, Summer, October half-term",
    "booking_url": "https://www.school-holiday-club.co.uk/booking"
  }
]
```

### Get School Detail (includes holiday clubs)
```bash
GET /api/schools/123
```

Response includes `holiday_clubs` array alongside `clubs`, `performance`, etc.

## Files Created

- `src/db/models.py` - Added HolidayClub model
- `src/db/base.py` - Added get_holiday_clubs_for_school method
- `src/db/sqlite_repo.py` - Implemented get_holiday_clubs_for_school
- `src/schemas/holiday_club.py` - NEW FILE
- `src/api/holiday_clubs.py` - NEW FILE
- `src/db/seed_holiday_clubs.py` - NEW FILE
- `tests/test_api/test_holiday_clubs.py` - NEW FILE
- `frontend/src/components/HolidayClubCard.tsx` - NEW FILE
- `frontend/src/components/HolidayClubsList.tsx` - NEW FILE

## Files Modified

- `src/db/models.py` - Added HolidayClub model and relationship
- `src/db/base.py` - Added repository method
- `src/db/sqlite_repo.py` - Added import and implementation
- `src/schemas/school.py` - Added holiday_clubs field to SchoolDetailResponse
- `src/api/schools.py` - Added holiday_clubs to school detail endpoint
- `src/main.py` - Registered holiday_clubs router

## Next Steps

1. **Integrate into seed script**: Add holiday club generation to the main seed flow
2. **Update frontend SchoolDetail page**: Add HolidayClubsList component to display
3. **Add to decision support**: Factor holiday club availability into scoring
4. **Add filtering**: Allow filtering schools by "has holiday club" in search
5. **Documentation**: Update API documentation with holiday club endpoints

## Testing

Run tests with:
```bash
uv run pytest tests/test_api/test_holiday_clubs.py -v
```

Run all tests:
```bash
uv run pytest
```

Start the API server:
```bash
uv run python -m src.main
```

Test endpoints manually:
```bash
curl http://localhost:8000/api/schools/1/holiday-clubs
```

## Notes

- The implementation follows the existing repository pattern
- Holiday clubs are kept separate from term-time clubs for clarity
- The data model supports both school-run and external providers
- Seed data generates realistic pricing based on operating hours
- Frontend components are reusable and can be embedded anywhere
- All code follows the existing project conventions (Pydantic, async/await, etc.)
