"""Ralph Wiggum v2 - Thorough API testing from the perspective of Sarah,
a parent of 4-year-old Lily in Milton Keynes (MK5 6EX), working until 5:30pm.

Probes every endpoint for real bugs, edge cases, data quality issues, and
missing features that a real parent would encounter.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.db.models import Base, School
from src.db.sqlite_repo import SQLiteSchoolRepository
from src.main import app
from tests.seed_test_data import (
    _generate_private_school_details,
    _generate_test_admissions,
    _generate_test_clubs,
    _generate_test_performance,
    _generate_test_schools,
    _seed_term_dates,
)

# ============================================================================
# Issue collector
# ============================================================================

_ISSUES: list[dict] = []


def _add_issue(
    category: str,
    severity: str,
    title: str,
    body: str,
    steps_to_reproduce: str = "",
) -> None:
    _ISSUES.append(
        {
            "category": category,
            "severity": severity,
            "title": title,
            "body": body,
            "steps_to_reproduce": steps_to_reproduce,
        }
    )


# ============================================================================
# Database and client fixtures - full seed data
# ============================================================================


@pytest.fixture(scope="module")
def seeded_db_path(tmp_path_factory) -> str:
    """Create a fully-seeded SQLite database with all data types."""
    tmp = tmp_path_factory.mktemp("ralph_v2")
    path = str(tmp / "test_schools.db")
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)

    council = "Milton Keynes"
    with Session(engine) as session:
        # 1) Insert schools from seed generator
        schools = _generate_test_schools(council)
        session.add_all(schools)
        session.commit()

        # Re-fetch so IDs are set
        all_schools = session.query(School).all()

        # 2) Clubs
        clubs = _generate_test_clubs(all_schools)
        session.add_all(clubs)
        session.commit()

        # 3) Term dates
        _seed_term_dates(session, council)

        # 4) Performance
        _generate_test_performance(all_schools, session)

        # 5) Admissions
        _generate_test_admissions(all_schools, session)

        # 6) Private school details
        _generate_private_school_details(session)

    engine.dispose()
    return path


@pytest.fixture(scope="module")
def client(seeded_db_path) -> TestClient:
    """FastAPI TestClient wired to the fully-seeded test database."""
    repo = SQLiteSchoolRepository(seeded_db_path)

    def _override() -> SchoolRepository:
        return repo

    app.dependency_overrides[get_school_repository] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ============================================================================
# Sarah's coordinates for MK5 6EX (from fallback table / approximate)
# ============================================================================

SARAH_LAT = 52.0115
SARAH_LNG = -0.7920
SARAH_POSTCODE = "MK5 6EX"


# ============================================================================
# 1. BASIC FLOW - Search, browse, detail
# ============================================================================


class TestBasicSearchFlow:
    """Sarah's first interaction: search for schools near her home."""

    def test_councils_endpoint_returns_mk(self, client: TestClient):
        """The councils endpoint should list Milton Keynes."""
        resp = client.get("/api/councils")
        assert resp.status_code == 200
        councils = resp.json()
        assert "Milton Keynes" in councils

    def test_search_schools_for_mk(self, client: TestClient):
        """Basic search for Milton Keynes state schools."""
        resp = client.get("/api/schools", params={"council": "Milton Keynes"})
        assert resp.status_code == 200
        schools = resp.json()
        assert len(schools) > 0, "Expected schools in Milton Keynes"

    def test_search_schools_near_mk5_6ex_for_4yo_girl(self, client: TestClient):
        """Sarah searches for schools for her 4yo daughter Lily."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "lat": SARAH_LAT,
                "lng": SARAH_LNG,
                "age": 4,
                "gender": "female",
                "max_distance_km": 5.0,
            },
        )
        assert resp.status_code == 200
        schools = resp.json()

        if len(schools) == 0:
            # This is the critical gender filter bug: 'Mixed' vs 'co-ed'
            _add_issue(
                "bug",
                "critical",
                "Sarah's primary search returns 0 schools (gender filter broken)",
                "Searching for schools near MK5 6EX for a 4-year-old girl "
                "returns 0 results. The SQLite repo filters "
                "gender_policy IN ('co-ed', 'girls') but seed data uses "
                "'Mixed' not 'co-ed'. This is the single most important "
                "user flow and it is completely broken.",
                "GET /api/schools?council=Milton+Keynes&lat=52.0115&lng=-0.792&age=4&gender=female&max_distance_km=5.0",
            )
            return

        # All results should accept age 4
        for s in schools:
            if s["age_range_from"] is not None:
                assert s["age_range_from"] <= 4, f"{s['name']} has age_range_from={s['age_range_from']}, should be <= 4"
            if s["age_range_to"] is not None:
                assert s["age_range_to"] >= 4, f"{s['name']} has age_range_to={s['age_range_to']}, should be >= 4"

        # No boys-only schools
        for s in schools:
            if s["gender_policy"] is not None:
                gender = s["gender_policy"].lower()
                if gender == "boys":
                    _add_issue(
                        "bug",
                        "high",
                        "Boys-only school shown for female filter",
                        f"School '{s['name']}' has gender_policy='Boys' but "
                        f"appears in results when gender=female. "
                        f"Expected: only co-ed and girls schools.",
                        "GET /api/schools?gender=female&council=Milton Keynes",
                    )

    def test_each_school_has_detail_page(self, client: TestClient):
        """Every school returned in a list should have a working detail page."""
        resp = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        )
        schools = resp.json()
        # Test first 10
        for s in schools[:10]:
            detail_resp = client.get(f"/api/schools/{s['id']}")
            assert detail_resp.status_code == 200, (
                f"School {s['id']} ({s['name']}) detail page returned {detail_resp.status_code}"
            )

    def test_school_detail_includes_all_sections(self, client: TestClient):
        """Detail response should have clubs, performance, term_dates, admissions, etc."""
        resp = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        )
        schools = resp.json()
        # Find a state primary school (likely to have data)
        primary = None
        for s in schools:
            if (
                s.get("age_range_from") is not None
                and s["age_range_from"] <= 4
                and s.get("age_range_to", 0) <= 11
                and not s.get("is_private", False)
            ):
                primary = s
                break

        if primary is None:
            pytest.skip("No primary school found to test")

        detail = client.get(f"/api/schools/{primary['id']}").json()
        expected_keys = {"clubs", "performance", "term_dates", "admissions_history"}
        missing = expected_keys - set(detail.keys())
        if missing:
            _add_issue(
                "bug",
                "high",
                f"School detail response missing keys: {missing}",
                f"School '{primary['name']}' detail is missing {missing}. "
                f"A parent needs all of this data on a single page.",
                f"GET /api/schools/{primary['id']}",
            )


# ============================================================================
# 2. POSTCODE EDGE CASES
# ============================================================================


class TestPostcodeEdgeCases:
    """Postcodes with different formatting."""

    def test_postcode_with_space(self, client: TestClient):
        """MK5 6EX (standard format) should work."""
        resp = client.get("/api/geocode", params={"postcode": "MK5 6EX"})
        # May fail if external API is unavailable and not in fallback table
        if resp.status_code == 200:
            data = resp.json()
            assert abs(data["lat"] - 52.0) < 0.2
            assert abs(data["lng"] - (-0.8)) < 0.2
        elif resp.status_code == 404:
            _add_issue(
                "bug",
                "high",
                "MK5 6EX not in fallback postcode table",
                "Sarah's postcode MK5 6EX returns 404 when geocoded. "
                "It should be in the fallback table since the app targets "
                "Milton Keynes parents. MK5 6EX is the postcode for "
                "Denbigh School and nearby residential area.",
                "GET /api/geocode?postcode=MK5+6EX",
            )

    def test_postcode_lowercase(self, client: TestClient):
        """mk5 6ex (lowercase) should also work."""
        resp = client.get("/api/geocode", params={"postcode": "mk5 6ex"})
        # The normaliser should handle this
        if resp.status_code == 200:
            data = resp.json()
            assert "lat" in data
        elif resp.status_code == 404:
            # Not necessarily a bug if the postcode itself is missing
            pass

    def test_postcode_no_space(self, client: TestClient):
        """MK56EX (no space) should also work."""
        resp = client.get("/api/geocode", params={"postcode": "MK56EX"})
        if resp.status_code == 404:
            _add_issue(
                "bug",
                "medium",
                "Postcode without space not normalised properly",
                "MK56EX (no space) returns 404. The normaliser uses "
                "' '.join(postcode.upper().split()) which won't insert "
                "a space into 'MK56EX' -- it stays as 'MK56EX'. "
                "Should split outward/inward codes properly.",
                "GET /api/geocode?postcode=MK56EX",
            )

    def test_postcode_empty_string(self, client: TestClient):
        """Empty postcode should return a clear error."""
        resp = client.get("/api/geocode", params={"postcode": ""})
        if resp.status_code == 200:
            _add_issue(
                "bug",
                "medium",
                "Empty postcode returns 200",
                "An empty postcode string should return 400 or 422, not 200.",
                "GET /api/geocode?postcode=",
            )


# ============================================================================
# 3. AGE FILTER EDGE CASES
# ============================================================================


class TestAgeFilterEdgeCases:
    """What happens with extreme age values?"""

    def test_age_zero(self, client: TestClient):
        """Age 0 - should return nurseries or nothing, not crash."""
        resp = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "age": 0},
        )
        assert resp.status_code == 200
        schools = resp.json()
        # Schools with age_range_from=0 do exist (Webber Independent)
        for s in schools:
            assert s["age_range_from"] <= 0
            assert s["age_range_to"] >= 0

    def test_age_25(self, client: TestClient):
        """Age 25 - beyond school age, should return empty list."""
        resp = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "age": 25},
        )
        assert resp.status_code == 200
        schools = resp.json()
        # Most schools only go up to 18-19
        for s in schools:
            if s["age_range_to"] is not None:
                assert s["age_range_to"] >= 25

    def test_age_negative(self, client: TestClient):
        """Age -1 - should return empty or 400."""
        resp = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "age": -1},
        )
        if resp.status_code == 200:
            schools = resp.json()
            if len(schools) > 0:
                _add_issue(
                    "bug",
                    "medium",
                    "Negative age returns results",
                    "age=-1 returns schools. No school accepts negative age "
                    "students. The API should validate age >= 0.",
                    "GET /api/schools?council=Milton+Keynes&age=-1",
                )
        # 422 is also acceptable (validation error)


# ============================================================================
# 4. DISTANCE FILTER EDGE CASES
# ============================================================================


class TestDistanceFilterEdgeCases:
    """Distance filter probing."""

    def test_distance_zero(self, client: TestClient):
        """max_distance_km=0 should return no schools (or the closest ones)."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "lat": SARAH_LAT,
                "lng": SARAH_LNG,
                "max_distance_km": 0,
            },
        )
        assert resp.status_code == 200
        schools = resp.json()
        # Technically 0km means the school must be at exactly this point
        # Should return 0 or maybe 1 school at that exact postcode
        if len(schools) > 3:
            _add_issue(
                "bug",
                "medium",
                "max_distance_km=0 returns many schools",
                f"Expected 0-1 schools at distance 0, got {len(schools)}. "
                f"This means the distance filter is not working properly.",
                "GET /api/schools?max_distance_km=0&lat=52.0115&lng=-0.792",
            )

    def test_very_small_distance(self, client: TestClient):
        """max_distance_km=0.001 (1 metre) - practically zero."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "lat": SARAH_LAT,
                "lng": SARAH_LNG,
                "max_distance_km": 0.001,
            },
        )
        assert resp.status_code == 200
        schools = resp.json()
        assert len(schools) <= 1, f"At 1 metre distance, expected 0-1 schools, got {len(schools)}"

    def test_distances_are_reasonable_for_mk(self, client: TestClient):
        """Schools in Milton Keynes should be within ~20km, not 1000km."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "lat": SARAH_LAT,
                "lng": SARAH_LNG,
                "max_distance_km": 50.0,
            },
        )
        assert resp.status_code == 200
        schools = resp.json()
        for s in schools:
            if s.get("lat") and s.get("lng"):
                # Rough check: all MK schools should be within 25km
                # of MK5 6EX
                lat_diff = abs(s["lat"] - SARAH_LAT)
                lng_diff = abs(s["lng"] - SARAH_LNG)
                # 0.1 degree ~ 11km
                if lat_diff > 0.25 or lng_diff > 0.25:
                    _add_issue(
                        "bug",
                        "medium",
                        f"School '{s['name']}' seems too far from MK",
                        f"Coordinates ({s['lat']}, {s['lng']}) are far from "
                        f"MK5 6EX ({SARAH_LAT}, {SARAH_LNG}). Lat diff="
                        f"{lat_diff:.4f}, lng diff={lng_diff:.4f}.",
                        "GET /api/schools?council=Milton+Keynes",
                    )


# ============================================================================
# 5. COUNCIL EDGE CASES
# ============================================================================


class TestCouncilEdgeCases:
    """Non-existent council, casing, etc."""

    def test_nonexistent_council(self, client: TestClient):
        """Searching for a council that doesn't exist."""
        resp = client.get(
            "/api/schools",
            params={"council": "Narnia"},
        )
        assert resp.status_code == 200
        schools = resp.json()
        assert len(schools) == 0, "Narnia should have no schools"

    def test_council_case_sensitivity(self, client: TestClient):
        """'milton keynes' lowercase - does it still work?"""
        resp = client.get(
            "/api/schools",
            params={"council": "milton keynes"},
        )
        assert resp.status_code == 200
        schools = resp.json()
        if len(schools) == 0:
            _add_issue(
                "bug",
                "medium",
                "Council filter is case-sensitive",
                "'milton keynes' (lowercase) returns 0 results, but "
                "'Milton Keynes' returns many. The council filter should "
                "be case-insensitive.",
                "GET /api/schools?council=milton+keynes",
            )


# ============================================================================
# 6. GENDER FILTER LOGIC
# ============================================================================


class TestGenderFilter:
    """Gender filter should exclude incompatible schools."""

    def test_gender_female_shows_girls_and_coed(self, client: TestClient):
        """Filtering for females should show co-ed and girls-only schools."""
        resp = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "gender": "female"},
        )
        assert resp.status_code == 200
        schools = resp.json()
        for s in schools:
            gp = (s.get("gender_policy") or "").lower()
            if gp == "boys":
                _add_issue(
                    "bug",
                    "critical",
                    "Boys-only school shown for female gender filter",
                    f"'{s['name']}' has gender_policy='Boys' but appears in gender=female results.",
                    "GET /api/schools?gender=female&council=Milton+Keynes",
                )

    def test_gender_filter_recognises_mixed(self, client: TestClient):
        """The seed data uses 'Mixed' not 'co-ed'. Does the filter handle it?"""
        resp = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "gender": "female"},
        )
        schools = resp.json()
        # The repository code checks for "co-ed" and "girls"
        # But seed data uses "Mixed" for gender_policy!
        if len(schools) == 0:
            _add_issue(
                "bug",
                "critical",
                "Gender filter returns 0 results due to 'Mixed' vs 'co-ed' mismatch",
                "The SQLite repo filters gender_policy IN ('co-ed', 'girls') "
                "for female queries, but the seed data uses 'Mixed' (not 'co-ed'). "
                "This means gender=female returns 0 schools, which is completely "
                "broken for Sarah trying to find schools for her daughter.",
                "GET /api/schools?gender=female&council=Milton+Keynes",
            )

    def test_thornton_college_shows_for_girls(self, client: TestClient):
        """Thornton College is girls-only. Should appear for gender=female."""
        resp = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "gender": "female"},
        )
        schools = resp.json()
        names = [s["name"] for s in schools]
        # We expect Thornton College (gender_policy="Girls") to show up
        # but the filter checks for 'girls' lowercase vs 'Girls' stored value
        thornton_found = any("Thornton" in n for n in names)
        if not thornton_found and len(schools) > 0:
            _add_issue(
                "bug",
                "high",
                "Thornton College (girls-only) not found with gender=female",
                "Thornton College has gender_policy='Girls' but does not "
                "appear in gender=female results. The filter may be doing "
                "case-sensitive comparison ('girls' vs 'Girls').",
                "GET /api/schools?gender=female&council=Milton+Keynes",
            )


# ============================================================================
# 7. RATING FILTER
# ============================================================================


class TestRatingFilter:
    """Minimum Ofsted rating filter."""

    def test_outstanding_filter(self, client: TestClient):
        """Only Outstanding schools should appear."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "min_rating": "Outstanding",
            },
        )
        assert resp.status_code == 200
        schools = resp.json()
        for s in schools:
            assert s.get("ofsted_rating") == "Outstanding", (
                f"School '{s['name']}' has rating '{s.get('ofsted_rating')}' but should be Outstanding only"
            )

    def test_outstanding_and_age_4_gives_results(self, client: TestClient):
        """Outstanding + age 4 should still return some schools."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "min_rating": "Outstanding",
                "age": 4,
            },
        )
        assert resp.status_code == 200
        schools = resp.json()
        # From seed data, there are several Outstanding primaries
        if len(schools) == 0:
            _add_issue(
                "feature_request",
                "medium",
                "No Outstanding schools for age 4 in results",
                "When filtering Outstanding + age=4 in Milton Keynes, "
                "no results. The seed data has Outstanding primaries "
                "like Caroline Haslett and Oxley Park. Something may "
                "be wrong with filter combination.",
                "GET /api/schools?council=Milton+Keynes&min_rating=Outstanding&age=4",
            )


# ============================================================================
# 8. CLUB FILTERS
# ============================================================================


class TestClubFilters:
    """Finding schools with breakfast and/or after-school clubs."""

    def test_breakfast_club_filter(self, client: TestClient):
        """Filter for schools with breakfast clubs."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "has_breakfast_club": True,
            },
        )
        assert resp.status_code == 200
        schools = resp.json()
        if len(schools) == 0:
            pytest.skip("No club data seeded (clubs come from agent, not seed)")

    def test_afterschool_club_filter(self, client: TestClient):
        """Filter for schools with after-school clubs."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "has_afterschool_club": True,
            },
        )
        assert resp.status_code == 200
        schools = resp.json()
        if len(schools) == 0:
            pytest.skip("No club data seeded (clubs come from agent, not seed)")

    def test_both_clubs_filter(self, client: TestClient):
        """Sarah works until 5:30 - she needs BOTH breakfast AND after-school."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "has_breakfast_club": True,
                "has_afterschool_club": True,
            },
        )
        assert resp.status_code == 200
        schools = resp.json()
        if len(schools) == 0:
            _add_issue(
                "enhancement",
                "high",
                "No schools with both breakfast and after-school clubs",
                "Sarah works until 5:30pm. She needs schools that have "
                "BOTH breakfast and after-school clubs. Filtering for both "
                "returns 0 results. Either the data is incomplete or the "
                "filter combination doesn't work properly.",
                "GET /api/schools?has_breakfast_club=true&has_afterschool_club=true",
            )

    def test_club_details_make_sense(self, client: TestClient):
        """Club times and costs should be sensible."""
        resp = client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "has_breakfast_club": True},
        )
        schools = resp.json()
        if schools:
            school_id = schools[0]["id"]
            clubs_resp = client.get(f"/api/schools/{school_id}/clubs")
            assert clubs_resp.status_code == 200
            clubs = clubs_resp.json()
            for club in clubs:
                if club["club_type"] == "breakfast":
                    # Breakfast should start before 9am
                    if club.get("start_time"):
                        hour = int(club["start_time"].split(":")[0])
                        assert hour < 9, f"Breakfast club starts at {club['start_time']}, should be before 9am"
                if club.get("cost_per_session") is not None:
                    cost = club["cost_per_session"]
                    assert 0 <= cost <= 30, f"Club cost {cost} seems unreasonable"


# ============================================================================
# 9. PRIVATE SCHOOLS
# ============================================================================


class TestPrivateSchools:
    """Private school listing, fees, and details."""

    def test_list_private_schools(self, client: TestClient):
        """List all private schools in Milton Keynes."""
        resp = client.get(
            "/api/private-schools",
            params={"council": "Milton Keynes"},
        )
        assert resp.status_code == 200
        schools = resp.json()
        assert len(schools) > 0, "Should find private schools in MK"
        for s in schools:
            assert s["is_private"] is True

    def test_private_school_detail_has_fees(self, client: TestClient):
        """Private school details should include fee information."""
        resp = client.get(
            "/api/private-schools",
            params={"council": "Milton Keynes"},
        )
        schools = resp.json()
        for s in schools:
            detail_resp = client.get(f"/api/private-schools/{s['id']}")
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            if not detail.get("private_details"):
                _add_issue(
                    "bug",
                    "high",
                    f"Private school '{s['name']}' missing fee details",
                    f"Private school '{s['name']}' has no private_details. "
                    f"A parent needs to see fees to make a decision.",
                    f"GET /api/private-schools/{s['id']}",
                )
            else:
                for pd in detail["private_details"]:
                    if pd.get("annual_fee") is None:
                        _add_issue(
                            "bug",
                            "medium",
                            "Private school detail missing annual_fee",
                            f"Private detail record for '{s['name']}' "
                            f"({pd.get('fee_age_group', '?')}) has no "
                            f"annual_fee.",
                            f"GET /api/private-schools/{s['id']}",
                        )

    def test_fee_increase_pct_returned(self, client: TestClient):
        """fee_increase_pct should be present in private school details."""
        resp = client.get(
            "/api/private-schools",
            params={"council": "Milton Keynes"},
        )
        schools = resp.json()
        found_any_pct = False
        for s in schools:
            detail = client.get(f"/api/private-schools/{s['id']}").json()
            for pd in detail.get("private_details", []):
                if pd.get("fee_increase_pct") is not None:
                    found_any_pct = True
                    # Should be a reasonable percentage (e.g. 2-10%)
                    pct = pd["fee_increase_pct"]
                    if pct < 0 or pct > 20:
                        _add_issue(
                            "bug",
                            "medium",
                            f"Unreasonable fee_increase_pct={pct}",
                            f"'{s['name']}' has fee_increase_pct={pct}%. Expected 0-20% range.",
                            f"GET /api/private-schools/{s['id']}",
                        )

        if not found_any_pct:
            _add_issue(
                "bug",
                "medium",
                "No private school has fee_increase_pct",
                "fee_increase_pct is never returned in any private school "
                "detail. This field is defined in the schema but may not "
                "be populated.",
                "GET /api/private-schools/{id}",
            )

    def test_cheapest_private_school_for_4yo(self, client: TestClient):
        """What's the cheapest private option for a 4-year-old?"""
        resp = client.get(
            "/api/private-schools",
            params={"council": "Milton Keynes", "age": 4},
        )
        schools = resp.json()
        cheapest_fee = None

        for s in schools:
            detail = client.get(f"/api/private-schools/{s['id']}").json()
            for pd in detail.get("private_details", []):
                fee = pd.get("annual_fee")
                if fee is not None:
                    if cheapest_fee is None or fee < cheapest_fee:
                        cheapest_fee = fee

        if cheapest_fee is not None:
            # Should be a realistic UK private school fee
            assert 3000 < cheapest_fee < 30000, f"Cheapest private school fee {cheapest_fee} seems unrealistic"


# ============================================================================
# 10. JOURNEY PLANNER
# ============================================================================


class TestJourneyPlanner:
    """Journey calculations for the school run."""

    def test_journey_to_nearest_school(self, client: TestClient):
        """Calculate journey to a school near MK5 6EX."""
        # Find a school near Sarah
        schools = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "lat": SARAH_LAT,
                "lng": SARAH_LNG,
                "max_distance_km": 3.0,
            },
        ).json()

        if not schools:
            pytest.skip("No nearby schools found")

        school_id = schools[0]["id"]
        resp = client.get(
            "/api/journey",
            params={
                "from_postcode": SARAH_POSTCODE,
                "to_school_id": school_id,
                "mode": "walking",
            },
        )
        assert resp.status_code == 200
        journey = resp.json()

        # Basic sanity
        assert journey["distance_km"] >= 0
        assert journey["dropoff"]["duration_minutes"] >= 0
        assert journey["pickup"]["duration_minutes"] >= 0

    def test_walking_time_is_reasonable(self, client: TestClient):
        """Walking 1km shouldn't take 60 minutes."""
        schools = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "lat": SARAH_LAT,
                "lng": SARAH_LNG,
                "max_distance_km": 2.0,
            },
        ).json()

        if not schools:
            pytest.skip("No nearby schools")

        school_id = schools[0]["id"]
        resp = client.get(
            "/api/journey",
            params={
                "from_postcode": SARAH_POSTCODE,
                "to_school_id": school_id,
                "mode": "walking",
            },
        )
        if resp.status_code != 200:
            pytest.skip(f"Journey endpoint returned {resp.status_code}")

        journey = resp.json()
        dist = journey["distance_km"]
        duration = journey["dropoff"]["duration_minutes"]

        if dist > 0:
            # Walking speed ~5km/h -> 12 min/km. Allow some route factor.
            max_reasonable = dist * 25  # 25 min/km is very generous
            if duration > max_reasonable:
                _add_issue(
                    "bug",
                    "high",
                    f"Walking time unreasonable: {duration:.1f}min for {dist:.1f}km",
                    f"Walking {dist:.1f}km takes {duration:.1f} minutes. "
                    f"At 5km/h with 1.3x route factor, expected ~{dist * 1.3 / 5 * 60:.0f}min.",
                    f"GET /api/journey?from_postcode=MK5+6EX&to_school_id={school_id}&mode=walking",
                )

    def test_driving_rush_hour_is_slower(self, client: TestClient):
        """Driving at 8am should be slower than off-peak."""
        schools = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "lat": SARAH_LAT,
                "lng": SARAH_LNG,
                "max_distance_km": 5.0,
            },
        ).json()

        if not schools:
            pytest.skip("No nearby schools")

        school_id = schools[0]["id"]
        resp = client.get(
            "/api/journey",
            params={
                "from_postcode": SARAH_POSTCODE,
                "to_school_id": school_id,
                "mode": "driving",
            },
        )
        if resp.status_code != 200:
            pytest.skip(f"Journey endpoint returned {resp.status_code}")

        journey = resp.json()
        dropoff_time = journey["dropoff"]["duration_minutes"]
        offpeak_time = journey["off_peak"]["duration_minutes"]

        assert journey["dropoff"]["is_rush_hour"] is True
        assert journey["off_peak"]["is_rush_hour"] is False

        if dropoff_time <= offpeak_time:
            _add_issue(
                "bug",
                "high",
                "Driving at rush hour not slower than off-peak",
                f"Dropoff (rush hour) = {dropoff_time:.1f}min, "
                f"Off-peak = {offpeak_time:.1f}min. Rush hour should "
                f"be slower for driving. The time multiplier may not "
                f"be applied correctly.",
                f"GET /api/journey?from_postcode=MK5+6EX&to_school_id={school_id}&mode=driving",
            )

    def test_invalid_travel_mode(self, client: TestClient):
        """mode='helicopter' should return 400."""
        schools = client.get("/api/schools", params={"council": "Milton Keynes"}).json()
        if not schools:
            pytest.skip("No schools")

        resp = client.get(
            "/api/journey",
            params={
                "from_postcode": SARAH_POSTCODE,
                "to_school_id": schools[0]["id"],
                "mode": "helicopter",
            },
        )
        assert resp.status_code == 400, f"Invalid mode 'helicopter' should return 400, got {resp.status_code}"

    def test_journey_compare_multiple_schools(self, client: TestClient):
        """Compare journeys to multiple schools."""
        schools = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "lat": SARAH_LAT,
                "lng": SARAH_LNG,
                "max_distance_km": 5.0,
            },
        ).json()

        if len(schools) < 2:
            pytest.skip("Not enough schools")

        ids = ",".join(str(s["id"]) for s in schools[:4])
        resp = client.get(
            "/api/journey/compare",
            params={
                "from_postcode": SARAH_POSTCODE,
                "school_ids": ids,
                "mode": "walking",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["journeys"]) >= 2

        # Should be sorted by dropoff duration (shortest first)
        durations = [j["dropoff"]["duration_minutes"] for j in data["journeys"]]
        assert durations == sorted(durations), f"Journeys not sorted by dropoff duration: {durations}"

    def test_journey_to_nonexistent_school(self, client: TestClient):
        """Journey to school_id=99999 should return 404."""
        resp = client.get(
            "/api/journey",
            params={
                "from_postcode": SARAH_POSTCODE,
                "to_school_id": 99999,
                "mode": "walking",
            },
        )
        assert resp.status_code == 404


# ============================================================================
# 11. COMPARE ENDPOINT
# ============================================================================


class TestCompareEndpoint:
    """Side-by-side school comparison."""

    def test_compare_two_schools(self, client: TestClient):
        """Compare two schools returns full detail for both."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if len(schools) < 2:
            pytest.skip("Not enough schools")

        ids = f"{schools[0]['id']},{schools[1]['id']}"
        resp = client.get("/api/compare", params={"ids": ids})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["schools"]) == 2

        # Each school in compare should have clubs, performance, etc.
        for s in data["schools"]:
            required_fields = ["clubs", "performance", "term_dates", "admissions_history"]
            for field in required_fields:
                assert field in s, f"Compare response for '{s['name']}' missing '{field}'"

    def test_compare_same_school_with_itself(self, client: TestClient):
        """Compare a school with itself - should work but is useless."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if not schools:
            pytest.skip("No schools")

        sid = schools[0]["id"]
        resp = client.get("/api/compare", params={"ids": f"{sid},{sid}"})
        assert resp.status_code == 200
        data = resp.json()
        # It will likely return the school twice
        # This is a valid edge case -- user might accidentally add same school
        if len(data["schools"]) == 2:
            assert data["schools"][0]["name"] == data["schools"][1]["name"]
        elif len(data["schools"]) == 1:
            pass  # Dedup'd, also fine

    def test_compare_four_schools(self, client: TestClient):
        """Compare 4 schools - the common use case for decision making."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if len(schools) < 4:
            pytest.skip("Not enough schools")

        ids = ",".join(str(s["id"]) for s in schools[:4])
        resp = client.get("/api/compare", params={"ids": ids})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["schools"]) == 4

    def test_compare_nonexistent_school(self, client: TestClient):
        """Comparing with a non-existent school_id should gracefully skip."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if not schools:
            pytest.skip("No schools")

        ids = f"{schools[0]['id']},99999"
        resp = client.get("/api/compare", params={"ids": ids})
        assert resp.status_code == 200
        data = resp.json()
        # Should return 1 school (the valid one) and skip 99999
        assert len(data["schools"]) >= 1


# ============================================================================
# 12. TERM DATES
# ============================================================================


class TestTermDates:
    """Term date data quality."""

    def test_term_dates_exist(self, client: TestClient):
        """Schools should have term date data."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        has_term_dates = False
        for s in schools[:10]:
            resp = client.get(f"/api/schools/{s['id']}/term-dates")
            assert resp.status_code == 200
            dates = resp.json()
            if dates:
                has_term_dates = True
                break

        if not has_term_dates:
            pytest.skip("No term date data (comes from term_times agent, not seed)")

    def test_term_dates_correct_year(self, client: TestClient):
        """Term dates should be for 2025-2026 academic year."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        for s in schools[:5]:
            dates = client.get(f"/api/schools/{s['id']}/term-dates").json()
            for td in dates:
                year = td.get("academic_year", "")
                assert "2025" in year or "2026" in year, (
                    f"Term date for {s['name']} has year '{year}', expected 2025/2026"
                )

    def test_term_date_ranges_make_sense(self, client: TestClient):
        """start_date should be before end_date."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        for s in schools[:5]:
            dates = client.get(f"/api/schools/{s['id']}/term-dates").json()
            for td in dates:
                if td.get("start_date") and td.get("end_date"):
                    assert td["start_date"] < td["end_date"], (
                        f"Term '{td['term_name']}' for {s['name']}: "
                        f"start_date ({td['start_date']}) >= "
                        f"end_date ({td['end_date']})"
                    )


# ============================================================================
# 13. PERFORMANCE DATA
# ============================================================================


class TestPerformanceData:
    """Academic performance metric sanity checks."""

    def test_performance_data_exists(self, client: TestClient):
        """Some schools should have performance data."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        has_perf = False
        for s in schools[:20]:
            resp = client.get(f"/api/schools/{s['id']}/performance")
            assert resp.status_code == 200
            perf = resp.json()
            if perf:
                has_perf = True
                break

        if not has_perf:
            pytest.skip("No performance data (comes from EES API, not seed)")

    def test_progress8_values_sensible(self, client: TestClient):
        """Progress8 scores should be between -2 and +2."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        for s in schools:
            perf = client.get(f"/api/schools/{s['id']}/performance").json()
            for p in perf:
                if p["metric_type"] == "Progress8":
                    # Parse the value (format is like "+0.34" or "-0.12")
                    val_str = p["metric_value"]
                    try:
                        val = float(val_str)
                        assert -2.0 <= val <= 2.0, f"Progress8 value {val} out of range for {s['name']}"
                    except ValueError:
                        _add_issue(
                            "bug",
                            "medium",
                            f"Progress8 value not parseable: '{val_str}'",
                            f"School '{s['name']}' has Progress8 value '{val_str}' which is not a valid number.",
                            f"GET /api/schools/{s['id']}/performance",
                        )

    def test_sats_percentages_sensible(self, client: TestClient):
        """SATs expected standard should be a % between 0 and 100."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        for s in schools[:20]:
            perf = client.get(f"/api/schools/{s['id']}/performance").json()
            for p in perf:
                if p["metric_type"] == "SATs":
                    val_str = p["metric_value"]
                    # Extract percentage
                    match = re.search(r"(\d+)%", val_str)
                    if match:
                        pct = int(match.group(1))
                        assert 0 <= pct <= 100, f"SATs % = {pct} for {s['name']}, out of range"


# ============================================================================
# 14. ADMISSIONS ESTIMATION
# ============================================================================


class TestAdmissionsEstimation:
    """Waiting list likelihood estimation."""

    def test_admissions_history_exists(self, client: TestClient):
        """State schools should have admissions history."""
        schools = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "age": 4,
            },
        ).json()

        has_admissions = False
        for s in schools[:10]:
            if s.get("is_private"):
                continue
            resp = client.get(f"/api/schools/{s['id']}/admissions")
            assert resp.status_code == 200
            admissions = resp.json()
            if admissions:
                has_admissions = True
                break

        if not has_admissions:
            pytest.skip("No admissions data (comes from EES API, not seed)")

    def test_admissions_estimate_close_distance(self, client: TestClient):
        """If I'm 0.5km away, should be 'Very likely' or 'Likely'."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        # Find a state school with admissions data
        for s in schools:
            if s.get("is_private"):
                continue
            admissions = client.get(f"/api/schools/{s['id']}/admissions").json()
            if admissions:
                resp = client.get(
                    f"/api/schools/{s['id']}/admissions/estimate",
                    params={"distance_km": 0.5},
                )
                assert resp.status_code == 200
                estimate = resp.json()
                likelihood = estimate["likelihood"]
                assert likelihood in [
                    "Very likely",
                    "Likely",
                    "Unlikely",
                    "Very unlikely",
                ], f"Unknown likelihood value: '{likelihood}'"

                if likelihood in ["Unlikely", "Very unlikely"]:
                    _add_issue(
                        "bug",
                        "medium",
                        f"0.5km distance gives '{likelihood}' for {s['name']}",
                        f"Living 0.5km from '{s['name']}' returns '{likelihood}'. "
                        f"For most schools, 0.5km should be Very likely or Likely. "
                        f"Avg last distance: {estimate.get('avg_last_distance_km')}km.",
                        f"GET /api/schools/{s['id']}/admissions/estimate?distance_km=0.5",
                    )
                break

    def test_admissions_estimate_far_distance(self, client: TestClient):
        """If I'm 10km away, should be 'Unlikely' or 'Very unlikely'."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        for s in schools:
            if s.get("is_private"):
                continue
            admissions = client.get(f"/api/schools/{s['id']}/admissions").json()
            if admissions:
                resp = client.get(
                    f"/api/schools/{s['id']}/admissions/estimate",
                    params={"distance_km": 10.0},
                )
                assert resp.status_code == 200
                estimate = resp.json()
                likelihood = estimate["likelihood"]
                if likelihood in ["Very likely", "Likely"]:
                    _add_issue(
                        "enhancement",
                        "low",
                        f"10km distance gives '{likelihood}' for {s['name']}",
                        f"Living 10km from '{s['name']}' returns '{likelihood}'. "
                        f"10km is very far for a school catchment. "
                        f"Avg last distance: {estimate.get('avg_last_distance_km')}km.",
                        f"GET /api/schools/{s['id']}/admissions/estimate?distance_km=10.0",
                    )
                break

    def test_admissions_estimate_nonexistent_school(self, client: TestClient):
        """Estimate for non-existent school should return 404."""
        resp = client.get(
            "/api/schools/99999/admissions/estimate",
            params={"distance_km": 1.0},
        )
        assert resp.status_code == 404


# ============================================================================
# 15. DECISION SUPPORT - SCORING
# ============================================================================


class TestDecisionScoring:
    """Weighted scoring, pros/cons, what-if scenarios."""

    def test_basic_scoring(self, client: TestClient):
        """Score some schools with default weights."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if len(schools) < 3:
            pytest.skip("Not enough schools")

        ids = ",".join(str(s["id"]) for s in schools[:3])
        resp = client.get("/api/decision/score", params={"school_ids": ids})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["schools"]) == 3
        assert "weights_used" in data

        # Scores should be 0-100
        for s in data["schools"]:
            score = s["composite_score"]
            assert 0 <= score <= 100, f"Score {score} out of 0-100 range"

        # Should be sorted by score (highest first)
        scores = [s["composite_score"] for s in data["schools"]]
        assert scores == sorted(scores, reverse=True), f"Schools not sorted by score: {scores}"

    def test_scoring_with_custom_weights(self, client: TestClient):
        """Custom weights: distance heavy."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if not schools:
            pytest.skip("No schools")

        ids = ",".join(str(s["id"]) for s in schools[:3])
        resp = client.get(
            "/api/decision/score",
            params={
                "school_ids": ids,
                "weights": "distance:0.9,ofsted:0.05,clubs:0.025,fees:0.025",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Weights should be normalised
        w = data["weights_used"]
        total = sum(w.values())
        assert abs(total - 1.0) < 0.01, f"Weights should sum to ~1.0, got {total}: {w}"

    def test_weights_sum_to_more_than_one(self, client: TestClient):
        """Weights summing to > 1 should still work (normalised internally)."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if not schools:
            pytest.skip("No schools")

        ids = str(schools[0]["id"])
        resp = client.get(
            "/api/decision/score",
            params={
                "school_ids": ids,
                "weights": "distance:5.0,ofsted:3.0,clubs:2.0,fees:1.0",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should normalise internally
        w = data["weights_used"]
        total = sum(w.values())
        assert abs(total - 1.0) < 0.01, f"Weights > 1 not normalised: {w}, sum={total}"

    def test_negative_weights(self, client: TestClient):
        """Negative weights should be handled gracefully."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if not schools:
            pytest.skip("No schools")

        ids = str(schools[0]["id"])
        resp = client.get(
            "/api/decision/score",
            params={
                "school_ids": ids,
                "weights": "distance:-0.5,ofsted:0.5,clubs:0.5,fees:0.5",
            },
        )
        # The code clamps negative weights to 0
        if resp.status_code == 200:
            data = resp.json()
            w = data["weights_used"]
            # distance weight should be 0 (clamped from -0.5)
            if w.get("distance", 0) < 0:
                _add_issue(
                    "bug",
                    "medium",
                    "Negative weight not clamped to 0",
                    f"distance weight = {w.get('distance')}, expected 0 "
                    f"(clamped from -0.5). Negative weights could produce "
                    f"counter-intuitive scores.",
                    "GET /api/decision/score?weights=distance:-0.5,...",
                )

    def test_score_nonexistent_school(self, client: TestClient):
        """Scoring non-existent school IDs should return 404."""
        resp = client.get(
            "/api/decision/score",
            params={"school_ids": "99999"},
        )
        assert resp.status_code == 404

    def test_score_empty_ids(self, client: TestClient):
        """Empty school_ids should return 400."""
        resp = client.get(
            "/api/decision/score",
            params={"school_ids": ""},
        )
        # Might return 400 or 500
        assert resp.status_code in (400, 422, 500)


# ============================================================================
# 16. PROS/CONS
# ============================================================================


class TestProsCons:
    """Auto-generated pros and cons."""

    def test_pros_cons_for_state_school(self, client: TestClient):
        """State school should have pros about being free."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        state_school = None
        for s in schools:
            if not s.get("is_private"):
                state_school = s
                break

        if state_school is None:
            pytest.skip("No state schools")

        resp = client.get(
            "/api/decision/pros-cons",
            params={"school_id": state_school["id"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["pros"]) > 0, "State school should have at least one pro"
        assert isinstance(data["cons"], list)

        # Should mention it's state-funded
        all_text = " ".join(data["pros"]).lower()
        assert "state" in all_text or "free" in all_text or "no tuition" in all_text, (
            f"Pros should mention state-funded/free: {data['pros']}"
        )

    def test_pros_cons_for_outstanding_school(self, client: TestClient):
        """Outstanding school should have that as a pro."""
        schools = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "min_rating": "Outstanding",
            },
        ).json()

        if not schools:
            pytest.skip("No Outstanding schools")

        resp = client.get(
            "/api/decision/pros-cons",
            params={"school_id": schools[0]["id"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        all_pros = " ".join(data["pros"]).lower()
        assert "outstanding" in all_pros, f"Outstanding school should have 'Outstanding' as a pro: {data['pros']}"

    def test_pros_cons_nonexistent_school(self, client: TestClient):
        """Pros/cons for non-existent school should return 404."""
        resp = client.get(
            "/api/decision/pros-cons",
            params={"school_id": 99999},
        )
        assert resp.status_code == 404


# ============================================================================
# 17. WHAT-IF SCENARIOS
# ============================================================================


class TestWhatIfScenarios:
    """What-if constraint re-ranking."""

    def test_what_if_max_distance(self, client: TestClient):
        """What if I'm OK with a 15min drive? (~ 5km)."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if len(schools) < 3:
            pytest.skip("Not enough schools")

        ids = [s["id"] for s in schools[:10]]
        resp = client.post(
            "/api/decision/what-if",
            json={
                "school_ids": ids,
                "max_distance_km": 5.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "schools" in data
        assert "filters_applied" in data

    def test_what_if_min_rating_good(self, client: TestClient):
        """What if I drop minimum to Good?"""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if not schools:
            pytest.skip("No schools")

        ids = [s["id"] for s in schools[:10]]
        resp = client.post(
            "/api/decision/what-if",
            json={
                "school_ids": ids,
                "min_rating": "Good",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        for s in data["schools"]:
            rating = s.get("ofsted_rating")
            assert rating in ["Outstanding", "Good", None], (
                f"School '{s['school_name']}' has rating '{rating}' which should be filtered by min_rating=Good"
            )

    def test_what_if_empty_school_ids(self, client: TestClient):
        """Empty school_ids should return 400."""
        resp = client.post(
            "/api/decision/what-if",
            json={"school_ids": []},
        )
        assert resp.status_code == 400

    def test_what_if_all_filtered_out(self, client: TestClient):
        """Aggressive filter that removes all schools."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if not schools:
            pytest.skip("No schools")

        ids = [s["id"] for s in schools[:5]]
        resp = client.post(
            "/api/decision/what-if",
            json={
                "school_ids": ids,
                "max_distance_km": 0.001,  # Almost no school is this close
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # All schools may be filtered out - this is fine if the response
        # is still valid
        assert isinstance(data["schools"], list)


# ============================================================================
# 18. PRIVATE SCHOOL SPECIFIC TESTS
# ============================================================================


class TestPrivateSchoolEndpoint:
    """The /api/private-schools endpoint."""

    def test_private_schools_only_returns_private(self, client: TestClient):
        """Should ONLY return private schools."""
        resp = client.get(
            "/api/private-schools",
            params={"council": "Milton Keynes"},
        )
        assert resp.status_code == 200
        schools = resp.json()
        for s in schools:
            assert s["is_private"] is True, f"'{s['name']}' is not private but appears in /api/private-schools"

    def test_private_school_journey(self, client: TestClient):
        """Can I calculate a journey to a private school?"""
        private_schools = client.get(
            "/api/private-schools",
            params={"council": "Milton Keynes"},
        ).json()

        if not private_schools:
            pytest.skip("No private schools")

        resp = client.get(
            "/api/journey",
            params={
                "from_postcode": SARAH_POSTCODE,
                "to_school_id": private_schools[0]["id"],
                "mode": "driving",
            },
        )
        # Should work for private schools too
        assert resp.status_code == 200

    def test_private_school_max_fee_filter(self, client: TestClient):
        """The max_fee filter param exists in the schema but is it implemented?"""
        resp = client.get(
            "/api/private-schools",
            params={"council": "Milton Keynes", "max_fee": 10000},
        )
        # Even if max_fee is accepted, check if it actually filters
        # (The _to_private_filters function doesn't use max_fee)
        if resp.status_code == 200:
            schools = resp.json()
            all_schools = client.get(
                "/api/private-schools",
                params={"council": "Milton Keynes"},
            ).json()
            if len(schools) == len(all_schools) and len(all_schools) > 0:
                _add_issue(
                    "bug",
                    "high",
                    "max_fee filter parameter accepted but not implemented",
                    "GET /api/private-schools?max_fee=10000 returns the same "
                    "number of schools as without the filter. The "
                    "_to_private_filters function ignores the max_fee param. "
                    "Parents need to filter private schools by price.",
                    "GET /api/private-schools?council=Milton+Keynes&max_fee=10000",
                )


# ============================================================================
# 19. SCHOOL DETAIL DATA QUALITY
# ============================================================================


class TestDataQuality:
    """Check that seeded data is realistic and complete."""

    def test_all_mk_schools_have_coordinates(self, client: TestClient):
        """Every school should have lat/lng for map display."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        missing_coords = []
        for s in schools:
            if s.get("lat") is None or s.get("lng") is None:
                missing_coords.append(s["name"])

        if missing_coords:
            _add_issue(
                "bug",
                "high",
                f"{len(missing_coords)} schools missing coordinates",
                f"Schools without lat/lng can't appear on the map: "
                f"{missing_coords[:5]}{'...' if len(missing_coords) > 5 else ''}",
                "GET /api/schools?council=Milton+Keynes",
            )

    def test_school_postcodes_are_mk(self, client: TestClient):
        """All MK schools should have MK postcodes."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        for s in schools:
            pc = s.get("postcode", "")
            if pc and not pc.upper().startswith("MK"):
                _add_issue(
                    "enhancement",
                    "low",
                    f"School '{s['name']}' has non-MK postcode: {pc}",
                    f"A Milton Keynes school has postcode '{pc}'. "
                    f"While edge-of-boundary schools may have non-MK "
                    f"postcodes, this could confuse parents.",
                    f"GET /api/schools/{s['id']}",
                )

    def test_ofsted_ratings_are_valid(self, client: TestClient):
        """Ofsted ratings should only be standard values."""
        valid_ratings = {
            "Outstanding",
            "Good",
            "Requires Improvement",
            "Requires improvement",  # case variation
            "Inadequate",
            None,
        }
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        for s in schools:
            rating = s.get("ofsted_rating")
            if rating is not None and rating not in valid_ratings:
                _add_issue(
                    "bug",
                    "medium",
                    f"Invalid Ofsted rating: '{rating}'",
                    f"School '{s['name']}' has Ofsted rating '{rating}'. "
                    f"Valid values: Outstanding, Good, Requires Improvement, "
                    f"Inadequate.",
                    f"GET /api/schools/{s['id']}",
                )

    def test_age_ranges_make_sense(self, client: TestClient):
        """age_range_from should be < age_range_to."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        for s in schools:
            fr = s.get("age_range_from")
            to = s.get("age_range_to")
            if fr is not None and to is not None:
                assert fr < to, f"'{s['name']}' has age_range_from={fr} >= age_range_to={to}"


# ============================================================================
# 20. DISTANCE CALCULATION ENDPOINT ABSENT
# ============================================================================


class TestMissingDistanceOnResults:
    """Check if distance_km is populated on search results."""

    def test_distance_km_populated_when_lat_lng_given(self, client: TestClient):
        """When I provide lat/lng, results should include distance_km."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "lat": SARAH_LAT,
                "lng": SARAH_LNG,
                "max_distance_km": 5.0,
            },
        )
        schools = resp.json()
        if schools:
            first = schools[0]
            if first.get("distance_km") is None:
                _add_issue(
                    "feature_request",
                    "high",
                    "distance_km not populated on search results",
                    "When searching with lat/lng, the response includes "
                    "schools but distance_km is null. Parents need to see "
                    "how far each school is from their home. The API uses "
                    "haversine for filtering but doesn't return the computed "
                    "distance in the response.",
                    "GET /api/schools?lat=52.0115&lng=-0.792&max_distance_km=5.0",
                )


# ============================================================================
# 21. OFSTED RATING CASE MISMATCH
# ============================================================================


class TestOfstedCaseSensitivity:
    """Check if 'Requires improvement' vs 'Requires Improvement' causes issues."""

    def test_requires_improvement_casing(self, client: TestClient):
        """Seed data uses 'Requires improvement' (lowercase i),
        but the filter system uses 'Requires Improvement' (uppercase I)."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "min_rating": "Good",
            },
        )
        all_resp = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        )

        resp.json()
        all_schools = all_resp.json()

        # Check if any school has 'Requires improvement' (lowercase i)
        ri_lowercase = [s for s in all_schools if s.get("ofsted_rating") == "Requires improvement"]
        ri_uppercase = [s for s in all_schools if s.get("ofsted_rating") == "Requires Improvement"]

        if ri_lowercase and not ri_uppercase:
            _add_issue(
                "bug",
                "high",
                "Ofsted rating case mismatch: 'Requires improvement' vs 'Requires Improvement'",
                f"Found {len(ri_lowercase)} schools with 'Requires improvement' "
                f"(lowercase i). The filter system uses 'Requires Improvement' "
                f"(uppercase I) in its rating order. This means these schools "
                f"may not be properly filtered/excluded by the min_rating param. "
                f"Schools: {[s['name'] for s in ri_lowercase[:3]]}",
                "GET /api/schools?council=Milton+Keynes&min_rating=Good",
            )


# ============================================================================
# 22. GEOCODE ENDPOINT - MK5 6EX FALLBACK
# ============================================================================


class TestGeocodeForSarah:
    """Ensure Sarah's specific postcode MK5 6EX works."""

    def test_mk5_6ex_in_fallback_or_api(self, client: TestClient):
        """MK5 6EX must be geocodeable for Sarah to use the app."""
        resp = client.get("/api/geocode", params={"postcode": "MK5 6EX"})
        if resp.status_code != 200:
            _add_issue(
                "bug",
                "critical",
                "Cannot geocode MK5 6EX - Sarah can't use the app",
                f"GET /api/geocode?postcode=MK5+6EX returns {resp.status_code}. "
                f"This is the primary use case postcode. Without geocoding, "
                f"the entire distance-based search is broken for Sarah.",
                "GET /api/geocode?postcode=MK5+6EX",
            )
        else:
            data = resp.json()
            # Should be near Milton Keynes (lat ~52, lng ~-0.8)
            assert 51.9 < data["lat"] < 52.2
            assert -1.0 < data["lng"] < -0.5


# ============================================================================
# 23. SEARCH WITH ALL FILTERS COMBINED
# ============================================================================


class TestCombinedFilters:
    """Sarah's realistic search: Outstanding, age 4, girl, within 2km."""

    def test_sarahs_ideal_search(self, client: TestClient):
        """Outstanding + age 4 + female + 2km radius."""
        resp = client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "lat": SARAH_LAT,
                "lng": SARAH_LNG,
                "age": 4,
                "gender": "female",
                "min_rating": "Outstanding",
                "max_distance_km": 2.0,
            },
        )
        assert resp.status_code == 200
        schools = resp.json()

        # This is a real parent query. Even if no exact matches,
        # the API should return valid results
        for s in schools:
            assert s.get("ofsted_rating") == "Outstanding"
            if s.get("age_range_from") is not None:
                assert s["age_range_from"] <= 4

        if len(schools) == 0:
            _add_issue(
                "enhancement",
                "medium",
                "No Outstanding schools within 2km for 4yo girl at MK5 6EX",
                "Sarah's ideal search (Outstanding, age 4, female, 2km) "
                "returns no results. Nearby Outstanding primaries like "
                "Caroline Haslett (~1km) should appear. This might be "
                "a gender filter issue or distance calculation problem.",
                "GET /api/schools?council=Milton+Keynes&lat=52.0115&lng=-0.792"
                "&age=4&gender=female&min_rating=Outstanding&max_distance_km=2.0",
            )


# ============================================================================
# 24. API ERROR HANDLING
# ============================================================================


class TestErrorHandling:
    """Ensure the API handles bad input gracefully."""

    def test_school_id_not_found(self, client: TestClient):
        """Non-existent school ID should return 404."""
        resp = client.get("/api/schools/99999")
        assert resp.status_code == 404

    def test_school_id_zero(self, client: TestClient):
        """School ID 0 should return 404."""
        resp = client.get("/api/schools/0")
        assert resp.status_code == 404

    def test_school_id_negative(self, client: TestClient):
        """School ID -1."""
        resp = client.get("/api/schools/-1")
        # Should be 404 or 422
        assert resp.status_code in (404, 422)

    def test_compare_empty_ids(self, client: TestClient):
        """Empty ids parameter."""
        resp = client.get("/api/compare", params={"ids": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["schools"] == []

    def test_journey_compare_too_many_schools(self, client: TestClient):
        """More than 10 schools should be rejected."""
        ids = ",".join(str(i) for i in range(1, 15))
        resp = client.get(
            "/api/journey/compare",
            params={
                "from_postcode": SARAH_POSTCODE,
                "school_ids": ids,
                "mode": "walking",
            },
        )
        assert resp.status_code == 400

    def test_journey_compare_non_numeric_ids(self, client: TestClient):
        """Non-numeric IDs should return 400."""
        resp = client.get(
            "/api/journey/compare",
            params={
                "from_postcode": SARAH_POSTCODE,
                "school_ids": "abc,def",
                "mode": "walking",
            },
        )
        assert resp.status_code in (400, 422, 500)


# ============================================================================
# 25. PICKUP TIME FOR WORKING PARENT
# ============================================================================


class TestPickupTimeForWorkingParent:
    """Sarah works until 5:30pm. Pickup estimates should reflect 5pm window."""

    def test_pickup_is_rush_hour(self, client: TestClient):
        """Pickup journey should be flagged as rush hour."""
        schools = client.get(
            "/api/schools",
            params={"council": "Milton Keynes"},
        ).json()

        if not schools:
            pytest.skip("No schools")

        resp = client.get(
            "/api/journey",
            params={
                "from_postcode": SARAH_POSTCODE,
                "to_school_id": schools[0]["id"],
                "mode": "driving",
            },
        )
        if resp.status_code != 200:
            pytest.skip(f"Journey returned {resp.status_code}")

        journey = resp.json()
        assert journey["pickup"]["is_rush_hour"] is True, "Pickup (5pm) should be flagged as rush hour"
        assert journey["pickup"]["time_of_day"] == "pickup"


# ============================================================================
# FINAL SUMMARY - Print all issues as JSON
# ============================================================================


def test_zz_final_summary():
    """Print summary of all issues found during testing.

    Named with 'zz' prefix to run last.
    """
    if _ISSUES:
        print("\n" + "=" * 70)
        print(f"ISSUES FOUND: {len(_ISSUES)}")
        print("=" * 70)

        by_severity = {}
        for issue in _ISSUES:
            sev = issue["severity"]
            by_severity.setdefault(sev, []).append(issue)

        for sev in ["critical", "high", "medium", "low"]:
            issues = by_severity.get(sev, [])
            if issues:
                print(f"\n--- {sev.upper()} ({len(issues)}) ---")
                for i, issue in enumerate(issues, 1):
                    print(f"\n  [{i}] [{issue['category']}] {issue['title']}")
                    print(f"      {issue['body'][:200]}")

        print("\n" + "=" * 70)
        print("FULL JSON OUTPUT:")
        print("=" * 70)
        print(json.dumps(_ISSUES, indent=2))
    else:
        print("\n" + "=" * 70)
        print("NO ISSUES FOUND - ALL CLEAR")
        print("=" * 70)
