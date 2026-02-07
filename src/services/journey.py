"""Journey calculation service for the school-run planner.

Provides travel-time and distance estimates between a home postcode and a school.

.. note::
    The current implementation uses straight-line (Haversine) distance as a
    placeholder.  This should be replaced with a real routing API such as OSRM,
    GraphHopper, or the Google Directions API to provide accurate road/path
    distances and time-of-day traffic estimates.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from src.services.catchment import haversine_distance as _haversine_distance

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TravelMode(enum.Enum):
    """Supported travel modes for the school-run journey planner."""

    WALKING = "walking"
    CYCLING = "cycling"
    DRIVING = "driving"
    TRANSIT = "transit"


class TimeOfDay(enum.Enum):
    """Time-of-day windows used for traffic-aware routing.

    * ``DROPOFF`` -- morning drop-off window (08:00 - 08:45)
    * ``PICKUP``  -- afternoon/evening pick-up window (17:00 - 17:30)
    * ``GENERIC`` -- no specific time-of-day (average conditions)
    """

    DROPOFF = "dropoff"  # 8:00 - 8:45 AM
    PICKUP = "pickup"  # 5:00 - 5:30 PM
    GENERIC = "generic"


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JourneyResult:
    """Result of a journey calculation between two points."""

    distance_km: float
    duration_minutes: float
    mode: TravelMode
    time_of_day: TimeOfDay
    is_rush_hour: bool = False
    route_polyline: str | None = None


@dataclass(frozen=True)
class SchoolJourneyResult:
    """Journey results for a single school, with both drop-off and pick-up estimates."""

    school_id: int
    school_name: str
    distance_km: float
    dropoff: JourneyResult
    pickup: JourneyResult
    off_peak: JourneyResult


# ---------------------------------------------------------------------------
# Approximate average speeds (km/h) used for the placeholder implementation
# ---------------------------------------------------------------------------

_AVERAGE_SPEEDS_KMH: dict[TravelMode, float] = {
    TravelMode.WALKING: 5.0,
    TravelMode.CYCLING: 15.0,
    TravelMode.DRIVING: 30.0,  # urban average
    TravelMode.TRANSIT: 20.0,  # bus/tram average including stops
}

# Route factor to convert straight-line distance to realistic road/path distance.
# Walking/cycling tend to follow more direct paths; driving uses roads.
_ROUTE_FACTORS: dict[TravelMode, float] = {
    TravelMode.WALKING: 1.3,
    TravelMode.CYCLING: 1.3,
    TravelMode.DRIVING: 1.4,
    TravelMode.TRANSIT: 1.4,
}

# Time-of-day multipliers to approximate congestion effects.
_TIME_MULTIPLIERS: dict[TimeOfDay, dict[TravelMode, float]] = {
    TimeOfDay.DROPOFF: {
        TravelMode.WALKING: 1.0,
        TravelMode.CYCLING: 1.0,
        TravelMode.DRIVING: 1.3,  # morning rush-hour penalty (8-9am)
        TravelMode.TRANSIT: 1.2,
    },
    TimeOfDay.PICKUP: {
        TravelMode.WALKING: 1.0,
        TravelMode.CYCLING: 1.0,
        TravelMode.DRIVING: 1.3,  # evening rush-hour penalty (5-5:30pm)
        TravelMode.TRANSIT: 1.15,
    },
    TimeOfDay.GENERIC: {
        TravelMode.WALKING: 1.0,
        TravelMode.CYCLING: 1.0,
        TravelMode.DRIVING: 1.0,
        TravelMode.TRANSIT: 1.0,
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def calculate_journey(
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
    mode: TravelMode = TravelMode.WALKING,
    time_of_day: TimeOfDay = TimeOfDay.GENERIC,
    *,
    straight_line_km: float | None = None,
) -> JourneyResult:
    """Calculate a journey between two geographic points.

    Uses straight-line (Haversine) distance with a route factor and rough
    speed estimates.  The route factor varies by mode (1.3 for walking/cycling,
    1.4 for driving/transit).  Rush-hour multipliers are applied for drop-off
    (08:00-08:45) and pick-up (17:00-17:30) windows.

    Parameters
    ----------
    from_lat, from_lng:
        Origin coordinates (decimal degrees).
    to_lat, to_lng:
        Destination coordinates (decimal degrees).
    mode:
        Travel mode (walking, cycling, driving, transit).
    time_of_day:
        Time-of-day window used for traffic estimation.
    straight_line_km:
        Optional pre-computed Haversine distance.  When provided the
        internal Haversine calculation is skipped, avoiding redundant work
        when the same origin/destination pair is used for multiple
        time-of-day windows.

    Returns
    -------
    JourneyResult
        Estimated distance (km), duration (minutes), and rush-hour flag.
    """
    if straight_line_km is None:
        straight_line_km = _haversine_distance(from_lat, from_lng, to_lat, to_lng)
    route_factor = _ROUTE_FACTORS[mode]
    estimated_road_km = straight_line_km * route_factor

    speed_kmh = _AVERAGE_SPEEDS_KMH[mode]
    base_duration_hours = estimated_road_km / speed_kmh if speed_kmh > 0 else 0.0

    time_multiplier = _TIME_MULTIPLIERS[time_of_day][mode]
    duration_minutes = base_duration_hours * 60.0 * time_multiplier

    is_rush_hour = time_of_day in (TimeOfDay.DROPOFF, TimeOfDay.PICKUP) and mode in (
        TravelMode.DRIVING,
        TravelMode.TRANSIT,
    )

    return JourneyResult(
        distance_km=round(estimated_road_km, 2),
        duration_minutes=round(duration_minutes, 1),
        mode=mode,
        time_of_day=time_of_day,
        is_rush_hour=is_rush_hour,
        route_polyline=None,
    )


@dataclass
class SchoolInfo:
    """Minimal school info needed for journey comparison."""

    id: int
    name: str
    lat: float
    lng: float


async def compare_journeys(
    from_lat: float,
    from_lng: float,
    schools: list[SchoolInfo],
    mode: TravelMode = TravelMode.WALKING,
) -> list[SchoolJourneyResult]:
    """Compare journey times from an origin to multiple schools.

    For each school, calculates three journey estimates:
    - Drop-off: 8:00-8:45am (rush hour for driving)
    - Pick-up: 5:00-5:30pm (rush hour for driving -- user works until 5:30)
    - Off-peak: generic non-rush-hour time

    Results are sorted by drop-off duration (shortest first).

    Parameters
    ----------
    from_lat, from_lng:
        Origin coordinates (decimal degrees).
    schools:
        List of schools with id, name, lat, lng.
    mode:
        Travel mode to use for all calculations.

    Returns
    -------
    list[SchoolJourneyResult]
        Journey results for each school, sorted by drop-off time.
    """
    results: list[SchoolJourneyResult] = []

    for school in schools:
        sl_km = _haversine_distance(from_lat, from_lng, school.lat, school.lng)
        route_factor = _ROUTE_FACTORS[mode]
        distance_km = round(sl_km * route_factor, 2)

        dropoff = await calculate_journey(
            from_lat, from_lng, school.lat, school.lng, mode, TimeOfDay.DROPOFF, straight_line_km=sl_km
        )
        pickup = await calculate_journey(
            from_lat, from_lng, school.lat, school.lng, mode, TimeOfDay.PICKUP, straight_line_km=sl_km
        )
        off_peak = await calculate_journey(
            from_lat, from_lng, school.lat, school.lng, mode, TimeOfDay.GENERIC, straight_line_km=sl_km
        )

        results.append(
            SchoolJourneyResult(
                school_id=school.id,
                school_name=school.name,
                distance_km=distance_km,
                dropoff=dropoff,
                pickup=pickup,
                off_peak=off_peak,
            )
        )

    # Sort by drop-off duration (quickest first)
    results.sort(key=lambda r: r.dropoff.duration_minutes)
    return results
