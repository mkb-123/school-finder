"""Seed the school-finder database from GIAS (Get Information About Schools) data.

Downloads the Department for Education's GIAS establishment CSV, filters to a
specific local authority (council), maps columns to the School model, and
upserts records into the SQLite database.

Usage::

    python -m src.db.seed --council "Milton Keynes"

The script caches the downloaded CSV in ``data/seeds/`` so that subsequent runs
do not re-download.  To force a fresh download, pass ``--force-download``.

Data source
-----------
https://get-information-schools.service.gov.uk/Downloads
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import sys
from datetime import date, datetime
from pathlib import Path

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import Base, School

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SEEDS_DIR = PROJECT_ROOT / "data" / "seeds"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "schools.db"

# ---------------------------------------------------------------------------
# GIAS download URL template
# ---------------------------------------------------------------------------
# The DfE publishes daily CSVs at a predictable URL.  The date component uses
# the ``YYYYMMDD`` format.  If the URL changes, the user can download the file
# manually from https://get-information-schools.service.gov.uk/Downloads and
# place it in ``data/seeds/``.

GIAS_CSV_URL_TEMPLATE = (
    "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/edubasealldata{date}.csv"
)

# ---------------------------------------------------------------------------
# GIAS column constants
# ---------------------------------------------------------------------------
# GIAS appends ``(name)`` to lookup/reference columns to distinguish the
# human-readable value from the underlying numeric code.

COL_URN = "URN"
COL_NAME = "EstablishmentName"
COL_TYPE = "TypeOfEstablishment (name)"
COL_TYPE_GROUP = "EstablishmentTypeGroup (name)"
COL_STATUS = "EstablishmentStatus (name)"
COL_LA = "LA (name)"
COL_STREET = "Street"
COL_LOCALITY = "Locality"
COL_ADDRESS3 = "Address3"
COL_TOWN = "Town"
COL_POSTCODE = "Postcode"
COL_EASTING = "Easting"
COL_NORTHING = "Northing"
COL_GENDER = "Gender (name)"
COL_RELIGION = "ReligiousCharacter (name)"
COL_LOW_AGE = "StatutoryLowAge"
COL_HIGH_AGE = "StatutoryHighAge"
COL_OFSTED_RATING = "OfstedRating (name)"
COL_OFSTED_DATE = "OfstedLastInsp"
COL_PHASE = "PhaseOfEducation (name)"
COL_WEBSITE = "SchoolWebsite"

# Establishment type groups that indicate a private (independent) school.
_PRIVATE_TYPE_GROUPS = frozenset({"Independent schools", "Independent special schools"})

# Establishment statuses to include -- we skip closed schools.
_OPEN_STATUSES = frozenset(
    {
        "Open",
        "Open, but proposed to close",
    }
)


# ---------------------------------------------------------------------------
# OSGB36  ->  WGS84  coordinate conversion
# ---------------------------------------------------------------------------
# GIAS provides Easting/Northing on the Ordnance Survey National Grid
# (OSGB36 / EPSG:27700).  We need WGS84 latitude and longitude.
#
# The conversion is a two-step process:
#   1. Reverse the Transverse Mercator projection to get lat/lon on the
#      Airy 1830 ellipsoid.
#   2. Apply a 7-parameter Helmert transformation to move from the Airy 1830
#      datum to WGS84.
#
# The maths below is the standard Ordnance Survey algorithm (see
# "A guide to coordinate systems in Great Britain", Ordnance Survey).
# ---------------------------------------------------------------------------


def _grid_to_osgb36_latlon(easting: float, northing: float) -> tuple[float, float]:
    """Convert National Grid Easting/Northing to lat/lon on the Airy 1830 ellipsoid."""
    # Airy 1830 ellipsoid parameters
    a = 6_377_563.396  # semi-major axis (m)
    b = 6_356_256.909  # semi-minor axis (m)

    # National Grid projection constants
    f0 = 0.9996012717  # scale factor on central meridian
    lat0 = math.radians(49.0)  # true origin latitude
    lon0 = math.radians(-2.0)  # true origin longitude
    n0 = -100_000.0  # northing of true origin
    e0 = 400_000.0  # easting of true origin

    e2 = 1.0 - (b * b) / (a * a)
    n = (a - b) / (a + b)
    n2 = n * n
    n3 = n2 * n

    lat = lat0
    m = 0.0

    # Iteratively solve for latitude
    while True:
        lat = lat + (northing - n0 - m) / (a * f0)

        ma = (1.0 + n + 1.25 * n2 + 1.25 * n3) * (lat - lat0)
        mb = (3.0 * n + 3.0 * n2 + 2.625 * n3) * math.sin(lat - lat0) * math.cos(lat + lat0)
        mc = (1.875 * n2 + 1.875 * n3) * math.sin(2.0 * (lat - lat0)) * math.cos(2.0 * (lat + lat0))
        md = (35.0 / 24.0) * n3 * math.sin(3.0 * (lat - lat0)) * math.cos(3.0 * (lat + lat0))
        m = b * f0 * (ma - mb + mc - md)

        if abs(northing - n0 - m) < 0.00001:
            break

    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    tan_lat = math.tan(lat)

    nu = a * f0 / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    rho = a * f0 * (1.0 - e2) / pow(1.0 - e2 * sin_lat * sin_lat, 1.5)
    eta2 = nu / rho - 1.0

    tan2 = tan_lat * tan_lat
    tan4 = tan2 * tan2
    tan6 = tan4 * tan2
    sec_lat = 1.0 / cos_lat

    vii = tan_lat / (2.0 * rho * nu)
    viii = tan_lat / (24.0 * rho * nu**3) * (5.0 + 3.0 * tan2 + eta2 - 9.0 * tan2 * eta2)
    ix = tan_lat / (720.0 * rho * nu**5) * (61.0 + 90.0 * tan2 + 45.0 * tan4)
    x = sec_lat / nu
    xi = sec_lat / (6.0 * nu**3) * (nu / rho + 2.0 * tan2)
    xii = sec_lat / (120.0 * nu**5) * (5.0 + 28.0 * tan2 + 24.0 * tan4)
    xiia = sec_lat / (5040.0 * nu**7) * (61.0 + 662.0 * tan2 + 1320.0 * tan4 + 720.0 * tan6)

    de = easting - e0
    de2 = de * de
    de3 = de2 * de
    de4 = de2 * de2
    de5 = de3 * de2
    de6 = de3 * de3
    de7 = de4 * de3

    result_lat = lat - vii * de2 + viii * de4 - ix * de6
    result_lon = lon0 + x * de - xi * de3 + xii * de5 - xiia * de7

    return math.degrees(result_lat), math.degrees(result_lon)


def _helmert_osgb36_to_wgs84(lat: float, lon: float) -> tuple[float, float]:
    """Apply a Helmert transformation from OSGB36 (Airy 1830) to WGS84."""
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)

    # Airy 1830 ellipsoid
    a1 = 6_377_563.396
    b1 = 6_356_256.909
    e2_1 = 1.0 - (b1 * b1) / (a1 * a1)

    sin_lat = math.sin(lat_r)
    cos_lat = math.cos(lat_r)
    sin_lon = math.sin(lon_r)
    cos_lon = math.cos(lon_r)

    nu = a1 / math.sqrt(1.0 - e2_1 * sin_lat * sin_lat)

    # Cartesian coordinates on Airy 1830
    x1 = nu * cos_lat * cos_lon
    y1 = nu * cos_lat * sin_lon
    z1 = (1.0 - e2_1) * nu * sin_lat

    # Helmert parameters (OSGB36 -> WGS84)
    tx = 446.448
    ty = -125.157
    tz = 542.060
    s = -20.4894e-6
    rx = math.radians(0.1502 / 3600.0)
    ry = math.radians(0.2470 / 3600.0)
    rz = math.radians(0.8421 / 3600.0)

    # Apply transformation
    x2 = tx + (1.0 + s) * x1 + (-rz) * y1 + ry * z1
    y2 = ty + rz * x1 + (1.0 + s) * y1 + (-rx) * z1
    z2 = tz + (-ry) * x1 + rx * y1 + (1.0 + s) * z1

    # WGS84 ellipsoid
    a2 = 6_378_137.0
    b2 = 6_356_752.3141
    e2_2 = 1.0 - (b2 * b2) / (a2 * a2)

    # Convert back to lat/lon (iterative)
    p = math.sqrt(x2 * x2 + y2 * y2)
    lat2 = math.atan2(z2, p * (1.0 - e2_2))

    for _ in range(10):
        nu2 = a2 / math.sqrt(1.0 - e2_2 * math.sin(lat2) * math.sin(lat2))
        lat2 = math.atan2(z2 + e2_2 * nu2 * math.sin(lat2), p)

    lon2 = math.atan2(y2, x2)

    return math.degrees(lat2), math.degrees(lon2)


def osgb36_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Convert OS National Grid Easting/Northing to WGS84 (lat, lon).

    Returns a ``(latitude, longitude)`` tuple in decimal degrees.
    """
    lat_osgb, lon_osgb = _grid_to_osgb36_latlon(easting, northing)
    return _helmert_osgb36_to_wgs84(lat_osgb, lon_osgb)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_address(row: dict[str, str]) -> str:
    """Join non-empty address component columns into a single comma-separated string."""
    parts = [
        row.get(COL_STREET, "").strip(),
        row.get(COL_LOCALITY, "").strip(),
        row.get(COL_ADDRESS3, "").strip(),
        row.get(COL_TOWN, "").strip(),
    ]
    return ", ".join(p for p in parts if p)


def _is_private(row: dict[str, str]) -> bool:
    """Return ``True`` when the establishment type group indicates an independent school."""
    return row.get(COL_TYPE_GROUP, "").strip() in _PRIVATE_TYPE_GROUPS


def _school_type(row: dict[str, str]) -> str:
    """Map GIAS establishment type to a simplified ``state`` or ``private`` label."""
    if _is_private(row):
        return "private"
    return "state"


def _default_catchment_km(phase: str) -> float:
    """Pick a sensible default catchment radius based on phase of education.

    GIAS does not include catchment radius data, so we use reasonable defaults.
    """
    phase_lower = phase.lower() if phase else ""
    if "secondary" in phase_lower or "16 plus" in phase_lower:
        return 3.0
    if "primary" in phase_lower or "nursery" in phase_lower:
        return 1.5
    # Middle, all-through, or unknown
    return 2.0


def _safe_int(value: str) -> int | None:
    """Parse a string to int, returning ``None`` on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_ofsted_date(value: str) -> date | None:
    """Parse a GIAS date string to a :class:`datetime.date`.

    GIAS uses ``DD-MM-YYYY`` or ``DD/MM/YYYY`` format.
    """
    value = value.strip()
    if not value:
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _normalise_gender(raw: str) -> str:
    """Normalise the GIAS gender field to ``Mixed``, ``Boys``, or ``Girls``."""
    raw = raw.strip()
    if raw in {"Boys", "Girls", "Mixed"}:
        return raw
    if "boy" in raw.lower():
        return "Boys"
    if "girl" in raw.lower():
        return "Girls"
    return "Mixed"


def _normalise_faith(raw: str) -> str | None:
    """Normalise the GIAS religious character field.

    Returns ``None`` for ``"None"`` / ``"Does not apply"`` / empty strings.
    """
    raw = raw.strip()
    if not raw or raw.lower() in {"none", "does not apply"}:
        return None
    return raw


# ---------------------------------------------------------------------------
# CSV download / cache
# ---------------------------------------------------------------------------


def _csv_cache_path() -> Path:
    """Return the path where today's GIAS CSV should be cached."""
    today = date.today().strftime("%Y%m%d")
    return SEEDS_DIR / f"edubasealldata{today}.csv"


def _find_cached_csv() -> Path | None:
    """Return the most recently cached GIAS CSV file, if any exists."""
    candidates = sorted(SEEDS_DIR.glob("edubasealldata*.csv"), reverse=True)
    return candidates[0] if candidates else None


def _download_gias_csv(force: bool = False) -> Path:
    """Download the GIAS establishment CSV and cache it locally.

    If a cached file already exists for today (and *force* is ``False``), the
    download is skipped and the cached path is returned.
    """
    cache_path = _csv_cache_path()

    if cache_path.exists() and not force:
        print(f"  Using cached CSV: {cache_path}")
        return cache_path

    today_str = date.today().strftime("%Y%m%d")
    url = GIAS_CSV_URL_TEMPLATE.format(date=today_str)

    print(f"  Downloading GIAS CSV from {url} ...")
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except httpx.HTTPStatusError:
        # The daily file might not be published yet.  Try yesterday.
        yesterday_str = (date.today().replace(day=date.today().day - 1)).strftime("%Y%m%d")
        fallback_url = GIAS_CSV_URL_TEMPLATE.format(date=yesterday_str)
        print(f"  Today's file not available; trying {fallback_url} ...")
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            resp = client.get(fallback_url)
            resp.raise_for_status()

    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(resp.content)
    print(f"  Saved to {cache_path} ({len(resp.content) / 1_048_576:.1f} MB)")
    return cache_path


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Read a GIAS CSV file into a list of row dicts.

    GIAS CSVs are encoded as Windows-1252 (cp1252).  We try that first and
    fall back to UTF-8 with BOM.
    """
    for encoding in ("cp1252", "utf-8-sig", "utf-8", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            reader = csv.DictReader(io.StringIO(text))
            return list(reader)
        except (UnicodeDecodeError, UnicodeError):
            continue
    print(f"  ERROR: Could not decode {path} with any known encoding.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Row -> School mapping
# ---------------------------------------------------------------------------


def _row_to_school(row: dict[str, str]) -> School | None:
    """Convert a single GIAS CSV row to a :class:`School` instance.

    Returns ``None`` if the row should be skipped (e.g. closed school, missing
    essential data).
    """
    status = row.get(COL_STATUS, "").strip()
    if status not in _OPEN_STATUSES:
        return None

    urn = row.get(COL_URN, "").strip()
    name = row.get(COL_NAME, "").strip()
    if not urn or not name:
        return None

    # Coordinates
    lat: float | None = None
    lng: float | None = None
    easting_str = row.get(COL_EASTING, "").strip()
    northing_str = row.get(COL_NORTHING, "").strip()
    if easting_str and northing_str:
        try:
            easting = float(easting_str)
            northing = float(northing_str)
            if easting > 0 and northing > 0:
                lat, lng = osgb36_to_wgs84(easting, northing)
        except (ValueError, ZeroDivisionError):
            pass

    phase = row.get(COL_PHASE, "").strip()

    # Ofsted fields may be absent (removed from GIAS in Sept 2024).
    ofsted_rating_raw = row.get(COL_OFSTED_RATING, "").strip()
    ofsted_rating = ofsted_rating_raw if ofsted_rating_raw else None
    ofsted_date = _parse_ofsted_date(row.get(COL_OFSTED_DATE, ""))

    return School(
        urn=urn,
        name=name,
        type=_school_type(row),
        council=row.get(COL_LA, "").strip(),
        address=_build_address(row),
        postcode=row.get(COL_POSTCODE, "").strip(),
        lat=lat,
        lng=lng,
        catchment_radius_km=_default_catchment_km(phase),
        gender_policy=_normalise_gender(row.get(COL_GENDER, "")),
        faith=_normalise_faith(row.get(COL_RELIGION, "")),
        age_range_from=_safe_int(row.get(COL_LOW_AGE, "")),
        age_range_to=_safe_int(row.get(COL_HIGH_AGE, "")),
        ofsted_rating=ofsted_rating,
        ofsted_date=ofsted_date,
        is_private=_is_private(row),
    )


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


def _ensure_database(db_path: Path) -> Session:
    """Create the SQLite database and tables, then return a Session."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return Session(engine)


def _upsert_schools(session: Session, schools: list[School]) -> tuple[int, int]:
    """Insert new schools and update existing ones (matched by URN).

    Returns ``(inserted, updated)`` counts.
    """
    inserted = 0
    updated = 0

    for school in schools:
        existing = session.query(School).filter_by(urn=school.urn).first()
        if existing is None:
            session.add(school)
            inserted += 1
        else:
            # Update mutable fields on the existing record.
            existing.name = school.name
            existing.type = school.type
            existing.council = school.council
            existing.address = school.address
            existing.postcode = school.postcode
            existing.lat = school.lat
            existing.lng = school.lng
            existing.catchment_radius_km = school.catchment_radius_km
            existing.gender_policy = school.gender_policy
            existing.faith = school.faith
            existing.age_range_from = school.age_range_from
            existing.age_range_to = school.age_range_to
            existing.ofsted_rating = school.ofsted_rating
            existing.ofsted_date = school.ofsted_date
            existing.is_private = school.is_private
            updated += 1

    session.commit()
    return inserted, updated


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="python -m src.db.seed",
        description="Seed the school-finder database from GIAS establishment data.",
    )
    parser.add_argument(
        "--council",
        required=True,
        help='Local authority name to filter by (e.g. "Milton Keynes").',
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to the SQLite database file (default: {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        default=False,
        help="Force re-download of the GIAS CSV even if a cached copy exists.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the seed script."""
    args = parse_args(argv)
    council: str = args.council
    db_path: Path = args.db
    force_download: bool = args.force_download

    print("School Finder - GIAS Seed")
    print(f"  Council filter : {council}")
    print(f"  Database       : {db_path}")
    print()

    # ------------------------------------------------------------------
    # 1. Obtain the GIAS CSV (download or use cache)
    # ------------------------------------------------------------------
    print("[1/4] Obtaining GIAS CSV ...")

    cached = _find_cached_csv()
    if cached and not force_download:
        print(f"  Found cached file: {cached}")
        csv_path = cached
    else:
        csv_path = _download_gias_csv(force=force_download)

    # ------------------------------------------------------------------
    # 2. Read and filter CSV rows
    # ------------------------------------------------------------------
    print("[2/4] Reading CSV ...")
    rows = _read_csv(csv_path)
    print(f"  Total rows in CSV: {len(rows)}")

    council_lower = council.lower()
    council_rows = [r for r in rows if r.get(COL_LA, "").strip().lower() == council_lower]
    print(f"  Rows matching council '{council}': {len(council_rows)}")

    if not council_rows:
        # Show available councils to help the user
        all_councils = sorted({r.get(COL_LA, "").strip() for r in rows if r.get(COL_LA, "").strip()})
        close_matches = [c for c in all_councils if council_lower in c.lower()]
        print(f"\n  No schools found for council '{council}'.", file=sys.stderr)
        if close_matches:
            print(f"  Did you mean one of: {', '.join(close_matches)}?", file=sys.stderr)
        else:
            print(f"  Available councils ({len(all_councils)} total):", file=sys.stderr)
            for c in all_councils[:20]:
                print(f"    - {c}", file=sys.stderr)
            if len(all_councils) > 20:
                print(f"    ... and {len(all_councils) - 20} more", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 3. Map rows to School objects
    # ------------------------------------------------------------------
    print("[3/4] Mapping to School records ...")
    schools: list[School] = []
    skipped = 0
    for row in council_rows:
        school = _row_to_school(row)
        if school is not None:
            schools.append(school)
        else:
            skipped += 1

    print(f"  Schools to seed: {len(schools)}  (skipped {skipped} closed/invalid)")

    geo_count = sum(1 for s in schools if s.lat is not None)
    print(f"  With coordinates: {geo_count}/{len(schools)}")

    # ------------------------------------------------------------------
    # 4. Write to database
    # ------------------------------------------------------------------
    print("[4/4] Writing to database ...")
    session = _ensure_database(db_path)
    try:
        inserted, updated = _upsert_schools(session, schools)
        total_in_db = session.query(School).filter_by(council=council).count()
        print(f"  Inserted: {inserted}")
        print(f"  Updated : {updated}")
        print(f"  Total schools for '{council}' in DB: {total_in_db}")
    finally:
        session.close()

    print()
    print("Done.")


if __name__ == "__main__":
    main()
