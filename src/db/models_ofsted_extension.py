# Temporary file for new models - to be merged into models.py

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base, School


class OfstedHistory(Base):
    __tablename__ = "ofsted_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    # Inspection details
    inspection_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    rating: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # Outstanding / Good / Requires Improvement / Inadequate
    report_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Key quotes from report
    strengths_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvements_quote: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Flags
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # True for the most recent inspection

    school: Mapped[School] = relationship("School", back_populates="ofsted_history")

    def __repr__(self) -> str:
        return f"<OfstedHistory(school_id={self.school_id}, date={self.inspection_date}, rating={self.rating!r})>"


class AbsencePolicy(Base):
    __tablename__ = "absence_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    # Policy details
    fines_issued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fine_threshold_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Days before fining
    term_time_holiday_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    unauthorised_absence_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # Percentage

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="absence_policy")

    def __repr__(self) -> str:
        return f"<AbsencePolicy(school_id={self.school_id}, fines={self.fines_issued})>"


class BusRoute(Base):
    __tablename__ = "bus_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    # Route details
    route_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost_per_term: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Eligibility
    min_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    year_groups: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g., "Year 7-11"

    # Stop locations (simplified as comma-separated postcodes or area names)
    stops: Mapped[str | None] = mapped_column(Text, nullable=True)
    pickup_times: Mapped[str | None] = mapped_column(Text, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    school: Mapped[School] = relationship("School", back_populates="bus_routes")

    def __repr__(self) -> str:
        return f"<BusRoute(school_id={self.school_id}, route={self.route_name!r})>"
