from __future__ import annotations

import math
from typing import Any

from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from src.db.base import SchoolFilters, SchoolRepository
from src.db.models import (
    AdmissionsCriteria,
    AdmissionsHistory,
    Base,
    BusRoute,
    BusStop,
    HolidayClub,
    ParkingRating,
    PrivateSchoolDetails,
    School,
    SchoolClassSize,
    SchoolClub,
    SchoolPerformance,
    SchoolTermDate,
    SchoolUniform,
)

# ---------------------------------------------------------------------------
# Haversine implementation registered as a SQLite custom function
# ---------------------------------------------------------------------------


def _haversine(lat1: float | None, lng1: float | None, lat2: float | None, lng2: float | None) -> float | None:
    """Return great-circle distance in km between two lat/lng pairs.

    Returns None if any coordinate is None (SQL NULL).
    """
    if lat1 is None or lng1 is None or lat2 is None or lng2 is None:
        return None

    earth_radius_km = 6371.0
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _register_haversine(dbapi_connection: Any, _connection_record: Any) -> None:
    """Register the ``haversine`` function on every raw SQLite connection."""
    dbapi_connection.create_function("haversine", 4, _haversine)


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class SQLiteSchoolRepository(SchoolRepository):
    """SQLite-backed implementation of :class:`SchoolRepository`.

    Uses *aiosqlite* via SQLAlchemy's async engine.  A custom ``haversine``
    scalar function is registered on each connection so that spatial distance
    calculations can be performed entirely inside SQL.
    """

    def __init__(self, sqlite_path: str = "./data/schools.db") -> None:
        url = f"sqlite+aiosqlite:///{sqlite_path}"
        self._engine = create_async_engine(url, echo=False)
        # Register the haversine function on every new raw DBAPI connection.
        event.listen(self._engine.sync_engine, "connect", _register_haversine)
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    @property
    def engine(self) -> AsyncEngine:
        """Expose the underlying async engine (used by the application lifespan)."""
        return self._engine

    async def init_db(self) -> None:
        """Create all tables if they do not already exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ------------------------------------------------------------------
    # Catchment / spatial
    # ------------------------------------------------------------------

    async def find_schools_by_filters(self, filters: SchoolFilters) -> list[School]:  # noqa: C901
        stmt = select(School)

        if filters.council is not None:
            stmt = stmt.where(School.council == filters.council)

        if filters.is_private is not None:
            stmt = stmt.where(School.is_private == filters.is_private)

        if filters.school_type is not None:
            stmt = stmt.where(School.type == filters.school_type)

        if filters.faith is not None:
            stmt = stmt.where(School.faith == filters.faith)

        if filters.gender is not None:
            # Exclude schools whose gender_policy is incompatible
            if filters.gender == "male":
                stmt = stmt.where(School.gender_policy.in_(["co-ed", "boys"]))
            elif filters.gender == "female":
                stmt = stmt.where(School.gender_policy.in_(["co-ed", "girls"]))

        if filters.age is not None:
            stmt = stmt.where(School.age_range_from <= filters.age).where(School.age_range_to >= filters.age)

        acceptable_ratings = filters.min_rating_values()
        if acceptable_ratings is not None:
            stmt = stmt.where(School.ofsted_rating.in_(acceptable_ratings))

        # Distance filter requires a reference point
        if filters.max_distance_km is not None and filters.lat is not None and filters.lng is not None:
            stmt = (
                stmt.where(School.lat.is_not(None))
                .where(School.lng.is_not(None))
                .where(text("haversine(schools.lat, schools.lng, :lat, :lng) <= :max_dist"))
            )

        # Club-based filters: use EXISTS sub-queries
        if filters.has_breakfast_club is True:
            stmt = stmt.where(
                select(SchoolClub.id)
                .where(SchoolClub.school_id == School.id)
                .where(SchoolClub.club_type == "breakfast")
                .correlate(School)
                .exists()
            )

        if filters.has_afterschool_club is True:
            stmt = stmt.where(
                select(SchoolClub.id)
                .where(SchoolClub.school_id == School.id)
                .where(SchoolClub.club_type == "after_school")
                .correlate(School)
                .exists()
            )

        # Max fee filter: join to private_school_details
        if filters.max_fee is not None:
            stmt = stmt.where(
                select(PrivateSchoolDetails.id)
                .where(PrivateSchoolDetails.school_id == School.id)
                .where(PrivateSchoolDetails.termly_fee <= filters.max_fee)
                .correlate(School)
                .exists()
            )

        # Name-based search filter
        if filters.search is not None:
            stmt = stmt.where(School.name.ilike(f"%{filters.search}%"))

        # Bounding-box pre-filter: cheap lat/lng rectangle before expensive haversine
        if filters.lat is not None and filters.lng is not None and filters.max_distance_km is not None:
            delta_lat = filters.max_distance_km / 111.0  # ~111 km per degree latitude
            delta_lng = filters.max_distance_km / (111.0 * math.cos(math.radians(filters.lat)))
            stmt = (
                stmt.where(School.lat >= filters.lat - delta_lat)
                .where(School.lat <= filters.lat + delta_lat)
                .where(School.lng >= filters.lng - delta_lng)
                .where(School.lng <= filters.lng + delta_lng)
            )

        params: dict[str, Any] = {}
        if filters.lat is not None:
            params["lat"] = filters.lat
        if filters.lng is not None:
            params["lng"] = filters.lng
        if filters.max_distance_km is not None:
            params["max_dist"] = filters.max_distance_km

        # Sort by nearest when a reference point is provided, otherwise by name
        if filters.lat is not None and filters.lng is not None:
            stmt = stmt.order_by(text("haversine(schools.lat, schools.lng, :lat, :lng)"))
        else:
            stmt = stmt.order_by(School.name)

        # Pagination
        if filters.offset is not None:
            stmt = stmt.offset(filters.offset)
        if filters.limit is not None:
            stmt = stmt.limit(filters.limit)

        async with self._session_factory() as session:
            result = await session.execute(stmt, params)
            return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Single-school lookups
    # ------------------------------------------------------------------

    async def get_school_by_id(self, school_id: int) -> School | None:
        stmt = (
            select(School)
            .where(School.id == school_id)
            .options(
                selectinload(School.term_dates),
                selectinload(School.clubs),
                selectinload(School.performance),
                selectinload(School.reviews),
                selectinload(School.private_details),
                selectinload(School.admissions_history),
            )
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return result.scalars().first()

    async def get_clubs_for_school(self, school_id: int) -> list[SchoolClub]:
        stmt = select(SchoolClub).where(SchoolClub.school_id == school_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_holiday_clubs_for_school(self, school_id: int) -> list[HolidayClub]:
        stmt = select(HolidayClub).where(HolidayClub.school_id == school_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_performance_for_school(self, school_id: int) -> list[SchoolPerformance]:
        stmt = select(SchoolPerformance).where(SchoolPerformance.school_id == school_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_term_dates_for_school(self, school_id: int) -> list[SchoolTermDate]:
        stmt = select(SchoolTermDate).where(SchoolTermDate.school_id == school_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_admissions_history(self, school_id: int) -> list[AdmissionsHistory]:
        stmt = select(AdmissionsHistory).where(AdmissionsHistory.school_id == school_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_private_school_details(self, school_id: int) -> list[PrivateSchoolDetails]:
        stmt = select(PrivateSchoolDetails).where(PrivateSchoolDetails.school_id == school_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_class_sizes(self, school_id: int) -> list[SchoolClassSize]:
        stmt = (
            select(SchoolClassSize)
            .where(SchoolClassSize.school_id == school_id)
            .order_by(SchoolClassSize.academic_year.desc(), SchoolClassSize.year_group)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_uniform_for_school(self, school_id: int) -> list[SchoolUniform]:
        stmt = select(SchoolUniform).where(SchoolUniform.school_id == school_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_admissions_criteria_for_school(self, school_id: int) -> list[AdmissionsCriteria]:
        stmt = (
            select(AdmissionsCriteria)
            .where(AdmissionsCriteria.school_id == school_id)
            .order_by(AdmissionsCriteria.priority_rank)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_ofsted_history(self, school_id: int) -> list:
        """Return Ofsted inspection history for a school, ordered by date descending."""
        from src.db.models import OfstedHistory

        stmt = (
            select(OfstedHistory)
            .where(OfstedHistory.school_id == school_id)
            .order_by(OfstedHistory.inspection_date.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------

    async def list_councils(self) -> list[str]:
        stmt = select(School.council).distinct().order_by(School.council)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Parking ratings
    # ------------------------------------------------------------------

    async def get_parking_ratings_for_school(self, school_id: int) -> list[ParkingRating]:
        stmt = (
            select(ParkingRating)
            .where(ParkingRating.school_id == school_id)
            .order_by(ParkingRating.submitted_at.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_parking_rating(self, rating: ParkingRating) -> ParkingRating:
        async with self._session_factory() as session:
            session.add(rating)
            await session.commit()
            await session.refresh(rating)
            return rating

    # ------------------------------------------------------------------
    # Bus routes
    # ------------------------------------------------------------------

    async def get_bus_routes_for_school(self, school_id: int) -> list[BusRoute]:
        stmt = select(BusRoute).where(BusRoute.school_id == school_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_bus_stops_for_route(self, route_id: int) -> list[BusStop]:
        stmt = select(BusStop).where(BusStop.route_id == route_id).order_by(BusStop.stop_order)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def find_nearby_bus_stops(
        self, lat: float, lng: float, max_distance_km: float = 0.5
    ) -> list[tuple[BusStop, BusRoute, School, float]]:
        """Find bus stops within max_distance_km of a location, with route and school info."""
        # Join BusStop -> BusRoute -> School and calculate distance
        stmt = (
            select(BusStop, BusRoute, School, text("haversine(bus_stops.lat, bus_stops.lng, :lat, :lng) AS distance"))
            .join(BusRoute, BusStop.route_id == BusRoute.id)
            .join(School, BusRoute.school_id == School.id)
            .where(BusStop.lat.is_not(None))
            .where(BusStop.lng.is_not(None))
            .where(text("haversine(bus_stops.lat, bus_stops.lng, :lat, :lng) <= :max_dist"))
            .order_by(text("distance"))
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt, {"lat": lat, "lng": lng, "max_dist": max_distance_km})
            rows = result.all()
            return [(row[0], row[1], row[2], row[3]) for row in rows]
