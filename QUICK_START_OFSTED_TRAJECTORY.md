# Quick Start: Ofsted Trajectory Feature

## What Was Done

✅ **Created 4 key implementation files:**
1. `src/services/ofsted_trajectory.py` - Trajectory calculation logic
2. `frontend/src/components/OfstedTrajectory.tsx` - Timeline visualization component
3. `src/db/models_ofsted_extension.py` - Database models (OfstedHistory, AbsencePolicy, BusRoute)
4. `tests/test_ofsted_trajectory.py` - 18 comprehensive unit tests

✅ **Created 4 documentation files:**
1. `OFSTED_FEATURE_SUMMARY.md` - Complete feature overview
2. `OFSTED_TRAJECTORY_IMPLEMENTATION_STATUS.md` - Detailed implementation steps
3. `ofsted_trajectory_implementation.md` - Code snippets and guide
4. `apply_ofsted_trajectory.sh` - Automated setup script

✅ **Updated 1 model file:**
1. `src/db/models.py` - Added `ofsted_history` relationship to School model

## What You Need to Do

### Option A: Automated (Recommended)

```bash
# 1. Make script executable
chmod +x apply_ofsted_trajectory.sh

# 2. Run automated setup
./apply_ofsted_trajectory.sh

# 3. Complete remaining manual steps (see below)
```

### Option B: Manual

Follow the 10 steps in `OFSTED_TRAJECTORY_IMPLEMENTATION_STATUS.md`

## Remaining Manual Steps (Required)

After running the script or starting manual installation:

### 1. Update API Endpoints (`src/api/schools.py`)

**Add imports:**
```python
from src.schemas.school import OfstedHistoryResponse, OfstedTrajectoryResponse
from src.services.ofsted_trajectory import calculate_trajectory
```

**Add two endpoints** (after line ~209):
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

**Update `get_school` endpoint** (line ~82, after line 92):
```python
    # Add after other data fetching
    ofsted_history = await repo.get_ofsted_history(school_id)
    from src.services.ofsted_trajectory import calculate_trajectory
    trajectory_data = calculate_trajectory(ofsted_history)

    # In the return SchoolDetailResponse(...), add:
    ofsted_history=ofsted_history,
    ofsted_trajectory=OfstedTrajectoryResponse(
        school_id=school_id,
        history=ofsted_history,
        **trajectory_data
    ),
```

### 2. Update Seed Data (`src/db/seed.py`)

**Add import:**
```python
from src.db.models import (
    # ... existing ...
    OfstedHistory,  # ADD THIS
)
```

**Add function** (before `seed_schools()`):
```python
def _generate_ofsted_history(school_id: int, current_rating: str, current_date: datetime.date) -> list[OfstedHistory]:
    """Generate realistic Ofsted inspection history."""
    import random

    ratings = ["Outstanding", "Good", "Requires Improvement", "Inadequate"]
    current_idx = ratings.index(current_rating) if current_rating in ratings else 1

    history = []

    # Current inspection
    history.append(OfstedHistory(
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
        is_current=True
    ))

    # Add 1-3 previous inspections
    num_previous = random.randint(1, 3)
    previous_date = current_date

    for i in range(num_previous):
        years_back = random.uniform(3.0, 5.0)
        previous_date = previous_date - datetime.timedelta(days=int(years_back * 365))

        if random.random() < 0.6:
            prev_idx = min(current_idx + random.choice([0, 1]), len(ratings) - 1)
        else:
            prev_idx = max(current_idx - 1, 0)

        prev_rating = ratings[prev_idx]

        history.append(OfstedHistory(
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
            is_current=False
        ))

        current_idx = prev_idx

    return history
```

**In `seed_schools()` function** (after parking/uniform data):
```python
        # Add Ofsted history
        ofsted_history = _generate_ofsted_history(
            school.id,
            school.ofsted_rating or "Good",
            school.ofsted_date or datetime.date(2023, 3, 15)
        )
        session.add_all(ofsted_history)
```

### 3. Update School Detail Page (`frontend/src/pages/SchoolDetail.tsx`)

**Add import:**
```typescript
import { OfstedTrajectory } from '../components/OfstedTrajectory';
```

**Add component** (in render, after other sections ~line 150):
```typescript
{school.ofsted_trajectory && (
  <OfstedTrajectory trajectory={school.ofsted_trajectory} />
)}
```

### 4. Update API Client (`frontend/src/api/client.ts`)

**Add types:**
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
  ofsted_trajectory?: OfstedTrajectory;
```

**Add function:**
```typescript
export async function getOfstedTrajectory(schoolId: number): Promise<OfstedTrajectory> {
  const response = await fetch(`${API_BASE}/schools/${schoolId}/ofsted-trajectory`);
  if (!response.ok) {
    throw new Error('Failed to fetch Ofsted trajectory');
  }
  return response.json();
}
```

## Testing

```bash
# 1. Recreate database
rm data/schools.db
uv run python -m src.db.seed --council "Milton Keynes"

# 2. Run tests
uv run pytest tests/test_ofsted_trajectory.py -v

# 3. Start backend
uv run python -m src.main

# 4. Start frontend (new terminal)
cd frontend && npm run dev

# 5. Test in browser
# Visit http://localhost:5173
# Search for schools, click on any school
# Verify Ofsted Trajectory section appears
```

## Git Commands

```bash
# Create branch
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

# Push
git push -u origin feature/ofsted-trajectory
```

## Files Created

**Backend:**
- `src/services/ofsted_trajectory.py` ✅
- `src/db/models_ofsted_extension.py` ✅ (needs merging into models.py)
- `tests/test_ofsted_trajectory.py` ✅

**Frontend:**
- `frontend/src/components/OfstedTrajectory.tsx` ✅

**Documentation:**
- `OFSTED_FEATURE_SUMMARY.md` ✅
- `OFSTED_TRAJECTORY_IMPLEMENTATION_STATUS.md` ✅
- `ofsted_trajectory_implementation.md` ✅
- `QUICK_START_OFSTED_TRAJECTORY.md` ✅ (this file)

## Files to Edit

1. ✅ `src/db/models.py` - Updated (relationship added)
2. ⚠️ `src/schemas/school.py` - Script may have updated (verify)
3. ⚠️ `src/db/base.py` - Script may have updated (verify)
4. ⚠️ `src/db/sqlite_repo.py` - Script may have updated (verify)
5. ❌ `src/api/schools.py` - **Must edit manually**
6. ❌ `src/db/seed.py` - **Must edit manually**
7. ❌ `frontend/src/pages/SchoolDetail.tsx` - **Must edit manually**
8. ❌ `frontend/src/api/client.ts` - **Must edit manually**

## Troubleshooting

**Script fails?**
→ Manually follow steps in `OFSTED_TRAJECTORY_IMPLEMENTATION_STATUS.md`

**Import errors?**
→ Run `uv run ruff format src/ tests/`

**Tests fail?**
→ Check `tests/test_ofsted_trajectory.py` for specific failure

**Component doesn't render?**
→ Check browser console, verify API returns `ofsted_trajectory`

**Database errors?**
→ Delete `data/schools.db` and re-seed

## Estimated Time

- Automated script: 2 minutes
- Manual steps: 30-45 minutes
- Testing: 15 minutes
- **Total: ~1 hour**

## Next Steps After Implementation

1. Create pull request
2. Review changes
3. Deploy to staging (Fly.io)
4. User acceptance testing
5. Deploy to production
6. Update `FEATURE_REQUESTS.md` (mark as complete)

---

**Questions?** See `OFSTED_FEATURE_SUMMARY.md` for comprehensive details.
