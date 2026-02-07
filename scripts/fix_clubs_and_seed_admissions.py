"""Fix duplicated clubs data and seed admissions history from real MK Council data.

This script:
1. Deduplicates the school_clubs table (keeping one entry per school+type+name combo)
2. Updates Caroline Haslett Primary School with real Faraday Club data
3. Seeds admissions_history with real 2024 allocation data from MK Council
4. Seeds 2022 secondary school allocation data

All data comes from official Milton Keynes City Council published documents:
- Primary: Parent Guide Primary 2025 (published Aug 2024)
- Secondary: Allocation Profile 1 March 2022

NO random/fake data is generated.
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "schools.db"
ADMISSIONS_JSON = Path(__file__).parent.parent / "data" / "cache" / "mk_admissions_2024.json"

# Conversion factor: miles to km
MILES_TO_KM = 1.60934

# Source URLs for admissions data
PRIMARY_2024_SOURCE = (
    "https://www.milton-keynes.gov.uk/sites/default/files/2024-08/"
    "Parent%20Guide%20Primary%202025%20FINAL.pdf"
)
SECONDARY_2022_SOURCE = (
    "https://www.milton-keynes.gov.uk/sites/default/files/2022-03/"
    "Allocation%20Profile%201%20March%202022AA.pdf"
)

# MK Council admissions page for general reference
MK_ADMISSIONS_PAGE = (
    "https://www.milton-keynes.gov.uk/schools-and-lifelong-learning/school-admissions"
)

# Secondary school allocation data from the 2022 allocation profile PDF
# This is real data extracted from the official document
SECONDARY_2022_DATA = [
    {
        "school_name": "Denbigh School",
        "allocation_description": "All applicants allocated up to criterion 4a (in catchment and attend a partner school) and some allocated to criterion 4b (in catchment) to a distance of 0.541 miles.",
        "last_distance_miles": 0.541,
        "had_vacancies": False,
    },
    {
        "school_name": "Glebe Farm School",
        "allocation_description": "All applicants offered a place plus additional children not allocated a preferred school.",
        "last_distance_miles": None,
        "had_vacancies": True,
    },
    {
        "school_name": "Kents Hill Park School",
        "allocation_description": "All applicants allocated up to criterion 5 (outside catchment with sibling) and some allocated under criterion 6 (other children) to a distance of 1.921 miles.",
        "last_distance_miles": 1.921,
        "had_vacancies": False,
    },
    {
        "school_name": "Lord Grey Academy",
        "allocation_description": "All applicants allocated up to criterion 2 (siblings attending the school) and some allocated under criterion 3 (living in catchment) to a distance of 0.987 miles",
        "last_distance_miles": 0.987,
        "had_vacancies": False,
    },
    {
        "school_name": "Oakgrove School",
        "allocation_description": "All applicants allocated up to criterion 6 (outside catchment with sibling) and some allocated under criterion 7 (outside catchment and attend a feeder school) to a distance of 1.332 miles.",
        "last_distance_miles": 1.332,
        "had_vacancies": False,
    },
    {
        "school_name": "Ousedale School",
        "allocation_description": "All applicants allocated up to criterion 2 (in catchment)",
        "last_distance_miles": None,
        "had_vacancies": False,
    },
    {
        "school_name": "Shenley Brook End School",
        "allocation_description": "All applicants allocated up to criterion 5 (children of staff) and some allocated under criterion 6 (outside catchment) to a distance of 1.007 miles.",
        "last_distance_miles": 1.007,
        "had_vacancies": False,
    },
    {
        "school_name": "Sir Herbert Leon Academy",
        "allocation_description": "All applicants allocated a place plus additional children not allocated a preferred school.",
        "last_distance_miles": None,
        "had_vacancies": False,
    },
    {
        "school_name": "St. Paul's Catholic School",
        "allocation_description": "All applicants allocated up to criterion J4 (children attending a feeder school)",
        "last_distance_miles": None,
        "had_vacancies": False,
    },
    {
        "school_name": "Stantonbury School",
        "allocation_description": "All applicants allocated a place plus additional children not allocated a preferred school.",
        "last_distance_miles": None,
        "had_vacancies": True,
    },
    {
        "school_name": "The Hazeley Academy",
        "allocation_description": "All applicants allocated up to criterion 5 (in catchment) and some allocated under criterion 6 (outside catchment with sibling) to a distance of 2.124 miles.",
        "last_distance_miles": 2.124,
        "had_vacancies": False,
    },
    {
        "school_name": "The Milton Keynes Academy",
        "allocation_description": "All applicants allocated a place plus additional children not allocated a preferred school.",
        "last_distance_miles": None,
        "had_vacancies": False,
    },
    {
        "school_name": "The Radcliffe School",
        "allocation_description": "All applicants allocated a place up to criterion 7 (outside catchment)",
        "last_distance_miles": None,
        "had_vacancies": False,
    },
    {
        "school_name": "Walton High",
        "allocation_description": "All applicants allocated up to criterion 10 (outside catchment and attends feeder school) and some allocated under criterion 11 (outside catchment) to a distance of 2.246 miles to the Walnut Tree campus.",
        "last_distance_miles": 2.246,
        "had_vacancies": False,
    },
    {
        "school_name": "Watling Academy",
        "allocation_description": "All applicants allocated up to criterion 4 (outside catchment with sibling) and some allocated up to criterion 5 (other children) to a distance of 3.593 miles",
        "last_distance_miles": 3.593,
        "had_vacancies": False,
    },
]


def get_school_id_by_name(conn: sqlite3.Connection, name: str) -> int | None:
    """Look up a school ID by name, using fuzzy matching."""
    # Try exact match first
    cur = conn.execute("SELECT id FROM schools WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]

    # Try LIKE match (handles minor name differences)
    # Extract first significant words for matching
    search_term = name.split(" ")[0]
    if search_term in ("The", "St", "St."):
        search_term = " ".join(name.split(" ")[:3])

    cur = conn.execute("SELECT id, name FROM schools WHERE name LIKE ?", (f"%{search_term}%",))
    rows = cur.fetchall()

    if len(rows) == 1:
        return rows[0][0]

    # More specific matching for common patterns
    for row in rows:
        db_name = row[1].lower()
        search_name = name.lower()
        # Remove common suffixes for comparison
        for suffix in [" school", " primary school", " academy", " primary", " and nursery"]:
            db_name = db_name.replace(suffix, "")
            search_name = search_name.replace(suffix, "")
        if db_name.strip() == search_name.strip():
            return row[0]

    return None


def deduplicate_clubs(conn: sqlite3.Connection) -> int:
    """Remove duplicate club entries, keeping the one with the most data (or lowest ID)."""
    # Find all duplicate groups
    cur = conn.execute("""
        SELECT school_id, club_type, name, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
        FROM school_clubs
        GROUP BY school_id, club_type, name
        HAVING cnt > 1
    """)
    duplicates = cur.fetchall()

    total_removed = 0
    for school_id, club_type, name, cnt, ids_str in duplicates:
        ids = [int(x) for x in ids_str.split(",")]
        # Keep the first ID (lowest), delete the rest
        keep_id = ids[0]
        delete_ids = ids[1:]

        placeholders = ",".join("?" * len(delete_ids))
        conn.execute(f"DELETE FROM school_clubs WHERE id IN ({placeholders})", delete_ids)
        total_removed += len(delete_ids)

    conn.commit()
    return total_removed


def update_caroline_haslett_clubs(conn: sqlite3.Connection) -> None:
    """Update Caroline Haslett Primary School with real Faraday Club data.

    Source: https://www.haslett.org.uk/faraday-club/breakfast-and-after-school-club
    - Breakfast Club: £5.00 per day
    - After School Club: £11.00 per day
    - Combined (BC & ASC): £14.50 per day
    - Registration: £8.00 per child or £10.00 per family
    - Staff hold minimum Level 2 qualifications and current DBS certificates
    - Ages 4-12
    """
    # Find Caroline Haslett's school ID
    cur = conn.execute("SELECT id FROM schools WHERE name LIKE '%Caroline Haslett%'")
    row = cur.fetchone()
    if not row:
        print("WARNING: Caroline Haslett Primary School not found in database")
        return

    school_id = row[0]

    # Delete existing clubs for this school
    conn.execute("DELETE FROM school_clubs WHERE school_id = ?", (school_id,))

    # Insert real club data from Faraday Club website
    clubs = [
        {
            "school_id": school_id,
            "club_type": "breakfast",
            "name": "Faraday Club - Breakfast Club",
            "description": "The Faraday Club is a safe, inclusive, welcoming setting for children aged 4-12. Staff hold minimum Level 2 qualifications and current DBS certificates. Contact: 01908 695410 or 07966 470676.",
            "days_available": "Mon,Tue,Wed,Thu,Fri",
            "start_time": None,  # Exact times not published on website
            "end_time": None,
            "cost_per_session": 5.00,
        },
        {
            "school_id": school_id,
            "club_type": "after_school",
            "name": "Faraday Club - After School Club",
            "description": "The Faraday Club offers great play opportunities including sports programmes with purpose-built facilities. Ages 4-12. Combined breakfast + after school: £14.50/day. Registration: £8.00/child or £10.00/family.",
            "days_available": "Mon,Tue,Wed,Thu,Fri",
            "start_time": None,
            "end_time": None,
            "cost_per_session": 11.00,
        },
    ]

    for club in clubs:
        conn.execute(
            """INSERT INTO school_clubs
               (school_id, club_type, name, description, days_available, start_time, end_time, cost_per_session)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                club["school_id"],
                club["club_type"],
                club["name"],
                club["description"],
                club["days_available"],
                club["start_time"],
                club["end_time"],
                club["cost_per_session"],
            ),
        )

    conn.commit()
    print(f"  Updated Caroline Haslett (school_id={school_id}) with 2 real Faraday Club entries")


def seed_primary_admissions_2024(conn: sqlite3.Connection) -> int:
    """Seed admissions_history with 2024 primary allocation data from MK Council."""
    if not ADMISSIONS_JSON.exists():
        print(f"WARNING: {ADMISSIONS_JSON} not found - skipping primary admissions seeding")
        return 0

    with open(ADMISSIONS_JSON) as f:
        admissions_data = json.load(f)

    # First, add the new columns if they don't exist
    # (migration-like approach for SQLite)
    try:
        conn.execute("SELECT allocation_description FROM admissions_history LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE admissions_history ADD COLUMN allocation_description TEXT")
        conn.execute("ALTER TABLE admissions_history ADD COLUMN had_vacancies BOOLEAN")
        conn.execute("ALTER TABLE admissions_history ADD COLUMN intake_year VARCHAR(20)")
        conn.execute("ALTER TABLE admissions_history ADD COLUMN source_url TEXT")

    inserted = 0
    not_found = []

    for entry in admissions_data:
        school_name = entry["school_name"]
        school_id = get_school_id_by_name(conn, school_name)

        if school_id is None:
            not_found.append(school_name)
            continue

        # Check if already exists for this school+year
        cur = conn.execute(
            "SELECT id FROM admissions_history WHERE school_id = ? AND academic_year = ? AND intake_year = ?",
            (school_id, "2024/2025", entry.get("intake_year", "Year R")),
        )
        if cur.fetchone():
            continue

        # Convert miles to km for last_distance
        last_distance_km = None
        if entry.get("last_distance_miles") is not None:
            last_distance_km = round(entry["last_distance_miles"] * MILES_TO_KM, 3)

        had_vacancies = entry.get("had_vacancies") == "YES" if entry.get("had_vacancies") else None

        conn.execute(
            """INSERT INTO admissions_history
               (school_id, academic_year, places_offered, applications_received,
                last_distance_offered_km, allocation_description, had_vacancies,
                intake_year, source_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                school_id,
                "2024/2025",
                entry.get("places_offered"),
                entry.get("applications_received"),
                last_distance_km,
                entry.get("offered_text"),
                had_vacancies,
                entry.get("intake_year", "Year R"),
                PRIMARY_2024_SOURCE,
            ),
        )
        inserted += 1

    conn.commit()

    if not_found:
        print(f"  WARNING: Could not match {len(not_found)} schools:")
        for name in not_found:
            print(f"    - {name}")

    return inserted


def seed_secondary_admissions_2022(conn: sqlite3.Connection) -> int:
    """Seed admissions_history with 2022 secondary allocation data from MK Council."""
    inserted = 0
    not_found = []

    for entry in SECONDARY_2022_DATA:
        school_name = entry["school_name"]
        school_id = get_school_id_by_name(conn, school_name)

        if school_id is None:
            not_found.append(school_name)
            continue

        # Check if already exists
        cur = conn.execute(
            "SELECT id FROM admissions_history WHERE school_id = ? AND academic_year = ?",
            (school_id, "2022/2023"),
        )
        if cur.fetchone():
            continue

        last_distance_km = None
        if entry.get("last_distance_miles") is not None:
            last_distance_km = round(entry["last_distance_miles"] * MILES_TO_KM, 3)

        conn.execute(
            """INSERT INTO admissions_history
               (school_id, academic_year, places_offered, applications_received,
                last_distance_offered_km, allocation_description, had_vacancies,
                intake_year, source_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                school_id,
                "2022/2023",
                None,  # Not available in the allocation profile
                None,
                last_distance_km,
                entry["allocation_description"],
                entry["had_vacancies"],
                "Year 7",
                SECONDARY_2022_SOURCE,
            ),
        )
        inserted += 1

    conn.commit()

    if not_found:
        print(f"  WARNING: Could not match {len(not_found)} secondary schools:")
        for name in not_found:
            print(f"    - {name}")

    return inserted


def main() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))

    print("=" * 60)
    print("School Finder: Fix Clubs & Seed Admissions Data")
    print("=" * 60)

    # Step 1: Deduplicate clubs
    print("\n1. Deduplicating clubs data...")
    removed = deduplicate_clubs(conn)
    print(f"  Removed {removed} duplicate club entries")

    # Verify
    cur = conn.execute("SELECT COUNT(*) FROM school_clubs")
    print(f"  Remaining clubs: {cur.fetchone()[0]}")

    # Step 2: Update Caroline Haslett
    print("\n2. Updating Caroline Haslett with real Faraday Club data...")
    update_caroline_haslett_clubs(conn)

    # Step 3: Seed primary admissions 2024
    print("\n3. Seeding primary school admissions data (2024/2025)...")
    primary_count = seed_primary_admissions_2024(conn)
    print(f"  Inserted {primary_count} primary admissions records")

    # Step 4: Seed secondary admissions 2022
    print("\n4. Seeding secondary school admissions data (2022/2023)...")
    secondary_count = seed_secondary_admissions_2022(conn)
    print(f"  Inserted {secondary_count} secondary admissions records")

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    cur = conn.execute("SELECT COUNT(*) FROM school_clubs")
    print(f"  Total clubs: {cur.fetchone()[0]}")
    cur = conn.execute("SELECT COUNT(*) FROM admissions_history")
    print(f"  Total admissions records: {cur.fetchone()[0]}")

    # Show oversubscribed schools
    cur = conn.execute("""
        SELECT s.name, ah.academic_year, ah.applications_received, ah.places_offered,
               ah.last_distance_offered_km, ah.had_vacancies
        FROM admissions_history ah
        JOIN schools s ON s.id = ah.school_id
        WHERE ah.had_vacancies = 0
        ORDER BY ah.last_distance_offered_km ASC
    """)
    oversubscribed = cur.fetchall()
    if oversubscribed:
        print(f"\n  Oversubscribed schools ({len(oversubscribed)}):")
        for name, year, apps, places, dist, _ in oversubscribed:
            dist_str = f"{dist:.3f} km" if dist else "N/A"
            apps_str = f"{apps} apps" if apps else ""
            print(f"    {name} ({year}): {places or '?'} places, {apps_str}, last distance: {dist_str}")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
