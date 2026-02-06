from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.db.factory import get_school_repository
from src.schemas.school import CompareResponse

router = APIRouter(tags=["compare"])


@router.get("/api/compare", response_model=CompareResponse)
async def compare_schools(
    ids: Annotated[str, Query(description="Comma-separated school IDs to compare")],
    repo: Annotated[object, Depends(get_school_repository)],
) -> CompareResponse:
    """Compare multiple schools side by side."""
    school_ids = [int(id_str.strip()) for id_str in ids.split(",") if id_str.strip()]
    schools = await repo.get_schools_by_ids(school_ids)
    return CompareResponse(schools=schools)
