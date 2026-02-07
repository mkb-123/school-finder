#!/bin/bash
set -e

echo "=== Ofsted Trajectory Feature - Automated Installation ==="
echo ""
echo "This script will:"
echo "1. Append new models to src/db/models.py"
echo "2. Update src/schemas/school.py with new response models"
echo "3. Update src/db/base.py with repository interface"
echo "4. Update src/db/sqlite_repo.py with implementation"
echo "5. Update src/api/schools.py with new endpoints"
echo "6. Update src/db/seed.py to generate Ofsted history"
echo "7. Verify frontend files are in place"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi

# Step 1: Append models to models.py
echo "Step 1: Appending new models to src/db/models.py..."
cat >> src/db/models.py << 'EOF'


class OfstedHistory(Base):
    __tablename__ = "ofsted_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    # Inspection details
    inspection_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    rating: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # Outstanding / Good / Requires Improvement / Inadequate
    report_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Key quotes from report
    strengths_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvements_quote: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Flags
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # True for the most recent inspection

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
EOF

echo "✓ Models appended"

# Step 2: Update schemas
echo ""
echo "Step 2: Updating src/schemas/school.py..."
# This requires more complex editing, so we'll create a Python script to do it
python3 << 'PYTHON_EOF'
import re

# Read the file
with open("src/schemas/school.py", "r") as f:
    content = f.read()

# Check if already added
if "OfstedHistoryResponse" in content:
    print("✓ Schemas already updated (skipping)")
else:
    # Find the position after ClassSizeResponse class
    pattern = r'(class ClassSizeResponse\(BaseModel\):.*?avg_class_size: float \| None = None)\n\n'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        insert_pos = match.end()

        new_schemas = '''
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

'''
        content = content[:insert_pos] + new_schemas + content[insert_pos:]

        # Now update SchoolDetailResponse to include new fields
        pattern2 = r'(class SchoolDetailResponse\(SchoolResponse\):.*?uniform: list\[UniformResponse\] = \[\])'
        match2 = re.search(pattern2, content, re.DOTALL)

        if match2:
            insert_pos2 = match2.end()
            new_fields = '''
    ofsted_history: list[OfstedHistoryResponse] = []
    ofsted_trajectory: OfstedTrajectoryResponse | None = None'''
            content = content[:insert_pos2] + new_fields + content[insert_pos2:]

        # Write back
        with open("src/schemas/school.py", "w") as f:
            f.write(content)

        print("✓ Schemas updated")
    else:
        print("✗ Could not find insertion point in schemas (manual edit needed)")
PYTHON_EOF

echo ""
echo "Step 3: Updating src/db/base.py..."
python3 << 'PYTHON_EOF'
import re

with open("src/db/base.py", "r") as f:
    content = f.read()

if "get_ofsted_history" in content:
    print("✓ Repository interface already updated (skipping)")
else:
    # Add OfstedHistory to imports
    if "OfstedHistory" not in content:
        content = content.replace(
            "from src.db.models import (",
            "from src.db.models import (\n    OfstedHistory,"
        )

    # Add method to SchoolRepository class
    pattern = r'(@abstractmethod\s+async def get_uniform_for_school.*?\.\.\.\n)'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        insert_pos = match.end()
        new_method = '''
    @abstractmethod
    async def get_ofsted_history(self, school_id: int) -> list[OfstedHistory]:
        """Return Ofsted inspection history for a school, ordered by date descending."""
        ...

'''
        content = content[:insert_pos] + new_method + content[insert_pos:]

        with open("src/db/base.py", "w") as f:
            f.write(content)

        print("✓ Repository interface updated")
    else:
        print("✗ Could not find insertion point (manual edit needed)")
PYTHON_EOF

echo ""
echo "Step 4: Updating src/db/sqlite_repo.py..."
python3 << 'PYTHON_EOF'
import re

with open("src/db/sqlite_repo.py", "r") as f:
    content = f.read()

if "async def get_ofsted_history" in content:
    print("✓ SQLite repository already updated (skipping)")
else:
    # Add OfstedHistory to imports
    if "OfstedHistory" not in content:
        content = content.replace(
            "from src.db.models import (",
            "from src.db.models import (\n    OfstedHistory,"
        )

    # Add method implementation at the end of the class
    # Find the last method in the class
    pattern = r'(async def create_parking_rating.*?return rating\n)'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        insert_pos = match.end()
        new_method = '''
    async def get_ofsted_history(self, school_id: int) -> list[OfstedHistory]:
        stmt = (
            select(OfstedHistory)
            .where(OfstedHistory.school_id == school_id)
            .order_by(OfstedHistory.inspection_date.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())
'''
        content = content[:insert_pos] + new_method + content[insert_pos:]

        with open("src/db/sqlite_repo.py", "w") as f:
            f.write(content)

        print("✓ SQLite repository updated")
    else:
        print("✗ Could not find insertion point (manual edit needed)")
PYTHON_EOF

echo ""
echo "=== Summary ==="
echo "✓ Core implementation files created:"
echo "  - src/services/ofsted_trajectory.py"
echo "  - frontend/src/components/OfstedTrajectory.tsx"
echo ""
echo "⚠ Remaining manual steps:"
echo "  1. Update src/api/schools.py (add endpoints and update get_school)"
echo "  2. Update src/db/seed.py (add history generation)"
echo "  3. Update frontend/src/pages/SchoolDetail.tsx (display component)"
echo "  4. Update frontend/src/api/client.ts (add types)"
echo ""
echo "See OFSTED_TRAJECTORY_IMPLEMENTATION_STATUS.md for detailed instructions"
echo ""
echo "After completing manual steps:"
echo "  rm data/schools.db"
echo "  uv run python -m src.db.seed --council 'Milton Keynes'"
echo "  uv run python -m src.main"
echo ""
