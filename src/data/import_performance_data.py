"""Import real school performance data from DfE School Performance Tables.

This script downloads and imports verified academic performance data
(SATs, GCSEs, Progress 8, Attainment 8) from the official Department for
Education School Performance Tables.

Source: https://www.compare-school-performance.service.gov.uk/download-data
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import httpx
import polars as pl


def download_performance_data(year: int = 2024) -> tuple[Path, Path]:
    """Download the latest DfE school performance CSV files.

    Args:
        year: Academic year end (e.g., 2024 for 2023/24)

    Returns:
        Tuple of (primary_csv_path, secondary_csv_path)
    """
    data_dir = Path(__file__).parent.parent.parent / "data" / "performance"
    data_dir.mkdir(exist_ok=True, parents=True)

    # Primary school performance (KS2 SATs)
    primary_url = f"https://www.compare-school-performance.service.gov.uk/download-data?download=true&year={year}&phase=primary&fileformat=csv"

    # Secondary school performance (KS4 GCSEs, Progress 8)
    secondary_url = f"https://www.compare-school-performance.service.gov.uk/download-data?download=true&year={year}&phase=secondary&fileformat=csv"

    print(f"📥 Downloading DfE school performance data for {year-1}/{year}...")

    primary_path = data_dir / f"primary_performance_{year}.csv"
    secondary_path = data_dir / f"secondary_performance_{year}.csv"

    # Download primary
    print(f"  Downloading primary (KS2) data...")
    response = httpx.get(primary_url, follow_redirects=True, timeout=120.0)
    response.raise_for_status()
    primary_path.write_bytes(response.content)
    print(f"  ✅ Primary: {len(response.content) / 1024 / 1024:.1f} MB")

    # Download secondary
    print(f"  Downloading secondary (KS4) data...")
    response = httpx.get(secondary_url, follow_redirects=True, timeout=120.0)
    response.raise_for_status()
    secondary_path.write_bytes(response.content)
    print(f"  ✅ Secondary: {len(response.content) / 1024 / 1024:.1f} MB")

    return primary_path, secondary_path


def import_primary_performance(db_path: Path, csv_path: Path, council_filter: str | None = None) -> int:
    """Import KS2 SATs data from primary school performance CSV.

    Args:
        db_path: Path to SQLite database
        csv_path: Path to primary performance CSV
        council_filter: Optional council name to filter

    Returns:
        Number of records imported
    """
    print("\n📊 Loading primary (KS2 SATs) data...")
    df = pl.read_csv(csv_path, encoding="utf8-lossy", ignore_errors=True, infer_schema_length=10000)

    if council_filter:
        df = df.filter(pl.col("LA") == council_filter)
        print(f"Filtered to {council_filter}: {df.height} schools")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    imported = 0

    for row in df.iter_rows(named=True):
        urn = str(row.get("URN", ""))
        if not urn:
            continue

        # Find school by URN
        cursor.execute("SELECT id FROM schools WHERE urn = ?", (urn,))
        school = cursor.fetchone()
        if not school:
            continue

        school_id = school[0]
        year = row.get("ACADEMICYEAR", "")

        # Extract KS2 metrics
        # Reading, Writing, Maths at expected standard
        reading_exp = row.get("PTREADEXPECTED_KS2", "")
        writing_exp = row.get("PTWRITTAEXP_KS2", "")
        maths_exp = row.get("PTMATHSEXPECTED_KS2", "")

        # Reading, Writing, Maths at higher standard
        reading_high = row.get("PTREADHIGHER_KS2", "")
        writing_high = row.get("PTWRITTHIGHER_KS2", "")
        maths_high = row.get("PTMATHSHIGHER_KS2", "")

        # RWM combined expected standard
        rwm_exp = row.get("PTRWMEXPECTED_KS2", "")

        # Insert expected standard metrics
        if reading_exp and reading_exp not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "SATs_Reading_Expected", f"{reading_exp}%", int(year) if year else None)
            )
            imported += 1

        if writing_exp and writing_exp not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "SATs_Writing_Expected", f"{writing_exp}%", int(year) if year else None)
            )
            imported += 1

        if maths_exp and maths_exp not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "SATs_Maths_Expected", f"{maths_exp}%", int(year) if year else None)
            )
            imported += 1

        if rwm_exp and rwm_exp not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "SATs", f"Expected standard: {rwm_exp}%", int(year) if year else None)
            )
            imported += 1

        # Insert higher standard metrics
        if reading_high and reading_high not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "SATs_Reading_Higher", f"{reading_high}%", int(year) if year else None)
            )
            imported += 1

        if writing_high and writing_high not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "SATs_Writing_Higher", f"{writing_high}%", int(year) if year else None)
            )
            imported += 1

        if maths_high and maths_high not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "SATs_Maths_Higher", f"{maths_high}%", int(year) if year else None)
            )
            imported += 1

    conn.commit()
    conn.close()

    print(f"✅ Imported {imported} primary performance metrics")
    return imported


def import_secondary_performance(db_path: Path, csv_path: Path, council_filter: str | None = None) -> int:
    """Import KS4 GCSE, Progress 8, Attainment 8 data from secondary performance CSV.

    Args:
        db_path: Path to SQLite database
        csv_path: Path to secondary performance CSV
        council_filter: Optional council name to filter

    Returns:
        Number of records imported
    """
    print("\n📊 Loading secondary (KS4 GCSE) data...")
    df = pl.read_csv(csv_path, encoding="utf8-lossy", ignore_errors=True, infer_schema_length=10000)

    if council_filter:
        df = df.filter(pl.col("LA") == council_filter)
        print(f"Filtered to {council_filter}: {df.height} schools")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    imported = 0

    for row in df.iter_rows(named=True):
        urn = str(row.get("URN", ""))
        if not urn:
            continue

        # Find school by URN
        cursor.execute("SELECT id FROM schools WHERE urn = ?", (urn,))
        school = cursor.fetchone()
        if not school:
            continue

        school_id = school[0]
        year = row.get("ACADEMICYEAR", "")

        # Progress 8 score
        progress8 = row.get("P8MEA", "")
        if progress8 and progress8 not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "Progress8", str(progress8), int(year) if year else None)
            )
            imported += 1

        # Attainment 8 score
        attainment8 = row.get("ATT8SCR", "")
        if attainment8 and attainment8 not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "Attainment8", str(attainment8), int(year) if year else None)
            )
            imported += 1

        # English & Maths 9-5
        eng_maths_95 = row.get("PT_L2BASICS_95", "")
        if eng_maths_95 and eng_maths_95 not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "GCSE", f"English & Maths 9-5: {eng_maths_95}%", int(year) if year else None)
            )
            imported += 1

        # English & Maths 9-4
        eng_maths_94 = row.get("PT_L2BASICS_94", "")
        if eng_maths_94 and eng_maths_94 not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "GCSE_94", f"English & Maths 9-4: {eng_maths_94}%", int(year) if year else None)
            )
            imported += 1

        # EBacc entered
        ebacc_entered = row.get("PT_EBACCENT", "")
        if ebacc_entered and ebacc_entered not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "EBacc_Entered", f"{ebacc_entered}%", int(year) if year else None)
            )
            imported += 1

        # EBacc achieved (9-5)
        ebacc_achieved = row.get("PT_EBACCACH_95", "")
        if ebacc_achieved and ebacc_achieved not in ["NE", "SUPP", "NA"]:
            cursor.execute(
                "INSERT INTO school_performance (school_id, metric_type, metric_value, year) VALUES (?, ?, ?, ?)",
                (school_id, "EBacc_Achieved", f"{ebacc_achieved}%", int(year) if year else None)
            )
            imported += 1

    conn.commit()
    conn.close()

    print(f"✅ Imported {imported} secondary performance metrics")
    return imported


if __name__ == "__main__":
    db_path = Path(__file__).parent.parent.parent / "data" / "schools.db"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run the seed script first: uv run python -m src.db.seed")
        exit(1)

    print("🏫 Importing real school performance data from DfE School Performance Tables...")
    print("=" * 70)

    # Download latest data
    primary_csv, secondary_csv = download_performance_data(year=2024)

    # Import primary (SATs)
    primary_count = import_primary_performance(db_path, primary_csv, council_filter="Milton Keynes")

    # Import secondary (GCSEs, Progress 8)
    secondary_count = import_secondary_performance(db_path, secondary_csv, council_filter="Milton Keynes")

    print(f"\n✅ Done! Imported {primary_count + secondary_count} total performance metrics from DfE")
