"""Tests for holiday clubs API endpoints."""

from __future__ import annotations

import datetime

from fastapi.testclient import TestClient

from src.db.models import HolidayClub
from src.db.sqlite_repo import SQLiteSchoolRepository


class TestHolidayClubsEndpoint:
    """Tests for the per-school holiday clubs endpoint."""

    def test_get_holiday_clubs_empty(self, test_client: TestClient):
        """Test getting holiday clubs when none exist."""
        response = test_client.get("/api/schools/1/holiday-clubs")
        assert response.status_code == 200
        assert response.json() == []

    def test_holiday_clubs_in_school_detail(self, test_client: TestClient):
        """Test that holiday_clubs key is present in school detail response."""
        response = test_client.get("/api/schools/1")
        assert response.status_code == 200
        data = response.json()
        assert "holiday_clubs" in data
        assert isinstance(data["holiday_clubs"], list)
