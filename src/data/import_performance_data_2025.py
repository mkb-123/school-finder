"""Import school performance data from the NEW Explore Education Statistics API (2025).

The DfE migrated from compare-school-performance to explore-education-statistics.
This script uses the official REST API to download 2024/2025 performance data.

API Documentation: https://api.education.gov.uk/statistics/docs/
Data Catalogue: https://explore-education-statistics.service.gov.uk/data-catalogue
"""

import sqlite3
from pathlib import Path

import httpx
import polars as pl


# Data set IDs from Explore Education Statistics API
# Find more at: https://explore-education-statistics.service.gov.uk/data-catalogue
KS2_DATASET_ID = "2ff21cfc-db60-413e-9b02-47dc91d12740"  # KS2 attainment by school location
KS4_DATASET_ID = "d7ce19cb-916b-45d6-9dc1-3e581e16fa1a"  # KS4 institution level (GCSEs, Progress 8)

API_BASE = "https://api.education.gov.uk/statistics/v1"


def download_dataset_csv(dataset_id: str, output_path: Path) -> None:
    """Download a dataset as CSV from Explore Education Statistics API.

    Args:
        dataset_id: The UUID of the dataset in the EES catalogue
        output_path: Where to save the CSV file
    """
    url = f"{API_BASE}/data-sets/{dataset_id}/csv"

    print(f"📥 Downloading dataset {dataset_id}...")
    print(f"   URL: {url}")

    headers = {
        "User-Agent": "School-Finder/1.0 (Education Data Import)",
        "Accept": "text/csv, application/x-gzip",
    }

    # API returns gzip-compressed CSV
    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=300.0) as response:
        response.raise_for_status()

        # Save compressed data
        with output_path.open("wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"   ✅ Downloaded: {size_mb:.1f} MB")


def import_ks2_performance(db_path: Path, csv_path: Path, council_filter: str | None = None) -> int:
    """Import KS2 SATs data from 2024/2025 EES dataset.

    Args:
        db_path: Path to SQLite database
        csv_path: Path to KS2 performance CSV
        council_filter: Optional local authority name to filter

    Returns:
        Number of records imported
    """
    print("\n📊 Loading KS2 (SATs) data from Explore Education Statistics...")

    # Read CSV (may be gzip-compressed)
    try:
        df = pl.read_csv(csv_path, encoding="utf8-lossy", ignore_errors=True, infer_schema_length=10000)
    except Exception:
        # Try reading as gzip
        import gzip
        with gzip.open(csv_path, "rb") as f:
            df = pl.read_csv(f, encoding="utf8-lossy", ignore_errors=True, infer_schema_length=10000)

    print(f"Loaded {df.height} rows, {df.width} columns")
    print(f"Columns: {df.columns[:10]}...")  # Show first 10 columns

    if council_filter:
        # Filter by local authority (column name may vary)
        la_cols = [c for c in df.columns if "local" in c.lower() or "authority" in c.lower()]
        if la_cols:
            df = df.filter(pl.col(la_cols[0]) == council_filter)
            print(f"Filtered to {council_filter}: {df.height} schools")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    imported = 0

    # TODO: Map EES column names to our database schema
    # The exact column names depend on the dataset structure
    # Example columns might be: "URN", "School_name", "Reading_%_expected", etc.

    print("⚠️  Column mapping needed - check CSV structure first")
    print(f"Available columns: {df.columns}")

    conn.close()
    return imported


def import_ks4_performance(db_path: Path, csv_path: Path, council_filter: str | None = None) -> int:
    """Import KS4 GCSE and Progress 8 data from 2024/2025 EES dataset.

    Args:
        db_path: Path to SQLite database
        csv_path: Path to KS4 performance CSV
        council_filter: Optional local authority name to filter

    Returns:
        Number of records imported
    """
    print("\n📊 Loading KS4 (GCSE) data from Explore Education Statistics...")

    try:
        df = pl.read_csv(csv_path, encoding="utf8-lossy", ignore_errors=True, infer_schema_length=10000)
    except Exception:
        import gzip
        with gzip.open(csv_path, "rb") as f:
            df = pl.read_csv(f, encoding="utf8-lossy", ignore_errors=True, infer_schema_length=10000)

    print(f"Loaded {df.height} rows, {df.width} columns")
    print(f"Columns: {df.columns[:10]}...")

    if council_filter:
        la_cols = [c for c in df.columns if "local" in c.lower() or "authority" in c.lower()]
        if la_cols:
            df = df.filter(pl.col(la_cols[0]) == council_filter)
            print(f"Filtered to {council_filter}: {df.height} schools")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    imported = 0

    print("⚠️  Column mapping needed - check CSV structure first")
    print(f"Available columns: {df.columns}")

    conn.close()
    return imported


if __name__ == "__main__":
    db_path = Path(__file__).parent.parent.parent / "data" / "schools.db"
    data_dir = Path(__file__).parent.parent.parent / "data" / "performance_2025"
    data_dir.mkdir(exist_ok=True, parents=True)

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run the seed script first: uv run python -m src.db.seed")
        exit(1)

    print("🏫 Importing 2024/2025 school performance data from Explore Education Statistics API")
    print("=" * 80)
    print(f"API: {API_BASE}")
    print(f"Data Catalogue: https://explore-education-statistics.service.gov.uk/data-catalogue")
    print()

    try:
        # Download KS2 data
        ks2_csv = data_dir / "ks2_2025.csv.gz"
        if not ks2_csv.exists():
            download_dataset_csv(KS2_DATASET_ID, ks2_csv)

        # Download KS4 data
        ks4_csv = data_dir / "ks4_2025.csv.gz"
        if not ks4_csv.exists():
            download_dataset_csv(KS4_DATASET_ID, ks4_csv)

        # Import data (column mapping needed first)
        print("\n⚠️  NEXT STEP: Inspect the CSV files to map column names")
        print(f"   KS2: {ks2_csv}")
        print(f"   KS4: {ks4_csv}")
        print("\nOnce column names are mapped, uncomment the import calls below:")
        print("   # ks2_count = import_ks2_performance(db_path, ks2_csv, 'Milton Keynes')")
        print("   # ks4_count = import_ks4_performance(db_path, ks4_csv, 'Milton Keynes')")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
