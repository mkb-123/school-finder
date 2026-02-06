from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.db.factory import get_school_repository
from src.schemas.filters import PrivateSchoolFilterParams
from src.schemas.school import SchoolDetailResponse, SchoolResponse

router = APIRouter(tags=["private-schools"])


@router.get("/api/private-schools", response_model=list[SchoolResponse])
async def list_private_schools(
    filters: Annotated[PrivateSchoolFilterParams, Query()],
    repo: Annotated[object, Depends(get_school_repository)],
) -> list[SchoolResponse]:
    """List private/independent schools with optional filters."""
    schools = await repo.find_private_schools(filters)
    return schools


@router.get("/api/private-schools/{school_id}", response_model=SchoolDetailResponse)
async def get_private_school(
    school_id: int,
    repo: Annotated[object, Depends(get_school_repository)],
) -> SchoolDetailResponse:
    """Get full details for a private school."""
    school = await repo.get_school_detail(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    return school
