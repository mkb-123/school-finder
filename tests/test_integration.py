"""Integration tests covering the full request flow, bug fixes, and cross-layer behaviour.

These tests exercise the API endpoints through FastAPI's TestClient with a real
(temporary) SQLite database, verifying that the API, repository, geocoding,
and schema layers work together correctly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.db.base import SchoolFilters
from src.db.sqlite_repo import SQLiteSchoolRepository
from src.services.geocoding import normalise_postcode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _school_names(schools) -> set[str]:
    return {s.name for s in schools}


def _api_school_names(data: list[dict]) -> set[str]:
    return {s["name"] for s in data}


# ===========================================================================
# 1. Postcode normalisation
# ===========================================================================


class TestPostcodeNormalisation:
    """The normalise_postcode helper must reformat any postcode variant
    into the standard 'OUTWARD INWARD' form (e.g. 'MK5 8DX')."""

    def test_no_space(self):
        assert normalise_postcode("MK58DX") == "MK5 8DX"

    def test_lowercase_no_space(self):
        assert normalise_postcode("mk58dx") == "MK5 8DX"

    def test_already_formatted(self):
        assert normalise_postcode("MK5 8DX") == "MK5 8DX"

    def test_extra_spaces(self):
        assert normalise_postcode("MK5  8DX") == "MK5 8DX"

    def test_leading_trailing_whitespace(self):
        assert normalise_postcode("  mk5 8dx  ") == "MK5 8DX"

    def test_short_postcode(self):
        assert normalise_postcode("W1A1AA") == "W1A 1AA"

    def test_long_postcode(self):
        assert normalise_postcode("SW1A 2AA") == "SW1A 2AA"

    def test_very_short_input(self):
        """Inputs shorter than 4 chars are returned uppercased as-is."""
        assert normalise_postcode("MK5") == "MK5"


# ===========================================================================
# 2. Geocode endpoint – fallback lookup
# ===========================================================================


class TestGeocodeFallback:
    """When the external postcodes.io API is unreachable, the /api/geocode
    endpoint should fall back to the built-in lookup table."""

    def test_fallback_with_space(self, test_client: TestClient):
        """A known MK postcode should resolve via fallback when the API is down."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("network down")

        with patch("src.api.geocode.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            response = test_client.get("/api/geocode", params={"postcode": "MK9 1AB"})

        assert response.status_code == 200
        data = response.json()
        assert data["postcode"] == "MK9 1AB"
        assert abs(data["lat"] - 52.043) < 0.01
        assert abs(data["lng"] - (-0.759)) < 0.01

    def test_fallback_without_space(self, test_client: TestClient):
        """Postcodes entered without a space should still resolve via normalisation + fallback."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("network down")

        with patch("src.api.geocode.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            response = test_client.get("/api/geocode", params={"postcode": "MK91AB"})

        assert response.status_code == 200
        data = response.json()
        assert data["postcode"] == "MK9 1AB"

    def test_fallback_outward_code_match(self, test_client: TestClient):
        """Unknown inward code but known outward code should still match a fallback entry."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("network down")

        with patch("src.api.geocode.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # "MK9 9ZZ" is not in fallback but "MK9" outward code matches "MK9 1AB"
            response = test_client.get("/api/geocode", params={"postcode": "MK9 9ZZ"})

        assert response.status_code == 200
        data = response.json()
        assert abs(data["lat"] - 52.043) < 0.01

    def test_fallback_unknown_postcode_returns_404(self, test_client: TestClient):
        """A completely unknown postcode with no outward match should return 404."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("network down")

        with patch("src.api.geocode.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            response = test_client.get("/api/geocode", params={"postcode": "ZZ99 9ZZ"})

        assert response.status_code == 404


# ===========================================================================
# 3. Gender filter with GIAS-style values
# ===========================================================================


class TestGenderFilterGIASValues:
    """The gender filter must work with both legacy ('co-ed', 'boys', 'girls')
    and GIAS-style ('Mixed', 'Boys', 'Girls') gender_policy values."""

    @pytest.mark.asyncio
    async def test_male_filter_includes_mixed(self, test_repo: SQLiteSchoolRepository):
        """Schools with gender_policy='Mixed' must appear for gender='male'."""
        filters = SchoolFilters(gender="male")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)
        assert "Shenley Brook End School" in names  # gender_policy="Mixed"

    @pytest.mark.asyncio
    async def test_female_filter_includes_mixed(self, test_repo: SQLiteSchoolRepository):
        """Schools with gender_policy='Mixed' must appear for gender='female'."""
        filters = SchoolFilters(gender="female")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)
        assert "Shenley Brook End School" in names  # gender_policy="Mixed"

    @pytest.mark.asyncio
    async def test_male_filter_includes_capitalised_boys(self, test_repo: SQLiteSchoolRepository):
        """Schools with gender_policy='Boys' (GIAS style) must appear for gender='male'."""
        filters = SchoolFilters(gender="male")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)
        assert "MK Boys Grammar" in names  # gender_policy="Boys"

    @pytest.mark.asyncio
    async def test_female_filter_includes_capitalised_girls(self, test_repo: SQLiteSchoolRepository):
        """Schools with gender_policy='Girls' (GIAS style) must appear for gender='female'."""
        filters = SchoolFilters(gender="female")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)
        assert "MK Girls Academy" in names  # gender_policy="Girls"

    @pytest.mark.asyncio
    async def test_male_filter_excludes_capitalised_girls(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(gender="male")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)
        assert "MK Girls Academy" not in names  # gender_policy="Girls"

    @pytest.mark.asyncio
    async def test_female_filter_excludes_capitalised_boys(self, test_repo: SQLiteSchoolRepository):
        filters = SchoolFilters(gender="female")
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)
        assert "MK Boys Grammar" not in names  # gender_policy="Boys"

    @pytest.mark.asyncio
    async def test_no_gender_filter_returns_all(self, test_repo: SQLiteSchoolRepository):
        """With no gender filter, all schools should be returned regardless of gender_policy."""
        filters = SchoolFilters()
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)
        assert "Shenley Brook End School" in names
        assert "MK Boys Grammar" in names
        assert "MK Girls Academy" in names
        assert "Broughton Fields Primary School" in names


# ===========================================================================
# 4. Full search flow via API (council + postcode + filters)
# ===========================================================================


class TestSchoolSearchFlow:
    """End-to-end tests simulating the user's search from the home page."""

    def test_council_search_returns_schools(self, test_client: TestClient):
        """Searching by council alone should return all schools in that council."""
        response = test_client.get("/api/schools", params={"council": "Milton Keynes"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 8
        names = _api_school_names(data)
        assert "Shenley Brook End School" in names
        assert "MK Boys Grammar" in names

    def test_council_with_postcode_geocode_fallback(self, test_client: TestClient):
        """When geocoding fails, schools should still be returned (without distance)."""
        # Mock the geocoding service to simulate failure (lazy import, patch at source)
        with patch("src.services.geocoding.geocode_postcode", side_effect=Exception("API down")):
            with patch("src.api.geocode._fallback_lookup", return_value=None):
                response = test_client.get(
                    "/api/schools",
                    params={"council": "Milton Keynes", "postcode": "MK5 8DX"},
                )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 8  # all MK schools returned
        # distance_km is null when geocoding fails completely
        assert all(s["distance_km"] is None for s in data)

    def test_gender_filter_via_api(self, test_client: TestClient):
        """Gender filter through the API should correctly handle Mixed/Boys/Girls."""
        response = test_client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "gender": "male"},
        )
        assert response.status_code == 200
        data = response.json()
        names = _api_school_names(data)

        # co-ed + Mixed + Boys schools should be included
        assert "Broughton Fields Primary School" in names  # co-ed
        assert "Shenley Brook End School" in names  # Mixed
        assert "MK Boys Grammar" in names  # Boys
        # Girls-only excluded
        assert "Thornton College" not in names  # girls
        assert "MK Girls Academy" not in names  # Girls

    def test_age_filter_via_api(self, test_client: TestClient):
        """Age filter through the API returns only schools covering that age."""
        response = test_client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "age": 5},
        )
        assert response.status_code == 200
        data = response.json()
        names = _api_school_names(data)

        assert "Shenley Brook End School" in names  # 4-11
        assert "Broughton Fields Primary School" in names  # 4-11
        assert "MK Boys Grammar" not in names  # 11-18
        assert "MK Girls Academy" not in names  # 11-18

    def test_min_rating_filter_via_api(self, test_client: TestClient):
        """Rating filter via the API uses correct casing."""
        response = test_client.get(
            "/api/schools",
            params={"min_rating": "Outstanding"},
        )
        assert response.status_code == 200
        data = response.json()
        ratings = {s["ofsted_rating"] for s in data}
        assert ratings == {"Outstanding"}
        names = _api_school_names(data)
        assert "MK Boys Grammar" in names

    def test_combined_filters_via_api(self, test_client: TestClient):
        """Multiple filters applied together via the API."""
        response = test_client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "age": 14,
                "gender": "male",
                "min_rating": "Good",
            },
        )
        assert response.status_code == 200
        data = response.json()
        names = _api_school_names(data)

        # MK + age 14 + male + Good or better
        assert "Walton High School" in names  # co-ed, 11-18, Good
        assert "MK Boys Grammar" in names  # Boys, 11-18, Outstanding
        # Excluded:
        assert "Thornton College" not in names  # girls
        assert "MK Girls Academy" not in names  # Girls
        assert "Broughton Fields Primary School" not in names  # primary only


# ===========================================================================
# 5. Club filtering
# ===========================================================================


class TestClubFiltering:
    """Tests for breakfast/after-school club filtering via the repository."""

    @pytest.mark.asyncio
    async def test_has_breakfast_club_filter(self, test_repo: SQLiteSchoolRepository):
        """Only schools with a breakfast club should be returned."""
        filters = SchoolFilters(has_breakfast_club=True)
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # School 1 and 7 have breakfast clubs
        assert "Broughton Fields Primary School" in names
        assert "Shenley Brook End School" in names
        assert "Walton High School" not in names

    @pytest.mark.asyncio
    async def test_has_afterschool_club_filter(self, test_repo: SQLiteSchoolRepository):
        """Only schools with an after-school club should be returned."""
        filters = SchoolFilters(has_afterschool_club=True)
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # School 1 and 2 have after-school clubs
        assert "Broughton Fields Primary School" in names
        assert "Walton High School" in names
        assert "Shenley Brook End School" not in names

    @pytest.mark.asyncio
    async def test_both_club_filters(self, test_repo: SQLiteSchoolRepository):
        """Requiring both breakfast AND after-school club narrows results."""
        filters = SchoolFilters(has_breakfast_club=True, has_afterschool_club=True)
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Only school 1 has both
        assert names == {"Broughton Fields Primary School"}

    def test_club_filter_via_api(self, test_client: TestClient):
        """Club filtering through the API endpoint."""
        response = test_client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "has_breakfast_club": True},
        )
        assert response.status_code == 200
        data = response.json()
        names = _api_school_names(data)
        assert "Broughton Fields Primary School" in names
        assert "Shenley Brook End School" in names
        assert "Walton High School" not in names


# ===========================================================================
# 6. Distance-based filtering and sorting
# ===========================================================================


class TestDistanceFiltering:
    """Tests for spatial queries using the Haversine function."""

    @pytest.mark.asyncio
    async def test_max_distance_filter(self, test_repo: SQLiteSchoolRepository):
        """Schools beyond max_distance_km should be excluded."""
        # Coordinates near Broughton Fields (52.036, -0.71)
        filters = SchoolFilters(
            council="Milton Keynes",
            lat=52.036,
            lng=-0.71,
            max_distance_km=3.0,
        )
        schools = await test_repo.find_schools_by_filters(filters)
        names = _school_names(schools)

        # Broughton Fields is at (52.036, -0.71) — ~0 km
        assert "Broughton Fields Primary School" in names
        # Thornton College is at (52.07, -0.82) — ~8+ km, should be excluded
        assert "Thornton College" not in names

    @pytest.mark.asyncio
    async def test_sorted_by_distance(self, test_repo: SQLiteSchoolRepository):
        """When lat/lng are provided, results should be sorted by distance (nearest first)."""
        # Coordinates near Shenley Brook End (52.007, -0.805)
        filters = SchoolFilters(
            council="Milton Keynes",
            lat=52.007,
            lng=-0.805,
        )
        schools = await test_repo.find_schools_by_filters(filters)

        # First result should be closest to the reference point
        assert len(schools) > 0
        assert schools[0].name == "Shenley Brook End School"  # almost exactly at this point

    @pytest.mark.asyncio
    async def test_sorted_by_name_without_coords(self, test_repo: SQLiteSchoolRepository):
        """Without lat/lng, results should be sorted alphabetically by name."""
        filters = SchoolFilters(council="Milton Keynes")
        schools = await test_repo.find_schools_by_filters(filters)
        names = [s.name for s in schools]
        assert names == sorted(names)


# ===========================================================================
# 7. School detail endpoints
# ===========================================================================


class TestSchoolDetailIntegration:
    """Integration tests for detail, clubs, performance, term-dates, and admissions."""

    def test_detail_includes_performance(self, test_client: TestClient):
        """School 1 has performance records from the test data."""
        response = test_client.get("/api/schools/1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["performance"]) == 2
        types = {p["metric_type"] for p in data["performance"]}
        assert "SATs" in types

    def test_detail_includes_term_dates(self, test_client: TestClient):
        """School 1 has term date records from the test data."""
        response = test_client.get("/api/schools/1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["term_dates"]) == 2
        terms = {t["term_name"] for t in data["term_dates"]}
        assert "Autumn 1" in terms
        assert "Spring 1" in terms

    def test_detail_includes_admissions(self, test_client: TestClient):
        """School 1 has admissions history from the test data."""
        response = test_client.get("/api/schools/1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["admissions_history"]) == 2
        years = {a["academic_year"] for a in data["admissions_history"]}
        assert "2023/2024" in years
        assert "2022/2023" in years

    def test_term_dates_endpoint(self, test_client: TestClient):
        response = test_client.get("/api/schools/1/term-dates")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_performance_endpoint(self, test_client: TestClient):
        response = test_client.get("/api/schools/1/performance")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_admissions_endpoint(self, test_client: TestClient):
        response = test_client.get("/api/schools/1/admissions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["places_offered"] == 60

    def test_new_school_detail(self, test_client: TestClient):
        """Shenley Brook End (school 7, GIAS-style data) has clubs and performance."""
        response = test_client.get("/api/schools/7")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Shenley Brook End School"
        assert data["gender_policy"] == "Mixed"
        assert len(data["clubs"]) == 1
        assert data["clubs"][0]["club_type"] == "breakfast"
        assert len(data["performance"]) == 1
        assert len(data["admissions_history"]) == 1


# ===========================================================================
# 8. Admissions estimate endpoint
# ===========================================================================


class TestAdmissionsEstimate:
    """Tests for the waiting-list likelihood estimation."""

    def test_estimate_for_nearby_family(self, test_client: TestClient):
        """A family within the last distance offered should get a positive likelihood."""
        response = test_client.get(
            "/api/schools/1/admissions/estimate",
            params={"distance_km": 1.0},
        )
        assert response.status_code == 200
        data = response.json()
        assert "likelihood" in data
        assert data["likelihood"] in ("Very likely", "Likely", "Unlikely", "Insufficient data")
        assert data["years_of_data"] == 2

    def test_estimate_for_distant_family(self, test_client: TestClient):
        """A family far outside historical cutoffs."""
        response = test_client.get(
            "/api/schools/1/admissions/estimate",
            params={"distance_km": 10.0},
        )
        assert response.status_code == 200
        data = response.json()
        assert "likelihood" in data

    def test_estimate_nonexistent_school(self, test_client: TestClient):
        response = test_client.get(
            "/api/schools/99999/admissions/estimate",
            params={"distance_km": 1.0},
        )
        assert response.status_code == 404


# ===========================================================================
# 9. Compare endpoint
# ===========================================================================


class TestCompareIntegration:
    """Tests for the school comparison endpoint with richer test data."""

    def test_compare_includes_nested_data(self, test_client: TestClient):
        """Comparing schools should include clubs, performance, etc."""
        response = test_client.get("/api/compare", params={"ids": "1,7"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["schools"]) == 2

        names = {s["name"] for s in data["schools"]}
        assert "Broughton Fields Primary School" in names
        assert "Shenley Brook End School" in names

        # Each school should have nested data
        for school in data["schools"]:
            assert "clubs" in school
            assert "performance" in school

    def test_compare_mixed_gender_policies(self, test_client: TestClient):
        """Comparing schools with different gender_policy formats."""
        response = test_client.get("/api/compare", params={"ids": "1,7,8"})
        assert response.status_code == 200
        data = response.json()
        policies = {s["gender_policy"] for s in data["schools"]}
        assert "co-ed" in policies
        assert "Mixed" in policies
        assert "Boys" in policies


# ===========================================================================
# 10. Ofsted rating consistency
# ===========================================================================


class TestOfstedRatingConsistency:
    """Verify Ofsted ratings are returned with consistent casing from the API."""

    def test_api_returns_correct_casing(self, test_client: TestClient):
        """All Ofsted ratings in API responses should use the standard casing."""
        response = test_client.get("/api/schools")
        assert response.status_code == 200
        data = response.json()

        valid_ratings = {"Outstanding", "Good", "Requires Improvement", "Inadequate", None}
        for school in data:
            assert school["ofsted_rating"] in valid_ratings, (
                f"School '{school['name']}' has unexpected rating: {school['ofsted_rating']}"
            )

    def test_requires_improvement_filter_matches_db(self, test_client: TestClient):
        """Filter value 'Requires Improvement' (capital I) should match DB records."""
        response = test_client.get(
            "/api/schools",
            params={"min_rating": "Requires Improvement"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 9  # all schools have RI or better
        names = _api_school_names(data)
        assert "St Thomas Aquinas Catholic Primary School" in names  # Requires Improvement
