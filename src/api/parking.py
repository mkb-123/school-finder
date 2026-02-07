from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.db.models import ParkingRating
from src.schemas.school import (
    ParkingRatingResponse,
    ParkingRatingSubmitRequest,
    ParkingRatingSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["parking"])


@router.get("/api/schools/{school_id}/parking-ratings", response_model=list[ParkingRatingResponse])
async def get_parking_ratings(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[ParkingRatingResponse]:
    """Get all parking chaos ratings for a school."""
    ratings = await repo.get_parking_ratings_for_school(school_id)
    return [ParkingRatingResponse.model_validate(r, from_attributes=True) for r in ratings]


@router.get("/api/schools/{school_id}/parking-summary", response_model=ParkingRatingSummary)
async def get_parking_summary(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> ParkingRatingSummary:
    """Get aggregated parking chaos statistics for a school."""
    ratings = await repo.get_parking_ratings_for_school(school_id)

    if not ratings:
        return ParkingRatingSummary(
            school_id=school_id,
            total_ratings=0,
        )

    # Calculate averages for each dimension
    def _avg(field: str) -> float | None:
        values = [getattr(r, field) for r in ratings if getattr(r, field) is not None]
        return sum(values) / len(values) if values else None

    avg_dropoff = _avg("dropoff_chaos")
    avg_pickup = _avg("pickup_chaos")
    avg_parking = _avg("parking_availability")
    avg_congestion = _avg("road_congestion")
    avg_restrictions = _avg("restrictions_hazards")

    # Calculate overall chaos score (average of all dimensions)
    all_scores = [avg_dropoff, avg_pickup, avg_parking, avg_congestion, avg_restrictions]
    valid_scores = [s for s in all_scores if s is not None]
    overall = sum(valid_scores) / len(valid_scores) if valid_scores else None

    return ParkingRatingSummary(
        school_id=school_id,
        total_ratings=len(ratings),
        avg_dropoff_chaos=avg_dropoff,
        avg_pickup_chaos=avg_pickup,
        avg_parking_availability=avg_parking,
        avg_road_congestion=avg_congestion,
        avg_restrictions_hazards=avg_restrictions,
        overall_chaos_score=overall,
    )


@router.post("/api/parking-ratings", response_model=ParkingRatingResponse)
async def submit_parking_rating(
    request: ParkingRatingSubmitRequest,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> ParkingRatingResponse:
    """Submit a new parking chaos rating for a school."""
    # Validate that the school exists
    school = await repo.get_school_by_id(request.school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    # Validate rating values (1-5 scale)
    rating_fields = [
        "dropoff_chaos",
        "pickup_chaos",
        "parking_availability",
        "road_congestion",
        "restrictions_hazards",
    ]
    for field in rating_fields:
        value = getattr(request, field)
        if value is not None and (value < 1 or value > 5):
            raise HTTPException(
                status_code=400,
                detail=f"{field} must be between 1 and 5",
            )

    # Ensure at least one rating is provided
    if all(getattr(request, f) is None for f in rating_fields):
        raise HTTPException(
            status_code=400,
            detail="At least one rating field must be provided",
        )

    # Create the rating
    rating = ParkingRating(
        school_id=request.school_id,
        dropoff_chaos=request.dropoff_chaos,
        pickup_chaos=request.pickup_chaos,
        parking_availability=request.parking_availability,
        road_congestion=request.road_congestion,
        restrictions_hazards=request.restrictions_hazards,
        comments=request.comments,
        parent_email=request.parent_email,
    )

    saved_rating = await repo.create_parking_rating(rating)
    return ParkingRatingResponse.model_validate(saved_rating, from_attributes=True)
