from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.db.base import SchoolFilters, SchoolRepository
from src.db.factory import get_school_repository
from src.schemas.filters import SchoolFilterParams
from src.schemas.school import (
    AdmissionsEstimateResponse,
    AdmissionsHistoryResponse,
    ClubResponse,
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
            logger.warning("External geocoding failed for '%s' – trying local fallback", params.postcode)
            # Fall back to the same local lookup table used by /api/geocode
            try:
                from src.api.geocode import _fallback_lookup

                fallback = _fallback_lookup(params.postcode)
                if fallback is not None:
                    lat, lng = fallback.lat, fallback.lng
                else:
                    logger.warning("No local fallback for postcode '%s' – skipping distance filters", params.postcode)
            except Exception:
                logger.warning("Fallback lookup failed for '%s' – skipping distance filters", params.postcode)

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
    performance = await repo.get_performance_for_school(school_id)
    term_dates = await repo.get_term_dates_for_school(school_id)
    admissions = await repo.get_admissions_history(school_id)
    private_details = await repo.get_private_school_details(school_id)

    base = SchoolResponse.model_validate(school, from_attributes=True)
    return SchoolDetailResponse(
        **base.model_dump(),
        clubs=clubs,
        performance=performance,
        term_dates=term_dates,
        admissions_history=admissions,
        private_details=private_details,
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
