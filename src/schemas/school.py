from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict

from src.schemas.holiday_club import HolidayClubResponse


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

    # Hidden costs breakdown
    lunches_per_term: float | None = None
    lunches_compulsory: bool = False
    trips_per_term: float | None = None
    trips_compulsory: bool = False
    exam_fees_per_year: float | None = None
    exam_fees_compulsory: bool = True
    textbooks_per_year: float | None = None
    textbooks_compulsory: bool = True
    music_tuition_per_term: float | None = None
    music_tuition_compulsory: bool = False
    sports_per_term: float | None = None
    sports_compulsory: bool = False
    uniform_per_year: float | None = None
    uniform_compulsory: bool = True
    registration_fee: float | None = None
    deposit_fee: float | None = None
    insurance_per_year: float | None = None
    insurance_compulsory: bool = False
    building_fund_per_year: float | None = None
    building_fund_compulsory: bool = False
    hidden_costs_notes: str | None = None


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
    allocation_description: str | None = None
    had_vacancies: bool | None = None
    intake_year: str | None = None
    source_url: str | None = None


class ClassSizeResponse(BaseModel):
    """Historical class size data for a year group."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    academic_year: str
    year_group: str
    num_pupils: int | None = None
    num_classes: int | None = None
    avg_class_size: float | None = None


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
    website: str | None = None
    prospectus_url: str | None = None
    ethos: str | None = None


class SchoolDetailResponse(SchoolResponse):
    """Full school detail including related data."""

    clubs: list[ClubResponse] = []
    holiday_clubs: list[HolidayClubResponse] = []
    performance: list[PerformanceResponse] = []
    term_dates: list[TermDateResponse] = []
    admissions_history: list[AdmissionsHistoryResponse] = []
    admissions_criteria: list[AdmissionsCriteriaResponse] = []
    private_details: list[PrivateSchoolDetailsResponse] = []
    class_sizes: list[ClassSizeResponse] = []
    parking_summary: ParkingRatingSummary | None = None
    uniform: list[UniformResponse] = []
    absence_policy: list[AbsencePolicyResponse] = []
    ofsted_trajectory: OfstedTrajectoryResponse | None = None
    bursaries: list[BursaryResponse] = []
    scholarships: list[ScholarshipResponse] = []
    entry_assessments: list[EntryAssessmentResponse] = []
    open_days: list[OpenDayResponse] = []
    sibling_discounts: list[SiblingDiscountResponse] = []
    curricula: list[CurriculumResponse] = []
    facilities: list[FacilityResponse] = []
    isi_inspections: list[ISIInspectionResponse] = []
    private_results: list[PrivateSchoolResultsResponse] = []


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


class AdmissionsCriteriaResponse(BaseModel):
    """Admissions criteria priority tier breakdown."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    priority_rank: int
    category: str
    description: str
    religious_requirement: str | None = None
    requires_sif: bool = False
    notes: str | None = None


class GeocodeResponse(BaseModel):
    """Geocoding result from postcode lookup."""

    postcode: str
    lat: float
    lng: float


class UniformResponse(BaseModel):
    """School uniform information including costs and supplier requirements."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    description: str | None = None
    style: str | None = None
    colors: str | None = None
    requires_specific_supplier: bool = False
    supplier_name: str | None = None
    supplier_website: str | None = None
    polo_shirts_cost: float | None = None
    jumper_cost: float | None = None
    trousers_skirt_cost: float | None = None
    pe_kit_cost: float | None = None
    bag_cost: float | None = None
    coat_cost: float | None = None
    other_items_cost: float | None = None
    other_items_description: str | None = None
    total_cost_estimate: float | None = None
    is_expensive: bool = False
    notes: str | None = None


class ParkingRatingResponse(BaseModel):
    """Parent-submitted parking chaos rating."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    dropoff_chaos: int | None = None
    pickup_chaos: int | None = None
    parking_availability: int | None = None
    road_congestion: int | None = None
    restrictions_hazards: int | None = None
    comments: str | None = None
    submitted_at: datetime.datetime
    parent_email: str | None = None


class ParkingRatingSubmitRequest(BaseModel):
    """Request body for submitting a parking rating."""

    school_id: int
    dropoff_chaos: int | None = None
    pickup_chaos: int | None = None
    parking_availability: int | None = None
    road_congestion: int | None = None
    restrictions_hazards: int | None = None
    comments: str | None = None
    parent_email: str | None = None


class ParkingRatingSummary(BaseModel):
    """Aggregated parking rating statistics for a school."""

    school_id: int
    total_ratings: int
    avg_dropoff_chaos: float | None = None
    avg_pickup_chaos: float | None = None
    avg_parking_availability: float | None = None
    avg_road_congestion: float | None = None
    avg_restrictions_hazards: float | None = None
    overall_chaos_score: float | None = None  # Average of all rating dimensions


class HiddenCostItem(BaseModel):
    """Individual hidden cost item with amount and compulsory flag."""

    name: str
    amount: float
    frequency: str  # "per term", "per year", "one-time"
    compulsory: bool


class TrueAnnualCostResponse(BaseModel):
    """True annual cost breakdown for a private school including all hidden costs."""

    school_id: int
    school_name: str
    fee_age_group: str | None = None

    # Headline costs
    termly_fee: float | None = None
    annual_fee: float | None = None

    # Breakdown of hidden costs
    hidden_cost_items: list[HiddenCostItem] = []

    # Calculated totals
    compulsory_hidden_costs_per_year: float = 0.0
    optional_hidden_costs_per_year: float = 0.0
    one_time_costs: float = 0.0

    # True annual cost (headline + compulsory extras)
    true_annual_cost: float = 0.0

    # Total if all optional extras are included
    total_with_optional: float = 0.0

    notes: str | None = None


class BursaryResponse(BaseModel):
    """Means-tested financial assistance offered by a private school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    max_percentage: int | None = None
    min_percentage: int | None = None
    income_threshold: float | None = None
    eligibility_notes: str | None = None
    application_deadline: datetime.date | None = None
    application_url: str | None = None
    percentage_of_pupils: float | None = None
    notes: str | None = None
    source_url: str | None = None


class ScholarshipResponse(BaseModel):
    """Merit-based financial award offered by a private school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    scholarship_type: str
    value_description: str | None = None
    value_percentage: int | None = None
    entry_points: str | None = None
    assessment_method: str | None = None
    application_deadline: datetime.date | None = None
    notes: str | None = None
    source_url: str | None = None


class EntryAssessmentResponse(BaseModel):
    """Entry assessment details for a specific age entry point."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    entry_point: str
    assessment_type: str | None = None
    subjects_tested: str | None = None
    registration_deadline: datetime.date | None = None
    assessment_date: datetime.date | None = None
    offer_date: datetime.date | None = None
    registration_fee: float | None = None
    notes: str | None = None
    source_url: str | None = None


class OpenDayResponse(BaseModel):
    """Upcoming open day or taster day event."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    event_date: datetime.date
    event_time: str | None = None
    event_type: str
    registration_required: bool = True
    booking_url: str | None = None
    description: str | None = None
    source_url: str | None = None


class SiblingDiscountResponse(BaseModel):
    """Sibling fee discount details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    second_child_percent: float | None = None
    third_child_percent: float | None = None
    fourth_child_percent: float | None = None
    conditions: str | None = None
    stacks_with_bursary: bool | None = None
    notes: str | None = None
    source_url: str | None = None


class CurriculumResponse(BaseModel):
    """Curriculum and qualification offered by a private school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    qualification_type: str
    subjects_offered: str | None = None
    key_stage: str | None = None
    notes: str | None = None
    source_url: str | None = None


class FacilityResponse(BaseModel):
    """Facility available at a private school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    facility_type: str
    name: str
    description: str | None = None
    notes: str | None = None
    source_url: str | None = None


class ISIInspectionResponse(BaseModel):
    """ISI inspection result for a private school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    inspection_date: datetime.date
    overall_rating: str | None = None
    achievement_rating: str | None = None
    personal_development_rating: str | None = None
    compliance_met: bool | None = None
    inspection_type: str | None = None
    report_url: str | None = None
    key_findings: str | None = None
    recommendations: str | None = None
    is_current: bool = False


class PrivateSchoolResultsResponse(BaseModel):
    """Exam results or university destination data for a private school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    result_type: str
    year: str
    metric_name: str
    metric_value: str
    source_url: str | None = None
    notes: str | None = None


class PrivateSchoolFullResponse(BaseModel):
    """Complete private school response with all extended data."""

    school: SchoolResponse
    private_details: list[PrivateSchoolDetailsResponse] = []
    bursaries: list[BursaryResponse] = []
    scholarships: list[ScholarshipResponse] = []
    entry_assessments: list[EntryAssessmentResponse] = []
    open_days: list[OpenDayResponse] = []
    sibling_discounts: list[SiblingDiscountResponse] = []
    curricula: list[CurriculumResponse] = []
    facilities: list[FacilityResponse] = []
    isi_inspections: list[ISIInspectionResponse] = []
    private_results: list[PrivateSchoolResultsResponse] = []


class UpcomingOpenDayEntry(BaseModel):
    """An upcoming open day with school info attached."""

    school_id: int
    school_name: str
    event_date: datetime.date
    event_time: str | None = None
    event_type: str
    registration_required: bool = True
    booking_url: str | None = None
    description: str | None = None


class UpcomingOpenDaysResponse(BaseModel):
    """All upcoming open days across private schools."""

    open_days: list[UpcomingOpenDayEntry]


class PrivateSchoolSummaryEntry(BaseModel):
    """Summary of a private school for discovery endpoints."""

    school_id: int
    school_name: str
    age_range_from: int | None = None
    age_range_to: int | None = None
    gender_policy: str | None = None
    min_termly_fee: float | None = None
    max_termly_fee: float | None = None
    provides_transport: bool | None = None


class ScholarshipSchoolEntry(PrivateSchoolSummaryEntry):
    """A private school with its scholarship offerings."""

    scholarships: list[ScholarshipResponse] = []


class BursarySchoolEntry(PrivateSchoolSummaryEntry):
    """A private school with its bursary offerings."""

    bursaries: list[BursaryResponse] = []


class FeeComparisonEntry(BaseModel):
    """Fee comparison entry for a single school."""

    school_id: int
    school_name: str
    age_range_from: int | None = None
    age_range_to: int | None = None
    gender_policy: str | None = None
    faith: str | None = None
    fee_tiers: list[PrivateSchoolDetailsResponse] = []
    min_termly_fee: float | None = None
    max_termly_fee: float | None = None
    provides_transport: bool | None = None
    has_bursaries: bool = False
    has_scholarships: bool = False


class FeeComparisonResponse(BaseModel):
    """Side-by-side fee comparison across multiple private schools."""

    schools: list[FeeComparisonEntry]


class AbsencePolicyResponse(BaseModel):
    """Term-time absence policy for a school."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    strictness_level: str | None = None
    issues_fines: bool = False
    fining_threshold_days: int | None = None
    fine_amount: float | None = None
    term_time_holiday_policy: str | None = None
    authorises_holidays: bool = False
    unauthorised_absence_rate: float | None = None
    overall_absence_rate: float | None = None
    policy_text: str | None = None
    exceptional_circumstances: str | None = None
    data_year: str | None = None
    source_url: str | None = None


class OfstedHistoryResponse(BaseModel):
    """Ofsted inspection history record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    inspection_date: datetime.date
    rating: str
    report_url: str | None = None
    strengths_quote: str | None = None
    improvements_quote: str | None = None
    is_current: bool = False


class OfstedTrajectoryResponse(BaseModel):
    """Ofsted trajectory analysis with inspection history."""

    school_id: int
    trajectory: str  # "improving", "stable", "declining", "unknown"
    current_rating: str | None = None
    previous_rating: str | None = None
    inspection_age_years: float | None = None
    is_stale: bool = False
    history: list[OfstedHistoryResponse] = []
