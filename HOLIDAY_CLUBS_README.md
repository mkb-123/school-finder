# Holiday Club Availability Feature

## Quick Start

### 1. Database Setup
The `holiday_clubs` table will be created automatically when the app starts. No manual migration needed.

### 2. Generate Seed Data
To populate holiday clubs for existing schools:

```python
from src.db.models import School, HolidayClub
from src.db.seed_holiday_clubs import generate_holiday_clubs, upsert_holiday_clubs
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Connect to database
engine = create_engine("sqlite:///./data/schools.db")
session = Session(engine)

# Get all schools
schools = session.query(School).all()

# Generate holiday clubs
holiday_clubs = generate_holiday_clubs(schools, seed=42)

# Insert into database
inserted = upsert_holiday_clubs(session, holiday_clubs)
print(f"Inserted {inserted} holiday clubs")
```

### 3. API Usage

**Get holiday clubs for a school:**
```bash
curl http://localhost:8000/api/schools/1/holiday-clubs
```

**Get school detail (includes holiday clubs):**
```bash
curl http://localhost:8000/api/schools/1
```

### 4. Frontend Integration

Import and use the components in your school detail page:

```tsx
import HolidayClubsList from '../components/HolidayClubsList';

function SchoolDetail() {
  const [school, setSchool] = useState(null);

  // ... fetch school data ...

  return (
    <div>
      {/* Other school info */}

      <section className="mt-8">
        <HolidayClubsList
          clubs={school.holiday_clubs}
          schoolName={school.name}
        />
      </section>
    </div>
  );
}
```

## Features

### Backend
- ✅ Database model for holiday clubs
- ✅ Repository pattern implementation
- ✅ API endpoint: `/api/schools/{id}/holiday-clubs`
- ✅ Included in school detail response
- ✅ Realistic seed data generation
- ✅ Comprehensive API tests

### Frontend
- ✅ HolidayClubCard component - displays individual club details
- ✅ HolidayClubsList component - lists all clubs with filtering
- ✅ Filter by school-run vs external providers
- ✅ Responsive design
- ✅ Empty state handling

### Data Fields
- Provider name and type (school-run vs external)
- Description of activities
- Age range covered
- Operating hours
- Daily and weekly costs
- Available holiday periods (Easter, Summer, half-terms)
- Booking URL (optional)

## Testing

Run the holiday clubs API tests:
```bash
uv run pytest tests/test_api/test_holiday_clubs.py -v
```

All tests should pass:
- ✅ Empty state handling
- ✅ Fetching holiday clubs
- ✅ Inclusion in school detail endpoint

## Architecture

### Repository Pattern
```
API Layer (holiday_clubs.py)
    ↓
Repository Interface (base.py)
    ↓
SQLite Implementation (sqlite_repo.py)
    ↓
Database (HolidayClub model)
```

### Data Flow
```
Frontend Component
    ↓
API Request (/api/schools/1/holiday-clubs)
    ↓
FastAPI Router (holiday_clubs.py)
    ↓
Repository (get_holiday_clubs_for_school)
    ↓
SQLAlchemy Query
    ↓
Pydantic Response (HolidayClubResponse)
    ↓
JSON Response to Frontend
```

## Filtering Options

The frontend component supports three filter modes:
1. **All** - Shows all holiday clubs
2. **School-run** - Shows only clubs operated by the school
3. **External** - Shows only external providers using school premises

## Seed Data Characteristics

Generated holiday clubs have realistic properties:
- 60% of schools have at least one holiday club
- 1-2 providers per school (weighted toward 1)
- Mix of school-run (40%) and external (60%) providers
- Age ranges typically 4-11 (some may be narrower)
- Operating hours between 7:30 AM - 6:00 PM
- Costs: £35-80 per day, with 10-20% weekly discount
- Coverage: Easter, Summer, October half-term, February half-term
- Some providers have booking URLs

## Example Response

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
    "cost_per_day": 45.50,
    "cost_per_week": 195.00,
    "available_weeks": "Easter, Summer, October half-term",
    "booking_url": "https://www.school-holiday-club.co.uk/booking"
  },
  {
    "id": 2,
    "school_id": 123,
    "provider_name": "Kids Zone Holiday Camp",
    "is_school_run": false,
    "description": "Active holiday camp with outdoor activities, team games, and creative workshops",
    "age_from": 5,
    "age_to": 10,
    "start_time": "08:30:00",
    "end_time": "17:30:00",
    "cost_per_day": 38.00,
    "cost_per_week": 165.00,
    "available_weeks": "Summer only",
    "booking_url": "https://www.kids-zone-holiday-camp.co.uk/booking"
  }
]
```

## Future Enhancements

Potential additions for future versions:
- Filter schools by "has holiday club" in main search
- Include holiday club availability in decision support scoring
- Add calendar view showing which specific weeks clubs operate
- User reviews/ratings for holiday clubs
- Comparison view for holiday club costs across schools
- Map view showing holiday clubs in the area
- Waiting list/availability status for popular clubs

## Support

For issues or questions about the holiday clubs feature, check:
- Implementation doc: `HOLIDAY_CLUB_IMPLEMENTATION.md`
- API tests: `tests/test_api/test_holiday_clubs.py`
- Seed data generator: `src/db/seed_holiday_clubs.py`
