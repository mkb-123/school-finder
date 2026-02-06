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
import math
from dataclasses import dataclass

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
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JourneyResult:
    """Result of a journey calculation between two points."""

    distance_km: float
    duration_minutes: float
    mode: TravelMode
    time_of_day: TimeOfDay
    route_polyline: str | None = None


# ---------------------------------------------------------------------------
# Approximate average speeds (km/h) used for the placeholder implementation
# ---------------------------------------------------------------------------

_AVERAGE_SPEEDS_KMH: dict[TravelMode, float] = {
    TravelMode.WALKING: 5.0,
    TravelMode.CYCLING: 15.0,
    TravelMode.DRIVING: 30.0,  # urban average
    TravelMode.TRANSIT: 20.0,  # bus/tram average including stops
}

# Rough multiplier to convert straight-line distance to road/path distance.
# Real-world routes are typically 20-40 % longer than the crow-flies distance.
_DETOUR_FACTOR = 1.3

# Time-of-day multipliers to approximate congestion effects.
# These are very rough placeholders.
_TIME_MULTIPLIERS: dict[TimeOfDay, dict[TravelMode, float]] = {
    TimeOfDay.DROPOFF: {
        TravelMode.WALKING: 1.0,
        TravelMode.CYCLING: 1.0,
        TravelMode.DRIVING: 1.3,  # morning rush-hour penalty
        TravelMode.TRANSIT: 1.2,
    },
    TimeOfDay.PICKUP: {
        TravelMode.WALKING: 1.0,
        TravelMode.CYCLING: 1.0,
        TravelMode.DRIVING: 1.25,  # evening rush-hour penalty
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
# Haversine helper (duplicated from catchment to avoid circular imports)
# ---------------------------------------------------------------------------


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the great-circle distance in km between two points (decimal degrees)."""
    earth_radius_km = 6371.0

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_km * c


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
) -> JourneyResult:
    """Calculate a journey between two geographic points.

    .. note::
        **Placeholder implementation** -- uses straight-line (Haversine) distance
        with a detour factor and rough speed estimates.  Replace with a real
        routing API (e.g. OSRM, GraphHopper, or Google Directions) for
        production use.

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

    Returns
    -------
    JourneyResult
        Estimated distance (km) and duration (minutes).
    """
    # TODO: Replace this placeholder with a real routing API call (OSRM or similar)
    # that returns actual road/path distances, turn-by-turn directions, and
    # time-of-day traffic data.

    straight_line_km = _haversine_distance(from_lat, from_lng, to_lat, to_lng)
    estimated_road_km = straight_line_km * _DETOUR_FACTOR

    speed_kmh = _AVERAGE_SPEEDS_KMH[mode]
    base_duration_hours = estimated_road_km / speed_kmh if speed_kmh > 0 else 0.0

    time_multiplier = _TIME_MULTIPLIERS[time_of_day][mode]
    duration_minutes = base_duration_hours * 60.0 * time_multiplier

    return JourneyResult(
        distance_km=round(estimated_road_km, 2),
        duration_minutes=round(duration_minutes, 1),
        mode=mode,
        time_of_day=time_of_day,
        route_polyline=None,  # No polyline available from the placeholder implementation
    )
