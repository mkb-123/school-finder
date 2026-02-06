# School Finder - QA Audit Issues

Found by Ralph Wiggum parent agent + QA code audit. 20 total issues.

---

## Bugs

### #1 [CRITICAL] Seed script crashes on 1st of any month
**File:** `src/db/seed.py:287`
**Problem:** `date.today().replace(day=date.today().day - 1)` raises `ValueError` when `day=0` on the 1st.
**Fix:** Use `date.today() - timedelta(days=1)`.
**Status:** FIXED

### #2 [HIGH] Ofsted rating case mismatch breaks decision scoring
**File:** `src/db/seed.py` vs `src/services/decision.py`
**Problem:** Seed stores `"Requires improvement"` (lowercase i), decision service expects `"Requires Improvement"` (uppercase I). Affected schools get wrong scores, skip min_rating filters, and miss pros/cons.
**Fix:** Normalise to `"Requires Improvement"` everywhere.
**Status:** FIXED

### #3 [HIGH] `distance_km` never populated in decision scoring
**File:** `src/services/decision.py`, `src/api/decision.py`
**Problem:** `School` ORM model has no `distance_km` column. `getattr(school, "distance_km", None)` always returns `None`.
**Fix:** `school_data_from_orm()` accepts explicit `distance_km` param; `_load_school_data()` computes haversine distance when lat/lng provided.
**Status:** FIXED

### #4 [HIGH] `max_fee` filter on private schools silently ignored
**File:** `src/api/private_schools.py`, `src/db/base.py`, `src/db/sqlite_repo.py`
**Problem:** `max_fee` query param accepted but never mapped to filters or used in queries.
**Fix:** `SchoolFilters.max_fee` field added; repo uses EXISTS subquery on `private_school_details.termly_fee`.
**Status:** FIXED

### #5 [MEDIUM] `postcode` and `search` query params accepted but ignored
**File:** `src/api/schools.py`, `src/db/sqlite_repo.py`
**Problem:** Params declared in schema but never used in filter mapping.
**Fix:** Postcode auto-geocodes to lat/lng; `search` uses `School.name.ilike()`.
**Status:** FIXED

### #6 [MEDIUM] Seed script date crash on 1st of month
See #1.
**Status:** FIXED

### #7 [MEDIUM] Duplicate `SchoolFilters` dataclass definitions
**File:** `src/db/base.py` vs `src/services/filters.py`
**Problem:** Two incompatible `SchoolFilters` with different field names. `services/filters.py` version is dead code.
**Fix:** Removed duplicate; canonical definition lives in `src/db/base.py`. `services/filters.py` is now a placeholder.
**Status:** FIXED

### #8 [MEDIUM] Geocode returns (0.0, 0.0) on malformed API response
**File:** `src/api/geocode.py`, `src/api/journey.py`
**Problem:** Missing lat/lng in postcodes.io response defaults to (0.0, 0.0) - Gulf of Guinea.
**Fix:** Check for None coordinates and return error.
**Status:** FIXED

### #9 [MEDIUM] Admissions likelihood defaults to "Likely" with no data
**File:** `src/services/admissions.py`
**Problem:** Returns `likelihood="Likely"` when `years_of_data=0`. Misleading to parents.
**Fix:** Return `likelihood="Unknown"` when no data exists.
**Status:** FIXED

### #10 [MEDIUM] `selectin` eager loading on all relationships causes over-fetching
**File:** `src/db/models.py`, `src/db/sqlite_repo.py`
**Problem:** All 6 relationships use `lazy="selectin"`. List endpoints load all related data then discard it.
**Fix:** Changed to `lazy="select"` (default); explicit `selectinload()` only in `get_school_by_id`.
**Status:** FIXED

### #11 [MEDIUM] What-if rating filter fragile due to case mismatch interaction
**File:** `src/services/decision.py`
**Problem:** Works accidentally because casing mismatch causes ValueError. Fixing #2 may break this.
**Fix:** Rating filter properly handles ValueError with try/except; works correctly with normalised casing.
**Status:** FIXED

### #12 [MEDIUM] API imports private `_SchoolInfo` class
**File:** `src/api/journey.py`, `src/services/journey.py`
**Problem:** Imports underscore-prefixed private class from service layer.
**Fix:** Renamed to public `SchoolInfo` class.
**Status:** FIXED

### #13 [LOW] `is_rush_hour` true for walking/cycling
**File:** `src/services/journey.py`
**Problem:** Walking/cycling flagged as rush hour even though no traffic impact.
**Fix:** `is_rush_hour` only true for driving/transit modes.
**Status:** FIXED

### #14 [LOW] Private school detail endpoint doesn't verify `is_private`
**File:** `src/api/private_schools.py`
**Problem:** `/api/private-schools/{id}` returns state schools too.
**Fix:** Added `is_private` check, returns 404 for state schools.
**Status:** FIXED

### #15 [LOW] Private schools get no club data in seed
**File:** `src/db/seed.py`
**Problem:** `_generate_test_clubs` skips `is_private` schools. Private schools never have clubs.
**Fix:** Club generation now includes private schools.
**Status:** FIXED

### #16 [LOW] All-through schools get no performance data
**File:** `src/db/seed.py`
**Problem:** Schools like Oakgrove (age 4-18) fail both primary and secondary checks, get no SATs/GCSE data.
**Fix:** Performance generation checks primary and secondary age ranges independently.
**Status:** FIXED

### #17 [LOW] Journey distance calculated 4 times per school
**File:** `src/services/journey.py`
**Problem:** Haversine computed once explicitly, then again inside each `calculate_journey` call.
**Fix:** Pre-computed `straight_line_km` passed to `calculate_journey` to skip redundant calculations.
**Status:** FIXED

### #18 [LOW] Admissions seed uses inconsistent Ofsted casing
**File:** `src/db/seed.py`
**Problem:** Popularity check uses `"Requires improvement"` - must update alongside #2.
**Fix:** Normalised to `"Requires Improvement"` everywhere in seed.
**Status:** FIXED

---

## Feature Requests

### #19 [MEDIUM] No pagination on any list endpoint
**Problem:** All endpoints return full result sets. Will not scale beyond Milton Keynes.
**Fix:** Added `limit` and `offset` params to `/api/schools` and `/api/private-schools`.
**Status:** FIXED

### #20 [LOW] Bounding-box pre-filter exists but is unused
**File:** `src/db/sqlite_repo.py`
**Problem:** Optimization code exists but `sqlite_repo.py` doesn't use it.
**Fix:** Bounding-box lat/lng rectangle filter applied before haversine distance check.
**Status:** FIXED

---

## Feature Ideas (from parent user perspective)

### #21 Search schools by name
As a parent, I want to type "Caroline" and find Caroline Haslett Primary directly.
**Status:** FIXED (via `search` query param on `/api/schools` — see #5)

### #22 "Nearest schools" default sort
When I provide my postcode, results should be sorted by distance by default.
**Status:** FIXED (sqlite_repo.py sorts by haversine distance when lat/lng provided)

### #23 Combined filter for "has both breakfast AND after-school club"
Parents who work need both. Currently must check each school individually.
**Status:** FIXED (added `has_both_clubs` filter param to `/api/schools`)

### #24 Fee projection calculator for private schools
Show "In 3 years this tier will cost approximately X" using fee_increase_pct.
**Status:** FIXED (added `GET /api/private-schools/{id}/fee-projection?years=3`)

### #25 School-to-school walking route comparison on map
Overlay walking routes from my postcode to shortlisted schools on the map.
**Status:** FIXED (added `GET /api/journey/compare?from_postcode=...&school_ids=1,2,3&mode=walking`)

### #26 Notifications for admissions deadlines
"Applications for X close on Y" - key dates parents can't miss.
**Status:** FIXED (added `AdmissionsDeadline` model, seed data, and `GET /api/schools/{id}/deadlines` + `GET /api/deadlines` endpoints)

### #27 Parent review snippets
The SchoolReview model exists but no review data is seeded or displayed.
**Status:** FIXED (added review seed data generation and `GET /api/schools/{id}/reviews` endpoint)

### #28 Export shortlist as PDF
DecisionSupport page has shortlist in localStorage but no export function.
**Status:** FIXED (added `GET /api/export/pdf?school_ids=1,2,3` endpoint using fpdf2)
