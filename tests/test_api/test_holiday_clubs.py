"""Tests for holiday clubs API endpoints."""

from __future__ import annotations

from datetime import time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import HolidayClub, School

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_school_with_club(db_path: str) -> int:
    """Insert a test school and a holiday club, return the school ID."""
    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        school = session.query(School).first()
        if not school:
            raise RuntimeError("No schools in test DB")

        club = HolidayClub(
            school_id=school.id,
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
        session.add(club)
        session.commit()
        school_id = school.id
    engine.dispose()
    return school_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHolidayClubsEndpoint:
    """Tests for the holiday clubs API."""

    def test_get_holiday_clubs_empty(self, test_client: TestClient) -> None:
        """Test getting holiday clubs when none exist."""
        response = test_client.get("/api/schools/1/holiday-clubs")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_holiday_clubs_with_data(self, db_path: str, test_client: TestClient) -> None:
        """Test getting holiday clubs when they exist."""
        school_id = _seed_school_with_club(db_path)

        response = test_client.get(f"/api/schools/{school_id}/holiday-clubs")
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

    def test_nonexistent_school_returns_empty(self, test_client: TestClient) -> None:
        """Test that a non-existent school returns an empty list."""
        response = test_client.get("/api/schools/99999/holiday-clubs")
        assert response.status_code == 200
        assert response.json() == []
