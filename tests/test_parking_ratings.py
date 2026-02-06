"""Tests for parking rating functionality."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.db.models import ParkingRating, School
from src.db.sqlite_repo import SQLiteSchoolRepository


@pytest.mark.asyncio
async def test_create_parking_rating(test_db_session):
    """Test creating a parking rating through the repository."""
    # Create a test school
    school = School(
        name="Test School",
        council="Test Council",
        type="Academy",
        lat=52.0,
        lng=-0.75,
        ofsted_rating="Good",
    )
    test_db_session.add(school)
    test_db_session.commit()

    repo = SQLiteSchoolRepository(":memory:")
    repo._session_factory = lambda: test_db_session

    # Create a parking rating
    rating = ParkingRating(
        school_id=school.id,
        dropoff_chaos=4,
        pickup_chaos=5,
        parking_availability=3,
        road_congestion=4,
        restrictions_hazards=2,
        comments="Very busy at drop-off time",
    )

    saved_rating = await repo.create_parking_rating(rating)
    assert saved_rating.id is not None
    assert saved_rating.school_id == school.id
    assert saved_rating.dropoff_chaos == 4
    assert saved_rating.pickup_chaos == 5


@pytest.mark.asyncio
async def test_get_parking_ratings_for_school(test_db_session):
    """Test retrieving parking ratings for a school."""
    # Create a test school
    school = School(
        name="Test School",
        council="Test Council",
        type="Academy",
        lat=52.0,
        lng=-0.75,
    )
    test_db_session.add(school)
    test_db_session.commit()

    # Add some ratings
    rating1 = ParkingRating(
        school_id=school.id,
        dropoff_chaos=3,
        pickup_chaos=4,
    )
    rating2 = ParkingRating(
        school_id=school.id,
        dropoff_chaos=2,
        pickup_chaos=3,
        comments="Much better in the morning",
    )
    test_db_session.add(rating1)
    test_db_session.add(rating2)
    test_db_session.commit()

    repo = SQLiteSchoolRepository(":memory:")
    repo._session_factory = lambda: test_db_session

    ratings = await repo.get_parking_ratings_for_school(school.id)
    assert len(ratings) == 2


@pytest.mark.asyncio
async def test_parking_api_endpoints(test_client: AsyncClient, test_db_session):
    """Test parking rating API endpoints."""
    # Create a test school
    school = School(
        name="Test School",
        council="Test Council",
        type="Academy",
        lat=52.0,
        lng=-0.75,
    )
    test_db_session.add(school)
    test_db_session.commit()

    # Test submitting a rating
    response = await test_client.post(
        "/api/parking-ratings",
        json={
            "school_id": school.id,
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
    assert data["school_id"] == school.id
    assert data["dropoff_chaos"] == 4

    # Test getting ratings for a school
    response = await test_client.get(f"/api/schools/{school.id}/parking-ratings")
    assert response.status_code == 200
    ratings = response.json()
    assert len(ratings) >= 1

    # Test getting parking summary
    response = await test_client.get(f"/api/schools/{school.id}/parking-summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["school_id"] == school.id
    assert summary["total_ratings"] >= 1
    assert summary["avg_dropoff_chaos"] is not None


@pytest.mark.asyncio
async def test_parking_rating_validation(test_client: AsyncClient, test_db_session):
    """Test validation of parking rating values."""
    school = School(
        name="Test School",
        council="Test Council",
        type="Academy",
    )
    test_db_session.add(school)
    test_db_session.commit()

    # Test invalid rating value (> 5)
    response = await test_client.post(
        "/api/parking-ratings",
        json={
            "school_id": school.id,
            "dropoff_chaos": 6,  # Invalid - should be 1-5
        },
    )
    assert response.status_code == 400

    # Test invalid school ID
    response = await test_client.post(
        "/api/parking-ratings",
        json={
            "school_id": 999999,
            "dropoff_chaos": 3,
        },
    )
    assert response.status_code == 404
