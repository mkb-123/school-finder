"""Tests that exercise the seed data – both by reading it directly and via the API.

These tests verify that _generate_test_schools() produces valid school records
and that the seeded database is queryable through the API layer.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.db.models import Base
from src.db.seed import _generate_test_schools
from src.db.sqlite_repo import SQLiteSchoolRepository
from src.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_db(tmp_path) -> str:
    """Create a temp DB populated with the real seed data and return its path."""
    path = str(tmp_path / "seed_test.db")
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)

    schools = _generate_test_schools("Milton Keynes")
    with Session(engine) as session:
        session.add_all(schools)
        session.commit()

    engine.dispose()
    return path


@pytest.fixture()
def seed_db_path(tmp_path) -> str:
    return _seed_db(tmp_path)


@pytest.fixture()
def seed_client(seed_db_path) -> TestClient:
    """TestClient backed by the real seed data."""
    repo = SQLiteSchoolRepository(seed_db_path)

    def _override() -> SchoolRepository:
        return repo

    app.dependency_overrides[get_school_repository] = _override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ===================================================================
# Direct seed-data tests (no API, read the generated list directly)
# ===================================================================


class TestSeedDataDirect:
    """Verify the seed data generator produces correct records."""

    def test_school_count_above_100(self):
        schools = _generate_test_schools("Milton Keynes")
        assert len(schools) >= 100, f"Expected 100+ schools, got {len(schools)}"

    def test_all_schools_have_required_fields(self):
        for s in _generate_test_schools("Milton Keynes"):
            assert s.name, f"School missing name: {s}"
            assert s.urn, f"School {s.name} missing URN"
            assert s.postcode, f"School {s.name} missing postcode"
            assert s.lat is not None, f"School {s.name} missing lat"
            assert s.lng is not None, f"School {s.name} missing lng"
            assert s.council == "Milton Keynes"

    def test_coordinates_in_mk_region(self):
        """All schools should be roughly in the Milton Keynes area."""
        for s in _generate_test_schools("Milton Keynes"):
            assert 51.8 < s.lat < 52.3, f"{s.name} lat {s.lat} out of range"
            assert -1.1 < s.lng < -0.5, f"{s.name} lng {s.lng} out of range"

    def test_contains_caroline_haslett(self):
        names = [s.name for s in _generate_test_schools("Milton Keynes")]
        assert any("Caroline Haslett" in n for n in names)

    def test_contains_thornton_college(self):
        schools = _generate_test_schools("Milton Keynes")
        thornton = [s for s in schools if "Thornton College" in s.name]
        assert len(thornton) == 1
        assert thornton[0].is_private is True
        assert thornton[0].gender_policy == "Girls"

    def test_contains_akeley_wood(self):
        schools = _generate_test_schools("Milton Keynes")
        akeley = [s for s in schools if "Akeley Wood" in s.name]
        assert len(akeley) >= 2, "Expected Senior + Junior Akeley Wood schools"
        assert all(s.is_private for s in akeley)

    def test_has_primary_and_secondary(self):
        schools = _generate_test_schools("Milton Keynes")
        primary = [s for s in schools if s.age_range_from <= 5 and s.age_range_to <= 12]
        secondary = [s for s in schools if s.age_range_from >= 11]
        assert len(primary) >= 50, f"Expected 50+ primary, got {len(primary)}"
        assert len(secondary) >= 10, f"Expected 10+ secondary, got {len(secondary)}"

    def test_has_private_schools(self):
        schools = _generate_test_schools("Milton Keynes")
        private = [s for s in schools if s.is_private]
        assert len(private) >= 3, f"Expected 3+ private, got {len(private)}"

    def test_ofsted_ratings_valid(self):
        valid = {"Outstanding", "Good", "Requires Improvement", "Inadequate", None}
        for s in _generate_test_schools("Milton Keynes"):
            assert s.ofsted_rating in valid, f"{s.name} has invalid rating: {s.ofsted_rating}"

    def test_age_ranges_sensible(self):
        for s in _generate_test_schools("Milton Keynes"):
            assert s.age_range_from < s.age_range_to, f"{s.name}: from={s.age_range_from} >= to={s.age_range_to}"
            assert 0 <= s.age_range_from <= 11
            assert 5 <= s.age_range_to <= 19

    def test_unique_urns(self):
        schools = _generate_test_schools("Milton Keynes")
        urns = [s.urn for s in schools]
        assert len(urns) == len(set(urns)), "Duplicate URNs found"


# ===================================================================
# API integration tests (seed data loaded into DB, queried via API)
# ===================================================================


class TestSeedDataViaAPI:
    """Hit the API with the real seed data loaded."""

    def test_schools_endpoint_returns_all(self, seed_client):
        r = seed_client.get("/api/schools", params={"council": "Milton Keynes"})
        assert r.status_code == 200
        schools = r.json()
        assert len(schools) >= 100

    def test_private_schools_endpoint(self, seed_client):
        r = seed_client.get("/api/private-schools", params={"council": "Milton Keynes"})
        assert r.status_code == 200
        privates = r.json()
        assert len(privates) >= 3
        names = [s["name"] for s in privates]
        assert any("Thornton" in n for n in names)
        assert any("Akeley Wood" in n for n in names)

    def test_school_detail_by_id(self, seed_client):
        # Get the first school
        r = seed_client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        first_id = schools[0]["id"]

        r = seed_client.get(f"/api/schools/{first_id}")
        assert r.status_code == 200
        detail = r.json()
        assert detail["id"] == first_id
        assert detail["name"]
        assert detail["postcode"]

    def test_filter_by_min_rating(self, seed_client):
        r = seed_client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "min_rating": "Outstanding"},
        )
        assert r.status_code == 200
        schools = r.json()
        for s in schools:
            assert s["ofsted_rating"] == "Outstanding"

    def test_filter_by_age(self, seed_client):
        r = seed_client.get(
            "/api/schools",
            params={"council": "Milton Keynes", "age": "5"},
        )
        assert r.status_code == 200
        schools = r.json()
        for s in schools:
            assert s["age_range_from"] <= 5 <= s["age_range_to"]

    def test_councils_includes_mk(self, seed_client):
        r = seed_client.get("/api/councils")
        assert r.status_code == 200
        assert "Milton Keynes" in r.json()

    def test_compare_endpoint(self, seed_client):
        # Get two school IDs
        r = seed_client.get("/api/schools", params={"council": "Milton Keynes"})
        ids = [s["id"] for s in r.json()[:2]]

        r = seed_client.get("/api/compare", params={"ids": f"{ids[0]},{ids[1]}"})
        assert r.status_code == 200
        body = r.json()
        # Compare returns {"schools": [...]} wrapper
        schools = body.get("schools", body) if isinstance(body, dict) else body
        assert len(schools) == 2
