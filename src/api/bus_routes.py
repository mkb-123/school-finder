"""Bus routes API endpoints.

Provides information about dedicated school bus routes, stops, and eligibility.
Extends the journey planner feature to include school bus transport options.
"""

from __future__ import annotations

import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bus_routes"])

# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class BusStopResponse(BaseModel):
    """A single bus stop with location and pickup times."""

    id: int
    stop_name: str
    stop_location: str | None
    lat: float | None
    lng: float | None
    morning_pickup_time: datetime.time | None
    afternoon_dropoff_time: datetime.time | None
    stop_order: int


class BusRouteResponse(BaseModel):
    """Bus route with stops and eligibility information."""

    id: int
    route_name: str
    provider: str | None
    route_type: str
    distance_eligibility_km: float | None
    year_groups_eligible: str | None
    eligibility_notes: str | None
    is_free: bool
    cost_per_term: float | None
    cost_per_year: float | None
    cost_notes: str | None
    operates_days: str | None
    morning_departure_time: datetime.time | None
    afternoon_departure_time: datetime.time | None
    booking_url: str | None
    notes: str | None
    stops: list[BusStopResponse]


class NearbyBusStopResponse(BaseModel):
    """A bus stop near the user's location, with route and school info."""

    stop: BusStopResponse
    route_name: str
    route_type: str
    is_free: bool
    cost_per_term: float | None
    school_id: int
    school_name: str
    distance_km: float


class BusRoutesForSchoolResponse(BaseModel):
    """All bus routes for a school."""

    school_id: int
    school_name: str
    routes: list[BusRouteResponse]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/schools/{school_id}/bus-routes", response_model=BusRoutesForSchoolResponse)
async def get_school_bus_routes(
    school_id: int,
    repo: SchoolRepository = Depends(get_school_repository),
) -> BusRoutesForSchoolResponse:
    """Get all bus routes for a school, including stops and eligibility."""
    school = await repo.get_school_by_id(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    routes = await repo.get_bus_routes_for_school(school_id)

    # Load stops for each route
    routes_with_stops: list[BusRouteResponse] = []
    for route in routes:
        stops = await repo.get_bus_stops_for_route(route.id)
        stops_response = [
            BusStopResponse(
                id=stop.id,
                stop_name=stop.stop_name,
                stop_location=stop.stop_location,
                lat=stop.lat,
                lng=stop.lng,
                morning_pickup_time=stop.morning_pickup_time,
                afternoon_dropoff_time=stop.afternoon_dropoff_time,
                stop_order=stop.stop_order,
            )
            for stop in stops
        ]
        routes_with_stops.append(
            BusRouteResponse(
                id=route.id,
                route_name=route.route_name,
                provider=route.provider,
                route_type=route.route_type,
                distance_eligibility_km=route.distance_eligibility_km,
                year_groups_eligible=route.year_groups_eligible,
                eligibility_notes=route.eligibility_notes,
                is_free=route.is_free,
                cost_per_term=route.cost_per_term,
                cost_per_year=route.cost_per_year,
                cost_notes=route.cost_notes,
                operates_days=route.operates_days,
                morning_departure_time=route.morning_departure_time,
                afternoon_departure_time=route.afternoon_departure_time,
                booking_url=route.booking_url,
                notes=route.notes,
                stops=stops_response,
            )
        )

    return BusRoutesForSchoolResponse(
        school_id=school.id,
        school_name=school.name,
        routes=routes_with_stops,
    )


@router.get("/api/bus-routes/nearby", response_model=list[NearbyBusStopResponse])
async def find_nearby_bus_stops(
    lat: float = Query(..., description="Latitude of user location"),
    lng: float = Query(..., description="Longitude of user location"),
    max_distance_km: float = Query(0.5, description="Maximum distance in km (default 0.5)"),
    repo: SchoolRepository = Depends(get_school_repository),
) -> list[NearbyBusStopResponse]:
    """Find bus stops within walking distance of a location.

    Returns stops with route and school information, sorted by distance.
    Useful for showing whether a school bus stop is accessible from the user's postcode.
    """
    if max_distance_km > 5.0:
        raise HTTPException(status_code=400, detail="max_distance_km must be <= 5.0")

    nearby = await repo.find_nearby_bus_stops(lat, lng, max_distance_km)

    results: list[NearbyBusStopResponse] = []
    for stop, route, school, distance in nearby:
        results.append(
            NearbyBusStopResponse(
                stop=BusStopResponse(
                    id=stop.id,
                    stop_name=stop.stop_name,
                    stop_location=stop.stop_location,
                    lat=stop.lat,
                    lng=stop.lng,
                    morning_pickup_time=stop.morning_pickup_time,
                    afternoon_dropoff_time=stop.afternoon_dropoff_time,
                    stop_order=stop.stop_order,
                ),
                route_name=route.route_name,
                route_type=route.route_type,
                is_free=route.is_free,
                cost_per_term=route.cost_per_term,
                school_id=school.id,
                school_name=school.name,
                distance_km=round(distance, 2),
            )
        )

    return results
