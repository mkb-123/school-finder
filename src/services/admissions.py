"""Admissions likelihood estimation service.

Uses historical admissions data (last distance offered, applications received,
waiting-list movement) to estimate how likely a child is to receive a place at
a given school based on their distance from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Likelihood labels
# ---------------------------------------------------------------------------

VERY_LIKELY = "Very likely"
LIKELY = "Likely"
UNLIKELY = "Unlikely"
VERY_UNLIKELY = "Very unlikely"

# ---------------------------------------------------------------------------
# Trend labels
# ---------------------------------------------------------------------------

TREND_SHRINKING = "shrinking"
TREND_STABLE = "stable"
TREND_GROWING = "growing"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class AdmissionsEstimate:
    """Result of an admissions likelihood estimation."""

    likelihood: str
    trend: str
    avg_last_distance_km: float | None
    min_last_distance_km: float | None
    max_last_distance_km: float | None
    latest_last_distance_km: float | None
    avg_oversubscription_ratio: float | None
    years_of_data: int


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _get_distances(admissions_history: list[Any]) -> list[float]:
    """Extract non-None last_distance_offered_km values from history records."""
    distances: list[float] = []
    for record in admissions_history:
        dist = (
            record.get("last_distance_offered_km")
            if isinstance(record, dict)
            else getattr(record, "last_distance_offered_km", None)
        )
        if dist is not None:
            distances.append(float(dist))
    return distances


def _get_sorted_by_year(admissions_history: list[Any]) -> list[Any]:
    """Sort admissions records by academic_year ascending."""

    def _year_key(record: Any) -> str:
        if isinstance(record, dict):
            return record.get("academic_year", "")
        return getattr(record, "academic_year", "")

    return sorted(admissions_history, key=_year_key)


def get_trend(
    school_id: int,
    admissions_history: list[Any] | None = None,
) -> str:
    """Determine whether a school's catchment is shrinking, stable, or growing.

    Analyses the trend in ``last_distance_offered_km`` over available years.
    A shrinking catchment (distances getting smaller) indicates increasing
    demand, while a growing catchment indicates decreasing demand.

    Parameters
    ----------
    school_id:
        The database ID of the target school (unused but kept for API
        consistency and future per-school logic).
    admissions_history:
        A list of historical admissions records for the school.

    Returns
    -------
    str
        One of ``"shrinking"``, ``"stable"``, or ``"growing"``.
    """
    _ = school_id

    if not admissions_history or len(admissions_history) < 2:
        return TREND_STABLE

    sorted_records = _get_sorted_by_year(admissions_history)
    distances: list[float] = []
    for record in sorted_records:
        dist = (
            record.get("last_distance_offered_km")
            if isinstance(record, dict)
            else getattr(record, "last_distance_offered_km", None)
        )
        if dist is not None:
            distances.append(float(dist))

    if len(distances) < 2:
        return TREND_STABLE

    # Simple linear trend: compare first half average to second half average
    mid = len(distances) // 2
    first_half_avg = sum(distances[:mid]) / mid
    second_half_avg = sum(distances[mid:]) / len(distances[mid:])

    pct_change = (second_half_avg - first_half_avg) / first_half_avg if first_half_avg > 0 else 0

    if pct_change < -0.08:
        return TREND_SHRINKING
    elif pct_change > 0.08:
        return TREND_GROWING
    else:
        return TREND_STABLE


def estimate_likelihood(
    school_id: int,
    distance_km: float,
    admissions_history: list[Any] | None = None,
) -> str:
    """Estimate the likelihood of a child being offered a place at a school.

    The estimation compares the user's distance against historical
    last-distance-offered data, factoring in trends and oversubscription.

    Parameters
    ----------
    school_id:
        The database ID of the target school.
    distance_km:
        The straight-line distance in kilometres from the child's home
        to the school.
    admissions_history:
        A list of historical admissions records for the school.

    Returns
    -------
    str
        One of ``"Very likely"``, ``"Likely"``, ``"Unlikely"``, or
        ``"Very unlikely"``.
    """
    if not admissions_history:
        return LIKELY

    distances = _get_distances(admissions_history)
    if not distances:
        return LIKELY

    avg_dist = sum(distances) / len(distances)

    # Weight recent years more: use the latest year's distance
    sorted_records = _get_sorted_by_year(admissions_history)
    latest_dist = None
    for record in reversed(sorted_records):
        d = (
            record.get("last_distance_offered_km")
            if isinstance(record, dict)
            else getattr(record, "last_distance_offered_km", None)
        )
        if d is not None:
            latest_dist = float(d)
            break

    # Use a weighted reference: 60% latest year, 40% average
    if latest_dist is not None:
        reference_dist = 0.6 * latest_dist + 0.4 * avg_dist
    else:
        reference_dist = avg_dist

    # Factor in trend - if shrinking, be more conservative
    trend = get_trend(school_id, admissions_history)
    if trend == TREND_SHRINKING:
        # Reduce the effective reference distance by 10% for shrinking catchments
        reference_dist *= 0.90
    elif trend == TREND_GROWING:
        # Increase the effective reference distance by 5% for growing catchments
        reference_dist *= 1.05

    # Classification based on user distance vs reference
    if distance_km <= reference_dist * 0.6:
        return VERY_LIKELY
    elif distance_km <= reference_dist:
        return LIKELY
    elif distance_km <= reference_dist * 1.3:
        return UNLIKELY
    else:
        return VERY_UNLIKELY


def estimate_full(
    school_id: int,
    distance_km: float,
    admissions_history: list[Any] | None = None,
) -> AdmissionsEstimate:
    """Return a full admissions estimate with supporting data.

    This is the rich version of :func:`estimate_likelihood` that returns
    all supporting data points alongside the likelihood label.

    Parameters
    ----------
    school_id:
        The database ID of the target school.
    distance_km:
        The user's distance in km from the school.
    admissions_history:
        Historical admissions records for the school.

    Returns
    -------
    AdmissionsEstimate
        Full estimate with likelihood, trend, and supporting statistics.
    """
    if not admissions_history:
        return AdmissionsEstimate(
            likelihood=LIKELY,
            trend=TREND_STABLE,
            avg_last_distance_km=None,
            min_last_distance_km=None,
            max_last_distance_km=None,
            latest_last_distance_km=None,
            avg_oversubscription_ratio=None,
            years_of_data=0,
        )

    distances = _get_distances(admissions_history)
    sorted_records = _get_sorted_by_year(admissions_history)

    # Compute statistics
    avg_dist = sum(distances) / len(distances) if distances else None
    min_dist = min(distances) if distances else None
    max_dist = max(distances) if distances else None

    # Latest distance
    latest_dist = None
    for record in reversed(sorted_records):
        d = (
            record.get("last_distance_offered_km")
            if isinstance(record, dict)
            else getattr(record, "last_distance_offered_km", None)
        )
        if d is not None:
            latest_dist = float(d)
            break

    # Average oversubscription ratio
    ratios: list[float] = []
    for record in admissions_history:
        if isinstance(record, dict):
            apps = record.get("applications_received")
            places = record.get("places_offered")
        else:
            apps = getattr(record, "applications_received", None)
            places = getattr(record, "places_offered", None)
        if apps is not None and places is not None and places > 0:
            ratios.append(apps / places)

    avg_ratio = round(sum(ratios) / len(ratios), 2) if ratios else None

    return AdmissionsEstimate(
        likelihood=estimate_likelihood(school_id, distance_km, admissions_history),
        trend=get_trend(school_id, admissions_history),
        avg_last_distance_km=round(avg_dist, 2) if avg_dist is not None else None,
        min_last_distance_km=round(min_dist, 2) if min_dist is not None else None,
        max_last_distance_km=round(max_dist, 2) if max_dist is not None else None,
        latest_last_distance_km=round(latest_dist, 2) if latest_dist is not None else None,
        avg_oversubscription_ratio=avg_ratio,
        years_of_data=len(set(_get_year(r) for r in admissions_history)),
    )


def _get_year(record: Any) -> str:
    """Extract academic_year from a record (dict or ORM object)."""
    if isinstance(record, dict):
        return record.get("academic_year", "")
    return getattr(record, "academic_year", "")
