"""User-agent test: Parent with a 4-year-old girl in Milton Keynes.

Simulates a real parent's journey through the School Finder app, testing
each endpoint and collecting issues. Designed to be run standalone or via
pytest. When run standalone with --file-issues, it files GitHub issues for
any errors found.

Persona:
  - Sarah, parent of Lily (age 4, girl)
  - Lives in Shenley Church End, postcode MK5 6EX
  - Looking for: primary schools in catchment, outstanding preferred
  - Interested in breakfast clubs (works 8am start)
  - Also exploring private schools (Thornton College for all-girls option)
  - Wants to compare top 3 choices side by side

Usage:
  pytest tests/test_user_agent_parent.py -v
  python -m tests.test_user_agent_parent --file-issues  # files GitHub issues
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.db.models import Base
from src.db.sqlite_repo import SQLiteSchoolRepository
from src.main import app
from tests.seed_test_data import _generate_private_school_details, _generate_test_schools

# ---------------------------------------------------------------------------
# Issue tracker
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    title: str
    body: str
    labels: list[str] = field(default_factory=lambda: ["bug", "user-agent-test"])


_issues: list[Issue] = []


def _record_issue(title: str, body: str, labels: list[str] | None = None):
    """Record an issue to be filed later."""
    _issues.append(
        Issue(
            title=title,
            body=body,
            labels=labels or ["bug", "user-agent-test"],
        )
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed_full_db(tmp_path) -> str:
    """Create a temp DB with full seed data including private school details."""
    path = str(tmp_path / "parent_test.db")
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)

    schools = _generate_test_schools("Milton Keynes")
    with Session(engine) as session:
        session.add_all(schools)
        session.commit()

        # Generate private school details (function queries DB and inserts directly)
        _generate_private_school_details(session)
        session.commit()

    engine.dispose()
    return path


@pytest.fixture()
def parent_client(tmp_path) -> TestClient:
    """TestClient with full seed data for the parent persona test."""
    db_path = _seed_full_db(tmp_path)
    repo = SQLiteSchoolRepository(db_path)

    def _override() -> SchoolRepository:
        return repo

    app.dependency_overrides[get_school_repository] = _override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ===================================================================
# Parent Journey: Sarah looking for schools for 4-year-old Lily
# ===================================================================


class TestParentJourney:
    """Simulate Sarah's journey finding schools for her 4-year-old daughter."""

    # -- Step 1: Land on the app and check councils are available --

    def test_step1_councils_available(self, parent_client):
        """Sarah opens the app and sees Milton Keynes in the council list."""
        r = parent_client.get("/api/councils")
        assert r.status_code == 200, f"Councils endpoint failed: {r.status_code}"
        councils = r.json()
        assert "Milton Keynes" in councils, "Milton Keynes not in council list"

    # -- Step 2: Geocode her postcode --

    def test_step2_geocode_postcode(self, parent_client):
        """Sarah enters her postcode MK5 6EX to find nearby schools."""
        r = parent_client.get("/api/geocode", params={"postcode": "MK5 6EX"})
        if r.status_code != 200:
            _record_issue(
                "Geocode fails for MK5 6EX",
                f"Parent postcode MK5 6EX returns {r.status_code}.\n"
                "This is a valid Milton Keynes postcode near Shenley Church End.\n"
                f"Response: {r.text}",
            )
            pytest.skip("Geocode not available for this postcode")
        data = r.json()
        assert "lat" in data and "lng" in data

    # -- Step 3: Search for schools accepting a 4-year-old girl --

    def test_step3_search_schools_for_4yo(self, parent_client):
        """Sarah filters for schools accepting age 4."""
        r = parent_client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "age": "4",
            },
        )
        assert r.status_code == 200
        schools = r.json()
        assert len(schools) > 0, "No schools found for age 4 in Milton Keynes"

        # All returned schools should accept age 4
        for s in schools:
            if s["age_range_from"] > 4 or s["age_range_to"] < 4:
                _record_issue(
                    f"School {s['name']} returned for age 4 but range is {s['age_range_from']}-{s['age_range_to']}",
                    f"The school `{s['name']}` (ID: {s['id']}) has age range "
                    f"{s['age_range_from']}-{s['age_range_to']} but was returned "
                    f"when filtering for age=4.\n\nEndpoint: GET /api/schools?council=Milton Keynes&age=4",
                    ["bug", "filtering"],
                )

    # -- Step 4: Filter for outstanding schools only --

    def test_step4_filter_outstanding(self, parent_client):
        """Sarah filters for Outstanding schools only."""
        r = parent_client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "age": "4",
                "min_rating": "Outstanding",
            },
        )
        assert r.status_code == 200
        schools = r.json()

        for s in schools:
            if s["ofsted_rating"] != "Outstanding":
                _record_issue(
                    f"Non-Outstanding school {s['name']} returned with Outstanding filter",
                    f"School `{s['name']}` has rating `{s['ofsted_rating']}` but was "
                    f"returned when min_rating=Outstanding.\n\n"
                    f"Endpoint: GET /api/schools?council=Milton Keynes&age=4&min_rating=Outstanding",
                    ["bug", "filtering"],
                )

    # -- Step 5: Check Caroline Haslett (her nearest school) --

    def test_step5_find_caroline_haslett(self, parent_client):
        """Sarah's nearest school is Caroline Haslett Primary - check it exists."""
        r = parent_client.get("/api/schools", params={"council": "Milton Keynes"})
        schools = r.json()
        caroline = [s for s in schools if "Caroline Haslett" in s["name"]]
        assert len(caroline) > 0, "Caroline Haslett Primary School not found in results"
        assert caroline[0]["age_range_from"] <= 4, "Caroline Haslett should accept age 4"

    # -- Step 6: View school detail page --

    def test_step6_school_detail(self, parent_client):
        """Sarah clicks on a school to see full details."""
        r = parent_client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "age": "4",
            },
        )
        schools = r.json()
        assert len(schools) > 0

        school_id = schools[0]["id"]
        r = parent_client.get(f"/api/schools/{school_id}")
        assert r.status_code == 200
        detail = r.json()
        assert detail["name"], "School detail missing name"
        assert detail["postcode"], "School detail missing postcode"

        # Check the detail response has the expected structure
        expected_keys = ["clubs", "performance", "term_dates", "admissions_history"]
        for key in expected_keys:
            if key not in detail:
                _record_issue(
                    f"School detail response missing '{key}' field",
                    f"GET /api/schools/{school_id} response is missing the `{key}` field.\n"
                    f"School: {detail.get('name', 'Unknown')}\n"
                    f"Available keys: {list(detail.keys())}",
                    ["bug", "api"],
                )

    # -- Step 7: Check clubs (Sarah needs breakfast club) --

    def test_step7_check_clubs(self, parent_client):
        """Sarah needs a breakfast club - check club data is available."""
        r = parent_client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "age": "4",
            },
        )
        schools = r.json()

        schools_with_clubs = 0
        for s in schools[:10]:  # Check first 10
            cr = parent_client.get(f"/api/schools/{s['id']}/clubs")
            assert cr.status_code == 200, f"Clubs endpoint failed for school {s['name']}"
            clubs = cr.json()
            if len(clubs) > 0:
                schools_with_clubs += 1
                # Validate club structure
                for club in clubs:
                    if "club_type" not in club:
                        _record_issue(
                            f"Club missing club_type for {s['name']}",
                            f"A club record for school `{s['name']}` is missing `club_type`.\n"
                            f"Club data: {json.dumps(club, indent=2)}",
                            ["bug", "data"],
                        )

    # -- Step 8: Look at private schools (Thornton College) --

    def test_step8_private_schools(self, parent_client):
        """Sarah explores Thornton College as an all-girls private option."""
        r = parent_client.get(
            "/api/private-schools",
            params={
                "council": "Milton Keynes",
            },
        )
        assert r.status_code == 200
        schools = r.json()
        assert len(schools) > 0, "No private schools returned"

        thornton = [s for s in schools if "Thornton" in s["name"]]
        assert len(thornton) > 0, "Thornton College not in private schools list"

        t = thornton[0]
        assert t["is_private"] is True, "Thornton should be marked as private"

        # Check Thornton detail page has fee data
        r = parent_client.get(f"/api/private-schools/{t['id']}")
        assert r.status_code == 200
        detail = r.json()

        if "private_details" not in detail or len(detail.get("private_details", [])) == 0:
            _record_issue(
                "Thornton College missing fee/private details",
                "Thornton College private school detail page has no `private_details` data.\n"
                "Parents need to see fees, hours, and transport information.\n"
                f"Endpoint: GET /api/private-schools/{t['id']}",
                ["bug", "data", "private-schools"],
            )

    # -- Step 9: Check girls-only filter works --

    def test_step9_gender_filter(self, parent_client):
        """Sarah filters for schools accepting girls."""
        r = parent_client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "age": "4",
                "gender": "female",
            },
        )
        assert r.status_code == 200
        schools = r.json()

        for s in schools:
            if s["gender_policy"] == "Boys":
                _record_issue(
                    f"Boys-only school {s['name']} returned with gender=female filter",
                    f"School `{s['name']}` has gender_policy=Boys but was returned "
                    f"when filtering for gender=female.\n\n"
                    f"Endpoint: GET /api/schools?council=Milton Keynes&age=4&gender=female",
                    ["bug", "filtering"],
                )

    # -- Step 10: Compare top choices --

    def test_step10_compare_schools(self, parent_client):
        """Sarah compares her top 3 school choices side by side."""
        r = parent_client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "age": "4",
            },
        )
        schools = r.json()
        assert len(schools) >= 3, "Need at least 3 schools to compare"

        ids = [s["id"] for s in schools[:3]]
        r = parent_client.get(
            "/api/compare",
            params={
                "ids": ",".join(str(i) for i in ids),
            },
        )
        assert r.status_code == 200
        body = r.json()

        compared = body.get("schools", body) if isinstance(body, dict) else body
        assert len(compared) == 3, f"Compare returned {len(compared)} schools, expected 3"

        # Each compared school should have full detail
        for school in compared:
            if "name" not in school:
                _record_issue(
                    "Compare response missing school name",
                    "The compare endpoint returned a school without a `name` field.\n"
                    f"Response: {json.dumps(school, indent=2)[:500]}",
                    ["bug", "api"],
                )

    # -- Step 11: Check a 404 for non-existent school --

    def test_step11_nonexistent_school_404(self, parent_client):
        """Sarah typos a URL - should get a clear 404."""
        r = parent_client.get("/api/schools/99999")
        assert r.status_code == 404, f"Expected 404 for non-existent school, got {r.status_code}"

    # -- Step 12: Check term dates are available --

    def test_step12_term_dates(self, parent_client):
        """Sarah wants to know term dates for planning holidays."""
        r = parent_client.get(
            "/api/schools",
            params={
                "council": "Milton Keynes",
                "age": "4",
            },
        )
        schools = r.json()
        assert len(schools) > 0

        school_id = schools[0]["id"]
        r = parent_client.get(f"/api/schools/{school_id}/term-dates")
        assert r.status_code == 200, f"Term dates endpoint failed: {r.status_code}"


# ===================================================================
# Issue filing (when run standalone)
# ===================================================================


def _file_github_issues():
    """File collected issues as GitHub issues."""
    if not _issues:
        print("No issues to file.")
        return

    print(f"\nFiling {len(_issues)} issues to GitHub...\n")
    for issue in _issues:
        labels = ",".join(issue.labels)
        body = issue.body + "\n\n---\n_Filed automatically by parent user-agent test._"
        cmd = [
            "gh",
            "issue",
            "create",
            "--title",
            issue.title,
            "--body",
            body,
            "--label",
            labels,
        ]
        print(f"  Filing: {issue.title}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"    -> {result.stdout.strip()}")
            else:
                print(f"    -> FAILED: {result.stderr.strip()}")
        except Exception as e:
            print(f"    -> ERROR: {e}")


if __name__ == "__main__":
    import tempfile

    file_issues = "--file-issues" in sys.argv

    print("=" * 60)
    print("  Parent User-Agent Test")
    print("  Persona: Sarah, parent of Lily (4yo girl)")
    print("  Location: Shenley Church End, MK5 6EX")
    print("=" * 60)

    # Create temp DB and run tests
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _seed_full_db(tmp)
        repo = SQLiteSchoolRepository(db_path)

        def _override() -> SchoolRepository:
            return repo

        app.dependency_overrides[get_school_repository] = _override

        with TestClient(app) as client:
            test = TestParentJourney()
            methods = [m for m in dir(test) if m.startswith("test_step")]
            methods.sort()

            passed = 0
            failed = 0
            for method_name in methods:
                method = getattr(test, method_name)
                step_name = method_name.replace("test_", "").replace("_", " ").title()
                try:
                    method(client)
                    print(f"  PASS  {step_name}")
                    passed += 1
                except Exception as e:
                    print(f"  FAIL  {step_name}: {e}")
                    _record_issue(
                        f"Parent journey failed: {step_name}",
                        f"The parent user-agent test failed at step: {step_name}\n\n"
                        f"Error: {e}\n\n"
                        f"Persona: Sarah, parent of Lily (4yo girl), MK5 6EX",
                        ["bug", "user-agent-test"],
                    )
                    failed += 1

        app.dependency_overrides.clear()

    print()
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"  Issues collected: {len(_issues)}")

    if file_issues and _issues:
        _file_github_issues()
    elif _issues:
        print("\n  Issues found (use --file-issues to submit to GitHub):")
        for issue in _issues:
            print(f"    - {issue.title}")
