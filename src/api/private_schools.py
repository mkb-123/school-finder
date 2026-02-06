from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.db.base import SchoolFilters, SchoolRepository
from src.db.factory import get_school_repository
from src.schemas.filters import PrivateSchoolFilterParams
from src.schemas.school import SchoolDetailResponse, SchoolResponse

router = APIRouter(tags=["private-schools"])


def _to_private_filters(params: PrivateSchoolFilterParams) -> SchoolFilters:
    """Convert private school API filter params to the repository's filter dataclass."""
    return SchoolFilters(
        council=params.council,
        age=params.age,
        gender=params.gender,
        is_private=True,
        max_fee=params.max_fee,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/api/private-schools", response_model=list[SchoolResponse])
async def list_private_schools(
    filters: Annotated[PrivateSchoolFilterParams, Query()],
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[SchoolResponse]:
    """List private/independent schools with optional filters."""
    school_filters = _to_private_filters(filters)
    schools = await repo.find_schools_by_filters(school_filters)
    return schools


@router.get("/api/private-schools/{school_id}", response_model=SchoolDetailResponse)
async def get_private_school(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> SchoolDetailResponse:
    """Get full details for a private school."""
    school = await repo.get_school_by_id(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    if not school.is_private:
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
