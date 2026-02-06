"""Tests for parking rating functionality."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.db.sqlite_repo import SQLiteSchoolRepository


class TestParkingRatings:
    """Tests for the parking rating API endpoints."""

    def test_get_parking_ratings_empty(self, test_client: TestClient):
        """School with no ratings returns empty list."""
        response = test_client.get("/api/schools/1/parking-ratings")
        assert response.status_code == 200
        assert response.json() == []

    def test_submit_parking_rating(self, test_client: TestClient):
        """Test submitting a parking rating for an existing school."""
        response = test_client.post(
            "/api/parking-ratings",
            json={
                "school_id": 1,
                "dropoff_chaos": 4,
                "pickup_chaos": 5,
                "parking_availability": 3,
                "road_congestion": 4,
                "restrictions_hazards": 2,
                "comments": "Very busy during school hours",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["school_id"] == 1
        assert data["dropoff_chaos"] == 4

    def test_get_parking_summary_no_ratings(self, test_client: TestClient):
        """Parking summary with no ratings should still return."""
        response = test_client.get("/api/schools/1/parking-summary")
        assert response.status_code == 200

    def test_parking_detail_in_school(self, test_client: TestClient):
        """School detail response should include parking_summary key."""
        response = test_client.get("/api/schools/1")
        assert response.status_code == 200
        data = response.json()
        assert "parking_summary" in data
