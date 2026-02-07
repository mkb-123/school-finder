from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Async-compatible declarative base for all ORM models."""


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    urn: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # state / academy / free / faith / private
    council: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    postcode: Mapped[str | None] = mapped_column(String(10), nullable=True)

    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    catchment_radius_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    catchment_geometry: Mapped[str | None] = mapped_column(Text, nullable=True)  # WKT polygon (Postgres only)

    gender_policy: Mapped[str | None] = mapped_column(String(20), nullable=True)  # co-ed / boys / girls
    faith: Mapped[str | None] = mapped_column(String(50), nullable=True)
    age_range_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_range_to: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ofsted_rating: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ofsted_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)

    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prospectus_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ethos: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    term_dates: Mapped[list[SchoolTermDate]] = relationship("SchoolTermDate", back_populates="school", lazy="select")
    clubs: Mapped[list[SchoolClub]] = relationship("SchoolClub", back_populates="school", lazy="select")
    holiday_clubs: Mapped[list[HolidayClub]] = relationship("HolidayClub", back_populates="school", lazy="select")
    performance: Mapped[list[SchoolPerformance]] = relationship(
        "SchoolPerformance", back_populates="school", lazy="select"
    )
    reviews: Mapped[list[SchoolReview]] = relationship("SchoolReview", back_populates="school", lazy="select")
    private_details: Mapped[list[PrivateSchoolDetails]] = relationship(
        "PrivateSchoolDetails", back_populates="school", lazy="select"
    )
    admissions_history: Mapped[list[AdmissionsHistory]] = relationship(
        "AdmissionsHistory", back_populates="school", lazy="select"
    )
    class_sizes: Mapped[list[SchoolClassSize]] = relationship("SchoolClassSize", back_populates="school", lazy="select")
    parking_ratings: Mapped[list[ParkingRating]] = relationship("ParkingRating", back_populates="school", lazy="select")
    uniform: Mapped[list[SchoolUniform]] = relationship("SchoolUniform", back_populates="school", lazy="select")
    admissions_criteria: Mapped[list[AdmissionsCriteria]] = relationship(
        "AdmissionsCriteria", back_populates="school", lazy="select"
    )
    absence_policy: Mapped[list[AbsencePolicy]] = relationship("AbsencePolicy", back_populates="school", lazy="select")
    ofsted_history: Mapped[list[OfstedHistory]] = relationship("OfstedHistory", back_populates="school", lazy="select")
    bus_routes: Mapped[list[BusRoute]] = relationship("BusRoute", back_populates="school", lazy="select")

    def __repr__(self) -> str:
        return f"<School(id={self.id}, name={self.name!r}, council={self.council!r})>"


class SchoolTermDate(Base):
    __tablename__ = "school_term_dates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2024/2025"

    term_name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "Autumn 1"
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    half_term_start: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    half_term_end: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="term_dates")

    def __repr__(self) -> str:
        return f"<SchoolTermDate(school_id={self.school_id}, term={self.term_name!r}, year={self.academic_year!r})>"


class SchoolClub(Base):
    __tablename__ = "school_clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    club_type: Mapped[str] = mapped_column(String(20), nullable=False)  # breakfast / after_school
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    days_available: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "Mon,Tue,Wed,Thu,Fri"
    start_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    cost_per_session: Mapped[float | None] = mapped_column(Float, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="clubs")

    def __repr__(self) -> str:
        return f"<SchoolClub(school_id={self.school_id}, name={self.name!r}, type={self.club_type!r})>"


class HolidayClub(Base):
    __tablename__ = "holiday_clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_school_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    age_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_to: Mapped[int | None] = mapped_column(Integer, nullable=True)

    start_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)

    cost_per_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_week: Mapped[float | None] = mapped_column(Float, nullable=True)

    available_weeks: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. "Easter, Summer, October half-term"
    booking_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    school: Mapped[School] = relationship("School", back_populates="holiday_clubs")

    def __repr__(self) -> str:
        return f"<HolidayClub(school_id={self.school_id}, provider={self.provider_name!r})>"


class SchoolPerformance(Base):
    __tablename__ = "school_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)  # SATs / GCSE / A-level / Progress8 / etc.
    metric_value: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="performance")

    def __repr__(self) -> str:
        return f"<SchoolPerformance(school_id={self.school_id}, metric={self.metric_type!r}, year={self.year})>"


class SchoolReview(Base):
    __tablename__ = "school_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="reviews")

    def __repr__(self) -> str:
        return f"<SchoolReview(school_id={self.school_id}, source={self.source!r})>"


class PrivateSchoolDetails(Base):
    __tablename__ = "private_school_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    termly_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    fee_age_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fee_increase_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # estimated annual % increase

    school_day_start: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    school_day_end: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)

    provides_transport: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    transport_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    holiday_schedule_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hidden costs breakdown (all costs in GBP per term unless noted)
    lunches_per_term: Mapped[float | None] = mapped_column(Float, nullable=True)
    lunches_compulsory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    trips_per_term: Mapped[float | None] = mapped_column(Float, nullable=True)
    trips_compulsory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    exam_fees_per_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    exam_fees_compulsory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    textbooks_per_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    textbooks_compulsory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    music_tuition_per_term: Mapped[float | None] = mapped_column(Float, nullable=True)
    music_tuition_compulsory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    sports_per_term: Mapped[float | None] = mapped_column(Float, nullable=True)
    sports_compulsory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    uniform_per_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    uniform_compulsory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    registration_fee: Mapped[float | None] = mapped_column(Float, nullable=True)  # one-time
    deposit_fee: Mapped[float | None] = mapped_column(Float, nullable=True)  # one-time, often refundable

    insurance_per_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    insurance_compulsory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    building_fund_per_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    building_fund_compulsory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    hidden_costs_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="private_details")

    def __repr__(self) -> str:
        return f"<PrivateSchoolDetails(school_id={self.school_id})>"


class AdmissionsHistory(Base):
    __tablename__ = "admissions_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)

    places_offered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applications_received: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_distance_offered_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    waiting_list_offers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    appeals_heard: Mapped[int | None] = mapped_column(Integer, nullable=True)
    appeals_upheld: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Allocation profile description (e.g. "All applicants offered up to criterion 6 (distance) up to 1.011 miles")
    allocation_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    had_vacancies: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    intake_year: Mapped[str | None] = mapped_column(String(20), nullable=True)  # e.g. "Year R", "Year 3"
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="admissions_history")

    def __repr__(self) -> str:
        return f"<AdmissionsHistory(school_id={self.school_id}, year={self.academic_year!r})>"


class SchoolClassSize(Base):
    __tablename__ = "school_class_sizes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)

    year_group: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "Reception", "Year 1", "Year 7"
    num_pupils: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_classes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_class_size: Mapped[float | None] = mapped_column(Float, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="class_sizes")

    def __repr__(self) -> str:
        return (
            f"<SchoolClassSize(school_id={self.school_id}, "
            f"year={self.academic_year!r}, year_group={self.year_group!r})>"
        )


class ParkingRating(Base):
    __tablename__ = "parking_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    # Parent-submitted ratings (1-5 scale where 5 is worst/most chaotic)
    dropoff_chaos: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5: drop-off congestion/chaos
    pickup_chaos: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5: pick-up congestion/chaos
    parking_availability: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5: parking difficulty
    road_congestion: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5: surrounding road traffic
    restrictions_hazards: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5: restrictions/hazards

    # Optional text feedback
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    submitted_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    parent_email: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Optional for follow-up

    school: Mapped[School] = relationship("School", back_populates="parking_ratings")

    def __repr__(self) -> str:
        return f"<ParkingRating(school_id={self.school_id}, submitted_at={self.submitted_at})>"


class SchoolUniform(Base):
    __tablename__ = "school_uniforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. "Navy jumper, grey trousers/skirt"
    style: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "Smart casual", "Traditional blazer"
    colors: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g. "Navy blue, grey, white"

    # Supplier requirements
    requires_specific_supplier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier_website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Cost breakdown (all costs in GBP)
    polo_shirts_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    jumper_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    trousers_skirt_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_kit_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    bag_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    coat_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    other_items_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    other_items_description: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. "Tie, blazer, hat"

    # Total cost estimate for full set
    total_cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Affordability indicator
    is_expensive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # True if branded/specific supplier required

    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Additional notes, e.g. "Supermarket alternatives acceptable"

    school: Mapped[School] = relationship("School", back_populates="uniform")

    def __repr__(self) -> str:
        return f"<SchoolUniform(school_id={self.school_id}, total_cost={self.total_cost_estimate})>"


class AdmissionsCriteria(Base):
    __tablename__ = "admissions_criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    # Priority tier (1 = highest priority)
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    # Criterion category (e.g., "Looked-after children", "Siblings", "Distance", "Faith")
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    # Human-readable description of this criterion
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # For faith schools: required level of religious practice (e.g., "Weekly attendance", "Baptism certificate")
    religious_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Whether this criterion requires supplementary information form (SIF)
    requires_sif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Additional notes or clarifications
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="admissions_criteria")

    def __repr__(self) -> str:
        return (
            f"<AdmissionsCriteria(school_id={self.school_id}, rank={self.priority_rank}, category={self.category!r})>"
        )


class AbsencePolicy(Base):
    __tablename__ = "absence_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    # Strictness level: "strict", "moderate", "lenient"
    strictness_level: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Fining policy
    issues_fines: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fining_threshold_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Days before fines issued
    fine_amount: Mapped[float | None] = mapped_column(Float, nullable=True)  # Fine amount in GBP per parent

    # Term-time holiday policy
    term_time_holiday_policy: Mapped[str | None] = mapped_column(Text, nullable=True)  # Policy text/description
    authorises_holidays: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # Ever authorises holidays

    # DfE official unauthorised absence rate (percentage)
    unauthorised_absence_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Overall absence rate (percentage)
    overall_absence_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Additional policy notes
    policy_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Full policy text or key excerpts
    exceptional_circumstances: Mapped[str | None] = mapped_column(Text, nullable=True)  # What counts as exceptional

    # Data source and year
    data_year: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Academic year e.g. "2023/2024"
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="absence_policy")

    def __repr__(self) -> str:
        return f"<AbsencePolicy(school_id={self.school_id}, strictness={self.strictness_level})>"


class OfstedHistory(Base):
    __tablename__ = "ofsted_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    inspection_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    rating: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # Outstanding / Good / Requires Improvement / Inadequate

    # Key quotes from report
    strengths_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvements_quote: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Report URL
    report_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Flag for current inspection
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    school: Mapped[School] = relationship("School", back_populates="ofsted_history")

    def __repr__(self) -> str:
        return f"<OfstedHistory(school_id={self.school_id}, date={self.inspection_date}, rating={self.rating!r})>"


class BusRoute(Base):
    __tablename__ = "bus_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    route_name: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "Route A", "North Route"
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Council or private operator
    route_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "dedicated" / "private_coach"

    # Eligibility criteria
    distance_eligibility_km: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # e.g. 2.0 for primary, 3.0 for secondary
    year_groups_eligible: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # e.g. "Year 7-11" or "Reception-Year 6"
    eligibility_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Additional criteria (SEN, low income, etc.)

    # Cost information
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost_per_term: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. "Free for pupils 3+ miles from school"

    # Schedule
    operates_days: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "Mon-Fri"
    morning_departure_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    afternoon_departure_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)

    # Additional info
    booking_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    school: Mapped[School] = relationship("School", back_populates="bus_routes")
    stops: Mapped[list[BusStop]] = relationship(
        "BusStop", back_populates="route", lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BusRoute(id={self.id}, school_id={self.school_id}, route_name={self.route_name!r})>"


class BusStop(Base):
    __tablename__ = "bus_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(Integer, ForeignKey("bus_routes.id"), nullable=False, index=True)

    stop_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stop_location: Mapped[str | None] = mapped_column(Text, nullable=True)  # Address or description
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Pick-up times
    morning_pickup_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    afternoon_dropoff_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)

    # Sequence order in route
    stop_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    route: Mapped[BusRoute] = relationship("BusRoute", back_populates="stops")

    def __repr__(self) -> str:
        return f"<BusStop(id={self.id}, route_id={self.route_id}, stop_name={self.stop_name!r})>"
