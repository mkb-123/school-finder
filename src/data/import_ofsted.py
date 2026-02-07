"""Import real Ofsted ratings and inspection history from official UK government data.

Downloads the official monthly management information CSV published by Ofsted
and imports both current ratings (into the ``schools`` table) and full inspection
history (into the ``ofsted_history`` table).

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

_CSV_URL = (
    "https://assets.publishing.service.gov.uk/media/696611308d599f4c09e1ffa9/"
    "Management_information_-_state-funded_schools_-_latest_inspections_as_at_31_Dec_2025.csv"
)


def _data_dir() -> Path:
    return Path(__file__).parent.parent.parent / "data"


def download_ofsted_data() -> Path:
    """Download the latest Ofsted management information CSV."""
    print("Downloading latest Ofsted data from GOV.UK...")
    response = httpx.get(_CSV_URL, follow_redirects=True, timeout=120.0)
    response.raise_for_status()

    data_dir = _data_dir()
    data_dir.mkdir(exist_ok=True, parents=True)
    csv_path = data_dir / "ofsted_latest.csv"

    csv_path.write_bytes(response.content)
    print(f"Downloaded {len(response.content) / 1024 / 1024:.1f} MB to {csv_path}")
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


def _load_csv(csv_path: Path, council_filter: str | None) -> pl.DataFrame:
    """Load and optionally filter the Ofsted CSV."""
    print("\nLoading Ofsted data...")
    df = pl.read_csv(csv_path, encoding="utf8-lossy", ignore_errors=True)
    print(f"Total records: {df.height:,}")
    if council_filter:
        df = df.filter(pl.col("Local authority") == council_filter)
        print(f"Filtered to {council_filter}: {df.height} schools")
    return df


def import_ofsted_ratings(db_path: Path, council_filter: str | None = None) -> dict:
    """Import current Ofsted ratings into the ``schools`` table.

    Returns dict with keys: updated, skipped, not_found.
    """
    csv_path = download_ofsted_data()
    df = _load_csv(csv_path, council_filter)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {"updated": 0, "skipped": 0, "not_found": 0}

    for row in df.iter_rows(named=True):
        urn = str(row.get("URN", ""))
        rating_code = str(row.get("Overall effectiveness", "")).strip()
        pub_date = row.get("Publication date", "")

        if rating_code not in OFSTED_RATINGS:
            stats["skipped"] += 1
            continue

        rating = OFSTED_RATINGS[rating_code]
        ofsted_date = parse_ofsted_date(pub_date)

        cursor.execute("SELECT id, name FROM schools WHERE urn = ?", (urn,))
        school = cursor.fetchone()
        if not school:
            stats["not_found"] += 1
            continue

        school_id, db_name = school
        cursor.execute(
            "UPDATE schools SET ofsted_rating = ?, ofsted_date = ? WHERE id = ?",
            (rating, ofsted_date, school_id),
        )
        stats["updated"] += 1
        print(f"  {db_name}: {rating} ({pub_date})")

    conn.commit()
    conn.close()

    print(f"\nRatings import: {stats['updated']} updated, {stats['skipped']} skipped, {stats['not_found']} not found")
    return stats


def import_ofsted_history(db_path: Path, council_filter: str | None = None) -> dict:
    """Import current and previous inspections into the ``ofsted_history`` table.

    Returns dict with keys: current_imported, previous_imported, errors.
    """
    csv_path = download_ofsted_data()
    df = _load_csv(csv_path, council_filter)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM ofsted_history")
    print("Cleared existing Ofsted history records")

    stats = {"current_imported": 0, "previous_imported": 0, "errors": 0}

    for row in df.iter_rows(named=True):
        urn = str(row.get("URN", ""))
        cursor.execute("SELECT id, name FROM schools WHERE urn = ?", (urn,))
        school = cursor.fetchone()
        if not school:
            continue

        school_id, db_name = school

        # Current inspection
        current_rating_code = str(row.get("Overall effectiveness", "")).strip()
        current_pub_date = row.get("Publication date", "")
        current_inspection_num = str(row.get("Inspection number of latest graded inspection", "")).strip()

        if current_rating_code in OFSTED_RATINGS and current_pub_date:
            current_date = parse_ofsted_date(current_pub_date)
            if current_date:
                report_url = None
                if current_inspection_num and current_inspection_num.isdigit():
                    report_url = f"https://reports.ofsted.gov.uk/provider/{current_inspection_num}"

                cursor.execute(
                    "INSERT INTO ofsted_history "
                    "(school_id, inspection_date, rating, report_url, is_current) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (school_id, current_date, OFSTED_RATINGS[current_rating_code], report_url, True),
                )
                stats["current_imported"] += 1
                print(f"  {db_name}: {OFSTED_RATINGS[current_rating_code]} ({current_pub_date}) - Current")

        # Previous inspection
        prev_rating_code = str(row.get("Previous graded inspection overall effectiveness", "")).strip()
        prev_pub_date = row.get("Previous publication date", "")
        prev_inspection_num = str(row.get("Previous graded inspection number", "")).strip()

        if prev_rating_code in OFSTED_RATINGS and prev_pub_date:
            prev_date = parse_ofsted_date(prev_pub_date)
            if prev_date:
                report_url = None
                if prev_inspection_num and prev_inspection_num.isdigit():
                    report_url = f"https://reports.ofsted.gov.uk/provider/{prev_inspection_num}"

                cursor.execute(
                    "INSERT INTO ofsted_history "
                    "(school_id, inspection_date, rating, report_url, is_current) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (school_id, prev_date, OFSTED_RATINGS[prev_rating_code], report_url, False),
                )
                stats["previous_imported"] += 1
                print(f"  {db_name}: {OFSTED_RATINGS[prev_rating_code]} ({prev_pub_date}) - Previous")

    conn.commit()
    conn.close()

    print(f"\nHistory import: {stats['current_imported']} current, {stats['previous_imported']} previous")
    return stats


if __name__ == "__main__":
    db_path = _data_dir() / "schools.db"

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Run the seed script first: uv run python -m src.db.seed")
        exit(1)

    print("Importing Ofsted data for Milton Keynes schools...")
    print("=" * 60)

    import_ofsted_ratings(db_path, council_filter="Milton Keynes")
    print()
    import_ofsted_history(db_path, council_filter="Milton Keynes")

    print("\nDone! Schools have verified Ofsted ratings and history from GOV.UK")
