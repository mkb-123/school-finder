"""Tests for admissions criteria feature."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import AdmissionsCriteria, Base, School


@pytest.fixture()
def db_with_criteria(tmp_path):
    """Create a test database with schools and admissions criteria."""
    path = str(tmp_path / "test_criteria.db")
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine)

    with Session(sync_engine) as session:
        # Add a test school
        school = School(
            id=1,
            name="Test Primary School",
            urn="100001",
            type="state",
            council="Test Council",
            address="Test Address",
            postcode="TE1 1ST",
            lat=51.5,
            lng=-0.1,
            catchment_radius_km=2.0,
            gender_policy="co-ed",
            age_range_from=4,
            age_range_to=11,
            ofsted_rating="Good",
            is_private=False,
        )
        session.add(school)

        # Add admissions criteria
        criteria = [
            AdmissionsCriteria(
                school_id=1,
                priority_rank=1,
                category="Looked-after children",
                description="Children in care or previously in care",
                religious_requirement=None,
                requires_sif=False,
                notes=None,
            ),
            AdmissionsCriteria(
                school_id=1,
                priority_rank=2,
                category="Siblings",
                description="Children with a sibling at the school",
                religious_requirement=None,
                requires_sif=False,
                notes=None,
            ),
            AdmissionsCriteria(
                school_id=1,
                priority_rank=3,
                category="Distance",
                description="All other applicants by distance from home",
                religious_requirement=None,
                requires_sif=False,
                notes="Tiebreaker: random ballot",
            ),
        ]
        session.add_all(criteria)
        session.commit()

    sync_engine.dispose()
    return path


@pytest.mark.asyncio
async def test_get_admissions_criteria(db_with_criteria):
    """Test that admissions criteria can be fetched for a school."""
    from src.db.sqlite_repo import SQLiteSchoolRepository

    repo = SQLiteSchoolRepository(db_with_criteria)

    criteria = await repo.get_admissions_criteria_for_school(1)

    assert len(criteria) == 3
    assert criteria[0].priority_rank == 1
    assert criteria[0].category == "Looked-after children"
    assert criteria[1].priority_rank == 2
    assert criteria[1].category == "Siblings"
    assert criteria[2].priority_rank == 3
    assert criteria[2].category == "Distance"
    assert criteria[2].notes == "Tiebreaker: random ballot"


@pytest.mark.asyncio
async def test_admissions_criteria_ordered_by_rank(db_with_criteria):
    """Test that criteria are returned in priority rank order."""
    from src.db.sqlite_repo import SQLiteSchoolRepository

    repo = SQLiteSchoolRepository(db_with_criteria)

    criteria = await repo.get_admissions_criteria_for_school(1)

    ranks = [c.priority_rank for c in criteria]
    assert ranks == sorted(ranks), "Criteria should be ordered by priority_rank"


@pytest.mark.asyncio
async def test_get_criteria_for_nonexistent_school(db_with_criteria):
    """Test that fetching criteria for non-existent school returns empty list."""
    from src.db.sqlite_repo import SQLiteSchoolRepository

    repo = SQLiteSchoolRepository(db_with_criteria)

    criteria = await repo.get_admissions_criteria_for_school(999)

    assert len(criteria) == 0


def test_admissions_criteria_endpoint(test_client):
    """Test the /api/schools/{id}/admissions/criteria endpoint."""
    # This uses the conftest.py test_client fixture which already has test data
    # But it doesn't have criteria, so we expect an empty list
    response = test_client.get("/api/schools/1/admissions/criteria")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # May be empty if conftest doesn't seed criteria - that's OK for now
