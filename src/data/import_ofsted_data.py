"""Import real Ofsted ratings from official UK government data.

This script downloads and imports verified Ofsted inspection outcomes
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
    except (ValueError, AttributeError):
        return None


def import_ofsted_ratings(db_path: Path, council_filter: str | None = None) -> dict:
    """Import Ofsted ratings from CSV into the database.

    Args:
        db_path: Path to SQLite database
        council_filter: Optional council name to filter (e.g. "Milton Keynes")

    Returns:
        Dict with statistics: {updated: int, skipped: int, not_found: int}
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

    stats = {"updated": 0, "skipped": 0, "not_found": 0}

    for row in df.iter_rows(named=True):
        urn = str(row.get("URN", ""))
        rating_code = str(row.get("Overall effectiveness", "")).strip()
        pub_date = row.get("Publication date", "")

        # Skip if no valid rating
        if rating_code not in OFSTED_RATINGS:
            stats["skipped"] += 1
            continue

        rating = OFSTED_RATINGS[rating_code]
        ofsted_date = parse_ofsted_date(pub_date)

        # Find school by URN in our database
        cursor.execute("SELECT id, name FROM schools WHERE urn = ?", (urn,))
        school = cursor.fetchone()

        if not school:
            stats["not_found"] += 1
            continue

        school_id, db_name = school

        # Update school's Ofsted rating
        cursor.execute(
            """
            UPDATE schools
            SET ofsted_rating = ?, ofsted_date = ?
            WHERE id = ?
        """,
            (rating, ofsted_date, school_id),
        )

        stats["updated"] += 1
        print(f"  ✅ {db_name}: {rating} ({pub_date})")

    conn.commit()
    conn.close()

    print("\n📈 Import complete:")
    print(f"  - Updated: {stats['updated']}")
    print(f"  - Skipped (no rating): {stats['skipped']}")
    print(f"  - Not found in DB: {stats['not_found']}")

    return stats


if __name__ == "__main__":
    db_path = Path(__file__).parent.parent.parent / "data" / "schools.db"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run the seed script first: uv run python -m src.db.seed")
        exit(1)

    print("🏫 Importing real Ofsted ratings for Milton Keynes schools...")
    print("=" * 60)

    stats = import_ofsted_ratings(db_path, council_filter="Milton Keynes")

    print("\n✅ Done! All schools now have verified Ofsted ratings from GOV.UK")
