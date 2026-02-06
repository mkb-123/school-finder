# Ofsted Trajectory Implementation Guide

This file contains all the code changes needed to implement the Ofsted Trajectory feature.

## 1. Database Models (add to src/db/models.py)

```python
class OfstedHistory(Base):
    __tablename__ = "ofsted_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    # Inspection details
    inspection_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    rating: Mapped[str] = mapped_column(String(30), nullable=False)  # Outstanding / Good / Requires Improvement / Inadequate
    report_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Key quotes from report
    strengths_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvements_quote: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Flags
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # True for the most recent inspection

    school: Mapped[School] = relationship("School", back_populates="ofsted_history")

    def __repr__(self) -> str:
        return f"<OfstedHistory(school_id={self.school_id}, date={self.inspection_date}, rating={self.rating!r})>"


class AbsencePolicy(Base):
    __tablename__ = "absence_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    # Policy details
    fines_issued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fine_threshold_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Days before fining
    term_time_holiday_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    unauthorised_absence_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # Percentage

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="absence_policy")

    def __repr__(self) -> str:
        return f"<AbsencePolicy(school_id={self.school_id}, fines={self.fines_issued})>"


class BusRoute(Base):
    __tablename__ = "bus_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    # Route details
    route_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost_per_term: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Eligibility
    min_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    year_groups: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g., "Year 7-11"

    # Stop locations (simplified as comma-separated postcodes or area names)
    stops: Mapped[str | None] = mapped_column(Text, nullable=True)
    pickup_times: Mapped[str | None] = mapped_column(Text, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="bus_routes")

    def __repr__(self) -> str:
        return f"<BusRoute(school_id={self.school_id}, route={self.route_name!r})>"
```

## 2. Schema Response Models (add to src/schemas/school.py after ClassSizeResponse)

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

## 3. Update SchoolDetailResponse (in src/schemas/school.py)

Add to SchoolDetailResponse:
```python
ofsted_history: list[OfstedHistoryResponse] = []
ofsted_trajectory: OfstedTrajectoryResponse | None = None
```

## 4. Repository Interface (add to src/db/base.py SchoolRepository)

```python
@abstractmethod
async def get_ofsted_history(self, school_id: int) -> list[OfstedHistory]:
    """Return Ofsted inspection history for a school, ordered by date descending."""
    ...
```

## 5. SQLite Repository Implementation (add to src/db/sqlite_repo.py)

```python
async def get_ofsted_history(self, school_id: int) -> list[OfstedHistory]:
    stmt = select(OfstedHistory).where(OfstedHistory.school_id == school_id).order_by(OfstedHistory.inspection_date.desc())
    async with self._session_factory() as session:
        result = await session.execute(stmt)
        return list(result.scalars().all())
```

## 6. Trajectory Calculation Service (create src/services/ofsted_trajectory.py)

```python
from __future__ import annotations

import datetime
from typing import Literal

from src.db.models import OfstedHistory

TrajectoryType = Literal["improving", "stable", "declining", "unknown"]


def calculate_trajectory(history: list[OfstedHistory]) -> dict:
    """Calculate Ofsted trajectory from inspection history.

    Args:
        history: List of OfstedHistory records ordered by date descending (newest first)

    Returns:
        Dict with trajectory, current_rating, previous_rating, inspection_age_years, is_stale
    """
    if not history:
        return {
            "trajectory": "unknown",
            "current_rating": None,
            "previous_rating": None,
            "inspection_age_years": None,
            "is_stale": False,
        }

    # Rating order (best to worst)
    rating_order = ["Outstanding", "Good", "Requires Improvement", "Inadequate"]

    current = history[0]
    current_rating = current.rating
    previous_rating = history[1].rating if len(history) > 1 else None

    # Calculate age of last inspection
    today = datetime.date.today()
    inspection_age_days = (today - current.inspection_date).days
    inspection_age_years = inspection_age_days / 365.25
    is_stale = inspection_age_years > 5.0

    # Determine trajectory
    trajectory: TrajectoryType = "unknown"
    if previous_rating and current_rating in rating_order and previous_rating in rating_order:
        current_idx = rating_order.index(current_rating)
        previous_idx = rating_order.index(previous_rating)

        if current_idx < previous_idx:
            trajectory = "improving"
        elif current_idx > previous_idx:
            trajectory = "declining"
        else:
            trajectory = "stable"
    elif not previous_rating:
        trajectory = "stable"  # Only one inspection, assume stable

    return {
        "trajectory": trajectory,
        "current_rating": current_rating,
        "previous_rating": previous_rating,
        "inspection_age_years": round(inspection_age_years, 1),
        "is_stale": is_stale,
    }
```

## 7. API Endpoint (add to src/api/schools.py)

```python
from src.schemas.school import OfstedHistoryResponse, OfstedTrajectoryResponse
from src.services.ofsted_trajectory import calculate_trajectory

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

## 8. Update get_school endpoint (in src/api/schools.py)

Add to the get_school function:
```python
ofsted_history = await repo.get_ofsted_history(school_id)
trajectory_data = calculate_trajectory(ofsted_history)

# ... in the return statement:
ofsted_history=ofsted_history,
ofsted_trajectory=OfstedTrajectoryResponse(
    school_id=school_id,
    history=ofsted_history,
    **trajectory_data
),
```

## 9. Seed Data (add to src/db/seed.py)

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
        # Go back 3-5 years
        years_back = random.uniform(3.0, 5.0)
        previous_date = previous_date - datetime.timedelta(days=int(years_back * 365))

        # Determine previous rating (slight bias towards stability or improvement)
        if random.random() < 0.6:  # 60% chance of same or worse rating
            prev_idx = min(current_idx + random.choice([0, 1]), len(ratings) - 1)
        else:  # 40% chance of better rating
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

        current_idx = prev_idx  # For next iteration

    return history
```

Then in the `seed_schools` function, add after creating each school:
```python
# Add Ofsted history
ofsted_history = _generate_ofsted_history(
    school.id,
    school.ofsted_rating or "Good",
    school.ofsted_date or datetime.date(2023, 3, 15)
)
session.add_all(ofsted_history)
```

## 10. Frontend Component (create frontend/src/components/OfstedTrajectory.tsx)

```typescript
import React from 'react';
import { TrendingUp, TrendingDown, Minus, AlertCircle, Clock } from 'lucide-react';

interface OfstedInspection {
  id: number;
  inspection_date: string;
  rating: string;
  strengths_quote?: string;
  improvements_quote?: string;
  report_url?: string;
}

interface OfstedTrajectory {
  trajectory: 'improving' | 'stable' | 'declining' | 'unknown';
  current_rating?: string;
  previous_rating?: string;
  inspection_age_years?: number;
  is_stale: boolean;
  history: OfstedInspection[];
}

interface OfstedTrajectoryProps {
  trajectory: OfstedTrajectory;
}

const ratingColors: Record<string, string> = {
  'Outstanding': 'text-green-700 bg-green-50 border-green-200',
  'Good': 'text-blue-700 bg-blue-50 border-blue-200',
  'Requires Improvement': 'text-amber-700 bg-amber-50 border-amber-200',
  'Inadequate': 'text-red-700 bg-red-50 border-red-200',
};

export function OfstedTrajectory({ trajectory }: OfstedTrajectoryProps) {
  const getTrajectoryIcon = () => {
    switch (trajectory.trajectory) {
      case 'improving':
        return <TrendingUp className="w-5 h-5 text-green-600" />;
      case 'declining':
        return <TrendingDown className="w-5 h-5 text-red-600" />;
      case 'stable':
        return <Minus className="w-5 h-5 text-blue-600" />;
      default:
        return null;
    }
  };

  const getTrajectoryText = () => {
    switch (trajectory.trajectory) {
      case 'improving':
        return 'Improving';
      case 'declining':
        return 'Declining';
      case 'stable':
        return 'Stable';
      default:
        return 'Unknown';
    }
  };

  const getTrajectoryColor = () => {
    switch (trajectory.trajectory) {
      case 'improving':
        return 'text-green-700 bg-green-50 border-green-200';
      case 'declining':
        return 'text-red-700 bg-red-50 border-red-200';
      case 'stable':
        return 'text-blue-700 bg-blue-50 border-blue-200';
      default:
        return 'text-gray-700 bg-gray-50 border-gray-200';
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Ofsted Trajectory</h2>
          <p className="text-sm text-gray-600 mt-1">
            Inspection history and direction of travel
          </p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${getTrajectoryColor()}`}>
          {getTrajectoryIcon()}
          <span className="font-semibold">{getTrajectoryText()}</span>
        </div>
      </div>

      {trajectory.is_stale && trajectory.inspection_age_years && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-semibold text-amber-900">Rating may be stale</p>
            <p className="text-sm text-amber-800 mt-1">
              The last inspection was {trajectory.inspection_age_years.toFixed(1)} years ago (over 5 years).
              A new inspection may be due soon.
            </p>
          </div>
        </div>
      )}

      {trajectory.inspection_age_years !== null && !trajectory.is_stale && (
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <Clock className="w-4 h-4" />
          <span>
            Last inspected {trajectory.inspection_age_years.toFixed(1)} years ago
          </span>
        </div>
      )}

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-900">Inspection History</h3>
        <div className="space-y-4">
          {trajectory.history.map((inspection, index) => (
            <div
              key={inspection.id}
              className="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold border ${ratingColors[inspection.rating]}`}>
                      {inspection.rating}
                    </span>
                    {index === 0 && (
                      <span className="text-xs text-gray-500 font-medium">Current</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600">
                    Inspected {formatDate(inspection.inspection_date)}
                  </p>
                </div>
                {inspection.report_url && (
                  <a
                    href={inspection.report_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:text-blue-700 underline"
                  >
                    View report
                  </a>
                )}
              </div>

              {inspection.strengths_quote && (
                <div className="mb-2">
                  <p className="text-xs font-semibold text-gray-700 mb-1">Strengths:</p>
                  <p className="text-sm text-gray-600 italic">"{inspection.strengths_quote}"</p>
                </div>
              )}

              {inspection.improvements_quote && (
                <div>
                  <p className="text-xs font-semibold text-gray-700 mb-1">Areas for improvement:</p>
                  <p className="text-sm text-gray-600 italic">"{inspection.improvements_quote}"</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

## 11. Add to School Detail Page (frontend/src/pages/SchoolDetail.tsx)

Import:
```typescript
import { OfstedTrajectory } from '../components/OfstedTrajectory';
```

Add to the component after fetching school data:
```typescript
{school.ofsted_trajectory && (
  <OfstedTrajectory trajectory={school.ofsted_trajectory} />
)}
```

## 12. Update API client (frontend/src/api/client.ts)

Add types and functions:
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

export async function getOfstedTrajectory(schoolId: number): Promise<OfstedTrajectory> {
  const response = await fetch(`${API_BASE}/schools/${schoolId}/ofsted-trajectory`);
  if (!response.ok) {
    throw new Error('Failed to fetch Ofsted trajectory');
  }
  return response.json();
}
```

## Implementation Checklist

- [ ] Add OfstedHistory, AbsencePolicy, BusRoute models to src/db/models.py
- [ ] Add ofsted_history relationship to School model
- [ ] Add OfstedHistoryResponse and OfstedTrajectoryResponse to src/schemas/school.py
- [ ] Update SchoolDetailResponse to include ofsted_history and ofsted_trajectory
- [ ] Add get_ofsted_history method to SchoolRepository interface
- [ ] Implement get_ofsted_history in SQLiteSchoolRepository
- [ ] Create src/services/ofsted_trajectory.py with calculate_trajectory function
- [ ] Add ofsted-history and ofsted-trajectory endpoints to src/api/schools.py
- [ ] Update get_school endpoint to include trajectory data
- [ ] Add Ofsted history generation to src/db/seed.py
- [ ] Create frontend/src/components/OfstedTrajectory.tsx
- [ ] Update frontend/src/pages/SchoolDetail.tsx to display trajectory
- [ ] Update frontend/src/api/client.ts with trajectory types and functions
- [ ] Test database seeding
- [ ] Test API endpoints
- [ ] Test frontend component rendering
- [ ] Git commit and push to feature/ofsted-trajectory branch
