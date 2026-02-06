"""Tests for holiday clubs API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.db.models import HolidayClub, School
from src.db.sqlite_repo import SQLiteSchoolRepository


@pytest.mark.asyncio
async def test_get_holiday_clubs_empty(test_client: AsyncClient, test_school: School) -> None:
    """Test getting holiday clubs when none exist."""
    response = await test_client.get(f"/api/schools/{test_school.id}/holiday-clubs")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_holiday_clubs_with_data(
    test_client: AsyncClient,
    test_school: School,
    test_repo: SQLiteSchoolRepository,
) -> None:
    """Test getting holiday clubs when they exist."""
    # Add a holiday club
    from datetime import time

    holiday_club = HolidayClub(
        school_id=test_school.id,
        provider_name="Test Holiday Club",
        is_school_run=True,
        description="Fun activities during school holidays",
        age_from=4,
        age_to=11,
        start_time=time(8, 0),
        end_time=time(18, 0),
        cost_per_day=35.00,
        cost_per_week=150.00,
        available_weeks="Easter, Summer, October half-term",
        booking_url="https://www.example.com/booking",
    )

    # Add to database
    async with test_repo._session_factory() as session:
        session.add(holiday_club)
        await session.commit()
        await session.refresh(holiday_club)

    # Fetch via API
    response = await test_client.get(f"/api/schools/{test_school.id}/holiday-clubs")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1

    club = data[0]
    assert club["provider_name"] == "Test Holiday Club"
    assert club["is_school_run"] is True
    assert club["description"] == "Fun activities during school holidays"
    assert club["age_from"] == 4
    assert club["age_to"] == 11
    assert club["cost_per_day"] == 35.00
    assert club["cost_per_week"] == 150.00
    assert club["available_weeks"] == "Easter, Summer, October half-term"
    assert club["booking_url"] == "https://www.example.com/booking"


@pytest.mark.asyncio
async def test_holiday_clubs_in_school_detail(
    test_client: AsyncClient,
    test_school: School,
    test_repo: SQLiteSchoolRepository,
) -> None:
    """Test that holiday clubs are included in school detail response."""
    from datetime import time

    # Add a holiday club
    holiday_club = HolidayClub(
        school_id=test_school.id,
        provider_name="School Holiday Activities",
        is_school_run=True,
        description="Full-day holiday care",
        age_from=5,
        age_to=10,
        start_time=time(8, 30),
        end_time=time(17, 30),
        cost_per_day=40.00,
        cost_per_week=175.00,
        available_weeks="All school holidays",
        booking_url=None,
    )

    async with test_repo._session_factory() as session:
        session.add(holiday_club)
        await session.commit()

    # Get school detail
    response = await test_client.get(f"/api/schools/{test_school.id}")
    assert response.status_code == 200

    data = response.json()
    assert "holiday_clubs" in data
    assert len(data["holiday_clubs"]) == 1

    club = data["holiday_clubs"][0]
    assert club["provider_name"] == "School Holiday Activities"
    assert club["is_school_run"] is True
    assert club["cost_per_day"] == 40.00
