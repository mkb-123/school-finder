from __future__ import annotations

from pydantic import BaseModel


class SchoolFilterParams(BaseModel):
    """Query parameters for filtering schools."""

    council: str | None = None
    postcode: str | None = None
    lat: float | None = None
    lng: float | None = None
    age: int | None = None
    gender: str | None = None
    type: str | None = None
    min_rating: str | None = None
    max_distance_km: float | None = None
    has_breakfast_club: bool | None = None
    has_afterschool_club: bool | None = None
    has_both_clubs: bool | None = None
    faith: str | None = None
    search: str | None = None
    limit: int | None = None
    offset: int | None = None


class PrivateSchoolFilterParams(BaseModel):
    """Query parameters for filtering private schools."""

    council: str | None = None
    age: int | None = None
    gender: str | None = None
    max_fee: float | None = None
    limit: int | None = None
    offset: int | None = None
