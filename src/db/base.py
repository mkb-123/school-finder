from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.db.models import (
    AdmissionsHistory,
    PrivateSchoolDetails,
    School,
    SchoolClub,
    SchoolPerformance,
    SchoolTermDate,
)


@dataclass
class SchoolFilters:
    """Filter criteria for searching schools."""

    council: str | None = None
    lat: float | None = None
    lng: float | None = None
    age: int | None = None
    gender: str | None = None  # "male" / "female" / "other"
    school_type: str | None = None  # state / academy / free / faith / private
    min_rating: str | None = None  # Outstanding / Good / Requires Improvement / Inadequate
    max_distance_km: float | None = None
    has_breakfast_club: bool | None = None
    has_afterschool_club: bool | None = None
    faith: str | None = None
    is_private: bool | None = None
    max_fee: float | None = None  # max termly fee for private school filtering
    search: str | None = None  # name-based search (case-insensitive substring)

    # Internal: ordered list of Ofsted ratings from best to worst, used by repositories
    _rating_order: list[str] = field(
        default_factory=lambda: ["Outstanding", "Good", "Requires Improvement", "Inadequate"],
        init=False,
        repr=False,
    )

    def min_rating_values(self) -> list[str] | None:
        """Return the list of acceptable ratings at or above *min_rating*."""
        if self.min_rating is None:
            return None
        try:
            idx = self._rating_order.index(self.min_rating)
        except ValueError:
            return None
        return self._rating_order[: idx + 1]


class SchoolRepository(ABC):
    """Abstract interface for all school data access."""

    # ------------------------------------------------------------------
    # Catchment / spatial
    # ------------------------------------------------------------------

    @abstractmethod
    async def find_schools_in_catchment(self, lat: float, lng: float, council: str) -> list[School]:
        """Return schools whose catchment area covers the given point within a council."""
        ...

    @abstractmethod
    async def find_schools_by_filters(self, filters: SchoolFilters) -> list[School]:
        """Return schools matching the supplied filter criteria."""
        ...

    # ------------------------------------------------------------------
    # Single-school lookups
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_school_by_id(self, school_id: int) -> School | None:
        """Return a single school by primary key, or ``None`` if not found."""
        ...

    @abstractmethod
    async def get_clubs_for_school(self, school_id: int) -> list[SchoolClub]:
        """Return all clubs (breakfast / after-school) for a school."""
        ...

    @abstractmethod
    async def get_performance_for_school(self, school_id: int) -> list[SchoolPerformance]:
        """Return academic performance metrics for a school."""
        ...

    @abstractmethod
    async def get_term_dates_for_school(self, school_id: int) -> list[SchoolTermDate]:
        """Return term date records for a school."""
        ...

    @abstractmethod
    async def get_admissions_history(self, school_id: int) -> list[AdmissionsHistory]:
        """Return historical admissions data for a school."""
        ...

    @abstractmethod
    async def get_private_school_details(self, school_id: int) -> list[PrivateSchoolDetails]:
        """Return private-school-specific details (one entry per fee age group)."""
        ...

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------

    @abstractmethod
    async def list_councils(self) -> list[str]:
        """Return a sorted list of distinct council names present in the database."""
        ...
