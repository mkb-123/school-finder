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
import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

import httpx
import polars as pl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import (
    AdmissionsHistory,
    Base,
    PrivateSchoolDetails,
    School,
    SchoolClub,
    SchoolPerformance,
    SchoolTermDate,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SEEDS_DIR = PROJECT_ROOT / "data" / "seeds"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "schools.db"

# ---------------------------------------------------------------------------
# GIAS download URL template
# ---------------------------------------------------------------------------
GIAS_CSV_URL_TEMPLATE = (
    "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/edubasealldata{date}.csv"
)

# ---------------------------------------------------------------------------
# GIAS column constants
# ---------------------------------------------------------------------------
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

_PRIVATE_TYPE_GROUPS = frozenset({"Independent schools", "Independent special schools"})
_OPEN_STATUSES = frozenset({"Open", "Open, but proposed to close"})


# ---------------------------------------------------------------------------
# OSGB36  ->  WGS84  coordinate conversion
# ---------------------------------------------------------------------------


def _grid_to_osgb36_latlon(easting: float, northing: float) -> tuple[float, float]:
    """Convert National Grid Easting/Northing to lat/lon on the Airy 1830 ellipsoid."""
    a = 6_377_563.396
    b = 6_356_256.909
    f0 = 0.9996012717
    lat0 = math.radians(49.0)
    lon0 = math.radians(-2.0)
    n0 = -100_000.0
    e0 = 400_000.0
    e2 = 1.0 - (b * b) / (a * a)
    n = (a - b) / (a + b)
    n2 = n * n
    n3 = n2 * n
    lat = lat0
    m = 0.0
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
    a1 = 6_377_563.396
    b1 = 6_356_256.909
    e2_1 = 1.0 - (b1 * b1) / (a1 * a1)
    sin_lat = math.sin(lat_r)
    cos_lat = math.cos(lat_r)
    sin_lon = math.sin(lon_r)
    cos_lon = math.cos(lon_r)
    nu = a1 / math.sqrt(1.0 - e2_1 * sin_lat * sin_lat)
    x1 = nu * cos_lat * cos_lon
    y1 = nu * cos_lat * sin_lon
    z1 = (1.0 - e2_1) * nu * sin_lat
    tx = 446.448
    ty = -125.157
    tz = 542.060
    s = -20.4894e-6
    rx = math.radians(0.1502 / 3600.0)
    ry = math.radians(0.2470 / 3600.0)
    rz = math.radians(0.8421 / 3600.0)
    x2 = tx + (1.0 + s) * x1 + (-rz) * y1 + ry * z1
    y2 = ty + rz * x1 + (1.0 + s) * y1 + (-rx) * z1
    z2 = tz + (-ry) * x1 + rx * y1 + (1.0 + s) * z1
    a2 = 6_378_137.0
    b2 = 6_356_752.3141
    e2_2 = 1.0 - (b2 * b2) / (a2 * a2)
    p = math.sqrt(x2 * x2 + y2 * y2)
    lat2 = math.atan2(z2, p * (1.0 - e2_2))
    for _ in range(10):
        nu2 = a2 / math.sqrt(1.0 - e2_2 * math.sin(lat2) * math.sin(lat2))
        lat2 = math.atan2(z2 + e2_2 * nu2 * math.sin(lat2), p)
    lon2 = math.atan2(y2, x2)
    return math.degrees(lat2), math.degrees(lon2)


def osgb36_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Convert OS National Grid Easting/Northing to WGS84 (lat, lon)."""
    lat_osgb, lon_osgb = _grid_to_osgb36_latlon(easting, northing)
    return _helmert_osgb36_to_wgs84(lat_osgb, lon_osgb)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_address(row: dict[str, str]) -> str:
    parts = [
        row.get(COL_STREET, "").strip(),
        row.get(COL_LOCALITY, "").strip(),
        row.get(COL_ADDRESS3, "").strip(),
        row.get(COL_TOWN, "").strip(),
    ]
    return ", ".join(p for p in parts if p)


def _is_private(row: dict[str, str]) -> bool:
    return row.get(COL_TYPE_GROUP, "").strip() in _PRIVATE_TYPE_GROUPS


def _school_type(row: dict[str, str]) -> str:
    if _is_private(row):
        return "private"
    return "state"


def _default_catchment_km(phase: str) -> float:
    phase_lower = phase.lower() if phase else ""
    if "secondary" in phase_lower or "16 plus" in phase_lower:
        return 3.0
    if "primary" in phase_lower or "nursery" in phase_lower:
        return 1.5
    return 2.0


def _safe_int(value: str) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_ofsted_date(value: str) -> date | None:
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
    raw = raw.strip()
    if raw in {"Boys", "Girls", "Mixed"}:
        return raw
    if "boy" in raw.lower():
        return "Boys"
    if "girl" in raw.lower():
        return "Girls"
    return "Mixed"


def _normalise_faith(raw: str) -> str | None:
    raw = raw.strip()
    if not raw or raw.lower() in {"none", "does not apply"}:
        return None
    return raw


# ---------------------------------------------------------------------------
# CSV download / cache
# ---------------------------------------------------------------------------


def _csv_cache_path() -> Path:
    today = date.today().strftime("%Y%m%d")
    return SEEDS_DIR / f"edubasealldata{today}.csv"


def _find_cached_csv() -> Path | None:
    candidates = sorted(SEEDS_DIR.glob("edubasealldata*.csv"), reverse=True)
    return candidates[0] if candidates else None


def _download_gias_csv(force: bool = False) -> Path:
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
    for encoding in ("cp1252", "utf-8-sig", "utf-8", "latin-1"):
        try:
            df = pl.read_csv(
                path,
                encoding=encoding,
                infer_schema_length=0,
                null_values=[""],
                truncate_ragged_lines=True,
            )
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
    status = row.get(COL_STATUS, "").strip()
    if status not in _OPEN_STATUSES:
        return None
    urn = row.get(COL_URN, "").strip()
    name = row.get(COL_NAME, "").strip()
    if not urn or not name:
        return None
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


def _generate_test_schools(council: str) -> list[School]:  # noqa: C901
    """Generate a set of realistic test schools for the given council."""
    # fmt: off
    mk_schools = [  # noqa: E501
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
        ("110197", "Knowles Nursery School", "MK2 2HB", 52.0050, -0.7310, 2, 5, "Nursery", "Mixed", None, "Good", "2022-06-15", False, "Local authority maintained schools"),  # noqa: E501
        ("110575", "White Spire School", "MK3 6EW", 51.9960, -0.7610, 2, 19, "Special", "Mixed", None, "Outstanding", "2022-03-09", False, "Local authority maintained schools"),  # noqa: E501
        ("110580a", "Romans Field Special School", "MK3 7AW", 51.9930, -0.7580, 3, 11, "Special", "Mixed", None, "Good", "2023-04-12", False, "Local authority maintained schools"),  # noqa: E501
        ("110584", "The Walnuts School", "MK8 0PU", 52.0260, -0.8080, 4, 19, "Special", "Mixed", None, "Good", "2023-06-28", False, "Local authority maintained schools"),  # noqa: E501
        ("110587", "Slated Row School", "MK12 5NJ", 52.0590, -0.7870, 3, 19, "Special", "Mixed", None, "Good", "2022-11-16", False, "Local authority maintained schools"),  # noqa: E501
        ("110592", "The Redway School", "MK6 4HG", 52.0340, -0.7500, 2, 19, "Special", "Mixed", None, "Outstanding", "2022-01-19", False, "Local authority maintained schools"),  # noqa: E501
        ("138253", "Stephenson Academy", "MK14 6AX", 52.0600, -0.7620, 11, 19, "Special", "Mixed", None, "Good", "2023-09-20", False, "Academies"),  # noqa: E501
        ("140252", "Bridge Academy", "MK14 6AX", 52.0610, -0.7630, 5, 16, "Special", "Mixed", None, "Good", "2023-02-01", False, "Academies"),  # noqa: E501
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
            is_private_val,
            _type_group,
        ) = row  # noqa: E501
        ofsted_date_val = None
        if ofsted_date_str:
            try:
                ofsted_date_val = datetime.strptime(ofsted_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        school_type = "private" if is_private_val else "state"
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
                is_private=is_private_val,
            )
        )
    return schools


# ---------------------------------------------------------------------------
# Club data generation
# ---------------------------------------------------------------------------

_BREAKFAST_CLUBS = [
    ("Early Birds Breakfast Club", "Start the day with a healthy breakfast and fun activities"),
    ("Sunshine Breakfast Club", "Morning care with toast, cereal, and supervised play"),
    ("Rise & Shine Club", "Nutritious breakfast with crafts and games before school"),
    ("Morning Stars Breakfast Club", "Enjoy breakfast and socialise before classes begin"),
    ("Bright Start Breakfast Club", "Fuelling young minds with a great start to the day"),
]

_AFTERSCHOOL_CLUBS = [
    ("Sports After-School Club", "Football, netball, athletics, and multi-sports sessions"),
    ("Homework Club", "Supervised homework time with teacher support"),
    ("Arts & Crafts Club", "Creative sessions including painting, drawing, and crafts"),
    ("Drama Club", "Acting, improvisation, and performance workshops"),
    ("Science Explorers Club", "Hands-on science experiments and STEM activities"),
    ("Coding Club", "Introduction to programming with Scratch and Python"),
    ("Music Club", "Learn instruments, sing, and explore rhythm"),
    ("Dance Club", "Street dance, ballet basics, and creative movement"),
    ("Gardening Club", "Growing vegetables and learning about nature"),
    ("Reading & Story Club", "Book club activities and creative writing"),
    ("Multi-Activity Club", "A mix of sports, games, and creative activities"),
    ("Chess Club", "Learn chess strategy and compete in friendly matches"),
]


def _generate_test_clubs(schools: list[School]) -> list[SchoolClub]:
    """Generate realistic breakfast and after-school club data for a sample of schools."""
    rng = random.Random(42)
    clubs: list[SchoolClub] = []
    for school in schools:
        if school.id is None or school.is_private:
            continue
        is_secondary = (
            school.age_range_from is not None
            and school.age_range_from >= 11
            and school.age_range_to is not None
            and school.age_range_to >= 16
        )
        breakfast_prob = 0.30 if is_secondary else 0.60
        afterschool_prob = 0.50 if is_secondary else 0.40
        if rng.random() < breakfast_prob:
            bname, bdesc = rng.choice(_BREAKFAST_CLUBS)
            start_min = rng.choice([30, 35, 40, 45])
            end_min = rng.choice([40, 45, 50])
            cost = round(rng.uniform(3.0, 5.0), 2)
            days = "Mon,Tue,Wed,Thu,Fri" if rng.random() < 0.85 else "Mon,Tue,Wed,Thu"
            clubs.append(
                SchoolClub(
                    school_id=school.id,
                    club_type="breakfast",
                    name=bname,
                    description=bdesc,
                    days_available=days,
                    start_time=time(7, start_min),
                    end_time=time(8, end_min),
                    cost_per_session=cost,
                )
            )
        if rng.random() < afterschool_prob:
            num_clubs = rng.choice([1, 1, 2, 2, 3])
            chosen = rng.sample(_AFTERSCHOOL_CLUBS, min(num_clubs, len(_AFTERSCHOOL_CLUBS)))
            for aname, adesc in chosen:
                as_start_min = rng.choice([15, 20, 30])
                as_end_hour = rng.choice([16, 17])
                as_end_min = rng.choice([0, 30]) if as_end_hour == 16 else rng.choice([0, 15, 30])
                cost = round(rng.uniform(5.0, 10.0), 2)
                all_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
                if rng.random() < 0.4:
                    num_days = rng.randint(2, 4)
                    selected_days = sorted(rng.sample(all_days, num_days), key=all_days.index)
                    days = ",".join(selected_days)
                else:
                    days = "Mon,Tue,Wed,Thu,Fri"
                clubs.append(
                    SchoolClub(
                        school_id=school.id,
                        club_type="after_school",
                        name=aname,
                        description=adesc,
                        days_available=days,
                        start_time=time(15, as_start_min),
                        end_time=time(as_end_hour, as_end_min),
                        cost_per_session=cost,
                    )
                )
    return clubs


def _upsert_clubs(session: Session, clubs: list[SchoolClub]) -> int:
    """Insert club records, skipping duplicates by (school_id, club_type, name)."""
    inserted = 0
    for club in clubs:
        existing = (
            session.query(SchoolClub)
            .filter_by(school_id=club.school_id, club_type=club.club_type, name=club.name)
            .first()
        )
        if existing is None:
            session.add(club)
            inserted += 1
    session.commit()
    return inserted


# ---------------------------------------------------------------------------
# Private school details (fees, hours, transport)
# ---------------------------------------------------------------------------
# Tuples: (school_name_fragment, fee_age_group, termly_fee, annual_fee,
#          fee_increase_pct, day_start, day_end, provides_transport,
#          transport_notes, holiday_notes)

_PRIVATE_DETAIL_ROWS: list[tuple[str, str, float, float, float, time, time, bool, str | None, str | None]] = [
    # Thornton College (Girls boarding/day, Catholic)
    (
        "Thornton",
        "Pre-prep (3-7)",
        3800.0,
        11400.0,
        4.5,
        time(8, 15),
        time(16, 0),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Thornton",
        "Prep (7-11)",
        4500.0,
        13500.0,
        4.5,
        time(8, 15),
        time(16, 15),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Thornton",
        "Senior (11-16)",
        5200.0,
        15600.0,
        4.2,
        time(8, 15),
        time(16, 30),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Thornton",
        "Sixth Form (16-18)",
        5500.0,
        16500.0,
        4.2,
        time(8, 15),
        time(16, 30),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    # Akeley Wood Senior
    (
        "Akeley Wood Senior",
        "Senior (11-16)",
        5800.0,
        17400.0,
        5.0,
        time(8, 30),
        time(16, 15),
        True,
        "Dedicated school bus service covering most of North Bucks.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Akeley Wood Senior",
        "Sixth Form (16-18)",
        6100.0,
        18300.0,
        5.0,
        time(8, 30),
        time(16, 15),
        True,
        "Dedicated school bus service covering most of North Bucks.",
        "Follows own term dates. Three terms per year.",
    ),
    # Akeley Wood Junior
    (
        "Akeley Wood Junior",
        "Pre-prep (3-7)",
        3200.0,
        9600.0,
        4.8,
        time(8, 30),
        time(15, 30),
        True,
        "Shared bus service with Senior School.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Akeley Wood Junior",
        "Prep (7-11)",
        4200.0,
        12600.0,
        4.8,
        time(8, 30),
        time(15, 45),
        True,
        "Shared bus service with Senior School.",
        "Follows own term dates. Three terms per year.",
    ),
    # MK Prep School
    (
        "Milton Keynes Prep",
        "Reception (4-5)",
        3500.0,
        10500.0,
        3.5,
        time(8, 20),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Milton Keynes Prep",
        "Prep (5-11)",
        4100.0,
        12300.0,
        3.5,
        time(8, 20),
        time(15, 45),
        False,
        None,
        "Follows own term dates. Three terms per year.",
    ),
    # Webber Independent
    (
        "Webber Independent",
        "Early Years (0-4)",
        3000.0,
        9000.0,
        3.0,
        time(8, 45),
        time(15, 30),
        False,
        None,
        "Follows own term dates, broadly aligned with state calendar.",
    ),
    (
        "Webber Independent",
        "Primary (4-11)",
        3500.0,
        10500.0,
        3.0,
        time(8, 45),
        time(15, 30),
        False,
        None,
        "Follows own term dates, broadly aligned with state calendar.",
    ),
    # Grove Independent
    (
        "Grove Independent",
        "Nursery (2-4)",
        3200.0,
        9600.0,
        3.2,
        time(8, 30),
        time(15, 30),
        False,
        "Limited minibus for local MK routes. Additional charge.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Grove Independent",
        "Infant (4-7)",
        3500.0,
        10500.0,
        3.2,
        time(8, 30),
        time(15, 30),
        False,
        "Limited minibus for local MK routes. Additional charge.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Grove Independent",
        "Junior (7-13)",
        3800.0,
        11400.0,
        3.2,
        time(8, 30),
        time(15, 30),
        False,
        "Limited minibus for local MK routes. Additional charge.",
        "Follows own term dates. Three terms per year.",
    ),
    # Broughton Manor Prep
    (
        "Broughton Manor",
        "Nursery (3-4)",
        3400.0,
        10200.0,
        3.8,
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
        3.8,
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
        3.8,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    # KWS Milton Keynes
    (
        "KWS Milton Keynes",
        "Primary (7-11)",
        3500.0,
        10500.0,
        4.0,
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
        4.0,
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
        4.0,
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

    # Build lookup: name fragment -> list of detail tuples
    details_by_frag: dict[str, list] = {}
    for entry in _PRIVATE_DETAIL_ROWS:
        details_by_frag.setdefault(entry[0], []).append(entry)

    count = 0
    for school in private_schools:
        matched: list | None = None
        for frag, entries in details_by_frag.items():
            if frag.lower() in school.name.lower():
                matched = entries
                break
        if not matched:
            continue

        # Remove existing details (idempotent re-seed)
        session.query(PrivateSchoolDetails).filter_by(school_id=school.id).delete()

        for entry in matched:
            (
                _,
                fee_age_group,
                termly_fee,
                annual_fee,
                fee_increase_pct,
                day_start,
                day_end,
                provides_transport,
                transport_notes,
                holiday_notes,
            ) = entry
            session.add(
                PrivateSchoolDetails(
                    school_id=school.id,
                    fee_age_group=fee_age_group,
                    termly_fee=termly_fee,
                    annual_fee=annual_fee,
                    fee_increase_pct=fee_increase_pct,
                    school_day_start=day_start,
                    school_day_end=day_end,
                    provides_transport=provides_transport,
                    transport_notes=transport_notes,
                    holiday_schedule_notes=holiday_notes,
                )
            )
            count += 1
    session.commit()
    return count


# ---------------------------------------------------------------------------
# Performance data generation
# ---------------------------------------------------------------------------


def _generate_test_performance(schools: list[School], session: Session) -> int:
    """Generate realistic SchoolPerformance records for seeded schools.

    Creates SATs data for primary schools and GCSE / Progress8 / Attainment8
    data for secondary schools, across two academic years for trend analysis.
    Returns the number of records inserted.
    """
    rng = random.Random(42)
    academic_years = [2023, 2024]  # representing 2022/2023 and 2023/2024
    count = 0

    for school in schools:
        if school.id is None or school.is_private:
            continue

        is_secondary = (
            school.age_range_from is not None
            and school.age_range_from >= 11
            and school.age_range_to is not None
            and school.age_range_to >= 16
        )
        is_primary = (
            school.age_range_from is not None
            and school.age_range_from < 11
            and school.age_range_to is not None
            and school.age_range_to <= 13
        )

        # Skip schools that don't clearly fit primary or secondary
        if not is_primary and not is_secondary:
            continue

        for year in academic_years:
            # Small year-on-year variation
            year_drift = rng.uniform(-3.0, 3.0)

            if is_primary:
                # SATs results: expected standard %
                base_expected = rng.uniform(55.0, 85.0)
                expected_pct = round(max(40.0, min(95.0, base_expected + year_drift)), 0)
                # Higher standard %
                base_higher = rng.uniform(5.0, 25.0)
                higher_pct = round(max(2.0, min(40.0, base_higher + year_drift * 0.5)), 0)

                session.add(
                    SchoolPerformance(
                        school_id=school.id,
                        metric_type="SATs",
                        metric_value=f"Expected standard: {int(expected_pct)}%",
                        year=year,
                        source_url="https://www.find-school-performance-data.service.gov.uk/",
                    )
                )
                count += 1
                session.add(
                    SchoolPerformance(
                        school_id=school.id,
                        metric_type="SATs_Higher",
                        metric_value=f"Higher standard: {int(higher_pct)}%",
                        year=year,
                        source_url="https://www.find-school-performance-data.service.gov.uk/",
                    )
                )
                count += 1

            elif is_secondary:
                # GCSE results: 5+ GCSEs at grade 9-4 %
                base_gcse = rng.uniform(50.0, 85.0)
                gcse_pct = round(max(30.0, min(98.0, base_gcse + year_drift)), 0)
                session.add(
                    SchoolPerformance(
                        school_id=school.id,
                        metric_type="GCSE",
                        metric_value=f"5+ GCSEs 9-4: {int(gcse_pct)}%",
                        year=year,
                        source_url="https://www.find-school-performance-data.service.gov.uk/",
                    )
                )
                count += 1

                # Progress 8 score (typically -1.5 to +1.5)
                base_p8 = rng.uniform(-0.8, 0.8)
                p8_score = round(base_p8 + year_drift * 0.02, 2)
                p8_score = max(-1.5, min(1.5, p8_score))
                session.add(
                    SchoolPerformance(
                        school_id=school.id,
                        metric_type="Progress8",
                        metric_value=f"{p8_score:+.2f}",
                        year=year,
                        source_url="https://www.find-school-performance-data.service.gov.uk/",
                    )
                )
                count += 1

                # Attainment 8 score (typically 30-70)
                base_a8 = rng.uniform(35.0, 60.0)
                a8_score = round(max(25.0, min(70.0, base_a8 + year_drift)), 1)
                session.add(
                    SchoolPerformance(
                        school_id=school.id,
                        metric_type="Attainment8",
                        metric_value=str(a8_score),
                        year=year,
                        source_url="https://www.find-school-performance-data.service.gov.uk/",
                    )
                )
                count += 1

    session.commit()
    return count


# ---------------------------------------------------------------------------
# Term date seed data
# ---------------------------------------------------------------------------

# Milton Keynes Council standard term dates for 2025-2026.
_MK_COUNCIL_TERMS_2025_2026 = [
    {
        "term_name": "Autumn Term",
        "start_date": date(2025, 9, 3),
        "end_date": date(2025, 12, 19),
        "half_term_start": date(2025, 10, 27),
        "half_term_end": date(2025, 10, 31),
    },
    {
        "term_name": "Spring Term",
        "start_date": date(2026, 1, 5),
        "end_date": date(2026, 3, 27),
        "half_term_start": date(2026, 2, 16),
        "half_term_end": date(2026, 2, 20),
    },
    {
        "term_name": "Summer Term",
        "start_date": date(2026, 4, 13),
        "end_date": date(2026, 7, 22),
        "half_term_start": date(2026, 5, 25),
        "half_term_end": date(2026, 5, 29),
    },
]

# Private schools typically have longer holidays (start later, end earlier).
_PRIVATE_SCHOOL_TERMS_2025_2026 = [
    {
        "term_name": "Autumn Term",
        "start_date": date(2025, 9, 8),
        "end_date": date(2025, 12, 12),
        "half_term_start": date(2025, 10, 20),
        "half_term_end": date(2025, 10, 31),
    },
    {
        "term_name": "Spring Term",
        "start_date": date(2026, 1, 12),
        "end_date": date(2026, 3, 20),
        "half_term_start": date(2026, 2, 16),
        "half_term_end": date(2026, 2, 20),
    },
    {
        "term_name": "Summer Term",
        "start_date": date(2026, 4, 20),
        "end_date": date(2026, 7, 10),
        "half_term_start": date(2026, 5, 25),
        "half_term_end": date(2026, 5, 29),
    },
]


def _generate_test_term_dates(schools: list[School]) -> list[SchoolTermDate]:
    """Generate realistic term date records for all schools."""
    rng = random.Random(42)
    academic_year = "2025/2026"
    term_dates: list[SchoolTermDate] = []
    for school in schools:
        if school.is_private:
            base_terms = _PRIVATE_SCHOOL_TERMS_2025_2026
        else:
            base_terms = _MK_COUNCIL_TERMS_2025_2026
        varies = not school.is_private and rng.random() < 0.30
        for term_info in base_terms:
            if varies:
                day_offset_start = timedelta(days=rng.randint(-3, 3))
                day_offset_end = timedelta(days=rng.randint(-3, 3))
                start = term_info["start_date"] + day_offset_start
                end = term_info["end_date"] + day_offset_end
                ht_start = term_info["half_term_start"] + timedelta(days=rng.randint(-1, 1))
                ht_end = term_info["half_term_end"] + timedelta(days=rng.randint(-1, 1))
            else:
                start = term_info["start_date"]
                end = term_info["end_date"]
                ht_start = term_info["half_term_start"]
                ht_end = term_info["half_term_end"]
            term_dates.append(
                SchoolTermDate(
                    school_id=school.id,
                    academic_year=academic_year,
                    term_name=term_info["term_name"],
                    start_date=start,
                    end_date=end,
                    half_term_start=ht_start,
                    half_term_end=ht_end,
                )
            )
    return term_dates


def _seed_term_dates(session: Session, council: str) -> int:
    """Generate and insert term dates for all schools in the given council."""
    school_ids = [s.id for s in session.query(School).filter_by(council=council).all()]
    if not school_ids:
        return 0
    session.query(SchoolTermDate).filter(SchoolTermDate.school_id.in_(school_ids)).delete(synchronize_session=False)
    session.flush()
    schools = session.query(School).filter_by(council=council).all()
    new_term_dates = _generate_test_term_dates(schools)
    session.add_all(new_term_dates)
    session.commit()
    return len(new_term_dates)


# ---------------------------------------------------------------------------
# Admissions history seed data
# ---------------------------------------------------------------------------

_ACADEMIC_YEARS = ["2021/2022", "2022/2023", "2023/2024", "2024/2025"]


def _generate_test_admissions(schools: list[School], session: Session) -> int:
    """Generate realistic historical admissions data for state schools.

    Creates 4 years of admissions history per state school with realistic
    data including places offered, applications received, last distance
    offered, waiting list offers, and appeals data.  Uses a deterministic
    RNG seeded with 42 for reproducibility.

    Returns the number of records inserted.
    """
    rng = random.Random(42)
    count = 0

    for school in schools:
        if school.id is None or school.is_private:
            continue

        # Determine school size category based on age range
        is_secondary = (
            school.age_range_from is not None
            and school.age_range_from >= 11
            and school.age_range_to is not None
            and school.age_range_to >= 16
        )

        # Base places offered: secondary schools are larger
        if is_secondary:
            base_places = rng.choice([150, 180, 210, 240])
        else:
            base_places = rng.choice([30, 45, 60, 90])

        # Popularity factor: Outstanding schools are more popular
        if school.ofsted_rating == "Outstanding":
            popularity = rng.uniform(2.0, 3.0)
        elif school.ofsted_rating == "Good":
            popularity = rng.uniform(1.2, 2.2)
        elif school.ofsted_rating == "Requires improvement":
            popularity = rng.uniform(0.8, 1.3)
        else:
            popularity = rng.uniform(1.0, 1.8)

        # Base last distance offered (km) - more popular = smaller catchment
        if popularity > 2.0:
            base_distance = rng.uniform(0.5, 1.5)
        elif popularity > 1.5:
            base_distance = rng.uniform(1.0, 2.5)
        else:
            base_distance = rng.uniform(2.0, 5.0)

        # Trend: popular schools shrink catchment over time
        is_shrinking = popularity > 1.5 and rng.random() < 0.65
        is_growing = popularity < 1.2 and rng.random() < 0.40

        # Delete existing records for idempotent re-seed
        session.query(AdmissionsHistory).filter_by(school_id=school.id).delete()

        for i, year in enumerate(_ACADEMIC_YEARS):
            # Places offered stays fairly constant (slight variation)
            places = base_places + rng.randint(-5, 5)
            places = max(15, places)

            # Applications received based on popularity
            apps = int(places * popularity) + rng.randint(-10, 20)
            apps = max(places, apps)  # at least as many as places

            # Last distance offered trends over years
            if is_shrinking:
                year_factor = 1.0 - (i * rng.uniform(0.05, 0.12))
            elif is_growing:
                year_factor = 1.0 + (i * rng.uniform(0.03, 0.08))
            else:
                year_factor = 1.0 + rng.uniform(-0.05, 0.05)

            last_dist = round(base_distance * year_factor, 2)
            last_dist = max(0.2, min(8.0, last_dist))

            # Waiting list offers: more oversubscribed = more movement
            oversubscription = apps / places if places > 0 else 1.0
            if oversubscription > 2.0:
                wl_offers = rng.randint(8, 20)
            elif oversubscription > 1.5:
                wl_offers = rng.randint(5, 15)
            else:
                wl_offers = rng.randint(2, 8)

            # Appeals: proportional to oversubscription
            if oversubscription > 2.0:
                appeals_heard = rng.randint(5, 15)
            elif oversubscription > 1.5:
                appeals_heard = rng.randint(3, 10)
            else:
                appeals_heard = rng.randint(1, 5)

            # Appeals upheld: typically 20-40% success rate
            appeals_upheld = min(appeals_heard, rng.randint(1, max(1, int(appeals_heard * 0.45))))

            session.add(
                AdmissionsHistory(
                    school_id=school.id,
                    academic_year=year,
                    places_offered=places,
                    applications_received=apps,
                    last_distance_offered_km=last_dist,
                    waiting_list_offers=wl_offers,
                    appeals_heard=appeals_heard,
                    appeals_upheld=appeals_upheld,
                )
            )
            count += 1

    session.commit()
    return count


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


def _ensure_database(db_path: Path) -> Session:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return Session(engine)


def _upsert_schools(session: Session, schools: list[School]) -> tuple[int, int]:
    inserted = 0
    updated = 0
    for school in schools:
        existing = session.query(School).filter_by(urn=school.urn).first()
        if existing is None:
            session.add(school)
            inserted += 1
        else:
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
    parser = argparse.ArgumentParser(
        prog="python -m src.db.seed",
        description="Seed the school-finder database from GIAS establishment data.",
    )
    parser.add_argument("--council", required=True, help="Local authority name to filter by.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to the SQLite database file.")
    parser.add_argument("--force-download", action="store_true", default=False, help="Force re-download.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:  # noqa: C901
    """Entry point for the seed script."""
    args = parse_args(argv)
    council: str = args.council
    db_path: Path = args.db
    force_download: bool = args.force_download

    print("School Finder - GIAS Seed")
    print(f"  Council filter : {council}")
    print(f"  Database       : {db_path}")
    print()

    print("[1/9] Obtaining GIAS CSV ...")
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

    schools: list[School] = []
    if use_test_data or csv_path is None:
        print("[2/9] Generating test school data ...")
        schools = _generate_test_schools(council)
        print(f"  Generated {len(schools)} test schools for '{council}'")
    else:
        print("[2/9] Reading CSV ...")
        rows = _read_csv(csv_path)
        print(f"  Total rows in CSV: {len(rows)}")
        council_lower = council.lower()
        council_rows = [r for r in rows if r.get(COL_LA, "").strip().lower() == council_lower]
        print(f"  Rows matching council '{council}': {len(council_rows)}")
        if not council_rows:
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
        print("[3/9] Mapping to School records ...")
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

    print("[4/9] Writing schools to database ...")
    session = _ensure_database(db_path)
    try:
        inserted, updated = _upsert_schools(session, schools)
        total_in_db = session.query(School).filter_by(council=council).count()
        print(f"  Inserted: {inserted}")
        print(f"  Updated : {updated}")
        print(f"  Total schools for '{council}' in DB: {total_in_db}")

        print("[5/9] Seeding term dates ...")
        term_count = _seed_term_dates(session, council)
        print(f"  Term date records created: {term_count}")

        print("[6/9] Generating club data ...")
        all_schools = session.query(School).filter_by(council=council).all()
        clubs = _generate_test_clubs(all_schools)
        clubs_inserted = _upsert_clubs(session, clubs)
        total_clubs = session.query(SchoolClub).count()
        breakfast_count = sum(1 for c in clubs if c.club_type == "breakfast")
        afterschool_count = sum(1 for c in clubs if c.club_type == "after_school")
        print(f"  Clubs generated : {len(clubs)} ({breakfast_count} breakfast, {afterschool_count} after-school)")
        print(f"  Clubs inserted  : {clubs_inserted}")
        print(f"  Total clubs in DB: {total_clubs}")

        print("[7/9] Generating private school details ...")
        pvt_count = _generate_private_school_details(session)
        print(f"  Private school detail tiers: {pvt_count}")

        print("[8/9] Generating performance data ...")
        # Clear existing performance data for idempotent re-seed
        school_ids = [s.id for s in all_schools]
        if school_ids:
            session.query(SchoolPerformance).filter(SchoolPerformance.school_id.in_(school_ids)).delete(
                synchronize_session=False
            )
            session.flush()
        perf_count = _generate_test_performance(all_schools, session)
        print(f"  Performance records created: {perf_count}")

        print("[9/9] Generating admissions history ...")
        admissions_count = _generate_test_admissions(all_schools, session)
        print(f"  Admissions history records created: {admissions_count}")

        print()
        print("=" * 60)
        print(f"  SUMMARY: {council}")
        print("=" * 60)
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
        print(f"  Total schools       : {len(all_schools)}")
        print(f"  State primary       : {primary_count}")
        print(f"  State secondary     : {secondary_count}")
        print(f"  Private/independent : {private_count}")
        print(f"  Term date records   : {term_count}")
        print(f"  Performance records : {perf_count}")
        print(f"  Admissions records  : {admissions_count}")
        print(f"  Breakfast clubs     : {breakfast_count}")
        print(f"  After-school clubs  : {afterschool_count}")
        print()
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
