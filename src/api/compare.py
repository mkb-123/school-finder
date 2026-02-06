from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.schemas.school import CompareResponse, SchoolDetailResponse, SchoolResponse

router = APIRouter(tags=["compare"])


@router.get("/api/compare", response_model=CompareResponse)
async def compare_schools(
    ids: Annotated[str, Query(description="Comma-separated school IDs to compare")],
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> CompareResponse:
    """Compare multiple schools side by side."""
    school_ids = [int(id_str.strip()) for id_str in ids.split(",") if id_str.strip()]

    details: list[SchoolDetailResponse] = []
    for school_id in school_ids:
        school = await repo.get_school_by_id(school_id)
        if school is None:
            continue

        clubs = await repo.get_clubs_for_school(school_id)
        performance = await repo.get_performance_for_school(school_id)
        term_dates = await repo.get_term_dates_for_school(school_id)
        admissions = await repo.get_admissions_history(school_id)
        private_details = await repo.get_private_school_details(school_id)

        base = SchoolResponse.model_validate(school, from_attributes=True)
        details.append(
            SchoolDetailResponse(
                **base.model_dump(),
                clubs=clubs,
                performance=performance,
                term_dates=term_dates,
                admissions_history=admissions,
                private_details=private_details,
            )
        )

    return CompareResponse(schools=details)
