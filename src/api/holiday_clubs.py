from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.schemas.holiday_club import HolidayClubResponse

router = APIRouter(tags=["holiday-clubs"])


@router.get("/api/schools/{school_id}/holiday-clubs", response_model=list[HolidayClubResponse])
async def get_school_holiday_clubs(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[HolidayClubResponse]:
    """Get holiday clubs available for a school during school breaks."""
    holiday_clubs = await repo.get_holiday_clubs_for_school(school_id)
    return holiday_clubs
