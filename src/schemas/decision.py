"""Pydantic schemas for the decision support API endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class SchoolScoreComponentResponse(BaseModel):
    """Individual dimension scores for a school."""

    distance: float
    ofsted: float
    clubs: float
    fees: float
    ofsted_trajectory: float
    attendance: float
    class_size: float
    parking: float
    holiday_club: float
    uniform: float
    diversity: float
    sibling_priority: float
    school_run_ease: float
    homework: float


class ScoredSchoolResponse(BaseModel):
    """A school with its composite score and component breakdown."""

    school_id: int
    school_name: str
    composite_score: float
    component_scores: SchoolScoreComponentResponse
    ofsted_rating: str | None = None
    distance_km: float | None = None
    is_private: bool = False
    has_breakfast_club: bool = False
    has_afterschool_club: bool = False
    annual_fee: float | None = None
    postcode: str | None = None
    school_type: str | None = None
    faith: str | None = None
    age_range_from: int | None = None
    age_range_to: int | None = None
    gender_policy: str | None = None


class DecisionScoreResponse(BaseModel):
    """Response for the scoring endpoint: ranked list of schools."""

    schools: list[ScoredSchoolResponse]
    weights_used: dict[str, float]


class ProsConsResponse(BaseModel):
    """Auto-generated pros and cons for a school."""

    school_id: int
    school_name: str
    pros: list[str]
    cons: list[str]


class WhatIfRequest(BaseModel):
    """Parameters for a 'what if' scenario re-ranking."""

    school_ids: list[int]
    weights: dict[str, float] | None = None
    max_distance_km: float | None = None
    min_rating: str | None = None
    include_faith: bool | None = None
    max_annual_fee: float | None = None
    lat: float | None = None
    lng: float | None = None


class WhatIfResponse(BaseModel):
    """Response after applying 'what if' constraints and re-ranking."""

    schools: list[ScoredSchoolResponse]
    weights_used: dict[str, float]
    filters_applied: dict[str, str | float | bool | None]
