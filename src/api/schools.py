from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.db.base import SchoolFilters, SchoolRepository
from src.db.factory import get_school_repository
from src.schemas.filters import SchoolFilterParams
from src.schemas.school import (
    AdmissionsCriteriaResponse,
    AdmissionsEstimateResponse,
    AdmissionsHistoryResponse,
    ClassSizeResponse,
    ClubResponse,
    OfstedHistoryResponse,
    OfstedTrajectoryResponse,
    ParkingRatingSummary,
    PerformanceResponse,
    SchoolDetailResponse,
    SchoolResponse,
    TermDateResponse,
)
from src.services.admissions import estimate_full

logger = logging.getLogger(__name__)

router = APIRouter(tags=["schools"])


async def _to_school_filters(params: SchoolFilterParams) -> SchoolFilters:
    """Convert API filter params to the repository's filter dataclass.

    When a *postcode* is provided but *lat*/*lng* are not, the postcode is
    auto-geocoded so that distance-based filtering and sorting work.
    """
    lat = params.lat
    lng = params.lng

    # Auto-geocode postcode when lat/lng are not explicitly provided
    if params.postcode and lat is None and lng is None:
        try:
            from src.services.geocoding import geocode_postcode

            lat, lng = await geocode_postcode(params.postcode)
        except Exception:
            logger.warning("Failed to geocode postcode '%s' – skipping distance filters", params.postcode)

    return SchoolFilters(
        council=params.council,
        lat=lat,
        lng=lng,
        age=params.age,
        gender=params.gender,
        school_type=params.type,
        min_rating=params.min_rating,
        max_distance_km=params.max_distance_km,
        has_breakfast_club=params.has_breakfast_club,
        has_afterschool_club=params.has_afterschool_club,
        faith=params.faith,
        search=params.search,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/api/schools", response_model=list[SchoolResponse])
async def list_schools(
    filters: Annotated[SchoolFilterParams, Query()],
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[SchoolResponse]:
    """List and search schools with optional filters."""
    school_filters = await _to_school_filters(filters)
    schools = await repo.find_schools_by_filters(school_filters)
    return schools


@router.get("/api/schools/{school_id}", response_model=SchoolDetailResponse)
async def get_school(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> SchoolDetailResponse:
    """Get full details for a single school including clubs, performance, etc."""
    school = await repo.get_school_by_id(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    clubs = await repo.get_clubs_for_school(school_id)
    holiday_clubs = await repo.get_holiday_clubs_for_school(school_id)
    performance = await repo.get_performance_for_school(school_id)
    term_dates = await repo.get_term_dates_for_school(school_id)
    admissions = await repo.get_admissions_history(school_id)
    admissions_criteria = await repo.get_admissions_criteria_for_school(school_id)
    private_details = await repo.get_private_school_details(school_id)
    class_sizes = await repo.get_class_sizes(school_id)
    uniform = await repo.get_uniform_for_school(school_id)

    # Get Ofsted trajectory
    from src.services.ofsted_trajectory import calculate_trajectory

    ofsted_history = await repo.get_ofsted_history(school_id)
    trajectory_data = calculate_trajectory(ofsted_history)
    ofsted_trajectory = (
        OfstedTrajectoryResponse(school_id=school_id, history=ofsted_history, **trajectory_data)
        if ofsted_history
        else None
    )

    # Calculate parking summary
    parking_ratings = await repo.get_parking_ratings_for_school(school_id)
    parking_summary = None
    if parking_ratings:

        def _avg(field: str) -> float | None:
            values = [getattr(r, field) for r in parking_ratings if getattr(r, field) is not None]
            return sum(values) / len(values) if values else None

        avg_dropoff = _avg("dropoff_chaos")
        avg_pickup = _avg("pickup_chaos")
        avg_parking = _avg("parking_availability")
        avg_congestion = _avg("road_congestion")
        avg_restrictions = _avg("restrictions_hazards")

        all_scores = [avg_dropoff, avg_pickup, avg_parking, avg_congestion, avg_restrictions]
        valid_scores = [s for s in all_scores if s is not None]
        overall = sum(valid_scores) / len(valid_scores) if valid_scores else None

        parking_summary = ParkingRatingSummary(
            school_id=school_id,
            total_ratings=len(parking_ratings),
            avg_dropoff_chaos=avg_dropoff,
            avg_pickup_chaos=avg_pickup,
            avg_parking_availability=avg_parking,
            avg_road_congestion=avg_congestion,
            avg_restrictions_hazards=avg_restrictions,
            overall_chaos_score=overall,
        )

    base = SchoolResponse.model_validate(school, from_attributes=True)
    return SchoolDetailResponse(
        **base.model_dump(),
        clubs=clubs,
        holiday_clubs=holiday_clubs,
        performance=performance,
        term_dates=term_dates,
        admissions_history=admissions,
        admissions_criteria=admissions_criteria,
        private_details=private_details,
        class_sizes=class_sizes,
        parking_summary=parking_summary,
        uniform=uniform,
        ofsted_trajectory=ofsted_trajectory,
    )


@router.get("/api/schools/{school_id}/clubs", response_model=list[ClubResponse])
async def get_school_clubs(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[ClubResponse]:
    """Get breakfast and after-school clubs for a school."""
    clubs = await repo.get_clubs_for_school(school_id)
    return clubs


@router.get("/api/schools/{school_id}/performance", response_model=list[PerformanceResponse])
async def get_school_performance(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[PerformanceResponse]:
    """Get academic performance metrics for a school."""
    performance = await repo.get_performance_for_school(school_id)
    return performance


@router.get("/api/schools/{school_id}/term-dates", response_model=list[TermDateResponse])
async def get_school_term_dates(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[TermDateResponse]:
    """Get term dates for a school."""
    term_dates = await repo.get_term_dates_for_school(school_id)
    return term_dates


@router.get("/api/schools/{school_id}/admissions", response_model=list[AdmissionsHistoryResponse])
async def get_school_admissions(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[AdmissionsHistoryResponse]:
    """Get historical admissions data for waiting-list estimation."""
    admissions = await repo.get_admissions_history(school_id)
    return admissions


@router.get("/api/schools/{school_id}/admissions/estimate", response_model=AdmissionsEstimateResponse)
async def get_admissions_estimate(
    school_id: int,
    distance_km: float,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> AdmissionsEstimateResponse:
    """Estimate likelihood of getting a place based on user's distance from school."""
    school = await repo.get_school_by_id(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    admissions = await repo.get_admissions_history(school_id)
    result = estimate_full(school_id, distance_km, admissions)

    return AdmissionsEstimateResponse(
        likelihood=result.likelihood,
        trend=result.trend,
        avg_last_distance_km=result.avg_last_distance_km,
        min_last_distance_km=result.min_last_distance_km,
        max_last_distance_km=result.max_last_distance_km,
        latest_last_distance_km=result.latest_last_distance_km,
        avg_oversubscription_ratio=result.avg_oversubscription_ratio,
        years_of_data=result.years_of_data,
    )


@router.get("/api/schools/{school_id}/admissions/criteria", response_model=list[AdmissionsCriteriaResponse])
async def get_admissions_criteria(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[AdmissionsCriteriaResponse]:
    """Get admissions criteria priority breakdown for a school."""
    criteria = await repo.get_admissions_criteria_for_school(school_id)
    return criteria


@router.get("/api/schools/{school_id}/class-sizes", response_model=list[ClassSizeResponse])
async def get_school_class_sizes(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[ClassSizeResponse]:
    """Get historical class size data for a school."""
    class_sizes = await repo.get_class_sizes(school_id)
    return class_sizes


@router.get("/api/schools/{school_id}/ofsted-history", response_model=list[OfstedHistoryResponse])
async def get_school_ofsted_history(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[OfstedHistoryResponse]:
    """Get Ofsted inspection history for a school."""
    history = await repo.get_ofsted_history(school_id)
    return history


@router.get("/api/schools/{school_id}/ofsted-trajectory", response_model=OfstedTrajectoryResponse)
async def get_school_ofsted_trajectory(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> OfstedTrajectoryResponse:
    """Get Ofsted trajectory analysis for a school."""
    from src.services.ofsted_trajectory import calculate_trajectory

    school = await repo.get_school_by_id(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    history = await repo.get_ofsted_history(school_id)
    trajectory_data = calculate_trajectory(history)

    return OfstedTrajectoryResponse(school_id=school_id, history=history, **trajectory_data)
