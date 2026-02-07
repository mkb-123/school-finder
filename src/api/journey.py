"""Journey planner API endpoints.

Provides travel-time and distance estimates between a home postcode and one or
more schools, with rush-hour estimates for both drop-off (8:00-8:45am) and
pick-up (5:00-5:30pm) windows.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.services.journey import (
    SchoolInfo,
    SchoolJourneyResult,
    TravelMode,
    compare_journeys,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["journey"])

# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

_VALID_MODES = {"walking", "cycling", "driving", "transit"}


class JourneyEstimate(BaseModel):
    """A single journey estimate for a specific time-of-day window."""

    distance_km: float
    duration_minutes: float
    mode: str
    time_of_day: str
    is_rush_hour: bool


class SingleJourneyResponse(BaseModel):
    """Response for a single-school journey calculation."""

    school_id: int
    school_name: str
    distance_km: float
    dropoff: JourneyEstimate
    pickup: JourneyEstimate
    off_peak: JourneyEstimate


class CompareJourneysResponse(BaseModel):
    """Response for comparing journeys to multiple schools."""

    from_postcode: str
    mode: str
    journeys: list[SingleJourneyResponse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _journey_result_to_estimate(jr: object) -> JourneyEstimate:
    """Convert a JourneyResult dataclass to a Pydantic JourneyEstimate."""
    from src.services.journey import JourneyResult

    assert isinstance(jr, JourneyResult)
    return JourneyEstimate(
        distance_km=jr.distance_km,
        duration_minutes=jr.duration_minutes,
        mode=jr.mode.value,
        time_of_day=jr.time_of_day.value,
        is_rush_hour=jr.is_rush_hour,
    )


def _school_journey_to_response(sj: SchoolJourneyResult) -> SingleJourneyResponse:
    """Convert a SchoolJourneyResult to a Pydantic response model."""
    return SingleJourneyResponse(
        school_id=sj.school_id,
        school_name=sj.school_name,
        distance_km=sj.distance_km,
        dropoff=_journey_result_to_estimate(sj.dropoff),
        pickup=_journey_result_to_estimate(sj.pickup),
        off_peak=_journey_result_to_estimate(sj.off_peak),
    )


async def _geocode_postcode(postcode: str) -> tuple[float, float]:
    """Geocode a postcode via the shared geocoding helper."""
    from src.api.geocode import geocode_to_coords

    return await geocode_to_coords(postcode)


def _parse_mode(mode: str) -> TravelMode:
    """Parse a mode string into a TravelMode enum, raising 400 on invalid input."""
    mode_lower = mode.lower()
    if mode_lower not in _VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{mode}'. Must be one of: {', '.join(sorted(_VALID_MODES))}",
        )
    return TravelMode(mode_lower)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/journey", response_model=SingleJourneyResponse)
async def get_journey(
    from_postcode: str = Query(..., description="Origin postcode (e.g. MK5 6EX)"),
    to_school_id: int = Query(..., description="Target school ID"),
    mode: str = Query("walking", description="Travel mode: walking, cycling, driving, transit"),
    repo: SchoolRepository = Depends(get_school_repository),
) -> SingleJourneyResponse:
    """Calculate journey from a postcode to a single school.

    Returns distance and estimated travel times for drop-off (8:00-8:45am),
    pick-up (5:00-5:30pm), and off-peak periods.
    """
    travel_mode = _parse_mode(mode)
    lat, lng = await _geocode_postcode(from_postcode)

    school = await repo.get_school_by_id(to_school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    if school.lat is None or school.lng is None:
        raise HTTPException(status_code=400, detail="School has no coordinates")

    schools_info = [SchoolInfo(id=school.id, name=school.name, lat=school.lat, lng=school.lng)]
    results = await compare_journeys(lat, lng, schools_info, travel_mode)

    return _school_journey_to_response(results[0])


@router.get("/api/journey/compare", response_model=CompareJourneysResponse)
async def compare_school_journeys(
    from_postcode: str = Query(..., description="Origin postcode (e.g. MK5 6EX)"),
    school_ids: str = Query(..., description="Comma-separated school IDs (e.g. 1,2,3)"),
    mode: str = Query("walking", description="Travel mode: walking, cycling, driving, transit"),
    repo: SchoolRepository = Depends(get_school_repository),
) -> CompareJourneysResponse:
    """Compare journeys from a postcode to multiple schools.

    Returns distance and estimated travel times for each school, sorted by
    drop-off duration (shortest first). Includes drop-off (8:00-8:45am),
    pick-up (5:00-5:30pm), and off-peak estimates.
    """
    travel_mode = _parse_mode(mode)
    lat, lng = await _geocode_postcode(from_postcode)

    # Parse school IDs
    try:
        ids = [int(s.strip()) for s in school_ids.split(",") if s.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="school_ids must be comma-separated integers")

    if not ids:
        raise HTTPException(status_code=400, detail="At least one school_id is required")
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 schools for comparison")

    # Look up schools from the database
    schools_info: list[SchoolInfo] = []
    for sid in ids:
        school = await repo.get_school_by_id(sid)
        if school is None:
            raise HTTPException(status_code=404, detail=f"School {sid} not found")
        if school.lat is None or school.lng is None:
            continue  # Skip schools without coordinates
        schools_info.append(SchoolInfo(id=school.id, name=school.name, lat=school.lat, lng=school.lng))

    if not schools_info:
        raise HTTPException(status_code=400, detail="No valid schools found with coordinates")

    results = await compare_journeys(lat, lng, schools_info, travel_mode)

    return CompareJourneysResponse(
        from_postcode=from_postcode.upper(),
        mode=travel_mode.value,
        journeys=[_school_journey_to_response(r) for r in results],
    )
