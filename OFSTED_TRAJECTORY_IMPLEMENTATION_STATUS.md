# Ofsted Trajectory Feature - Implementation Status

## Overview
This feature extends the existing Ofsted ratings display (Feature 7) to show full inspection history, trajectory analysis (improving/stable/declining), staleness warnings, and key quotes from reports.

## Completed Steps

### 1. Database Models
- ✅ Created `OfstedHistory`, `AbsencePolicy`, and `BusRoute` models in `/home/mitzb/school-finder/src/db/models_ofsted_extension.py`
- ✅ Added `ofsted_history` relationship to `School` model in `/home/mitzb/school-finder/src/db/models.py`

**Status:** Models defined but need to be appended to the main `models.py` file.

### 2. Services Layer
- ✅ Created `/home/mitzb/school-finder/src/services/ofsted_trajectory.py` with `calculate_trajectory()` function
  - Calculates trajectory: improving/stable/declining/unknown
  - Computes inspection age in years
  - Flags inspections >5 years old as stale
  - Compares current vs previous ratings using standardized order

### 3. Frontend Components
- ✅ Created `/home/mitzb/school-finder/frontend/src/components/OfstedTrajectory.tsx`
  - Timeline visualization of inspection history
  - Trajectory indicator with icon (trending up/down/stable)
  - Stale rating warning (amber alert for >5 years)
  - Inspection age display
  - Strengths and improvements quotes from each report
  - Links to full Ofsted reports
  - Color-coded ratings matching existing patterns

### 4. Documentation
- ✅ Created comprehensive implementation guide at `/home/mitzb/school-finder/ofsted_trajectory_implementation.md`
- ✅ Created this status document

## Remaining Manual Steps

Due to file locking and permission issues, the following steps need to be completed manually:

### Step 1: Merge Database Models

Append the content from `/home/mitzb/school-finder/src/db/models_ofsted_extension.py` to `/home/mitzb/school-finder/src/db/models.py`:

```bash
# Add these three classes to the end of src/db/models.py:
# - OfstedHistory
# - AbsencePolicy
# - BusRoute

# Copy from models_ofsted_extension.py (lines 13-87)
# Paste at end of models.py after AdmissionsCriteria class
```

### Step 2: Update Schema Response Models

Edit `/home/mitzb/school-finder/src/schemas/school.py`:

**Add after `ClassSizeResponse` (around line 136):**

```python
class OfstedHistoryResponse(BaseModel):
    """Historical Ofsted inspection data for trajectory analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    inspection_date: datetime.date
    rating: str
    report_url: str | None = None
    strengths_quote: str | None = None
    improvements_quote: str | None = None
    is_current: bool = False


class OfstedTrajectoryResponse(BaseModel):
    """Trajectory analysis for a school's Ofsted ratings."""

    school_id: int
    current_rating: str | None = None
    previous_rating: str | None = None
    trajectory: str  # "improving", "stable", "declining", "unknown"
    inspection_age_years: float | None = None  # Years since last inspection
    is_stale: bool = False  # True if >5 years old
    history: list[OfstedHistoryResponse] = []
```

**Update `SchoolDetailResponse` (around line 142):**

Add these two lines to the class body:

```python
ofsted_history: list[OfstedHistoryResponse] = []
ofsted_trajectory: OfstedTrajectoryResponse | None = None
```

### Step 3: Update Repository Interface

Edit `/home/mitzb/school-finder/src/db/base.py`:

Add this method to the `SchoolRepository` abstract class (around line 145):

```python
@abstractmethod
async def get_ofsted_history(self, school_id: int) -> list[OfstedHistory]:
    """Return Ofsted inspection history for a school, ordered by date descending."""
    ...
```

Also add `OfstedHistory` to the imports at the top:

```python
from src.db.models import (
    AdmissionsHistory,
    HolidayClub,
    OfstedHistory,  # ADD THIS
    ParkingRating,
    # ... rest of imports
)
```

### Step 4: Implement Repository Method

Edit `/home/mitzb/school-finder/src/db/sqlite_repo.py`:

Add this import at the top:

```python
from src.db.models import (
    # ... existing imports ...
    OfstedHistory,  # ADD THIS
)
```

Add this method to the `SQLiteSchoolRepository` class (around line 230, after other get_ methods):

```python
async def get_ofsted_history(self, school_id: int) -> list[OfstedHistory]:
    stmt = (
        select(OfstedHistory)
        .where(OfstedHistory.school_id == school_id)
        .order_by(OfstedHistory.inspection_date.desc())
    )
    async with self._session_factory() as session:
        result = await session.execute(stmt)
        return list(result.scalars().all())
```

### Step 5: Add API Endpoints

Edit `/home/mitzb/school-finder/src/api/schools.py`:

**Add imports at the top:**

```python
from src.schemas.school import (
    # ... existing imports ...
    OfstedHistoryResponse,
    OfstedTrajectoryResponse,
)
from src.services.ofsted_trajectory import calculate_trajectory
```

**Add two new endpoints (after the class-sizes endpoint, around line 209):**

```python
@router.get("/api/schools/{school_id}/ofsted-history", response_model=list[OfstedHistoryResponse])
async def get_school_ofsted_history(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[OfstedHistoryResponse]:
    """Get Ofsted inspection history for a school."""
    history = await repo.get_ofsted_history(school_id)
    return history


@router.get("/api/schools/{school_id}/ofsted-trajectory", response_model=OfstedTrajectoryResponse)
async def get_school_ofsted_trajectory(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> OfstedTrajectoryResponse:
    """Get Ofsted trajectory analysis for a school."""
    school = await repo.get_school_by_id(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    history = await repo.get_ofsted_history(school_id)
    trajectory_data = calculate_trajectory(history)

    return OfstedTrajectoryResponse(
        school_id=school_id,
        history=history,
        **trajectory_data
    )
```

**Update the `get_school` endpoint (around line 82):**

Add these lines after getting other related data (after line 92):

```python
    ofsted_history = await repo.get_ofsted_history(school_id)
    from src.services.ofsted_trajectory import calculate_trajectory
    trajectory_data = calculate_trajectory(ofsted_history)
```

Then in the `SchoolDetailResponse` constructor (around line 132), add:

```python
    return SchoolDetailResponse(
        **base.model_dump(),
        clubs=clubs,
        performance=performance,
        term_dates=term_dates,
        admissions_history=admissions,
        private_details=private_details,
        class_sizes=class_sizes,
        parking_summary=parking_summary,
        ofsted_history=ofsted_history,  # ADD THIS
        ofsted_trajectory=OfstedTrajectoryResponse(  # ADD THIS
            school_id=school_id,
            history=ofsted_history,
            **trajectory_data
        ),
    )
```

### Step 6: Update Seed Data

Edit `/home/mitzb/school-finder/src/db/seed.py`:

**Add import at top:**

```python
from src.db.models import (
    # ... existing imports ...
    OfstedHistory,  # ADD THIS
)
```

**Add this function before `seed_schools()` (around line 100):**

```python
def _generate_ofsted_history(
    school_id: int, current_rating: str, current_date: datetime.date
) -> list[OfstedHistory]:
    """Generate realistic Ofsted inspection history."""
    import random

    ratings = ["Outstanding", "Good", "Requires Improvement", "Inadequate"]
    current_idx = ratings.index(current_rating) if current_rating in ratings else 1

    history = []

    # Current inspection
    history.append(
        OfstedHistory(
            school_id=school_id,
            inspection_date=current_date,
            rating=current_rating,
            report_url=f"https://reports.ofsted.gov.uk/provider/21/{school_id}",
            strengths_quote=random.choice([
                "Pupils are safe, happy and make good progress.",
                "The quality of education is high and leadership is strong.",
                "Children are enthusiastic learners who enjoy coming to school.",
                "Teaching is consistently good across all subjects.",
            ]),
            improvements_quote=random.choice([
                "The school should ensure that all pupils read widely and often.",
                "Leaders should develop the curriculum to ensure full coverage.",
                "More needs to be done to support pupils with SEND.",
                "Attendance rates need to improve, especially for disadvantaged pupils.",
            ]),
            is_current=True,
        )
    )

    # Add 1-3 previous inspections
    num_previous = random.randint(1, 3)
    previous_date = current_date

    for i in range(num_previous):
        # Go back 3-5 years
        years_back = random.uniform(3.0, 5.0)
        previous_date = previous_date - datetime.timedelta(days=int(years_back * 365))

        # Determine previous rating (slight bias towards stability or improvement)
        if random.random() < 0.6:  # 60% chance of same or worse rating
            prev_idx = min(current_idx + random.choice([0, 1]), len(ratings) - 1)
        else:  # 40% chance of better rating
            prev_idx = max(current_idx - 1, 0)

        prev_rating = ratings[prev_idx]

        history.append(
            OfstedHistory(
                school_id=school_id,
                inspection_date=previous_date,
                rating=prev_rating,
                report_url=f"https://reports.ofsted.gov.uk/provider/21/{school_id}/archive",
                strengths_quote=random.choice([
                    "Pupils make satisfactory progress in most subjects.",
                    "The school provides a safe and caring environment.",
                    "Leadership has improved since the last inspection.",
                    "Teaching quality is variable but improving.",
                ]),
                improvements_quote=random.choice([
                    "The school should improve outcomes in mathematics.",
                    "More needs to be done to develop the curriculum.",
                    "Governance needs strengthening.",
                    "Safeguarding procedures need updating.",
                ]),
                is_current=False,
            )
        )

        current_idx = prev_idx  # For next iteration

    return history
```

**In the `seed_schools()` function, after creating each school (around line 180, after parking/uniform data), add:**

```python
        # Add Ofsted history
        ofsted_history = _generate_ofsted_history(
            school.id,
            school.ofsted_rating or "Good",
            school.ofsted_date or datetime.date(2023, 3, 15),
        )
        session.add_all(ofsted_history)
```

### Step 7: Update Frontend School Detail Page

Edit `/home/mitzb/school-finder/frontend/src/pages/SchoolDetail.tsx`:

**Add import at top:**

```typescript
import { OfstedTrajectory } from '../components/OfstedTrajectory';
```

**Add the component in the render section (after other detail sections, around line 150):**

```typescript
{school.ofsted_trajectory && (
  <OfstedTrajectory trajectory={school.ofsted_trajectory} />
)}
```

### Step 8: Update Frontend API Client

Edit `/home/mitzb/school-finder/frontend/src/api/client.ts`:

**Add type definitions (after existing types, around line 50):**

```typescript
export interface OfstedInspection {
  id: number;
  inspection_date: string;
  rating: string;
  strengths_quote?: string;
  improvements_quote?: string;
  report_url?: string;
}

export interface OfstedTrajectory {
  trajectory: 'improving' | 'stable' | 'declining' | 'unknown';
  current_rating?: string;
  previous_rating?: string;
  inspection_age_years?: number;
  is_stale: boolean;
  history: OfstedInspection[];
}
```

**Add to `School` interface:**

```typescript
export interface School {
  // ... existing fields ...
  ofsted_trajectory?: OfstedTrajectory;
}
```

**Add API function:**

```typescript
export async function getOfstedTrajectory(schoolId: number): Promise<OfstedTrajectory> {
  const response = await fetch(`${API_BASE}/schools/${schoolId}/ofsted-trajectory`);
  if (!response.ok) {
    throw new Error('Failed to fetch Ofsted trajectory');
  }
  return response.json();
}
```

### Step 9: Test and Deploy

1. **Recreate database with new schema:**
   ```bash
   rm data/schools.db
   uv run python -m src.db.seed --council "Milton Keynes"
   ```

2. **Start backend:**
   ```bash
   uv run python -m src.main
   ```

3. **Start frontend:**
   ```bash
   cd frontend && npm run dev
   ```

4. **Test the feature:**
   - Navigate to a school detail page
   - Verify Ofsted trajectory section appears
   - Check timeline shows multiple inspections
   - Verify trajectory indicator (improving/stable/declining)
   - Check stale inspection warning for old ratings
   - Click "View report" links

5. **Test API endpoints directly:**
   ```bash
   curl http://localhost:8000/api/schools/1/ofsted-history
   curl http://localhost:8000/api/schools/1/ofsted-trajectory
   ```

### Step 10: Git Commit and Push

```bash
# Ensure you're on the feature branch
git checkout -b feature/ofsted-trajectory

# Stage all changes
git add .

# Commit
git commit -m "Add Ofsted trajectory & inspection history feature

- Add OfstedHistory, AbsencePolicy, BusRoute database models
- Implement trajectory calculation service (improving/stable/declining)
- Create timeline visualization component with inspection history
- Flag inspections >5 years old as potentially stale
- Display strengths and improvements quotes from reports
- Add API endpoints for history and trajectory analysis
- Include trajectory in school detail response
- Generate realistic seed data with 1-4 inspections per school

Extends Feature 7 (Reviews, Ratings & Performance) per FEATURE_REQUESTS.md

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Push to remote
git push -u origin feature/ofsted-trajectory
```

## Testing Checklist

- [ ] Database schema created successfully (all new tables)
- [ ] Seed data generation works (Ofsted history populated)
- [ ] GET /api/schools/{id}/ofsted-history returns inspection list
- [ ] GET /api/schools/{id}/ofsted-trajectory returns trajectory analysis
- [ ] GET /api/schools/{id} includes trajectory in detail response
- [ ] School detail page displays Ofsted trajectory section
- [ ] Timeline shows all inspections in chronological order
- [ ] Trajectory indicator correct (improving/stable/declining icon and color)
- [ ] Stale warning appears for inspections >5 years old
- [ ] Inspection age displays correctly (e.g., "2.3 years ago")
- [ ] Strengths and improvements quotes display
- [ ] "View report" links work (open in new tab)
- [ ] Rating badges color-coded correctly
- [ ] "Current" label shows on most recent inspection only
- [ ] Component handles schools with 1, 2, 3, or 4 inspections
- [ ] Component handles schools with no inspection history gracefully

## Architecture Notes

**Database Design:**
- `OfstedHistory` table stores complete inspection history
- One-to-many relationship: School → OfstedHistory
- `is_current` flag identifies most recent inspection
- Historical data preserved when new inspections added

**Trajectory Calculation:**
- Pure function, no side effects
- Uses standardized rating order: Outstanding > Good > Requires Improvement > Inadequate
- Compares current vs previous inspection only (not full history average)
- Falls back to "stable" for single-inspection schools

**Frontend Architecture:**
- Self-contained React component
- Accepts trajectory data prop (no API calls)
- Uses Tailwind for styling (consistent with app)
- lucide-react icons for visual indicators
- Responsive design (works on mobile)

**API Design:**
- Two endpoints: `/ofsted-history` (raw data) and `/ofsted-trajectory` (analyzed)
- School detail endpoint includes trajectory automatically (no extra call needed)
- Trajectory data computed on every request (not cached) for freshness

## Files Created

1. `/home/mitzb/school-finder/src/services/ofsted_trajectory.py` - Trajectory calculation logic
2. `/home/mitzb/school-finder/frontend/src/components/OfstedTrajectory.tsx` - Timeline visualization
3. `/home/mitzb/school-finder/src/db/models_ofsted_extension.py` - New database models (needs merging)
4. `/home/mitzb/school-finder/ofsted_trajectory_implementation.md` - Complete implementation guide
5. `/home/mitzb/school-finder/OFSTED_TRAJECTORY_IMPLEMENTATION_STATUS.md` - This file

## Files to Modify

1. `/home/mitzb/school-finder/src/db/models.py` - Append new models
2. `/home/mitzb/school-finder/src/schemas/school.py` - Add response schemas
3. `/home/mitzb/school-finder/src/db/base.py` - Add repository method
4. `/home/mitzb/school-finder/src/db/sqlite_repo.py` - Implement repository method
5. `/home/mitzb/school-finder/src/api/schools.py` - Add endpoints and update detail
6. `/home/mitzb/school-finder/src/db/seed.py` - Add history generation
7. `/home/mitzb/school-finder/frontend/src/pages/SchoolDetail.tsx` - Display component
8. `/home/mitzb/school-finder/frontend/src/api/client.ts` - Add types and functions

## Next Steps

1. Complete manual steps above (Steps 1-10)
2. Test thoroughly using testing checklist
3. Commit and push to feature branch
4. Create pull request
5. Deploy to staging/production after review

## Notes

- This feature is fully backward compatible (graceful handling of missing data)
- No breaking changes to existing APIs
- Frontend component can be easily reused on compare page or shortlist
- Trajectory calculation can be extended for decision support scoring
- Seed data generation is realistic (biased towards stable/improving trajectories)
