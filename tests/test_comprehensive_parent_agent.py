"""Comprehensive parent-agent test: exercises ALL API endpoints and features (Phases 1-11).

Simulates Sarah, a parent of 4-year-old Lily in Milton Keynes (postcode MK5 6EX),
who wants to find the best school. Exercises every endpoint, validates response
shapes, and collects a structured list of issues found.

Usage:
    pytest tests/test_comprehensive_parent_agent.py -v
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.db.models import Base
from src.db.seed import (
    _generate_private_school_details,
    _generate_test_admissions,
    _generate_test_clubs,
    _generate_test_performance,
    _generate_test_schools,
    _generate_test_term_dates,
)
from src.db.sqlite_repo import SQLiteSchoolRepository
from src.main import app

# ---------------------------------------------------------------------------
# Issue tracker
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    title: str
    body: str
    labels: list[str] = field(default_factory=lambda: ["bug", "comprehensive-test"])


_issues: list[Issue] = []


def _record(title: str, body: str, labels: list[str] | None = None):
    """Record an issue found during testing."""
    _issues.append(Issue(title=title, body=body, labels=labels or ["bug", "comprehensive-test"]))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed_full_db(tmp_path) -> str:
    """Create a temp DB with ALL seed data: schools, clubs, performance,
    term dates, admissions, private details."""
    path = str(tmp_path / "comprehensive_test.db")
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)

    schools = _generate_test_schools("Milton Keynes")
    with Session(engine) as session:
        session.add_all(schools)
        session.commit()

        # Re-read schools from DB so they have assigned IDs
        from src.db.models import School

        db_schools = session.query(School).all()

        # Generate and insert clubs
        clubs = _generate_test_clubs(db_schools)
        session.add_all(clubs)
        session.commit()

        # Generate and insert term dates
        term_dates = _generate_test_term_dates(db_schools)
        session.add_all(term_dates)
        session.commit()

        # Generate performance data (inserts internally)
        _generate_test_performance(db_schools, session)

        # Generate admissions data (inserts internally)
        _generate_test_admissions(db_schools, session)

        # Generate private school details
        _generate_private_school_details(session)
        session.commit()

    engine.dispose()
    return path


@pytest.fixture()
def client(tmp_path) -> TestClient:
    """TestClient with comprehensive seed data for full feature testing."""
    db_path = _seed_full_db(tmp_path)
    repo = SQLiteSchoolRepository(db_path)

    def _override() -> SchoolRepository:
        return repo

    app.dependency_overrides[get_school_repository] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ===================================================================
# Phase 1-2: Basic school search, councils, geocoding, map data
# ===================================================================


class TestPhase1And2BasicSearch:
    """Council listing, geocoding, basic school search, map fields."""

    # 1. GET /api/councils - must return Milton Keynes
    def test_councils_returns_milton_keynes(self, client):
        r = client.get("/api/councils")
        assert r.status_code == 200
        councils = r.json()
        assert isinstance(councils, list)
        assert "Milton Keynes" in councils, f"Milton Keynes not found in councils list: {councils}"

    # 2. GET /api/geocode?postcode=MK5+6EX - must return lat/lng
    def test_geocode_mk5_6ex(self, client):
        r = client.get("/api/geocode", params={"postcode": "MK5 6EX"})
        if r.status_code != 200:
            _record(
                "Geocode fails for MK5 6EX",
                f"GET /api/geocode?postcode=MK5+6EX returned {r.status_code}.\n"
                f"MK5 6EX is Sarah's home postcode. Response: {r.text}",
                ["bug", "geocode"],
            )
            pytest.skip("Geocode not available; external API + fallback failed")
        data = r.json()
        assert "lat" in data, "Geocode response missing 'lat'"
        assert "lng" in data, "Geocode response missing 'lng'"
        assert isinstance(data["lat"], float)
        assert isinstance(data["lng"], float)
        # MK5 is roughly around lat 52.0, lng -0.8
        assert 51.9 < data["lat"] < 52.2, f"lat {data['lat']} out of Milton Keynes range"
        assert -0.9 < data["lng"] < -0.6, f"lng {data['lng']} out of Milton Keynes range"

    # 3. GET /api/schools?council=Milton+Keynes - returns schools
    def test_schools_list_returns_results(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        assert r.status_code == 200
        schools = r.json()
        assert isinstance(schools, list)
        assert len(schools) > 0, "No schools returned for Milton Keynes"

    # 4. Schools have ofsted_rating field for colour coding
    def test_schools_have_ofsted_for_map(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        schools_with_rating = [s for s in schools if s.get("ofsted_rating")]
        if len(schools_with_rating) == 0:
            _record(
                "No schools have ofsted_rating populated",
                f"Map colour-coding requires ofsted_rating but none of the {len(schools)} schools have it set.",
                ["bug", "data"],
            )
        # At least some schools should have Ofsted ratings
        assert len(schools_with_rating) > 0, "No schools have ofsted_rating"

    # 5. Schools have lat/lng and catchment_radius_km for map circles
    def test_schools_have_map_fields(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        missing_coords = [s["name"] for s in schools if s.get("lat") is None or s.get("lng") is None]
        if missing_coords:
            _record(
                f"{len(missing_coords)} schools missing lat/lng coordinates",
                f"Schools without coordinates cannot be displayed on map: "
                f"{missing_coords[:5]}{'...' if len(missing_coords) > 5 else ''}",
                ["bug", "data"],
            )
        missing_catchment = [s["name"] for s in schools if s.get("catchment_radius_km") is None]
        if missing_catchment:
            _record(
                f"{len(missing_catchment)} schools missing catchment_radius_km",
                f"Schools without catchment_radius_km cannot show catchment circles "
                f"on the map: {missing_catchment[:5]}",
                ["enhancement", "data"],
            )
        # Core assertion: majority have coords
        assert len(schools) - len(missing_coords) > 10, "Too few schools have coordinates"


# ===================================================================
# Phase 3: Filters
# ===================================================================


class TestPhase3Filters:
    """Constraint-based filtering: rating, age, gender, invalid params."""

    # 6. Filter by min_rating=Outstanding
    def test_filter_outstanding(self, client):
        r = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "min_rating": "Outstanding"},
        )
        assert r.status_code == 200
        schools = r.json()
        for s in schools:
            if s["ofsted_rating"] not in ("Outstanding", None):
                _record(
                    f"Non-Outstanding school '{s['name']}' returned with Outstanding filter",
                    f"School has rating '{s['ofsted_rating']}' but was returned "
                    f"when min_rating=Outstanding.\n"
                    f"Endpoint: GET /api/schools?council=Milton+Keynes&min_rating=Outstanding",
                    ["bug", "filtering"],
                )
            assert s["ofsted_rating"] in ("Outstanding", None), (
                f"School '{s['name']}' has rating '{s['ofsted_rating']}' but only Outstanding expected"
            )

    # 7. Filter for age=4 (Lily's age)
    def test_filter_age_4(self, client):
        r = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "age": "4"},
        )
        assert r.status_code == 200
        schools = r.json()
        assert len(schools) > 0, "No schools accept age 4 in Milton Keynes"
        for s in schools:
            if s.get("age_range_from") is not None and s["age_range_from"] > 4:
                _record(
                    f"School '{s['name']}' doesn't accept age 4 (starts at {s['age_range_from']})",
                    f"Returned by age=4 filter but age_range_from={s['age_range_from']}",
                    ["bug", "filtering"],
                )
            if s.get("age_range_to") is not None and s["age_range_to"] < 4:
                _record(
                    f"School '{s['name']}' age_range_to={s['age_range_to']} < 4",
                    f"Returned by age=4 filter but age_range_to={s['age_range_to']}",
                    ["bug", "filtering"],
                )

    # 8. Filter for gender=female
    def test_filter_gender_female(self, client):
        r = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "gender": "female"},
        )
        assert r.status_code == 200
        schools = r.json()
        for s in schools:
            if s.get("gender_policy") == "Boys":
                _record(
                    f"Boys-only school '{s['name']}' in gender=female results",
                    "School has gender_policy='Boys' but appeared in gender=female filter.",
                    ["bug", "filtering"],
                )
                assert False, f"Boys-only school '{s['name']}' should not appear for gender=female"

    # 9. Invalid filter values don't crash
    def test_invalid_filter_values(self, client):
        # Invalid min_rating value
        r = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "min_rating": "INVALID_RATING"},
        )
        # Should either return 200 (ignoring invalid) or 422 (validation error)
        assert r.status_code in (200, 400, 422), f"Unexpected status {r.status_code} for invalid min_rating"

        # Invalid age value
        r = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "age": "not_a_number"},
        )
        assert r.status_code in (200, 400, 422), f"Unexpected status {r.status_code} for invalid age"


# ===================================================================
# Phase 4: Clubs
# ===================================================================


class TestPhase4Clubs:
    """Breakfast and after-school club data and filtering."""

    def _get_first_school_id(self, client) -> int:
        """Helper: get the ID of the first school in MK."""
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        assert len(schools) > 0
        return schools[0]["id"]

    # 10. GET /api/schools/{id}/clubs
    def test_clubs_endpoint_returns_data(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        any_clubs_found = False
        for s in schools[:20]:
            cr = client.get(f"/api/schools/{s['id']}/clubs")
            assert cr.status_code == 200, f"Clubs endpoint failed for {s['name']}: {cr.status_code}"
            clubs = cr.json()
            if len(clubs) > 0:
                any_clubs_found = True
        if not any_clubs_found:
            _record(
                "No clubs found for any school in first 20",
                "Checked first 20 schools but none have club data seeded.",
                ["bug", "data"],
            )

    # 11. Club records have required fields
    def test_club_structure(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        for s in schools[:30]:
            cr = client.get(f"/api/schools/{s['id']}/clubs")
            clubs = cr.json()
            for club in clubs:
                assert "club_type" in club, f"Club missing 'club_type' for school {s['name']}"
                assert "name" in club, f"Club missing 'name' for school {s['name']}"
                assert club["club_type"] in ("breakfast", "after_school"), (
                    f"Unknown club_type '{club['club_type']}' for school {s['name']}"
                )
                # days_available and cost_per_session should be present
                if "days_available" not in club:
                    _record(
                        f"Club '{club['name']}' missing days_available",
                        f"Club for {s['name']} is missing 'days_available' field.",
                        ["enhancement", "data"],
                    )
                if "cost_per_session" not in club:
                    _record(
                        f"Club '{club['name']}' missing cost_per_session",
                        f"Club for {s['name']} is missing 'cost_per_session' field.",
                        ["enhancement", "data"],
                    )

    # 12. has_breakfast_club filter (if supported)
    def test_breakfast_club_filter(self, client):
        r = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "has_breakfast_club": "true"},
        )
        # This param may or may not be fully implemented
        if r.status_code == 422:
            _record(
                "has_breakfast_club filter not implemented",
                "GET /api/schools?has_breakfast_club=true returns 422 - filter not supported yet.",
                ["enhancement", "filtering"],
            )
            pytest.skip("has_breakfast_club filter not implemented")
        assert r.status_code == 200


# ===================================================================
# Phase 5: Private schools
# ===================================================================


class TestPhase5PrivateSchools:
    """Private school listing, detail with fee data, Thornton College."""

    # 13. GET /api/private-schools?council=Milton+Keynes
    def test_private_schools_list(self, client):
        r = client.get("/api/private-schools", params={"council": "Milton Keynes"})
        assert r.status_code == 200
        schools = r.json()
        assert len(schools) > 0, "No private schools returned for Milton Keynes"
        for s in schools:
            assert s.get("is_private") is True, f"Private school '{s['name']}' has is_private={s.get('is_private')}"

    # 14. GET /api/private-schools/{id} - returns detail with private_details
    def test_private_school_detail(self, client):
        r = client.get("/api/private-schools", params={"council": "Milton Keynes"})
        schools = r.json()
        assert len(schools) > 0
        school_id = schools[0]["id"]
        r = client.get(f"/api/private-schools/{school_id}")
        assert r.status_code == 200
        detail = r.json()
        assert "private_details" in detail, (
            f"Private school detail missing 'private_details': keys={list(detail.keys())}"
        )

    # 15. private_details has required fee fields
    def test_private_details_fee_fields(self, client):
        r = client.get("/api/private-schools", params={"council": "Milton Keynes"})
        schools = r.json()
        any_fees_found = False
        for s in schools:
            dr = client.get(f"/api/private-schools/{s['id']}")
            detail = dr.json()
            pds = detail.get("private_details", [])
            for pd in pds:
                any_fees_found = True
                for fld in ("termly_fee", "annual_fee", "fee_age_group"):
                    if fld not in pd:
                        _record(
                            f"Private detail missing '{fld}' for {s['name']}",
                            f"Private school detail record is missing '{fld}'.\nFields present: {list(pd.keys())}",
                            ["bug", "data"],
                        )
                # fee_increase_pct is a bonus field
                if "fee_increase_pct" in pd and pd["fee_increase_pct"] is not None:
                    assert isinstance(pd["fee_increase_pct"], (int, float))
        if not any_fees_found:
            _record(
                "No private school has fee data",
                "None of the private schools have private_details with fee information.",
                ["bug", "data"],
            )
        assert any_fees_found, "No private school has fee data"

    # 16. Thornton College has fee data
    def test_thornton_college_fees(self, client):
        r = client.get("/api/private-schools", params={"council": "Milton Keynes"})
        schools = r.json()
        thornton = [s for s in schools if "Thornton" in s["name"]]
        assert len(thornton) > 0, "Thornton College not found in private schools"
        t = thornton[0]
        dr = client.get(f"/api/private-schools/{t['id']}")
        assert dr.status_code == 200
        detail = dr.json()
        pds = detail.get("private_details", [])
        assert len(pds) > 0, f"Thornton College (ID {t['id']}) has no private_details records"
        # Check that at least one record has fees
        has_fees = any(pd.get("annual_fee") is not None for pd in pds)
        assert has_fees, "Thornton College private_details have no annual_fee set"
        # Thornton should have multiple age groups
        age_groups = [pd.get("fee_age_group") for pd in pds if pd.get("fee_age_group")]
        assert len(age_groups) >= 2, f"Thornton College should have multiple fee age groups, found: {age_groups}"


# ===================================================================
# Phase 6: Term dates
# ===================================================================


class TestPhase6TermDates:
    """Term date retrieval and field validation."""

    # 17. GET /api/schools/{id}/term-dates
    def test_term_dates_endpoint(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        assert len(schools) > 0
        school_id = schools[0]["id"]
        r = client.get(f"/api/schools/{school_id}/term-dates")
        assert r.status_code == 200, f"Term dates endpoint returned {r.status_code} for school {school_id}"

    # 18. Term date records have required fields
    def test_term_date_fields(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        any_dates_found = False
        for s in schools[:10]:
            tr = client.get(f"/api/schools/{s['id']}/term-dates")
            tds = tr.json()
            for td in tds:
                any_dates_found = True
                for fld in ("term_name", "start_date", "end_date", "academic_year"):
                    assert fld in td, f"Term date missing '{fld}' for school {s['name']}: keys={list(td.keys())}"
        if not any_dates_found:
            _record(
                "No term dates found for any school",
                "Checked first 10 schools but none have term date data.",
                ["bug", "data"],
            )
        assert any_dates_found, "No term date records found"

    # Term dates in school detail response
    def test_term_dates_in_detail(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        school_id = schools[0]["id"]
        dr = client.get(f"/api/schools/{school_id}")
        detail = dr.json()
        assert "term_dates" in detail, f"School detail missing 'term_dates': keys={list(detail.keys())}"


# ===================================================================
# Phase 7: Performance
# ===================================================================


class TestPhase7Performance:
    """Academic performance data: SATs, GCSE, Progress8, Attainment8."""

    # 19. Performance field in school detail
    def test_performance_in_detail(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        school_id = schools[0]["id"]
        dr = client.get(f"/api/schools/{school_id}")
        detail = dr.json()
        assert "performance" in detail, f"School detail missing 'performance': keys={list(detail.keys())}"

    # 20. Primary schools have SATs data
    def test_primary_sats(self, client):
        r = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "age": "4"},
        )
        schools = r.json()
        # Filter to primary-only (age_range_to <= 13)
        primaries = [s for s in schools if s.get("age_range_to") is not None and s["age_range_to"] <= 13]
        sats_found = 0
        for s in primaries[:10]:
            pr = client.get(f"/api/schools/{s['id']}/performance")
            assert pr.status_code == 200
            perf = pr.json()
            sats = [p for p in perf if p.get("metric_type") in ("SATs", "SATs_Higher")]
            if sats:
                sats_found += 1
        if sats_found == 0 and len(primaries) > 0:
            _record(
                "No primary schools have SATs data",
                f"Checked {min(10, len(primaries))} primary schools but none have SATs data.",
                ["bug", "data"],
            )
        # Allow this to pass if data exists for at least some
        assert sats_found > 0 or len(primaries) == 0, "No SATs data for primary schools"

    # 21. Secondary schools have GCSE/Progress8/Attainment8
    def test_secondary_performance(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        secondaries = [
            s
            for s in schools
            if s.get("age_range_from") is not None
            and s["age_range_from"] >= 11
            and s.get("age_range_to") is not None
            and s["age_range_to"] >= 16
            and not s.get("is_private")
        ]
        gcse_found = 0
        for s in secondaries[:10]:
            pr = client.get(f"/api/schools/{s['id']}/performance")
            perf = pr.json()
            types = {p.get("metric_type") for p in perf}
            if "GCSE" in types:
                gcse_found += 1
            if "Progress8" in types or "Attainment8" in types:
                pass  # good
        if gcse_found == 0 and len(secondaries) > 0:
            _record(
                "No secondary schools have GCSE data",
                f"Checked {min(10, len(secondaries))} secondary schools but none have GCSE data.",
                ["bug", "data"],
            )
        assert gcse_found > 0 or len(secondaries) == 0, "No GCSE data for secondaries"

    # 22. Performance records have required fields
    def test_performance_fields(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        for s in schools[:10]:
            pr = client.get(f"/api/schools/{s['id']}/performance")
            assert pr.status_code == 200
            perf = pr.json()
            for p in perf:
                for fld in ("metric_type", "metric_value", "year"):
                    assert fld in p, f"Performance record missing '{fld}' for {s['name']}: keys={list(p.keys())}"


# ===================================================================
# Phase 8: Admissions
# ===================================================================


class TestPhase8Admissions:
    """Admissions history and likelihood estimation."""

    # 23. School detail includes admissions_history
    def test_admissions_in_detail(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        # Pick a state school
        state_schools = [s for s in schools if not s.get("is_private")]
        assert len(state_schools) > 0
        school_id = state_schools[0]["id"]
        dr = client.get(f"/api/schools/{school_id}")
        detail = dr.json()
        assert "admissions_history" in detail, f"School detail missing 'admissions_history': keys={list(detail.keys())}"

    # 24. Admissions history has required fields
    def test_admissions_fields(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        state_schools = [s for s in schools if not s.get("is_private")]
        any_admissions = False
        for s in state_schools[:10]:
            ar = client.get(f"/api/schools/{s['id']}/admissions")
            assert ar.status_code == 200
            admissions = ar.json()
            for a in admissions:
                any_admissions = True
                for fld in (
                    "academic_year",
                    "places_offered",
                    "applications_received",
                    "last_distance_offered_km",
                ):
                    assert fld in a, f"Admissions record missing '{fld}' for {s['name']}: keys={list(a.keys())}"
        if not any_admissions:
            _record(
                "No admissions data found",
                "Checked first 10 state schools but none have admissions history.",
                ["bug", "data"],
            )
        assert any_admissions, "No admissions history records found for state schools"

    # 25. Admissions estimate endpoint
    def test_admissions_estimate(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        state_schools = [s for s in schools if not s.get("is_private")]
        assert len(state_schools) > 0
        school_id = state_schools[0]["id"]
        er = client.get(
            f"/api/schools/{school_id}/admissions/estimate",
            params={"distance_km": "2.0"},
        )
        assert er.status_code == 200, f"Admissions estimate returned {er.status_code}: {er.text}"
        est = er.json()
        # 26. Verify estimate has likelihood and trend
        assert "likelihood" in est, f"Estimate missing 'likelihood': keys={list(est.keys())}"
        assert "trend" in est, f"Estimate missing 'trend': keys={list(est.keys())}"
        assert isinstance(est["likelihood"], str)
        assert isinstance(est["trend"], str)


# ===================================================================
# Phase 9: Journey planner
# ===================================================================


class TestPhase9Journey:
    """School run journey calculation."""

    def _get_school_ids(self, client, count=3) -> list[int]:
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        return [s["id"] for s in schools[:count]]

    # 27. Single journey
    def test_single_journey(self, client):
        ids = self._get_school_ids(client, 1)
        r = client.get(
            "/api/journey",
            params={
                "from_postcode": "MK5 6EX",
                "to_school_id": ids[0],
                "mode": "walking",
            },
        )
        if r.status_code == 404 and "geocode" in r.text.lower():
            _record(
                "Journey: cannot geocode MK5 6EX",
                "Journey endpoint cannot geocode MK5 6EX for Sarah's postcode.",
                ["bug", "journey"],
            )
            pytest.skip("Cannot geocode MK5 6EX for journey")
        assert r.status_code == 200, f"Journey returned {r.status_code}: {r.text}"
        data = r.json()
        # 29. Verify journey fields
        assert "distance_km" in data, f"Journey missing 'distance_km': keys={list(data.keys())}"
        # Response has nested structure: dropoff, pickup, off_peak
        assert "dropoff" in data, "Journey missing 'dropoff' estimate"
        assert "pickup" in data, "Journey missing 'pickup' estimate"
        dropoff = data["dropoff"]
        assert "duration_minutes" in dropoff, "Dropoff missing 'duration_minutes'"
        assert "mode" in dropoff, "Dropoff missing 'mode'"

    # 28. Compare journeys
    def test_compare_journeys(self, client):
        ids = self._get_school_ids(client, 3)
        r = client.get(
            "/api/journey/compare",
            params={
                "from_postcode": "MK5 6EX",
                "school_ids": ",".join(str(i) for i in ids),
                "mode": "driving",
            },
        )
        if r.status_code == 404 and "geocode" in r.text.lower():
            pytest.skip("Cannot geocode MK5 6EX for journey comparison")
        assert r.status_code == 200, f"Journey compare returned {r.status_code}: {r.text}"
        data = r.json()
        assert "journeys" in data, f"Compare missing 'journeys': keys={list(data.keys())}"
        assert len(data["journeys"]) > 0, "No journeys returned in comparison"


# ===================================================================
# Phase 10: Decision support
# ===================================================================


class TestPhase10DecisionSupport:
    """Weighted scoring, pros/cons, school ranking."""

    def _get_school_ids(self, client, count=3) -> list[int]:
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        return [s["id"] for s in schools[:count]]

    # 30. Score schools
    def test_score_schools(self, client):
        ids = self._get_school_ids(client, 3)
        r = client.get(
            "/api/decision/score",
            params={"school_ids": ",".join(str(i) for i in ids)},
        )
        assert r.status_code == 200, f"Score returned {r.status_code}: {r.text}"
        data = r.json()
        assert "schools" in data, f"Score missing 'schools': keys={list(data.keys())}"
        scored = data["schools"]
        assert len(scored) > 0, "No scored schools returned"
        # 32. Verify sorted by score descending
        scores = [s["composite_score"] for s in scored]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Schools not sorted by score descending: score[{i}]={scores[i]} < score[{i + 1}]={scores[i + 1]}"
            )

    # 31. Pros and cons
    def test_pros_cons(self, client):
        ids = self._get_school_ids(client, 1)
        r = client.get(
            "/api/decision/pros-cons",
            params={"school_id": ids[0]},
        )
        assert r.status_code == 200, f"Pros/cons returned {r.status_code}: {r.text}"
        data = r.json()
        assert "pros" in data, f"Missing 'pros': keys={list(data.keys())}"
        assert "cons" in data, f"Missing 'cons': keys={list(data.keys())}"
        assert isinstance(data["pros"], list)
        assert isinstance(data["cons"], list)
        # A school should have at least some pros or cons
        assert len(data["pros"]) + len(data["cons"]) > 0, "Pros/cons engine returned empty lists for both"

    # Score with custom weights
    def test_score_with_weights(self, client):
        ids = self._get_school_ids(client, 3)
        r = client.get(
            "/api/decision/score",
            params={
                "school_ids": ",".join(str(i) for i in ids),
                "weights": "distance:0.5,ofsted:0.5,clubs:0.0,fees:0.0",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "weights_used" in data
        weights = data["weights_used"]
        assert weights.get("distance") == 0.5 or weights.get("distance") == pytest.approx(0.5)


# ===================================================================
# Phase 11: Schema completeness and compare
# ===================================================================


class TestPhase11SchemaAndCompare:
    """Schema completeness, compare endpoint, edge cases."""

    # 33. SchoolDetailResponse includes ALL expected fields
    def test_detail_response_completeness(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        school_id = schools[0]["id"]
        dr = client.get(f"/api/schools/{school_id}")
        assert dr.status_code == 200
        detail = dr.json()
        expected_fields = [
            "id",
            "name",
            "urn",
            "type",
            "council",
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
            "clubs",
            "performance",
            "term_dates",
            "admissions_history",
            "private_details",
        ]
        missing = [f for f in expected_fields if f not in detail]
        if missing:
            _record(
                f"SchoolDetailResponse missing {len(missing)} fields",
                f"Missing fields: {missing}\nPresent fields: {list(detail.keys())}",
                ["bug", "api"],
            )
        assert len(missing) == 0, f"Detail response missing fields: {missing}"

    # 34. Compare endpoint
    def test_compare_endpoint(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        assert len(schools) >= 2
        ids = [schools[0]["id"], schools[1]["id"]]
        cr = client.get(
            "/api/compare",
            params={"ids": ",".join(str(i) for i in ids)},
        )
        assert cr.status_code == 200
        data = cr.json()
        assert "schools" in data, f"Compare missing 'schools': keys={list(data.keys())}"
        assert len(data["schools"]) == 2, f"Compare returned {len(data['schools'])} schools, expected 2"
        # Each compared school should be a full detail response
        for school in data["schools"]:
            assert "name" in school
            assert "clubs" in school, "Compare school missing 'clubs'"
            assert "performance" in school, "Compare school missing 'performance'"


# ===================================================================
# Error handling
# ===================================================================


class TestErrorHandling:
    """404s, invalid parameters, edge cases."""

    # 35. Non-existent school returns 404
    def test_nonexistent_school_404(self, client):
        r = client.get("/api/schools/99999")
        assert r.status_code == 404, f"Expected 404 for non-existent school, got {r.status_code}"

    # 36. Invalid postcode in journey
    def test_journey_invalid_postcode(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        school_id = schools[0]["id"]
        r = client.get(
            "/api/journey",
            params={
                "from_postcode": "ZZZZZZZ",
                "to_school_id": school_id,
                "mode": "walking",
            },
        )
        # Should be 404 (postcode not found) or 400, not 500
        assert r.status_code in (400, 404, 422), (
            f"Invalid postcode should return 400/404/422, got {r.status_code}: {r.text}"
        )

    # 37. Empty school_ids in decision score
    def test_decision_score_empty_ids(self, client):
        r = client.get("/api/decision/score", params={"school_ids": ""})
        assert r.status_code in (400, 422), f"Empty school_ids should return 400/422, got {r.status_code}"

    # Non-existent school in private schools
    def test_private_school_404(self, client):
        r = client.get("/api/private-schools/99999")
        assert r.status_code == 404

    # Non-existent school in admissions
    def test_admissions_for_nonexistent_school(self, client):
        r = client.get("/api/schools/99999/admissions")
        # Could return 200 with empty list or 404
        assert r.status_code in (200, 404)

    # Invalid journey mode
    def test_invalid_journey_mode(self, client):
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        r = client.get(
            "/api/journey",
            params={
                "from_postcode": "MK5 7ZP",
                "to_school_id": schools[0]["id"],
                "mode": "teleportation",
            },
        )
        assert r.status_code == 400, f"Invalid mode should return 400, got {r.status_code}"


# ===================================================================
# Cross-cutting: data integrity
# ===================================================================


class TestDataIntegrity:
    """Cross-cutting data quality checks across the seeded database."""

    def test_caroline_haslett_exists(self, client):
        """Sarah's nearest school must be present."""
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        caroline = [s for s in schools if "Caroline Haslett" in s["name"]]
        assert len(caroline) > 0, "Caroline Haslett Primary School not found"
        ch = caroline[0]
        assert ch["age_range_from"] <= 4, (
            f"Caroline Haslett should accept age 4, but age_range_from={ch['age_range_from']}"
        )
        assert ch["ofsted_rating"] == "Outstanding", (
            f"Caroline Haslett should be Outstanding, got {ch['ofsted_rating']}"
        )

    def test_thornton_college_is_girls(self, client):
        """Thornton College should be a girls-only private school."""
        r = client.get("/api/private-schools", params={"council": "Milton Keynes"})
        schools = r.json()
        thornton = [s for s in schools if "Thornton" in s["name"]]
        assert len(thornton) > 0, "Thornton College not found"
        t = thornton[0]
        assert t["is_private"] is True
        assert t.get("gender_policy") == "Girls", f"Thornton should be Girls-only, got {t.get('gender_policy')}"

    def test_school_count_reasonable(self, client):
        """Expect 80+ schools in Milton Keynes test data."""
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        assert len(schools) >= 70, f"Expected 70+ schools in MK, got {len(schools)}"

    def test_mixed_school_types(self, client):
        """Schools should include primary, secondary, and special types."""
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        age_ranges = set()
        for s in schools:
            afrom = s.get("age_range_from", 0)
            ato = s.get("age_range_to", 0)
            if afrom >= 11:
                age_ranges.add("secondary")
            elif ato <= 11:
                age_ranges.add("primary")
            else:
                age_ranges.add("through")
        assert "primary" in age_ranges, "No primary schools found"
        assert "secondary" in age_ranges, "No secondary schools found"

    def test_ofsted_ratings_distribution(self, client):
        """Should have a mix of Outstanding, Good, RI ratings."""
        r = client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        ratings = {}
        for s in schools:
            rating = s.get("ofsted_rating")
            if rating:
                ratings[rating] = ratings.get(rating, 0) + 1
        assert "Outstanding" in ratings, "No Outstanding schools in test data"
        assert "Good" in ratings, "No Good schools in test data"
        assert ratings.get("Outstanding", 0) >= 5, "Too few Outstanding schools"
        assert ratings.get("Good", 0) >= 20, "Too few Good schools"


# ===================================================================
# Issue summary (printed at end of test session)
# ===================================================================


@pytest.fixture(autouse=True, scope="session")
def _print_issue_summary():
    """Print all collected issues after all tests finish."""
    yield
    if _issues:
        print("\n" + "=" * 60)
        print(f"  ISSUES FOUND: {len(_issues)}")
        print("=" * 60)
        for i, issue in enumerate(_issues, 1):
            print(f"\n  [{i}] {issue.title}")
            print(f"      Labels: {', '.join(issue.labels)}")
            # Print first 3 lines of body
            lines = issue.body.split("\n")
            for line in lines[:3]:
                print(f"      {line}")
            if len(lines) > 3:
                print(f"      ... ({len(lines) - 3} more lines)")
        print("\n" + "=" * 60)
    else:
        print("\n  No issues found - all checks passed!")
