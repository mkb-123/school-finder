"""Tests for parking rating functionality."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import ParkingRating


def _add_parking_rating(db_path: str, school_id: int, **kwargs) -> int:
    """Insert a parking rating for a school and return its ID."""
    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        rating = ParkingRating(school_id=school_id, **kwargs)
        session.add(rating)
        session.commit()
        rating_id = rating.id
    engine.dispose()
    return rating_id


class TestParkingRatingsAPI:
    """Tests for parking rating API endpoints using the sync test client."""

    def test_get_parking_ratings_empty(self, test_client: TestClient) -> None:
        """School 1 has no parking ratings initially."""
        response = test_client.get("/api/schools/1/parking-ratings")
        assert response.status_code == 200
        assert response.json() == []

    def test_submit_parking_rating(self, test_client: TestClient) -> None:
        """Submit a parking rating via the API."""
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

    def test_get_parking_ratings_after_submit(self, db_path: str, test_client: TestClient) -> None:
        """After inserting a rating, the API should return it."""
        _add_parking_rating(db_path, school_id=1, dropoff_chaos=3, pickup_chaos=4)

        response = test_client.get("/api/schools/1/parking-ratings")
        assert response.status_code == 200
        ratings = response.json()
        assert len(ratings) >= 1

    def test_parking_summary(self, db_path: str, test_client: TestClient) -> None:
        """Test the parking summary endpoint."""
        _add_parking_rating(
            db_path,
            school_id=1,
            dropoff_chaos=3,
            pickup_chaos=4,
            parking_availability=2,
            road_congestion=3,
            restrictions_hazards=1,
        )

        response = test_client.get("/api/schools/1/parking-summary")
        assert response.status_code == 200
        summary = response.json()
        assert summary["school_id"] == 1
        assert summary["total_ratings"] >= 1

    def test_nonexistent_school_parking_ratings(self, test_client: TestClient) -> None:
        """Parking ratings for a non-existent school returns empty or 404."""
        response = test_client.get("/api/schools/99999/parking-ratings")
        assert response.status_code in (200, 404)
