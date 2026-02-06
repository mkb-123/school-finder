"""Import Ofsted inspection history from official UK government data.

This script imports both current and historical Ofsted inspection records
from the official monthly management information CSV published by Ofsted.

Source: https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import httpx
import polars as pl


# Ofsted rating mappings (1=Outstanding, 2=Good, 3=Requires Improvement, 4=Inadequate)
OFSTED_RATINGS = {
    "1": "Outstanding",
    "2": "Good",
    "3": "Requires Improvement",
    "4": "Inadequate",
}


def download_ofsted_data() -> Path:
    """Download the latest Ofsted management information CSV."""
    csv_url = "https://assets.publishing.service.gov.uk/media/696611308d599f4c09e1ffa9/Management_information_-_state-funded_schools_-_latest_inspections_as_at_31_Dec_2025.csv"

    print("📥 Downloading latest Ofsted data from GOV.UK...")
    response = httpx.get(csv_url, follow_redirects=True, timeout=120.0)
    response.raise_for_status()

    data_dir = Path(__file__).parent.parent.parent / "data"
    data_dir.mkdir(exist_ok=True, parents=True)
    csv_path = data_dir / "ofsted_latest.csv"

    csv_path.write_bytes(response.content)
    print(f"✅ Downloaded {len(response.content) / 1024 / 1024:.1f} MB to {csv_path}")

    return csv_path


def parse_ofsted_date(date_str: str) -> str | None:
    """Parse Ofsted date from DD/MM/YYYY format to YYYY-MM-DD."""
    if not date_str or date_str.strip() == "":
        return None

    try:
        dt = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except:
        return None


def import_ofsted_history(db_path: Path, council_filter: str | None = None) -> dict:
    """Import Ofsted inspection history from CSV into the database.

    Imports both the latest inspection and previous inspection for each school.

    Args:
        db_path: Path to SQLite database
        council_filter: Optional council name to filter (e.g. "Milton Keynes")

    Returns:
        Dict with statistics: {current_imported: int, previous_imported: int, errors: int}
    """
    # Download data
    csv_path = download_ofsted_data()

    # Load CSV
    print("\n📊 Loading Ofsted data...")
    df = pl.read_csv(csv_path, encoding="utf8-lossy", ignore_errors=True)
    print(f"Total records: {df.height:,}")

    # Filter by council if specified
    if council_filter:
        df = df.filter(pl.col("Local authority") == council_filter)
        print(f"Filtered to {council_filter}: {df.height} schools")

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Clear existing Ofsted history (we're reimporting from source)
    cursor.execute("DELETE FROM ofsted_history")
    print("🗑️  Cleared existing Ofsted history records")

    stats = {"current_imported": 0, "previous_imported": 0, "errors": 0}

    for row in df.iter_rows(named=True):
        urn = str(row.get("URN", ""))
        school_name = row.get("School name", "")

        # Find school by URN in our database
        cursor.execute("SELECT id, name FROM schools WHERE urn = ?", (urn,))
        school = cursor.fetchone()

        if not school:
            continue

        school_id, db_name = school

        # Import current/latest graded inspection
        current_rating_code = str(row.get("Overall effectiveness", "")).strip()
        current_pub_date = row.get("Publication date", "")
        current_inspection_num = str(row.get("Inspection number of latest graded inspection", "")).strip()

        if current_rating_code in OFSTED_RATINGS and current_pub_date:
            current_rating = OFSTED_RATINGS[current_rating_code]
            current_date = parse_ofsted_date(current_pub_date)

            if current_date:
                # Build report URL if we have inspection number
                report_url = None
                if current_inspection_num and current_inspection_num.isdigit():
                    report_url = f"https://reports.ofsted.gov.uk/provider/{current_inspection_num}"

                cursor.execute(
                    """
                    INSERT INTO ofsted_history (
                        school_id, inspection_date, rating, report_url, is_current
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (school_id, current_date, current_rating, report_url, True),
                )
                stats["current_imported"] += 1
                print(f"  ✅ {db_name}: {current_rating} ({current_pub_date}) - Current")

        # Import previous graded inspection
        previous_rating_code = str(row.get("Previous graded inspection overall effectiveness", "")).strip()
        previous_pub_date = row.get("Previous publication date", "")
        previous_inspection_num = str(row.get("Previous graded inspection number", "")).strip()

        if previous_rating_code in OFSTED_RATINGS and previous_pub_date:
            previous_rating = OFSTED_RATINGS[previous_rating_code]
            previous_date = parse_ofsted_date(previous_pub_date)

            if previous_date:
                # Build report URL if we have inspection number
                report_url = None
                if previous_inspection_num and previous_inspection_num.isdigit():
                    report_url = f"https://reports.ofsted.gov.uk/provider/{previous_inspection_num}"

                cursor.execute(
                    """
                    INSERT INTO ofsted_history (
                        school_id, inspection_date, rating, report_url, is_current
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (school_id, previous_date, previous_rating, report_url, False),
                )
                stats["previous_imported"] += 1
                print(f"  ✅ {db_name}: {previous_rating} ({previous_pub_date}) - Previous")

    conn.commit()
    conn.close()

    print(f"\n📈 Import complete:")
    print(f"  - Current inspections imported: {stats['current_imported']}")
    print(f"  - Previous inspections imported: {stats['previous_imported']}")
    print(f"  - Errors: {stats['errors']}")

    return stats


if __name__ == "__main__":
    db_path = Path(__file__).parent.parent.parent / "data" / "schools.db"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run the seed script first: uv run python -m src.db.seed")
        exit(1)

    print("🏫 Importing real Ofsted inspection history for Milton Keynes schools...")
    print("=" * 60)

    stats = import_ofsted_history(db_path, council_filter="Milton Keynes")

    print("\n✅ Done! Schools now have verified Ofsted inspection history from GOV.UK")
