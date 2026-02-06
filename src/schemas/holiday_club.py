from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict


class HolidayClubResponse(BaseModel):
    """A holiday club available at or near a school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    provider_name: str
    is_school_run: bool
    description: str | None = None
    age_from: int | None = None
    age_to: int | None = None
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    cost_per_day: float | None = None
    cost_per_week: float | None = None
    available_weeks: str | None = None
    booking_url: str | None = None
