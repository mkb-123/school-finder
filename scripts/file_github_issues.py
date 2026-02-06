#!/usr/bin/env python3
"""File GitHub issues for the school-finder project.

Usage:
    # Set your GitHub token
    export GITHUB_TOKEN=ghp_xxxxx

    # File all issues
    python scripts/file_github_issues.py

    # Dry run (print issues without filing)
    python scripts/file_github_issues.py --dry-run

    # File to a different repo
    python scripts/file_github_issues.py --repo owner/repo-name
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx

REPO = "mkb-123/school-finder"

ISSUES: list[dict] = [
    # ---- BUGS ----
    {
        "title": "Seed script crashes on 1st of any month",
        "labels": ["bug", "critical"],
        "body": """## Description
`src/db/seed.py` line ~287 uses `date.today().replace(day=date.today().day - 1)` which raises `ValueError` on the 1st of any month because `day=0` is invalid.

## Steps to Reproduce
Run `python -m src.db.seed --council "Milton Keynes"` on the 1st of any month.

## Expected
Script runs successfully.

## Actual
`ValueError: day is out of range for month`

## Fix
Use `date.today() - timedelta(days=1)`.

**Status:** FIXED in commit c85d42c
""",
    },
    {
        "title": "Ofsted rating case mismatch breaks decision scoring and filtering",
        "labels": ["bug", "high"],
        "body": """## Description
Seed data stores `"Requires improvement"` (lowercase i) but the decision service, filter logic, and OFSTED_ORDER all expect `"Requires Improvement"` (uppercase I).

## Impact
- Affected schools get a neutral 50.0 score instead of 25.0 in weighted scoring
- Not matched by `min_rating` filters
- Never receive the "Requires Improvement" con in pros/cons generation

## Files
- `src/db/seed.py` (source of data)
- `src/services/decision.py` (OFSTED_ORDER, scoring)
- `src/db/base.py` (filter logic)

**Status:** FIXED in commit c85d42c - normalised to "Requires Improvement" everywhere
""",
    },
    {
        "title": "distance_km is never populated - decision scoring distance dimension inoperative",
        "labels": ["bug", "high"],
        "body": """## Description
The `School` ORM model has no `distance_km` column. `school_data_from_orm` in `src/services/decision.py` does `getattr(school, "distance_km", None)` which always returns `None`.

## Impact
- Distance dimension always scores 50.0 (neutral) regardless of actual distance
- Distance-based pros/cons are never generated ("Walking distance" / "Over 3km away")
- What-if `max_distance_km` filter never excludes any school
- `SchoolResponse.distance_km` is always `None` unless lat/lng query params provide it

## Suggested Fix
Pass `distance_km` through from the API layer (computed via Haversine) into the decision service, rather than relying on the ORM model.
""",
    },
    {
        "title": "Private school max_fee filter parameter accepted but silently ignored",
        "labels": ["bug", "high"],
        "body": """## Description
`PrivateSchoolFilterParams` in `src/schemas/filters.py` declares `max_fee: float | None = None`. However:
1. `_to_private_filters()` in `src/api/private_schools.py` never maps it to `SchoolFilters`
2. `SchoolFilters` in `base.py` has no `max_fee` field
3. The repository has no join to `private_school_details` for fee-based filtering

## Steps to Reproduce
```
GET /api/private-schools?council=Milton+Keynes&max_fee=1000
```
Returns ALL private schools, not just those under £1000/term.

## Expected
Only schools with termly_fee <= 1000 are returned.
""",
    },
    {
        "title": "postcode and search query parameters accepted but ignored on /api/schools",
        "labels": ["bug", "medium"],
        "body": """## Description
`SchoolFilterParams` accepts `postcode` and `search` parameters but `_to_school_filters()` never uses them.

A client sending `?postcode=MK5+6EX` without explicit `lat`/`lng` gets unfiltered distance results. Text search via `?search=Oakgrove` returns all schools.

## Expected
- `postcode` should auto-geocode and filter by distance
- `search` should filter by school name (case-insensitive substring match)
""",
    },
    {
        "title": "Duplicate SchoolFilters dataclass definitions with incompatible field names",
        "labels": ["bug", "medium"],
        "body": """## Description
Two `SchoolFilters` definitions exist with different field names:

1. `src/db/base.py` (lines 16-48): `age`, `gender`, `min_rating` (string), `lat`/`lng`
2. `src/services/filters.py` (lines 35-60): `child_age`, `child_gender`, `min_ofsted_rating` (integer), `ref_lat`/`ref_lng`

Only the `db/base.py` version is used. The `services/filters.py` version and its `build_filter_clauses` function are dead code.

## Fix
Remove the unused version from `services/filters.py` or consolidate into a single definition.
""",
    },
    {
        "title": "Geocode returns (0.0, 0.0) on malformed postcodes.io response",
        "labels": ["bug", "medium"],
        "body": """## Description
In `src/api/journey.py` and `src/api/geocode.py`, if postcodes.io returns HTTP 200 but JSON is missing `latitude`/`longitude` keys, coordinates default to `(0.0, 0.0)` - a point in the Gulf of Guinea. Journey calculations produce wildly incorrect distances.

## Fix
Check for None/missing coordinates and return a 422 error or use fallback geocoding.

**Status:** FIXED in commit c85d42c
""",
    },
    {
        "title": "Admissions likelihood defaults to 'Likely' when no historical data exists",
        "labels": ["bug", "medium"],
        "body": """## Description
When a school has zero years of admissions history, `src/services/admissions.py` returns `likelihood="Likely"` and `years_of_data=0`. This misleads parents into thinking they have a good chance when there's simply no data.

## Fix
Return `likelihood="Unknown"` when `years_of_data=0`.

**Status:** FIXED in commit c85d42c
""",
    },
    {
        "title": "selectin eager loading on all School relationships causes over-fetching for list endpoints",
        "labels": ["bug", "medium", "performance"],
        "body": """## Description
All six relationships on the `School` model use `lazy="selectin"`. When `/api/schools` loads dozens of schools, SQLAlchemy fires 6 additional SELECT queries per school to load clubs, term dates, performance, reviews, private details, and admissions. The list endpoint only uses `SchoolResponse` fields and discards all related data.

## Impact
Unnecessary database queries on every list request. Will become a performance bottleneck as data grows.

## Fix
Change to `lazy="select"` (default) and use `selectinload()` only in detail endpoints that need the related data.
""",
    },
    {
        "title": "What-if rating filter fragile due to case mismatch interaction",
        "labels": ["bug", "medium"],
        "body": """## Description
In `src/services/decision.py` (lines 291-304), when `min_rating` is valid (e.g., `"Good"`) but a school's `ofsted_rating` was `"Requires improvement"`, `OFSTED_ORDER.index("Requires improvement")` would raise `ValueError` and the school was excluded. This was accidentally correct but relied on the case mismatch bug.

Now that the casing is fixed (issue #2), this code path should be tested to ensure the filter still works correctly.
""",
    },
    {
        "title": "API imports private _SchoolInfo class from service module",
        "labels": ["bug", "low", "code-quality"],
        "body": """## Description
`src/api/journey.py` line 20 imports `_SchoolInfo` (underscore-prefixed private class) from `src.services.journey`. This creates tight coupling to an implementation detail.

## Fix
Rename to `SchoolInfo` (public) or have the API use its own data structure.
""",
    },
    {
        "title": "is_rush_hour flag set for walking and cycling during peak windows",
        "labels": ["bug", "low"],
        "body": """## Description
`is_rush_hour` was set to True for all transport modes during drop-off/pick-up windows. Walking and cycling have no traffic impact (1.0x multiplier) but the API flagged them as rush hour, which is misleading.

**Status:** FIXED in commit c85d42c
""",
    },
    {
        "title": "Private school detail endpoint doesn't verify school is actually private",
        "labels": ["bug", "low"],
        "body": """## Description
`/api/private-schools/{school_id}` fetches any school by ID without checking `is_private == True`. A state school can be retrieved through the private school endpoint.

**Status:** FIXED in commit c85d42c
""",
    },
    {
        "title": "Private schools get no club data in seed script",
        "labels": ["bug", "low"],
        "body": """## Description
`_generate_test_clubs` in `src/db/seed.py` explicitly skips private schools with `if school.is_private: continue`. Private schools never have breakfast/after-school club records, so club-based filters always exclude them.

## Fix
Generate club data for private schools too, or document that clubs are state-school only.
""",
    },
    {
        "title": "All-through schools (age 4-18) get no performance data in seed",
        "labels": ["bug", "low"],
        "body": """## Description
Schools like Oakgrove (age 4-18) fail both the `is_primary` check (`age_range_to <= 13` fails because it's 18) and the `is_secondary` check (`age_range_from >= 11` fails because it's 4). These schools get no SATs, GCSE, or Progress8 data.

## Fix
Check overlapping ranges: primary performance if school accepts age 5-11, secondary if school accepts age 11-16+.
""",
    },
    {
        "title": "Journey distance calculated redundantly 4 times per school in compare",
        "labels": ["bug", "low", "performance"],
        "body": """## Description
In `src/services/journey.py` (compare_journeys), the Haversine distance is computed once explicitly and then again inside each of the three `calculate_journey` calls. Four identical computations per school per comparison.

## Fix
Compute distance once and pass it to `calculate_journey`.
""",
    },
    # ---- FEATURE REQUESTS ----
    {
        "title": "Add pagination (limit/offset) to list endpoints",
        "labels": ["enhancement", "feature-request"],
        "body": """## Description
No endpoint implements pagination. `/api/schools` returns all matching schools in a single response. As the dataset grows beyond Milton Keynes, response sizes will become problematic.

## Suggestion
Add `limit` (default 50) and `offset` (default 0) query params to:
- `GET /api/schools`
- `GET /api/private-schools`

Return total count in a wrapper: `{"total": 127, "schools": [...]}`
""",
    },
    {
        "title": "Use bounding-box pre-filter for Haversine distance queries",
        "labels": ["enhancement", "performance"],
        "body": """## Description
`src/services/filters.py` (lines 146-170) implements a bounding-box pre-filter to narrow candidate rows before applying the Haversine function. The actual repository in `src/db/sqlite_repo.py` does not use this optimization.

## Benefit
For larger datasets, this would significantly reduce the number of Haversine computations needed.
""",
    },
    {
        "title": "Search schools by name",
        "labels": ["feature-request"],
        "body": """## User Story
As a parent, I want to type "Caroline" in a search box and find Caroline Haslett Primary directly, without scrolling through all 127 schools.

## Suggestion
Add `?search=<term>` support to `/api/schools` that does case-insensitive substring matching on `school.name`.
""",
    },
    {
        "title": "Default sort by distance when postcode/coordinates provided",
        "labels": ["feature-request"],
        "body": """## User Story
When I search from my postcode MK5 6EX, I expect the nearest schools to appear first, not in arbitrary order.

## Suggestion
When `lat`/`lng` query params are provided, sort results by `distance_km` ascending by default. Add a `sort` param (`distance`, `name`, `rating`) for user control.
""",
    },
    {
        "title": "Combined filter: schools with BOTH breakfast AND after-school clubs",
        "labels": ["feature-request"],
        "body": """## User Story
As a working parent (finishing at 5:30pm), I need both breakfast club (morning drop-off before work) and after-school club (late pickup). I want to filter for schools that have BOTH, not just one or the other.

## Suggestion
Add `?has_both_clubs=true` filter or allow `?has_breakfast_club=true&has_afterschool_club=true` to work as AND logic.
""",
    },
    {
        "title": "Fee projection calculator for private schools",
        "labels": ["feature-request"],
        "body": """## User Story
We already have `fee_increase_pct` data. As a parent considering a private school for Reception (age 4), I want to see projected costs through Year 6 (age 11) so I can budget for the full primary journey.

## Suggestion
Add a fee projection component that shows:
- Current termly/annual fee per tier
- Projected fee in 1, 3, 5, 7 years using `fee_increase_pct`
- Total cost over the school journey (e.g., Reception through Year 6)
""",
    },
    {
        "title": "School walking route comparison overlay on map",
        "labels": ["feature-request"],
        "body": """## User Story
I've shortlisted 3 schools. I want to see the walking routes from my postcode to each one overlaid on the same map, so I can compare the actual routes (not just straight-line distance).

## Suggestion
On the Journey page, add a "Show on map" button that draws polyline routes from the user's postcode to each selected school using a routing API (OSRM is free).
""",
    },
    {
        "title": "Admissions deadline notifications",
        "labels": ["feature-request"],
        "body": """## User Story
School admissions have strict deadlines. I want to see key dates:
- "Applications for Milton Keynes primary schools open: November 2025"
- "Deadline: 15 January 2026"
- "Offers day: 16 April 2026"

## Suggestion
Add a prominent banner/card showing upcoming admissions deadlines based on the council calendar. Could also support email/calendar reminders.
""",
    },
    {
        "title": "Seed and display parent review data",
        "labels": ["feature-request"],
        "body": """## Description
The `SchoolReview` model exists in `src/db/models.py` but no review data is seeded or displayed. Parent reviews are a major factor in school choice.

## Suggestion
1. Seed example review snippets (source, rating, snippet, review_date)
2. Display on SchoolDetail page in a Reviews tab
3. Show aggregate satisfaction score on SchoolCard
""",
    },
    {
        "title": "Export shortlist comparison as PDF",
        "labels": ["feature-request"],
        "body": """## User Story
I've shortlisted 4 schools on the Decision Support page. I want to download a PDF summary to share with my partner or print for our discussion.

## Suggestion
Add an "Export as PDF" button that generates a styled document with:
- School comparison table
- Pros/cons for each school
- Weighted scores and ranking
- Key details (Ofsted, distance, clubs, fees)

Could use `window.print()` with a print-specific CSS stylesheet, or a library like jsPDF.
""",
    },
    {
        "title": "SEND provision data and filtering",
        "labels": ["feature-request"],
        "body": """## Description
The SEND toggle UI exists (Phase 11) but there's no actual SEND data in the database. The toggle shows/hides a panel, but the panel has no real data to display.

## Suggestion
1. Add SEND fields to the School model (sen_provision_type, ehcp_friendly, accessibility_info, specialist_unit)
2. Seed SEND data for MK schools
3. Add SEND-aware filters (`?has_specialist_unit=true`, `?ehcp_friendly=true`)
4. Display in the SendInfoPanel when toggle is enabled
""",
    },
]


def file_issue(client: httpx.Client, repo: str, issue: dict) -> dict | None:
    """File a single GitHub issue. Returns the created issue or None on error."""
    url = f"https://api.github.com/repos/{repo}/issues"
    payload = {
        "title": issue["title"],
        "body": issue["body"],
        "labels": issue.get("labels", []),
    }
    resp = client.post(url, json=payload)
    if resp.status_code == 201:
        data = resp.json()
        return {"number": data["number"], "url": data["html_url"], "title": issue["title"]}
    print(f"  ERROR filing '{issue['title']}': {resp.status_code} {resp.text[:200]}", file=sys.stderr)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="File GitHub issues for school-finder")
    parser.add_argument("--repo", default=REPO, help=f"GitHub repo (default: {REPO})")
    parser.add_argument("--dry-run", action="store_true", help="Print issues without filing")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""), help="GitHub token")
    args = parser.parse_args()

    if args.dry_run:
        print(f"DRY RUN: Would file {len(ISSUES)} issues to {args.repo}\n")
        for i, issue in enumerate(ISSUES, 1):
            labels = ", ".join(issue.get("labels", []))
            print(f"  {i:2d}. [{labels}] {issue['title']}")
        print(f"\nTotal: {len(ISSUES)} issues")
        return

    if not args.token:
        print("ERROR: Set GITHUB_TOKEN env var or pass --token", file=sys.stderr)
        sys.exit(1)

    client = httpx.Client(
        headers={"Authorization": f"token {args.token}", "Accept": "application/vnd.github.v3+json"},
        timeout=30,
    )

    print(f"Filing {len(ISSUES)} issues to {args.repo}...\n")
    filed = []
    for i, issue in enumerate(ISSUES, 1):
        result = file_issue(client, args.repo, issue)
        if result:
            filed.append(result)
            print(f"  {i:2d}. #{result['number']} - {result['title']}")
        else:
            print(f"  {i:2d}. FAILED - {issue['title']}")
        time.sleep(1)  # Rate limit courtesy

    print(f"\nFiled {len(filed)}/{len(ISSUES)} issues successfully.")
    if filed:
        print("\nIssue URLs:")
        for f in filed:
            print(f"  #{f['number']}: {f['url']}")


if __name__ == "__main__":
    main()
