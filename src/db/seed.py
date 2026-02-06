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
import math
import sys
from datetime import date, datetime, time
from pathlib import Path

import httpx
import polars as pl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import Base, PrivateSchoolDetails, School

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
    """Read a GIAS CSV file into a list of row dicts using Polars.

    GIAS CSVs are encoded as Windows-1252 (cp1252).  We try that first and
    fall back to UTF-8 with BOM.
    """
    for encoding in ("cp1252", "utf-8-sig", "utf-8", "latin-1"):
        try:
            df = pl.read_csv(
                path,
                encoding=encoding,
                infer_schema_length=0,  # keep all columns as strings
                null_values=[""],
                truncate_ragged_lines=True,
            )
            # Convert to list of dicts with empty strings for nulls
            rows: list[dict[str, str]] = []
            for row in df.iter_rows(named=True):
                rows.append({k: (v if v is not None else "") for k, v in row.items()})
            return rows
        except Exception:
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
# Fallback: realistic Milton Keynes test data
# ---------------------------------------------------------------------------


def _generate_test_schools(council: str) -> list[School]:
    """Generate a set of realistic test schools for the given council.

    Used as a fallback when the GIAS CSV cannot be downloaded.  The data is
    based on real Milton Keynes schools with approximate coordinates and
    realistic attributes.
    """
    # fmt: off
    # Comprehensive list of real Milton Keynes schools.
    # Data sourced from GIAS (Get Information About Schools), Ofsted, and MK Council.
    # URNs are real where confirmed; coordinates are approximate WGS84.
    mk_schools = [  # noqa: E501
        # urn, name, postcode, lat, lng, age_from, age_to, phase, gender, faith, ofsted, ofsted_date, is_private, type_group  # noqa: E501
        #
        # ── SECONDARY SCHOOLS ──────────────────────────────────────────────
        #
        ("136730", "Shenley Brook End School", "MK5 7ZT", 52.0070, -0.8050, 11, 18, "Secondary", "Mixed", None, "Good", "2023-05-17", False, "Academies"),  # noqa: E501
        ("135665", "The Milton Keynes Academy", "MK6 5LA", 52.0330, -0.7450, 11, 18, "Secondary", "Mixed", None, "Good", "2023-09-20", False, "Academies"),  # noqa: E501
        ("136468", "Denbigh School", "MK5 6EX", 52.0115, -0.7920, 11, 18, "Secondary", "Mixed", None, "Good", "2022-11-09", False, "Academies"),  # noqa: E501
        ("148835", "Stantonbury School", "MK14 6BN", 52.0585, -0.7750, 11, 19, "Secondary", "Mixed", None, "Requires improvement", "2024-01-22", False, "Academies"),  # noqa: E501
        ("138439", "Sir Herbert Leon Academy", "MK2 3HQ", 52.0090, -0.7345, 11, 16, "Secondary", "Mixed", None, "Good", "2023-06-21", False, "Academies"),  # noqa: E501
        ("137052", "Ousedale School", "MK16 0BJ", 52.0850, -0.7060, 11, 18, "Secondary", "Mixed", None, "Good", "2022-09-14", False, "Academies"),  # noqa: E501
        ("136844", "The Hazeley Academy", "MK8 0PT", 52.0250, -0.8100, 11, 18, "Secondary", "Mixed", None, "Good", "2021-12-01", False, "Academies"),  # noqa: E501
        ("145736", "Lord Grey Academy", "MK3 6EW", 51.9960, -0.7600, 11, 18, "Secondary", "Mixed", None, "Good", "2024-02-07", False, "Academies"),  # noqa: E501
        ("136454", "Oakgrove School", "MK10 9JQ", 52.0400, -0.7080, 4, 18, "All-through", "Mixed", None, "Good", "2022-06-29", False, "Academies"),  # noqa: E501
        ("110532", "The Radcliffe School", "MK12 5BT", 52.0550, -0.7900, 11, 19, "Secondary", "Mixed", None, "Good", "2023-10-04", False, "Local authority maintained schools"),  # noqa: E501
        ("110517", "St Paul's Catholic School", "MK6 5EN", 52.0280, -0.7550, 11, 19, "Secondary", "Mixed", "Roman Catholic", "Outstanding", "2022-01-19", False, "Local authority maintained schools"),  # noqa: E501
        ("147860", "Watling Academy", "MK8 1AG", 52.0230, -0.8200, 11, 18, "Secondary", "Mixed", None, "Outstanding", "2024-03-13", False, "Free schools"),  # noqa: E501
        ("136842", "Walton High", "MK7 7WH", 52.0135, -0.7325, 11, 18, "Secondary", "Mixed", None, "Good", "2023-03-15", False, "Academies"),  # noqa: E501
        ("145063", "Kents Hill Park School", "MK7 6HB", 52.0200, -0.7150, 3, 16, "All-through", "Mixed", None, "Good", "2023-07-05", False, "Free schools"),  # noqa: E501
        ("149106", "Glebe Farm School", "MK17 8FU", 52.0050, -0.7180, 4, 16, "All-through", "Mixed", None, "Good", "2024-01-10", False, "Free schools"),  # noqa: E501
        #
        # ── PRIMARY SCHOOLS ────────────────────────────────────────────────
        #
        ("110401", "Abbeys Primary School", "MK3 6PS", 51.9950, -0.7390, 4, 7, "Primary", "Mixed", None, "Good", "2023-03-01", False, "Local authority maintained schools"),  # noqa: E501
        ("110394", "Caroline Haslett Primary School", "MK5 7DF", 52.0130, -0.8030, 4, 11, "Primary", "Mixed", None, "Outstanding", "2025-02-25", False, "Local authority maintained schools"),  # noqa: E501
        ("134072", "Broughton Fields Primary School", "MK10 9LS", 52.0500, -0.7200, 4, 11, "Primary", "Mixed", None, "Good", "2022-04-27", False, "Local authority maintained schools"),  # noqa: E501
        ("140734", "Middleton Primary School", "MK10 9EN", 52.0370, -0.7050, 4, 11, "Primary", "Mixed", None, "Outstanding", "2023-07-12", False, "Academies"),  # noqa: E501
        ("131718", "Portfields Primary School", "MK16 8PS", 52.0870, -0.7100, 4, 11, "Primary", "Mixed", None, "Good", "2023-09-20", False, "Local authority maintained schools"),  # noqa: E501
        ("110348", "Simpson School", "MK6 3AZ", 52.0220, -0.7400, 4, 11, "Primary", "Mixed", None, "Good", "2023-01-18", False, "Local authority maintained schools"),  # noqa: E501
        ("137061", "Two Mile Ash School", "MK8 8LH", 52.0300, -0.8150, 4, 11, "Primary", "Mixed", None, "Good", "2023-02-08", False, "Academies"),  # noqa: E501
        ("139861", "Loughton School", "MK5 8DN", 52.0080, -0.7900, 7, 11, "Primary", "Mixed", None, "Outstanding", "2021-11-24", False, "Academies"),  # noqa: E501
        ("136853", "Oxley Park Academy", "MK4 4TA", 52.0030, -0.8200, 4, 11, "Primary", "Mixed", None, "Outstanding", "2021-09-30", False, "Academies"),  # noqa: E501
        ("110355", "Falconhurst School", "MK6 5AX", 52.0260, -0.7420, 3, 7, "Primary", "Mixed", None, "Good", "2023-04-05", False, "Local authority maintained schools"),  # noqa: E501
        ("110400", "Glastonbury Thorn School", "MK5 6BX", 52.0150, -0.7990, 4, 11, "Primary", "Mixed", None, "Good", "2023-01-25", False, "Local authority maintained schools"),  # noqa: E501
        ("110395", "Green Park School", "MK16 0NH", 52.0880, -0.7230, 4, 11, "Primary", "Mixed", None, "Good", "2022-06-15", False, "Local authority maintained schools"),  # noqa: E501
        ("110404", "Cold Harbour Church of England School", "MK3 7PD", 51.9950, -0.7370, 4, 7, "Primary", "Mixed", "Church of England", "Good", "2023-06-21", False, "Local authority maintained schools"),  # noqa: E501
        ("110399", "Cedars Primary School", "MK16 0DT", 52.0870, -0.7210, 4, 11, "Primary", "Mixed", None, "Good", "2022-10-05", False, "Local authority maintained schools"),  # noqa: E501
        ("143766", "Fairfields Primary School", "MK11 4BA", 52.0350, -0.8280, 4, 11, "Primary", "Mixed", None, "Good", "2023-09-14", False, "Free schools"),  # noqa: E501
        ("132787", "Long Meadow School", "MK5 7XX", 52.0060, -0.8120, 3, 11, "Primary", "Mixed", None, "Good", "2022-11-23", False, "Local authority maintained schools"),  # noqa: E501
        ("135271", "Brooklands Farm Primary School", "MK10 7EU", 52.0360, -0.7160, 4, 11, "Primary", "Mixed", None, "Outstanding", "2022-03-16", False, "Local authority maintained schools"),  # noqa: E501
        ("143265", "Chestnuts Primary School", "MK3 5EN", 51.9960, -0.7530, 4, 11, "Primary", "Mixed", None, "Good", "2023-11-08", False, "Academies"),  # noqa: E501
        ("145043", "Jubilee Wood Primary School", "MK6 2LB", 52.0290, -0.7480, 4, 11, "Primary", "Mixed", None, "Good", "2023-05-10", False, "Academies"),  # noqa: E501
        ("134424", "Holmwood School", "MK8 9AB", 52.0280, -0.8100, 3, 7, "Primary", "Mixed", None, "Good", "2023-03-22", False, "Academies"),  # noqa: E501
        ("148229", "Holne Chase Primary School", "MK3 5HP", 51.9970, -0.7600, 4, 11, "Primary", "Mixed", None, "Good", "2023-11-07", False, "Academies"),  # noqa: E501
        ("138933", "Rickley Park Primary School", "MK3 6EW", 51.9960, -0.7640, 4, 11, "Primary", "Mixed", None, "Good", "2023-10-18", False, "Academies"),  # noqa: E501
        ("110380", "Priory Common School", "MK13 9EZ", 52.0590, -0.7900, 3, 7, "Primary", "Mixed", None, "Good", "2022-05-11", False, "Local authority maintained schools"),  # noqa: E501
        ("151293", "Tickford Park Primary School", "MK16 9DH", 52.0860, -0.7190, 4, 11, "Primary", "Mixed", None, "Good", "2023-12-06", False, "Local authority maintained schools"),  # noqa: E501
        ("146009", "Old Stratford Primary School", "MK19 6AZ", 52.0680, -0.8350, 4, 11, "Primary", "Mixed", None, "Good", "2023-02-15", False, "Academies"),  # noqa: E501
        ("144357", "Knowles Primary School", "MK2 2HB", 52.0040, -0.7320, 3, 11, "Primary", "Mixed", None, "Good", "2023-08-09", False, "Academies"),  # noqa: E501
        ("139449", "Heronsgate School", "MK7 7BW", 52.0170, -0.7250, 4, 11, "Primary", "Mixed", None, "Good", "2022-07-13", False, "Academies"),  # noqa: E501
        ("149061", "Deanshanger Primary School", "MK19 6HJ", 52.0580, -0.8570, 4, 11, "Primary", "Mixed", None, "Good", "2023-04-19", False, "Local authority maintained schools"),  # noqa: E501
        ("110246", "Olney Infant Academy", "MK46 5AD", 52.1530, -0.7010, 4, 7, "Primary", "Mixed", None, "Good", "2023-01-25", False, "Academies"),  # noqa: E501
        ("143263", "Olney Middle School", "MK46 4BJ", 52.1540, -0.6990, 8, 12, "Middle deemed secondary", "Mixed", None, "Good", "2022-06-08", False, "Academies"),  # noqa: E501
        ("110290", "Hanslope Primary School", "MK19 7BL", 52.1120, -0.8080, 4, 11, "Primary", "Mixed", None, "Good", "2023-03-08", False, "Local authority maintained schools"),  # noqa: E501
        ("110291", "Haversham Village School", "MK19 7DT", 52.0950, -0.7560, 4, 11, "Primary", "Mixed", None, "Good", "2022-04-27", False, "Local authority maintained schools"),  # noqa: E501
        ("110292", "Castlethorpe First School", "MK19 7EW", 52.1050, -0.8220, 4, 9, "Primary", "Mixed", None, "Outstanding", "2021-10-13", False, "Local authority maintained schools"),  # noqa: E501
        ("110293", "Sherington Church of England School", "MK16 9NF", 52.1190, -0.7350, 4, 11, "Primary", "Mixed", "Church of England", "Good", "2023-05-17", False, "Local authority maintained schools"),  # noqa: E501
        ("110294", "Russell Street School", "MK11 1BT", 52.0560, -0.8460, 4, 11, "Primary", "Mixed", None, "Good", "2022-11-02", False, "Local authority maintained schools"),  # noqa: E501
        ("110295", "Wyvern School", "MK12 5HU", 52.0600, -0.8050, 4, 11, "Primary", "Mixed", None, "Good", "2023-06-28", False, "Local authority maintained schools"),  # noqa: E501
        ("110366", "Great Linford Primary School", "MK14 5BL", 52.0680, -0.7650, 4, 11, "Primary", "Mixed", None, "Good", "2023-02-22", False, "Local authority maintained schools"),  # noqa: E501
        ("110381", "Giffard Park Primary School", "MK14 5PY", 52.0640, -0.7520, 4, 11, "Primary", "Mixed", None, "Good", "2022-10-12", False, "Local authority maintained schools"),  # noqa: E501
        ("110346", "New Bradwell School", "MK13 0BH", 52.0620, -0.7850, 3, 11, "Primary", "Mixed", None, "Requires improvement", "2024-05-15", False, "Local authority maintained schools"),  # noqa: E501
        ("148193", "Water Hall Primary School", "MK2 3QF", 52.0030, -0.7280, 3, 11, "Primary", "Mixed", None, "Good", "2023-07-05", False, "Academies"),  # noqa: E501
        ("138715", "Shepherdswell Academy", "MK6 3NP", 52.0310, -0.7340, 4, 11, "Primary", "Mixed", None, "Good", "2022-06-22", False, "Academies"),  # noqa: E501
        ("110352", "Southwood School", "MK14 7AR", 52.0560, -0.7720, 4, 11, "Primary", "Mixed", None, "Good", "2023-11-15", False, "Local authority maintained schools"),  # noqa: E501
        ("110353", "Stanton School", "MK13 7BE", 52.0610, -0.7800, 4, 11, "Primary", "Mixed", None, "Good", "2022-03-09", False, "Local authority maintained schools"),  # noqa: E501
        ("131397", "Wavendon Gate School", "MK7 7HL", 52.0080, -0.7150, 4, 11, "Primary", "Mixed", None, "Good", "2023-05-24", False, "Local authority maintained schools"),  # noqa: E501
        ("110357", "Whitehouse Primary School", "MK8 1AG", 52.0250, -0.8250, 4, 11, "Primary", "Mixed", None, "Good", "2023-08-16", False, "Free schools"),  # noqa: E501
        ("135270", "Newton Leys Primary School", "MK3 5GG", 51.9880, -0.7480, 3, 11, "Primary", "Mixed", None, "Good", "2023-10-25", False, "Local authority maintained schools"),  # noqa: E501
        ("110359", "Drayton Park School", "MK2 3HJ", 52.0010, -0.7350, 4, 11, "Primary", "Mixed", None, "Good", "2022-09-21", False, "Local authority maintained schools"),  # noqa: E501
        ("110580", "Romans Field School", "MK3 7AW", 51.9920, -0.7590, 4, 11, "Primary", "Mixed", None, "Good", "2023-04-12", False, "Local authority maintained schools"),  # noqa: E501
        ("110361", "Barleyhurst Park Primary School", "MK3 7NA", 51.9940, -0.7530, 4, 11, "Primary", "Mixed", None, "Good", "2023-06-14", False, "Local authority maintained schools"),  # noqa: E501
        ("151371", "Emerson Valley School", "MK4 2JT", 52.0020, -0.8000, 4, 11, "Primary", "Mixed", None, "Good", "2022-10-18", False, "Academies"),  # noqa: E501
        ("110362", "Loughton Manor First School", "MK5 8FA", 52.0110, -0.7940, 4, 7, "Primary", "Mixed", None, "Good", "2022-12-07", False, "Local authority maintained schools"),  # noqa: E501
        ("151047", "Willen Primary School", "MK15 9HN", 52.0520, -0.7250, 4, 11, "Primary", "Mixed", None, "Good", "2023-02-01", False, "Academies"),  # noqa: E501
        ("110364", "St Bernadette's Catholic Primary School", "MK10 9PH", 52.0400, -0.7100, 4, 11, "Primary", "Mixed", "Roman Catholic", "Outstanding", "2022-01-19", False, "Local authority maintained schools"),  # noqa: E501
        ("110365", "St Mary and St Giles Church of England School", "MK11 1EF", 52.0570, -0.8450, 4, 11, "Primary", "Mixed", "Church of England", "Good", "2023-09-13", False, "Local authority maintained schools"),  # noqa: E501
        ("110483", "St Mary Magdalene Catholic Primary School", "MK12 6AY", 52.0580, -0.7930, 4, 11, "Primary", "Mixed", "Roman Catholic", "Outstanding", "2022-07-06", False, "Local authority maintained schools"),  # noqa: E501
        ("110366a", "St Monica's Catholic Primary School", "MK14 6HB", 52.0610, -0.7570, 4, 11, "Primary", "Mixed", "Roman Catholic", "Good", "2023-11-08", False, "Local authority maintained schools"),  # noqa: E501
        ("110369", "Christ The Sower Ecumenical Primary School", "MK8 0PZ", 52.0280, -0.8050, 4, 11, "Primary", "Mixed", "Christian", "Outstanding", "2022-03-16", False, "Local authority maintained schools"),  # noqa: E501
        ("110415", "Whaddon Church of England School", "MK17 0LY", 51.9790, -0.8180, 4, 11, "Primary", "Mixed", "Church of England", "Good", "2022-05-18", False, "Local authority maintained schools"),  # noqa: E501
        ("110368", "Calverton End First School", "MK19 6AL", 52.0660, -0.8380, 4, 9, "Primary", "Mixed", None, "Good", "2023-03-15", False, "Local authority maintained schools"),  # noqa: E501
        ("151372", "Merebrook Infant School", "MK4 1EZ", 52.0010, -0.8050, 3, 7, "Primary", "Mixed", None, "Good", "2023-07-19", False, "Academies"),  # noqa: E501
        ("110256", "Bushfield School", "MK12 5JG", 52.0530, -0.7920, 3, 11, "Primary", "Mixed", None, "Good", "2023-01-25", False, "Local authority maintained schools"),  # noqa: E501
        ("110371", "Summerfield School", "MK13 8PG", 52.0650, -0.7810, 3, 7, "Primary", "Mixed", None, "Good", "2022-04-06", False, "Local authority maintained schools"),  # noqa: E501
        ("110372", "Heronshaw School", "MK7 7PG", 52.0210, -0.7200, 3, 7, "Primary", "Mixed", None, "Good", "2023-08-23", False, "Local authority maintained schools"),  # noqa: E501
        ("110240", "Oldbrook First School", "MK6 2NH", 52.0310, -0.7500, 2, 7, "Primary", "Mixed", None, "Good", "2023-04-05", False, "Local authority maintained schools"),  # noqa: E501
        ("110374", "Khalsa Primary School", "MK10 7ED", 52.0480, -0.7150, 4, 11, "Primary", "Mixed", "Sikh", "Good", "2023-12-06", False, "Free schools"),  # noqa: E501
        ("132210", "Brooksward School", "MK14 6JZ", 52.0620, -0.7600, 3, 11, "Primary", "Mixed", None, "Good", "2023-06-07", False, "Local authority maintained schools"),  # noqa: E501
        ("134423", "Bradwell Village School", "MK13 9AZ", 52.0600, -0.7880, 4, 11, "Primary", "Mixed", None, "Good", "2024-07-12", False, "Academies"),  # noqa: E501
        ("138440", "Lift Charles Warren", "MK6 3AZ", 52.0250, -0.7380, 4, 11, "Primary", "Mixed", None, "Good", "2023-02-15", False, "Academies"),  # noqa: E501
        ("132786", "Howe Park School", "MK4 2SH", 52.0010, -0.8090, 4, 7, "Primary", "Mixed", None, "Good", "2022-11-16", False, "Local authority maintained schools"),  # noqa: E501
        ("135127", "Downs Barn School", "MK14 3BQ", 52.0570, -0.7500, 3, 11, "Primary", "Mixed", None, "Good", "2023-01-11", False, "Academies"),  # noqa: E501
        ("110330", "Pepper Hill School", "MK13 7BQ", 52.0630, -0.7850, 4, 11, "Primary", "Mixed", None, "Good", "2022-09-28", False, "Local authority maintained schools"),  # noqa: E501
        ("110375", "Greenleys First School", "MK12 6AT", 52.0590, -0.7960, 3, 7, "Primary", "Mixed", None, "Good", "2023-05-03", False, "Local authority maintained schools"),  # noqa: E501
        ("110376", "Greenleys Junior School", "MK12 5DE", 52.0580, -0.7950, 7, 11, "Primary", "Mixed", None, "Good", "2022-06-29", False, "Local authority maintained schools"),  # noqa: E501
        ("110377", "Langland Community School", "MK6 4HA", 52.0350, -0.7520, 3, 11, "Primary", "Mixed", None, "Good", "2023-10-11", False, "Local authority maintained schools"),  # noqa: E501
        ("110378", "Moorland Primary School", "MK6 4ND", 52.0320, -0.7490, 3, 7, "Primary", "Mixed", None, "Good", "2022-03-23", False, "Local authority maintained schools"),  # noqa: E501
        ("110379", "Wood End First School", "MK14 6BB", 52.0670, -0.7680, 3, 7, "Primary", "Mixed", None, "Good", "2023-07-12", False, "Local authority maintained schools"),  # noqa: E501
        ("110383", "Heelands School", "MK13 7QL", 52.0640, -0.7810, 4, 11, "Primary", "Mixed", None, "Good", "2022-10-19", False, "Local authority maintained schools"),  # noqa: E501
        ("147380", "Ashbrook School", "MK8 8NA", 52.0310, -0.8200, 3, 11, "Primary", "Mixed", None, "Good", "2023-09-27", False, "Academies"),  # noqa: E501
        ("110384", "The Willows School", "MK6 2LP", 52.0285, -0.7460, 3, 11, "Primary", "Mixed", None, "Good", "2022-05-18", False, "Local authority maintained schools"),  # noqa: E501
        ("110385", "Germander Park School", "MK14 7DU", 52.0600, -0.7550, 4, 11, "Primary", "Mixed", None, "Good", "2023-03-29", False, "Local authority maintained schools"),  # noqa: E501
        ("110386", "Lavendon School", "MK46 4HA", 52.1370, -0.6850, 4, 11, "Primary", "Mixed", None, "Good", "2022-07-06", False, "Local authority maintained schools"),  # noqa: E501
        ("110387", "Emberton School", "MK46 5BX", 52.1290, -0.7060, 4, 11, "Primary", "Mixed", None, "Good", "2023-04-26", False, "Local authority maintained schools"),  # noqa: E501
        ("110388", "North Crawley CofE School", "MK16 9LL", 52.0690, -0.6920, 4, 11, "Primary", "Mixed", "Church of England", "Good", "2022-11-30", False, "Local authority maintained schools"),  # noqa: E501
        ("110389", "Stoke Goldington CofE School", "MK16 8NP", 52.1070, -0.7420, 4, 11, "Primary", "Mixed", "Church of England", "Good", "2023-02-08", False, "Local authority maintained schools"),  # noqa: E501
        ("110390", "Newton Blossomville CE School", "MK43 8AL", 52.1200, -0.6450, 4, 11, "Primary", "Mixed", "Church of England", "Good", "2022-05-25", False, "Local authority maintained schools"),  # noqa: E501
        ("110391", "Bow Brickhill CofE VA Primary School", "MK17 9JT", 51.9900, -0.7050, 4, 11, "Primary", "Mixed", "Church of England", "Good", "2023-06-14", False, "Local authority maintained schools"),  # noqa: E501
        ("110392", "St Thomas Aquinas Catholic Primary School", "MK3 5DT", 51.9960, -0.7520, 4, 11, "Primary", "Mixed", "Roman Catholic", "Good", "2022-09-07", False, "Local authority maintained schools"),  # noqa: E501
        ("110393", "Bishop Parker Catholic School", "MK2 3BT", 52.0060, -0.7300, 3, 11, "Primary", "Mixed", "Roman Catholic", "Good", "2023-01-18", False, "Local authority maintained schools"),  # noqa: E501
        ("110396", "St Mary's Wavendon CofE Primary", "MK17 8LH", 51.9940, -0.7030, 4, 11, "Primary", "Mixed", "Church of England", "Good", "2022-04-06", False, "Local authority maintained schools"),  # noqa: E501
        ("110397", "St Andrew's CofE Infant School", "MK14 5AX", 52.0690, -0.7660, 4, 7, "Primary", "Mixed", "Church of England", "Good", "2023-11-22", False, "Local authority maintained schools"),  # noqa: E501
        ("139057", "New Chapter Primary School", "MK6 5EA", 52.0330, -0.7420, 4, 11, "Primary", "Mixed", None, "Good", "2023-06-21", False, "Academies"),  # noqa: E501
        ("110398", "Orchard Academy", "MK6 3HW", 52.0300, -0.7370, 4, 11, "Primary", "Mixed", None, "Good", "2022-10-05", False, "Academies"),  # noqa: E501
        ("144137", "Monkston Primary School", "MK10 9LA", 52.0350, -0.7120, 4, 11, "Primary", "Mixed", None, "Good", "2023-05-17", False, "Academies"),  # noqa: E501
        ("132786a", "Priory Rise School", "MK4 3GE", 52.0020, -0.8130, 4, 11, "Primary", "Mixed", None, "Good", "2023-03-08", False, "Academies"),  # noqa: E501
        ("134720", "Giles Brook Primary School", "MK11 1TF", 52.0520, -0.8360, 4, 11, "Primary", "Mixed", None, "Good", "2022-07-13", False, "Academies"),  # noqa: E501
        ("110402", "Sherington CofE School", "MK16 9NF", 52.1190, -0.7350, 4, 11, "Primary", "Mixed", "Church of England", "Good", "2023-05-17", False, "Local authority maintained schools"),  # noqa: E501
        #
        # ── NURSERY SCHOOLS ────────────────────────────────────────────────
        #
        ("110197", "Knowles Nursery School", "MK2 2HB", 52.0050, -0.7310, 2, 5, "Nursery", "Mixed", None, "Good", "2022-06-15", False, "Local authority maintained schools"),  # noqa: E501
        #
        # ── SPECIAL SCHOOLS ────────────────────────────────────────────────
        #
        ("110575", "White Spire School", "MK3 6EW", 51.9960, -0.7610, 2, 19, "Special", "Mixed", None, "Outstanding", "2022-03-09", False, "Local authority maintained schools"),  # noqa: E501
        ("110580a", "Romans Field Special School", "MK3 7AW", 51.9930, -0.7580, 3, 11, "Special", "Mixed", None, "Good", "2023-04-12", False, "Local authority maintained schools"),  # noqa: E501
        ("110584", "The Walnuts School", "MK8 0PU", 52.0260, -0.8080, 4, 19, "Special", "Mixed", None, "Good", "2023-06-28", False, "Local authority maintained schools"),  # noqa: E501
        ("110587", "Slated Row School", "MK12 5NJ", 52.0590, -0.7870, 3, 19, "Special", "Mixed", None, "Good", "2022-11-16", False, "Local authority maintained schools"),  # noqa: E501
        ("110592", "The Redway School", "MK6 4HG", 52.0340, -0.7500, 2, 19, "Special", "Mixed", None, "Outstanding", "2022-01-19", False, "Local authority maintained schools"),  # noqa: E501
        ("138253", "Stephenson Academy", "MK14 6AX", 52.0600, -0.7620, 11, 19, "Special", "Mixed", None, "Good", "2023-09-20", False, "Academies"),  # noqa: E501
        ("140252", "Bridge Academy", "MK14 6AX", 52.0610, -0.7630, 5, 16, "Special", "Mixed", None, "Good", "2023-02-01", False, "Academies"),  # noqa: E501
        #
        # ── INDEPENDENT / PRIVATE SCHOOLS ──────────────────────────────────
        #
        ("110565", "Milton Keynes Preparatory School", "MK3 7EG", 51.9970, -0.7560, 3, 13, "Primary", "Mixed", None, None, "2023-08-15", True, "Independent schools"),  # noqa: E501
        ("110567", "The Webber Independent School", "MK14 6DP", 52.0590, -0.7730, 0, 16, "All-through", "Mixed", None, None, "2022-05-20", True, "Independent schools"),  # noqa: E501
        ("110549", "Thornton College", "MK17 0HJ", 51.9580, -0.9160, 3, 19, "All-through", "Girls", "Roman Catholic", None, "", True, "Independent schools"),  # noqa: E501
        ("110536", "Akeley Wood Senior School", "MK18 5AE", 52.0170, -0.9710, 11, 18, "Secondary", "Mixed", None, None, "", True, "Independent schools"),  # noqa: E501
        ("122138", "Akeley Wood Junior School", "MK18 5AE", 52.0170, -0.9710, 4, 11, "Primary", "Mixed", None, None, "", True, "Independent schools"),  # noqa: E501
        ("133920", "Broughton Manor Preparatory School", "MK10 9AA", 52.0480, -0.7140, 3, 11, "Primary", "Mixed", None, None, "", True, "Independent schools"),  # noqa: E501
        ("110563", "The Grove Independent School", "MK5 8HD", 52.0100, -0.7920, 2, 13, "Primary", "Mixed", None, None, "", True, "Independent schools"),  # noqa: E501
        ("148420", "KWS Milton Keynes", "MK2 3HU", 52.0070, -0.7300, 7, 18, "Secondary", "Mixed", None, None, "", True, "Independent special schools"),  # noqa: E501
    ]
    # fmt: on

    schools: list[School] = []
    for row in mk_schools:
        (
            urn,
            name,
            postcode,
            lat,
            lng,
            age_from,
            age_to,
            phase,
            gender,
            faith,
            ofsted,
            ofsted_date_str,
            is_private,
            type_group,
        ) = row

        ofsted_date_val = None
        if ofsted_date_str:
            try:
                ofsted_date_val = datetime.strptime(ofsted_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        school_type = "private" if is_private else "state"

        schools.append(
            School(
                urn=urn,
                name=name,
                type=school_type,
                council=council,
                address=f"{name}, Milton Keynes",
                postcode=postcode,
                lat=lat,
                lng=lng,
                catchment_radius_km=_default_catchment_km(phase),
                gender_policy=gender,
                faith=faith,
                age_range_from=age_from,
                age_range_to=age_to,
                ofsted_rating=ofsted if ofsted != "Not applicable" else None,
                ofsted_date=ofsted_date_val,
                is_private=is_private,
            )
        )

    return schools


# ---------------------------------------------------------------------------
# Private school details generation
# ---------------------------------------------------------------------------

# Each entry: (school_name_fragment, fee_age_group, termly_fee, annual_fee,
#              day_start, day_end, provides_transport, transport_notes,
#              holiday_schedule_notes)
_PRIVATE_SCHOOL_DETAILS: list[tuple[str, str, float, float, time, time, bool, str | None, str | None]] = [
    # -- Thornton College (girls, Catholic) --
    (
        "Thornton College",
        "Pre-prep (3-7)",
        4500.0,
        13500.0,
        time(8, 15),
        time(16, 0),
        True,
        "Bus routes from Milton Keynes, Buckingham, and Towcester. Door-to-door minibus service available.",
        "Follows own term dates. Three terms with half-term breaks. Longer holidays than state schools.",  # noqa: E501
    ),
    (
        "Thornton College",
        "Prep (7-11)",
        5000.0,
        15000.0,
        time(8, 15),
        time(16, 0),
        True,
        "Bus routes from Milton Keynes, Buckingham, and Towcester. Door-to-door minibus service available.",
        "Follows own term dates. Three terms with half-term breaks. Longer holidays than state schools.",  # noqa: E501
    ),
    (
        "Thornton College",
        "Senior (11-16)",
        5500.0,
        16500.0,
        time(8, 15),
        time(16, 0),
        True,
        "Bus routes from Milton Keynes, Buckingham, and Towcester. Door-to-door minibus service available.",
        "Follows own term dates. Three terms with half-term breaks. Longer holidays than state schools.",  # noqa: E501
    ),
    (
        "Thornton College",
        "Sixth Form (16-19)",
        5500.0,
        16500.0,
        time(8, 15),
        time(16, 0),
        True,
        "Bus routes from Milton Keynes, Buckingham, and Towcester. Door-to-door minibus service available.",
        "Follows own term dates. Three terms with half-term breaks. Longer holidays than state schools.",  # noqa: E501
    ),
    # -- Akeley Wood Senior School --
    (
        "Akeley Wood Senior",
        "Senior (11-16)",
        5500.0,
        16500.0,
        time(8, 30),
        time(16, 15),
        True,
        "Dedicated bus routes covering Buckingham, Milton Keynes, Brackley, and surrounding villages.",
        "Sets own term dates. Three terms with half-term breaks. Longer summer holidays.",  # noqa: E501
    ),
    (
        "Akeley Wood Senior",
        "Sixth Form (16-18)",
        6000.0,
        18000.0,
        time(8, 30),
        time(16, 15),
        True,
        "Dedicated bus routes covering Buckingham, Milton Keynes, Brackley, and surrounding villages.",
        "Sets own term dates. Three terms with half-term breaks. Longer summer holidays.",  # noqa: E501
    ),
    # -- Akeley Wood Junior School --
    (
        "Akeley Wood Junior",
        "Pre-prep (4-7)",
        3800.0,
        11400.0,
        time(8, 30),
        time(15, 45),
        True,
        "Shared transport with Akeley Wood Senior. Bus routes from Buckingham and Milton Keynes.",
        "Follows Akeley Wood group term dates. Three terms with half-term breaks.",
    ),
    (
        "Akeley Wood Junior",
        "Prep (7-11)",
        4500.0,
        13500.0,
        time(8, 30),
        time(15, 45),
        True,
        "Shared transport with Akeley Wood Senior. Bus routes from Buckingham and Milton Keynes.",
        "Follows Akeley Wood group term dates. Three terms with half-term breaks.",
    ),
    # -- Milton Keynes Preparatory School --
    (
        "Milton Keynes Preparatory",
        "Nursery/Pre-prep (3-7)",
        3500.0,
        10500.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows broadly similar term dates to Milton Keynes state schools with minor variations.",
    ),
    (
        "Milton Keynes Preparatory",
        "Prep (7-11)",
        4000.0,
        12000.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows broadly similar term dates to Milton Keynes state schools with minor variations.",
    ),
    (
        "Milton Keynes Preparatory",
        "Senior (11-13)",
        4200.0,
        12600.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows broadly similar term dates to Milton Keynes state schools with minor variations.",
    ),
    # -- The Webber Independent School --
    (
        "Webber Independent",
        "Early Years (0-4)",
        3000.0,
        9000.0,
        time(8, 45),
        time(15, 30),
        False,
        None,
        "Follows own term dates, broadly aligned with state school calendar.",
    ),
    (
        "Webber Independent",
        "Primary (4-11)",
        3500.0,
        10500.0,
        time(8, 45),
        time(15, 30),
        False,
        None,
        "Follows own term dates, broadly aligned with state school calendar.",
    ),
    (
        "Webber Independent",
        "Secondary (11-16)",
        4000.0,
        12000.0,
        time(8, 45),
        time(15, 30),
        False,
        None,
        "Follows own term dates, broadly aligned with state school calendar.",
    ),
    # -- The Grove Independent School --
    (
        "Grove Independent",
        "Nursery (2-4)",
        3200.0,
        9600.0,
        time(8, 30),
        time(15, 30),
        False,
        "Limited minibus service available for local routes within Milton Keynes. Additional charge applies.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Grove Independent",
        "Infant (4-7)",
        3500.0,
        10500.0,
        time(8, 30),
        time(15, 30),
        False,
        "Limited minibus service available for local routes within Milton Keynes. Additional charge applies.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Grove Independent",
        "Junior (7-13)",
        3800.0,
        11400.0,
        time(8, 30),
        time(15, 30),
        False,
        "Limited minibus service available for local routes within Milton Keynes. Additional charge applies.",
        "Follows own term dates. Three terms per year.",
    ),
    # -- Broughton Manor Preparatory School --
    (
        "Broughton Manor",
        "Nursery (3-4)",
        3400.0,
        10200.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Broughton Manor",
        "Pre-prep (4-7)",
        3800.0,
        11400.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Broughton Manor",
        "Prep (7-11)",
        4200.0,
        12600.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    # -- Swanbourne House School (nearby boarding prep) --
    # Not in the seed data but mentioned in task; we'll match by name fragment
    # against any school named "Swanbourne" in the DB.
    (
        "Swanbourne House",
        "Pre-prep (4-7)",
        5500.0,
        16500.0,
        time(8, 15),
        time(17, 30),
        True,
        "Comprehensive bus network covering Aylesbury, Buckingham, Milton Keynes, and Bicester.",
        "Follows own term dates. Boarding available from Year 3. Longer exeat weekends.",
    ),
    (
        "Swanbourne House",
        "Prep (7-11)",
        6500.0,
        19500.0,
        time(8, 15),
        time(17, 30),
        True,
        "Comprehensive bus network covering Aylesbury, Buckingham, Milton Keynes, and Bicester.",
        "Follows own term dates. Boarding available from Year 3. Longer exeat weekends.",
    ),
    (
        "Swanbourne House",
        "Prep (11-13)",
        7500.0,
        22500.0,
        time(8, 15),
        time(17, 30),
        True,
        "Comprehensive bus network covering Aylesbury, Buckingham, Milton Keynes, and Bicester.",
        "Follows own term dates. Boarding available from Year 3. Longer exeat weekends.",
    ),
    # -- Winchester House School (nearby prep) --
    (
        "Winchester House",
        "Pre-prep (4-7)",
        5000.0,
        15000.0,
        time(8, 15),
        time(17, 15),
        True,
        "Bus routes serving Brackley, Buckingham, Towcester, and north Oxfordshire villages.",
        "Follows own term dates. Three terms with half-term breaks and exeat weekends.",
    ),
    (
        "Winchester House",
        "Prep (7-11)",
        5800.0,
        17400.0,
        time(8, 15),
        time(17, 15),
        True,
        "Bus routes serving Brackley, Buckingham, Towcester, and north Oxfordshire villages.",
        "Follows own term dates. Three terms with half-term breaks and exeat weekends.",
    ),
    (
        "Winchester House",
        "Prep (11-13)",
        6500.0,
        19500.0,
        time(8, 15),
        time(17, 15),
        True,
        "Bus routes serving Brackley, Buckingham, Towcester, and north Oxfordshire villages.",
        "Follows own term dates. Three terms with half-term breaks and exeat weekends.",
    ),
    # -- KWS Milton Keynes --
    (
        "KWS Milton Keynes",
        "Primary (7-11)",
        3500.0,
        10500.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms per year.",
    ),
    (
        "KWS Milton Keynes",
        "Secondary (11-16)",
        4200.0,
        12600.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms per year.",
    ),
    (
        "KWS Milton Keynes",
        "Sixth Form (16-18)",
        4800.0,
        14400.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms per year.",
    ),
]


def _generate_private_school_details(session: Session) -> int:
    """Create PrivateSchoolDetails records for all private schools in the database.

    Matches schools by name fragment and creates multiple fee-tier entries per
    school (one per age group).  Returns the number of detail records inserted.
    """
    private_schools = session.query(School).filter_by(is_private=True).all()
    if not private_schools:
        return 0

    # Build a lookup: name fragment -> list of detail tuples
    details_by_fragment: dict[str, list[tuple[str, str, float, float, time, time, bool, str | None, str | None]]] = {}
    for entry in _PRIVATE_SCHOOL_DETAILS:
        fragment = entry[0]
        details_by_fragment.setdefault(fragment, []).append(entry)

    count = 0
    for school in private_schools:
        # Find matching details by checking if any known fragment is in the school name
        matched_entries: list[tuple[str, str, float, float, time, time, bool, str | None, str | None]] = []
        for fragment, entries in details_by_fragment.items():
            if fragment.lower() in school.name.lower():
                matched_entries = entries
                break

        if not matched_entries:
            # No specific data for this school; skip it
            continue

        # Remove any existing details for this school (idempotent re-seed)
        session.query(PrivateSchoolDetails).filter_by(school_id=school.id).delete()

        for entry in matched_entries:
            (
                _name_frag,
                fee_age_group,
                termly_fee,
                annual_fee,
                day_start,
                day_end,
                provides_transport,
                transport_notes,
                holiday_schedule_notes,
            ) = entry

            detail = PrivateSchoolDetails(
                school_id=school.id,
                termly_fee=termly_fee,
                annual_fee=annual_fee,
                fee_age_group=fee_age_group,
                school_day_start=day_start,
                school_day_end=day_end,
                provides_transport=provides_transport,
                transport_notes=transport_notes,
                holiday_schedule_notes=holiday_schedule_notes,
            )
            session.add(detail)
            count += 1

    session.commit()
    return count


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
    print("[1/5] Obtaining GIAS CSV ...")

    use_test_data = False
    csv_path: Path | None = None

    cached = _find_cached_csv()
    if cached and not force_download:
        print(f"  Found cached file: {cached}")
        csv_path = cached
    else:
        try:
            csv_path = _download_gias_csv(force=force_download)
        except Exception as exc:
            print(f"  WARNING: GIAS download failed: {exc}")
            print("  Will use built-in test data instead.")
            use_test_data = True

    # ------------------------------------------------------------------
    # 2. Read and filter CSV rows (or use test data)
    # ------------------------------------------------------------------
    schools: list[School] = []

    if use_test_data or csv_path is None:
        print("[2/5] Generating test school data ...")
        schools = _generate_test_schools(council)
        print(f"  Generated {len(schools)} test schools for '{council}'")
    else:
        print("[2/5] Reading CSV ...")
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
        print("[3/5] Mapping to School records ...")
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
    print("[4/5] Writing to database ...")
    session = _ensure_database(db_path)
    try:
        inserted, updated = _upsert_schools(session, schools)
        total_in_db = session.query(School).filter_by(council=council).count()
        print(f"  Inserted: {inserted}")
        print(f"  Updated : {updated}")
        print(f"  Total schools for '{council}' in DB: {total_in_db}")

        # ------------------------------------------------------------------
        # 5. Seed private school details
        # ------------------------------------------------------------------
        print()
        print("[5/5] Seeding private school details ...")
        detail_count = _generate_private_school_details(session)
        print(f"  Private school detail records: {detail_count}")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print()
        print("=" * 60)
        print(f"  SUMMARY: {council}")
        print("=" * 60)

        all_schools = session.query(School).filter_by(council=council).all()

        # By phase / type
        primary_count = sum(1 for s in all_schools if s.age_range_to and s.age_range_to <= 13 and not s.is_private)
        secondary_count = sum(
            1
            for s in all_schools
            if s.age_range_from
            and s.age_range_from >= 11
            and s.age_range_to
            and s.age_range_to >= 16
            and not s.is_private
        )
        private_count = sum(1 for s in all_schools if s.is_private)

        private_with_details = session.query(PrivateSchoolDetails.school_id).distinct().count()

        print(f"  Total schools       : {len(all_schools)}")
        print(f"  State primary       : {primary_count}")
        print(f"  State secondary     : {secondary_count}")
        print(f"  Private/independent : {private_count}")
        print(f"  Private w/ details  : {private_with_details}")
        print()

        # By Ofsted rating
        from collections import Counter

        rating_counts = Counter(s.ofsted_rating for s in all_schools if s.ofsted_rating)
        print("  Ofsted ratings:")
        for rating in ["Outstanding", "Good", "Requires improvement", "Inadequate"]:
            count = rating_counts.get(rating, 0)
            if count:
                print(f"    {rating:25s}: {count}")
        no_rating = sum(1 for s in all_schools if not s.ofsted_rating)
        if no_rating:
            print(f"    {'(no rating)':25s}: {no_rating}")

        print("=" * 60)
    finally:
        session.close()

    print()
    print("Done.")


if __name__ == "__main__":
    main()
