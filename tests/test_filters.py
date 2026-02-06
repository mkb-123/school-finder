"""Tests for the constraint-based filtering logic in the SQLite repository."""

from __future__ import annotations

import pytest

from src.db.base import SchoolFilters
from src.db.sqlite_repo import SQLiteSchoolRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _school_names(schools) -> set[str]:
    """Extract a set of school names from a list of School ORM objects."""
    return {s.name for s in schools}


# ---------------------------------------------------------------------------
# Single-filter tests
# ---------------------------------------------------------------------------


class TestFilterByCouncil:
    """Filter on *council* should only return schools in that council."""

    @pytest.mark.asyncio
    async def test_milton_keynes_council(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(council="Milton Keynes")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        assert len(schools) == 8
        assert "Bedford Modern School" not in names
        assert "Broughton Fields Primary School" in names

    @pytest.mark.asyncio
    async def test_bedford_council(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(council="Bedford")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        assert len(schools) == 1
        assert "Bedford Modern School" in names

    @pytest.mark.asyncio
    async def test_nonexistent_council_returns_empty(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(council="Narnia")
        schools = await test_repo.find_schools_by_filters(filters)
        assert schools == []


class TestFilterByGender:
    """Gender filter must exclude schools whose *gender_policy* is incompatible."""

    @pytest.mark.asyncio
    async def test_female_excludes_boys_only(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(gender="female")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Boys-only schools excluded (both lowercase and GIAS-style capitalized)
        assert "Bedford Modern School" not in names  # gender_policy="boys"
        assert "MK Boys Grammar" not in names  # gender_policy="Boys"
        # Girls-only should stay
        assert "Thornton College" in names  # gender_policy="girls"
        assert "MK Girls Academy" in names  # gender_policy="Girls"

    @pytest.mark.asyncio
    async def test_male_excludes_girls_only(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(gender="male")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Girls-only schools excluded (both lowercase and GIAS-style capitalized)
        assert "Thornton College" not in names  # gender_policy="girls"
        assert "MK Girls Academy" not in names  # gender_policy="Girls"
        # Boys-only should stay
        assert "Bedford Modern School" in names  # gender_policy="boys"
        assert "MK Boys Grammar" in names  # gender_policy="Boys"

    @pytest.mark.asyncio
    async def test_coed_schools_always_included(self, test_repo: SQLiteSchoolRepository):
        """Co-ed schools must appear regardless of gender filter, whether stored as 'co-ed' or 'Mixed'."""
        for gender in ("male", "female"):
            filters = SchoolFilters(gender=gender)
            schools = await test_repo.find_schools_by_filters(filters)
            names = _school_names(schools)
            assert "Broughton Fields Primary School" in names  # gender_policy="co-ed"
            assert "Walton High School" in names  # gender_policy="co-ed"
            assert "Shenley Brook End School" in names  # gender_policy="Mixed" (GIAS style)


class TestFilterByAge:
    """Age filter must restrict to schools whose age range covers the child's age."""

    @pytest.mark.asyncio
    async def test_age_5_includes_primary(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(age=5)
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Primary/prep schools that accept 5-year-olds
        assert "Broughton Fields Primary School" in names  # 4-11
        assert "Milton Keynes Preparatory School" in names  # 2-11
        assert "St Thomas Aquinas Catholic Primary School" in names  # 4-11
        assert "Thornton College" in names  # 3-18
        assert "Shenley Brook End School" in names  # 4-11

    @pytest.mark.asyncio
    async def test_age_5_excludes_secondary(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(age=5)
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Secondary-only schools don't accept 5-year-olds
        assert "Walton High School" not in names  # 11-18
        assert "Bedford Modern School" not in names  # 7-18
        assert "MK Boys Grammar" not in names  # 11-18
        assert "MK Girls Academy" not in names  # 11-18

    @pytest.mark.asyncio
    async def test_age_14_includes_secondary(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(age=14)
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Secondary schools: Walton (11-18), Thornton (3-18), Bedford (7-18), MK Boys (11-18), MK Girls (11-18)
        assert "Walton High School" in names
        assert "Thornton College" in names
        assert "Bedford Modern School" in names
        assert "MK Boys Grammar" in names
        assert "MK Girls Academy" in names

    @pytest.mark.asyncio
    async def test_age_14_excludes_primary_only(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(age=14)
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Primary-only schools should be excluded
        assert "Broughton Fields Primary School" not in names
        assert "Milton Keynes Preparatory School" not in names
        assert "St Thomas Aquinas Catholic Primary School" not in names
        assert "Shenley Brook End School" not in names


class TestFilterByMinRating:
    """min_rating filter should accept ratings at or above the specified level."""

    @pytest.mark.asyncio
    async def test_outstanding_only(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(min_rating="Outstanding")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Only Outstanding: Broughton Fields, Thornton College, MK Boys Grammar
        assert names == {"Broughton Fields Primary School", "Thornton College", "MK Boys Grammar"}

    @pytest.mark.asyncio
    async def test_good_or_better(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(min_rating="Good")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Outstanding + Good schools
        assert "Broughton Fields Primary School" in names
        assert "Thornton College" in names
        assert "Walton High School" in names
        assert "Milton Keynes Preparatory School" in names
        assert "Bedford Modern School" in names
        assert "Shenley Brook End School" in names
        assert "MK Boys Grammar" in names
        assert "MK Girls Academy" in names
        # Requires Improvement is excluded
        assert "St Thomas Aquinas Catholic Primary School" not in names

    @pytest.mark.asyncio
    async def test_requires_improvement_or_better(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(min_rating="Requires Improvement")
        schools = await test_repo.find_schools_by_filters(filters)

        # All schools except Inadequate (none in test data are Inadequate)
        assert len(schools) == 9


class TestFilterByPrivate:
    """is_private flag isolates state vs private schools."""

    @pytest.mark.asyncio
    async def test_private_only(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(is_private=True)
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        assert names == {"Milton Keynes Preparatory School", "Thornton College"}

    @pytest.mark.asyncio
    async def test_state_only(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(is_private=False)
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        assert "Milton Keynes Preparatory School" not in names
        assert "Thornton College" not in names
        assert len(schools) == 7


# ---------------------------------------------------------------------------
# Combined filters
# ---------------------------------------------------------------------------


class TestCombinedFilters:
    """Multiple filters applied simultaneously must all be satisfied."""

    @pytest.mark.asyncio
    async def test_mk_council_and_age_5(self, test_repo: SQLiteSchoolRepository):
        """MK council + age 5 should return MK primary/all-through schools."""
        filters = SchoolFilters(council="Milton Keynes", age=5)
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Must be MK AND accept 5-year-olds
        assert "Broughton Fields Primary School" in names
        assert "Milton Keynes Preparatory School" in names
        assert "St Thomas Aquinas Catholic Primary School" in names
        assert "Thornton College" in names
        assert "Shenley Brook End School" in names
        # Secondary schools excluded by age
        assert "Walton High School" not in names
        assert "MK Boys Grammar" not in names
        assert "MK Girls Academy" not in names
        # Bedford excluded by council
        assert "Bedford Modern School" not in names

    @pytest.mark.asyncio
    async def test_mk_council_age_5_male(self, test_repo: SQLiteSchoolRepository):
        """MK + age 5 + male should exclude Thornton College (girls only)."""
        filters = SchoolFilters(council="Milton Keynes", age=5, gender="male")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        assert "Thornton College" not in names
        assert "Broughton Fields Primary School" in names
        assert "Milton Keynes Preparatory School" in names
        assert "St Thomas Aquinas Catholic Primary School" in names

    @pytest.mark.asyncio
    async def test_mk_council_outstanding_only(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(council="Milton Keynes", min_rating="Outstanding")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        assert names == {"Broughton Fields Primary School", "Thornton College", "MK Boys Grammar"}

    @pytest.mark.asyncio
    async def test_no_filters_returns_all(self, test_repo: SQLiteSchoolRepository):
        """Passing no filter criteria should return every school in the database."""
        filters = SchoolFilters()
        schools = await test_repo.find_schools_by_filters(filters)
        assert len(schools) == 9


# ---------------------------------------------------------------------------
# SchoolFilters.min_rating_values unit tests (no DB needed)
# ---------------------------------------------------------------------------


class TestMinRatingValues:
    """Unit tests for the rating-level helper on SchoolFilters."""

    def test_outstanding(self):
        f = SchoolFilters(min_rating="Outstanding")
        assert f.min_rating_values() == ["Outstanding"]

    def test_good(self):
        f = SchoolFilters(min_rating="Good")
        assert f.min_rating_values() == ["Outstanding", "Good"]

    def test_requires_improvement(self):
        f = SchoolFilters(min_rating="Requires Improvement")
        assert f.min_rating_values() == ["Outstanding", "Good", "Requires Improvement"]

    def test_inadequate(self):
        f = SchoolFilters(min_rating="Inadequate")
        assert f.min_rating_values() == ["Outstanding", "Good", "Requires Improvement", "Inadequate"]

    def test_none(self):
        f = SchoolFilters()
        assert f.min_rating_values() is None

    def test_invalid_rating_returns_none(self):
        f = SchoolFilters(min_rating="Excellent")
        assert f.min_rating_values() is None
