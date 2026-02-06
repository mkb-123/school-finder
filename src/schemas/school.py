from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict


class ClubResponse(BaseModel):
    """A breakfast or after-school club offered by a school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    club_type: str
    name: str
    description: str | None = None
    days_available: str | None = None
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    cost_per_session: float | None = None


class PerformanceResponse(BaseModel):
    """Academic performance metric for a school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    metric_type: str
    metric_value: str
    year: int
    source_url: str | None = None


class TermDateResponse(BaseModel):
    """Term date entry for a school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    academic_year: str
    term_name: str
    start_date: datetime.date
    end_date: datetime.date
    half_term_start: datetime.date | None = None
    half_term_end: datetime.date | None = None


class ReviewResponse(BaseModel):
    """Parent or external review for a school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    source: str
    rating: float | None = None
    snippet: str | None = None
    review_date: datetime.date | None = None


class PrivateSchoolDetailsResponse(BaseModel):
    """Additional details specific to private/independent schools."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    termly_fee: float | None = None
    annual_fee: float | None = None
    fee_age_group: str | None = None
    fee_increase_pct: float | None = None
    school_day_start: datetime.time | None = None
    school_day_end: datetime.time | None = None
    provides_transport: bool | None = None
    transport_notes: str | None = None
    holiday_schedule_notes: str | None = None


class AdmissionsHistoryResponse(BaseModel):
    """Historical admissions data for waiting-list estimation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    academic_year: str
    places_offered: int | None = None
    applications_received: int | None = None
    last_distance_offered_km: float | None = None
    waiting_list_offers: int | None = None
    appeals_heard: int | None = None
    appeals_upheld: int | None = None


class SchoolResponse(BaseModel):
    """Summary representation of a school for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    urn: str | None = None
    type: str | None = None
    council: str | None = None
    address: str | None = None
    postcode: str | None = None
    lat: float | None = None
    lng: float | None = None
    distance_km: float | None = None
    gender_policy: str | None = None
    faith: str | None = None
    age_range_from: int | None = None
    age_range_to: int | None = None
    ofsted_rating: str | None = None
    ofsted_date: datetime.date | None = None
    is_private: bool = False
    catchment_radius_km: float | None = None


class SchoolDetailResponse(SchoolResponse):
    """Full school detail including related data."""

    clubs: list[ClubResponse] = []
    performance: list[PerformanceResponse] = []
    term_dates: list[TermDateResponse] = []
    admissions_history: list[AdmissionsHistoryResponse] = []
    private_details: list[PrivateSchoolDetailsResponse] = []


class CompareResponse(BaseModel):
    """Response for side-by-side school comparison."""

    schools: list[SchoolDetailResponse]


class AdmissionsEstimateResponse(BaseModel):
    """Admissions likelihood estimate with supporting data."""

    likelihood: str
    trend: str
    avg_last_distance_km: float | None = None
    min_last_distance_km: float | None = None
    max_last_distance_km: float | None = None
    latest_last_distance_km: float | None = None
    avg_oversubscription_ratio: float | None = None
    years_of_data: int = 0


class GeocodeResponse(BaseModel):
    """Geocoding result from postcode lookup."""

    postcode: str
    lat: float
    lng: float
