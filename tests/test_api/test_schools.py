"""Integration tests for the schools API using FastAPI TestClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# GET /api/councils
# ---------------------------------------------------------------------------


class TestCouncilsEndpoint:
    """Tests for the councils listing endpoint."""

    def test_returns_list(self, test_client: TestClient):
        response = test_client.get("/api/councils")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_contains_known_councils(self, test_client: TestClient):
        response = test_client.get("/api/councils")
        data = response.json()
        assert "Milton Keynes" in data
        assert "Bedford" in data

    def test_councils_are_sorted(self, test_client: TestClient):
        response = test_client.get("/api/councils")
        data = response.json()
        assert data == sorted(data)


# ---------------------------------------------------------------------------
# GET /api/schools
# ---------------------------------------------------------------------------


class TestSchoolsListEndpoint:
    """Tests for the schools list/search endpoint."""

    def test_returns_array(self, test_client: TestClient):
        response = test_client.get("/api/schools")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_filter_by_council(self, test_client: TestClient):
        response = test_client.get("/api/schools", params={"council": "Milton Keynes"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 8
        assert all(s["council"] == "Milton Keynes" for s in data)

    def test_filter_by_council_no_results(self, test_client: TestClient):
        response = test_client.get("/api/schools", params={"council": "Atlantis"})
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_school_response_shape(self, test_client: TestClient):
        """Verify the schema of a school object in the list response."""
        response = test_client.get("/api/schools", params={"council": "Milton Keynes"})
        data = response.json()
        assert len(data) > 0

        school = data[0]
        # Required fields
        assert "id" in school
        assert "name" in school
        assert "council" in school
        # Optional fields should exist (even if None)
        for field in (
            "urn",
            "type",
            "address",
            "postcode",
            "lat",
            "lng",
            "gender_policy",
            "faith",
            "age_range_from",
            "age_range_to",
            "ofsted_rating",
            "is_private",
            "catchment_radius_km",
        ):
            assert field in school, f"Missing field: {field}"

    def test_filter_by_min_rating(self, test_client: TestClient):
        response = test_client.get("/api/schools", params={"min_rating": "Outstanding"})
        assert response.status_code == 200
        data = response.json()
        ratings = {s["ofsted_rating"] for s in data}
        assert ratings == {"Outstanding"}

    def test_filter_by_age(self, test_client: TestClient):
        response = test_client.get("/api/schools", params={"age": 5})
        assert response.status_code == 200
        data = response.json()
        # Every returned school's age range should cover age 5
        for school in data:
            assert school["age_range_from"] <= 5 <= school["age_range_to"]


# ---------------------------------------------------------------------------
# GET /api/schools/{id}
# ---------------------------------------------------------------------------


class TestSchoolDetailEndpoint:
    """Tests for the single-school detail endpoint."""

    def test_existing_school(self, test_client: TestClient):
        response = test_client.get("/api/schools/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Broughton Fields Primary School"

    def test_detail_includes_nested_data(self, test_client: TestClient):
        response = test_client.get("/api/schools/1")
        data = response.json()
        # The detail response should include nested arrays for clubs, etc.
        assert "clubs" in data
        assert "performance" in data
        assert "term_dates" in data
        assert "admissions_history" in data
        assert isinstance(data["clubs"], list)

    def test_detail_includes_clubs(self, test_client: TestClient):
        """School 1 has two clubs in the test data."""
        response = test_client.get("/api/schools/1")
        data = response.json()
        assert len(data["clubs"]) == 2
        club_types = {c["club_type"] for c in data["clubs"]}
        assert club_types == {"breakfast", "after_school"}

    def test_nonexistent_school_returns_404(self, test_client: TestClient):
        response = test_client.get("/api/schools/99999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


# ---------------------------------------------------------------------------
# GET /api/schools/{id}/clubs
# ---------------------------------------------------------------------------


class TestSchoolClubsEndpoint:
    """Tests for the per-school clubs endpoint."""

    def test_returns_clubs(self, test_client: TestClient):
        response = test_client.get("/api/schools/1/clubs")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_school_without_clubs(self, test_client: TestClient):
        """School 3 (MK Prep) has no clubs in the test data."""
        response = test_client.get("/api/schools/3/clubs")
        assert response.status_code == 200
        data = response.json()
        assert data == []


# ---------------------------------------------------------------------------
# GET /api/compare
# ---------------------------------------------------------------------------


class TestCompareEndpoint:
    """Tests for the school comparison endpoint."""

    def test_compare_two_schools(self, test_client: TestClient):
        response = test_client.get("/api/compare", params={"ids": "1,2"})
        assert response.status_code == 200
        data = response.json()
        assert "schools" in data
        assert len(data["schools"]) == 2
        names = {s["name"] for s in data["schools"]}
        assert "Broughton Fields Primary School" in names
        assert "Walton High School" in names

    def test_compare_ignores_missing_ids(self, test_client: TestClient):
        response = test_client.get("/api/compare", params={"ids": "1,99999"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["schools"]) == 1


# ---------------------------------------------------------------------------
# GET /api/geocode  (mocked external HTTP call)
# ---------------------------------------------------------------------------


class TestGeocodeEndpoint:
    """Tests for the postcode geocoding proxy (external call is mocked)."""

    def test_geocode_success(self, test_client: TestClient):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": 200,
            "result": {
                "postcode": "MK9 1AB",
                "latitude": 52.0406,
                "longitude": -0.7594,
            },
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response

        with patch("src.api.geocode.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_async_client.return_value.__aexit__ = AsyncMock(return_value=False)

            response = test_client.get("/api/geocode", params={"postcode": "MK9 1AB"})

        assert response.status_code == 200
        data = response.json()
        assert data["postcode"] == "MK9 1AB"
        assert data["lat"] == 52.0406
        assert data["lng"] == -0.7594

    def test_geocode_bad_postcode(self, test_client: TestClient):
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response

        with patch("src.api.geocode.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_async_client.return_value.__aexit__ = AsyncMock(return_value=False)

            response = test_client.get("/api/geocode", params={"postcode": "INVALID"})

        assert response.status_code == 404
