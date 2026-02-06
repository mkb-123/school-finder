from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text, Time
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

    # Relationships
    term_dates: Mapped[list[SchoolTermDate]] = relationship("SchoolTermDate", back_populates="school", lazy="select")
    clubs: Mapped[list[SchoolClub]] = relationship("SchoolClub", back_populates="school", lazy="select")
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

    school: Mapped[School] = relationship("School", back_populates="admissions_history")

    def __repr__(self) -> str:
        return f"<AdmissionsHistory(school_id={self.school_id}, year={self.academic_year!r})>"
