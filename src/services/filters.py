"""Filter application logic for school search queries.

Translates a ``SchoolFilters`` parameter object into a list of SQLAlchemy
filter clauses that can be appended to a query against the ``schools`` table.

The filter types handled are:
  * council
  * age range overlap (school's age range covers the child's age)
  * gender compatibility
  * school type (state / academy / free school / faith school)
  * minimum Ofsted rating
  * maximum distance from a reference point
  * breakfast club availability
  * after-school club availability
  * faith / religion
  * private school flag
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import sqlalchemy as sa

if TYPE_CHECKING:
    from sqlalchemy.sql import ColumnElement


# ---------------------------------------------------------------------------
# SchoolFilters dataclass
# ---------------------------------------------------------------------------


@dataclass
class SchoolFilters:
    """Parameters that a user can set to narrow down the school results.

    All fields are optional.  When a field is ``None`` the corresponding
    filter is not applied.
    """

    council: str | None = None
    child_age: int | None = None
    child_gender: str | None = None  # "male", "female", or None
    school_type: str | None = None  # e.g. "state", "academy", "free_school", "faith"
    min_ofsted_rating: int | None = None  # 1 (Outstanding) to 4 (Inadequate)
    max_distance_km: float | None = None
    has_breakfast_club: bool | None = None
    has_afterschool_club: bool | None = None
    faith: str | None = None
    is_private: bool | None = None

    # Reference point for distance filtering (lat/lng of the user's postcode).
    # Required when ``max_distance_km`` is set.
    ref_lat: float | None = None
    ref_lng: float | None = None

    # Extra filters can be passed as raw SQLAlchemy expressions.
    extra: list[ColumnElement] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ofsted rating ordering
# ---------------------------------------------------------------------------
# Ofsted ratings are typically stored as integers:
#   1 = Outstanding
#   2 = Good
#   3 = Requires Improvement
#   4 = Inadequate
# A *lower* number is a *better* rating.  ``min_ofsted_rating`` therefore
# means "at least this good", i.e. the stored value must be <= the threshold.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_filter_clauses(
    filters: SchoolFilters,
    schools_table: sa.Table,
    clubs_table: sa.Table | None = None,
) -> list[ColumnElement]:
    """Build a list of SQLAlchemy filter clauses from *filters*.

    Parameters
    ----------
    filters:
        The user-supplied filter parameters.
    schools_table:
        The SQLAlchemy ``Table`` (or ORM model ``__table__``) for the
        ``schools`` table.  Column names are expected to match the data model
        described in ``CLAUDE.md`` (e.g. ``council``, ``age_range_from``,
        ``age_range_to``, ``gender_policy``, ``type``, ``ofsted_rating``,
        ``faith``, ``is_private``, ``lat``, ``lng``).
    clubs_table:
        Optional SQLAlchemy ``Table`` for ``school_clubs``.  Required when
        ``has_breakfast_club`` or ``has_afterschool_club`` is set; if not
        provided those filters are silently skipped.

    Returns
    -------
    list[ColumnElement]
        A list of SQLAlchemy boolean expressions that can be passed to
        ``query.where(*clauses)`` or ``select(...).where(sa.and_(*clauses))``.
    """
    clauses: list[ColumnElement] = []

    # -- Council --
    if filters.council is not None:
        clauses.append(schools_table.c.council == filters.council)

    # -- Age range overlap --
    # A school is compatible if its age range covers the child's age:
    #   school.age_range_from <= child_age <= school.age_range_to
    if filters.child_age is not None:
        clauses.append(schools_table.c.age_range_from <= filters.child_age)
        clauses.append(schools_table.c.age_range_to >= filters.child_age)

    # -- Gender compatibility --
    # gender_policy values: "co-ed", "boys", "girls"
    # If child is female, exclude "boys only" schools.
    # If child is male, exclude "girls only" schools.
    if filters.child_gender is not None:
        gender = filters.child_gender.lower()
        if gender == "female":
            clauses.append(schools_table.c.gender_policy != "boys")
        elif gender == "male":
            clauses.append(schools_table.c.gender_policy != "girls")

    # -- School type --
    if filters.school_type is not None:
        clauses.append(schools_table.c.type == filters.school_type)

    # -- Minimum Ofsted rating --
    # Lower number = better rating, so we want ofsted_rating <= threshold.
    if filters.min_ofsted_rating is not None:
        clauses.append(schools_table.c.ofsted_rating <= filters.min_ofsted_rating)

    # -- Maximum distance (Haversine) --
    # Uses a SQLite-compatible Haversine approximation via a bounding-box
    # pre-filter plus the custom ``haversine`` SQL function (registered on the
    # SQLite connection elsewhere).
    if filters.max_distance_km is not None and filters.ref_lat is not None and filters.ref_lng is not None:
        # Rough bounding-box pre-filter (1 degree latitude ~ 111 km).
        delta_lat = filters.max_distance_km / 111.0
        # Longitude degrees vary with latitude; use a conservative estimate.
        import math

        delta_lng = filters.max_distance_km / (111.0 * max(math.cos(math.radians(filters.ref_lat)), 0.01))

        clauses.append(schools_table.c.lat >= filters.ref_lat - delta_lat)
        clauses.append(schools_table.c.lat <= filters.ref_lat + delta_lat)
        clauses.append(schools_table.c.lng >= filters.ref_lng - delta_lng)
        clauses.append(schools_table.c.lng <= filters.ref_lng + delta_lng)

        # Precise Haversine filter using the custom SQL function.
        # The function ``haversine(lat1, lng1, lat2, lng2)`` must be registered
        # on the SQLite connection (see ``src/db/sqlite_repo.py``).
        clauses.append(
            sa.func.haversine(
                schools_table.c.lat,
                schools_table.c.lng,
                sa.literal(filters.ref_lat),
                sa.literal(filters.ref_lng),
            )
            <= filters.max_distance_km
        )

    # -- Breakfast club / After-school club --
    if clubs_table is not None:
        if filters.has_breakfast_club is True:
            breakfast_subquery = (
                sa.select(clubs_table.c.school_id)
                .where(clubs_table.c.club_type == "breakfast")
                .correlate(schools_table)
                .exists()
            )
            clauses.append(breakfast_subquery)

        if filters.has_afterschool_club is True:
            afterschool_subquery = (
                sa.select(clubs_table.c.school_id)
                .where(clubs_table.c.club_type == "after_school")
                .correlate(schools_table)
                .exists()
            )
            clauses.append(afterschool_subquery)

    # -- Faith --
    if filters.faith is not None:
        clauses.append(schools_table.c.faith == filters.faith)

    # -- Private school flag --
    if filters.is_private is not None:
        clauses.append(schools_table.c.is_private == filters.is_private)

    # -- Extra raw clauses --
    clauses.extend(filters.extra)

    return clauses
