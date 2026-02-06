"""Shared pytest fixtures for the school-finder test suite."""

from __future__ import annotations

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.db.models import Base, School, SchoolClub
from src.db.sqlite_repo import SQLiteSchoolRepository
from src.main import app

# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------


def _create_test_schools() -> list[School]:
    """Return a fresh list of realistic Milton Keynes (and one Bedford) school records."""
    return [
        School(
            id=1,
            name="Broughton Fields Primary School",
            urn="110001",
            type="academy",
            council="Milton Keynes",
            address="Broughton, Milton Keynes",
            postcode="MK10 9JQ",
            lat=52.0360,
            lng=-0.7100,
            catchment_radius_km=2.0,
            gender_policy="co-ed",
            age_range_from=4,
            age_range_to=11,
            ofsted_rating="Outstanding",
            ofsted_date=datetime.date(2023, 3, 15),
            is_private=False,
        ),
        School(
            id=2,
            name="Walton High School",
            urn="110002",
            type="academy",
            council="Milton Keynes",
            address="Walton, Milton Keynes",
            postcode="MK7 7WH",
            lat=52.0250,
            lng=-0.7350,
            catchment_radius_km=3.0,
            gender_policy="co-ed",
            age_range_from=11,
            age_range_to=18,
            ofsted_rating="Good",
            ofsted_date=datetime.date(2022, 11, 1),
            is_private=False,
        ),
        School(
            id=3,
            name="Milton Keynes Preparatory School",
            urn="110003",
            type="private",
            council="Milton Keynes",
            address="Tattenhoe, Milton Keynes",
            postcode="MK3 6EN",
            lat=52.0010,
            lng=-0.7800,
            catchment_radius_km=None,
            gender_policy="co-ed",
            age_range_from=2,
            age_range_to=11,
            ofsted_rating="Good",
            ofsted_date=datetime.date(2023, 6, 20),
            is_private=True,
        ),
        School(
            id=4,
            name="St Thomas Aquinas Catholic Primary School",
            urn="110004",
            type="faith",
            council="Milton Keynes",
            address="Bletchley, Milton Keynes",
            postcode="MK14 6DP",
            lat=52.0480,
            lng=-0.7620,
            catchment_radius_km=1.5,
            gender_policy="co-ed",
            faith="Catholic",
            age_range_from=4,
            age_range_to=11,
            ofsted_rating="Requires Improvement",
            ofsted_date=datetime.date(2024, 1, 10),
            is_private=False,
        ),
        School(
            id=5,
            name="Thornton College",
            urn="110005",
            type="private",
            council="Milton Keynes",
            address="Thornton, Milton Keynes",
            postcode="MK17 0HJ",
            lat=52.0700,
            lng=-0.8200,
            catchment_radius_km=None,
            gender_policy="girls",
            age_range_from=3,
            age_range_to=18,
            ofsted_rating="Outstanding",
            ofsted_date=datetime.date(2022, 5, 5),
            is_private=True,
        ),
        School(
            id=6,
            name="Bedford Modern School",
            urn="120001",
            type="academy",
            council="Bedford",
            address="Manton Lane, Bedford",
            postcode="MK41 7NT",
            lat=52.1400,
            lng=-0.4700,
            catchment_radius_km=5.0,
            gender_policy="boys",
            age_range_from=7,
            age_range_to=18,
            ofsted_rating="Good",
            ofsted_date=datetime.date(2023, 9, 12),
            is_private=False,
        ),
    ]


def _create_test_clubs() -> list[SchoolClub]:
    """Return a set of test clubs to verify club-based filtering."""
    return [
        SchoolClub(
            id=1,
            school_id=1,
            club_type="breakfast",
            name="Early Birds Breakfast Club",
            days_available="Mon,Tue,Wed,Thu,Fri",
            start_time=datetime.time(7, 30),
            end_time=datetime.time(8, 45),
            cost_per_session=4.50,
        ),
        SchoolClub(
            id=2,
            school_id=1,
            club_type="after_school",
            name="Sports After-School Club",
            days_available="Mon,Wed,Fri",
            start_time=datetime.time(15, 15),
            end_time=datetime.time(17, 0),
            cost_per_session=6.00,
        ),
        SchoolClub(
            id=3,
            school_id=2,
            club_type="after_school",
            name="Homework Club",
            days_available="Tue,Thu",
            start_time=datetime.time(15, 30),
            end_time=datetime.time(16, 30),
            cost_per_session=0.0,
        ),
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path) -> str:
    """Create a temporary SQLite database seeded with test data and return its path."""
    path = str(tmp_path / "test_schools.db")
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine)

    with Session(sync_engine) as session:
        session.add_all(_create_test_schools())
        session.add_all(_create_test_clubs())
        session.commit()

    sync_engine.dispose()
    return path


@pytest.fixture()
def test_repo(db_path) -> SQLiteSchoolRepository:
    """Return an async :class:`SQLiteSchoolRepository` backed by the test database."""
    return SQLiteSchoolRepository(db_path)


@pytest.fixture()
def test_client(db_path) -> TestClient:
    """Return a FastAPI ``TestClient`` wired to the test database."""
    repo = SQLiteSchoolRepository(db_path)

    def _override() -> SchoolRepository:
        return repo

    app.dependency_overrides[get_school_repository] = _override

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
