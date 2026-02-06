from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.db.factory import get_school_repository
from src.schemas.filters import SchoolFilterParams
from src.schemas.school import (
    AdmissionsHistoryResponse,
    ClubResponse,
    PerformanceResponse,
    SchoolDetailResponse,
    SchoolResponse,
    TermDateResponse,
)

router = APIRouter(tags=["schools"])


@router.get("/api/schools", response_model=list[SchoolResponse])
async def list_schools(
    filters: Annotated[SchoolFilterParams, Query()],
    repo: Annotated[object, Depends(get_school_repository)],
) -> list[SchoolResponse]:
    """List and search schools with optional filters."""
    schools = await repo.find_schools(filters)
    return schools


@router.get("/api/schools/{school_id}", response_model=SchoolDetailResponse)
async def get_school(
    school_id: int,
    repo: Annotated[object, Depends(get_school_repository)],
) -> SchoolDetailResponse:
    """Get full details for a single school."""
    school = await repo.get_school_detail(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    return school


@router.get("/api/schools/{school_id}/clubs", response_model=list[ClubResponse])
async def get_school_clubs(
    school_id: int,
    repo: Annotated[object, Depends(get_school_repository)],
) -> list[ClubResponse]:
    """Get breakfast and after-school clubs for a school."""
    clubs = await repo.get_clubs(school_id)
    return clubs


@router.get("/api/schools/{school_id}/performance", response_model=list[PerformanceResponse])
async def get_school_performance(
    school_id: int,
    repo: Annotated[object, Depends(get_school_repository)],
) -> list[PerformanceResponse]:
    """Get academic performance metrics for a school."""
    performance = await repo.get_performance(school_id)
    return performance


@router.get("/api/schools/{school_id}/term-dates", response_model=list[TermDateResponse])
async def get_school_term_dates(
    school_id: int,
    repo: Annotated[object, Depends(get_school_repository)],
) -> list[TermDateResponse]:
    """Get term dates for a school."""
    term_dates = await repo.get_term_dates(school_id)
    return term_dates


@router.get("/api/schools/{school_id}/admissions", response_model=list[AdmissionsHistoryResponse])
async def get_school_admissions(
    school_id: int,
    repo: Annotated[object, Depends(get_school_repository)],
) -> list[AdmissionsHistoryResponse]:
    """Get historical admissions data for waiting-list estimation."""
    admissions = await repo.get_admissions(school_id)
    return admissions
