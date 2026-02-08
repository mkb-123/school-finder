"""GIAS (Get Information About Schools) data service.

Downloads the DfE GIAS establishment CSV, parses it with Polars, converts
OSGB36 coordinates to WGS84, and upserts school records into the database.

Data source: https://get-information-schools.service.gov.uk/Downloads
The CSV is published daily at a predictable URL.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta
from pathlib import Path

import polars as pl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import School
from src.services.gov_data.base import BaseGovDataService

logger = logging.getLogger(__name__)

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
# OSGB36 -> WGS84 coordinate conversion
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


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return great-circle distance in km between two WGS84 coordinate pairs."""
    earth_radius_km = 6371.0
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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
    return "private" if _is_private(row) else "state"


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


def _prospectus_url(website: str) -> str | None:
    """Derive a prospectus URL from a school website."""
    if not website or website.strip() == "":
        return None
    website = website.strip()
    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"
    return f"{website.rstrip('/')}/prospectus"


# ---------------------------------------------------------------------------
# CSV reading
# ---------------------------------------------------------------------------


def _read_gias_csv(path: Path) -> list[dict[str, str]]:
    """Read GIAS CSV with Polars, handling encoding variants."""
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
    raise RuntimeError(f"Could not decode {path} with any known encoding")


def _row_to_school(row: dict[str, str]) -> School | None:
    """Convert a GIAS CSV row to a School ORM object."""
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
    ofsted_date_val = _parse_ofsted_date(row.get(COL_OFSTED_DATE, ""))
    website = row.get(COL_WEBSITE, "").strip()
    faith = _normalise_faith(row.get(COL_RELIGION, ""))

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
        faith=faith,
        age_range_from=_safe_int(row.get(COL_LOW_AGE, "")),
        age_range_to=_safe_int(row.get(COL_HIGH_AGE, "")),
        ofsted_rating=ofsted_rating,
        ofsted_date=ofsted_date_val,
        is_private=_is_private(row),
        prospectus_url=_prospectus_url(website),
        website=website if website else None,
        ethos="",  # Not available in GIAS - populated by ethos agent
    )


# ---------------------------------------------------------------------------
# GIASService
# ---------------------------------------------------------------------------


class GIASService(BaseGovDataService):
    """Fetch and import school register data from the GIAS daily CSV.

    Usage::

        service = GIASService()
        stats = service.refresh(council="Milton Keynes")
    """

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        cache_ttl_hours: int | None = None,
    ) -> None:
        settings = get_settings()
        super().__init__(
            cache_dir=cache_dir or Path("./data/seeds"),
            cache_ttl_hours=cache_ttl_hours or settings.GIAS_CACHE_TTL_HOURS,
        )
        self._url_template = settings.GIAS_CSV_URL_TEMPLATE

    def _build_csv_urls(self) -> list[str]:
        """Build download URLs for today and yesterday (fallback)."""
        today = date.today().strftime("%Y%m%d")
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
        return [
            self._url_template.format(date=today),
            self._url_template.format(date=yesterday),
        ]

    def download_csv(self, force: bool = False) -> Path:
        """Download the latest GIAS CSV.

        Tries today's date first, falls back to yesterday if unavailable.

        Returns
        -------
        Path
            Path to the downloaded CSV file.
        """
        today = date.today().strftime("%Y%m%d")
        filename = f"edubasealldata{today}.csv"
        urls = self._build_csv_urls()
        return self.download_with_fallback(urls, filename=filename, force=force)

    def refresh(
        self,
        council: str,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, int]:
        """Download GIAS CSV and upsert schools for the given council.

        Parameters
        ----------
        council:
            Local authority name to filter (e.g. "Milton Keynes").
        force_download:
            If True, bypass cache and re-download.
        db_path:
            Override database path. Uses config default if None.

        Returns
        -------
        dict
            Statistics: {inserted, updated, total, with_coordinates}.
        """
        settings = get_settings()
        db = db_path or settings.SQLITE_PATH

        csv_path = self.download_csv(force=force_download)
        self._logger.info("Reading GIAS CSV: %s", csv_path)

        rows = _read_gias_csv(csv_path)
        self._logger.info("Total rows in CSV: %d", len(rows))

        council_lower = council.lower()
        council_rows = [r for r in rows if r.get(COL_LA, "").strip().lower() == council_lower]
        self._logger.info("Rows matching '%s': %d", council, len(council_rows))

        if not council_rows:
            all_councils = sorted({r.get(COL_LA, "").strip() for r in rows if r.get(COL_LA, "").strip()})
            close = [c for c in all_councils if council_lower in c.lower()]
            msg = f"No schools found for council '{council}'."
            if close:
                msg += f" Did you mean: {', '.join(close)}?"
            raise ValueError(msg)

        schools: list[School] = []
        skipped = 0
        for row in council_rows:
            school = _row_to_school(row)
            if school is not None:
                schools.append(school)
            else:
                skipped += 1

        self._logger.info("Mapped %d schools (%d skipped as closed/invalid)", len(schools), skipped)

        geo_count = sum(1 for s in schools if s.lat is not None)
        self._logger.info("Schools with coordinates: %d/%d", geo_count, len(schools))

        inserted, updated = self._upsert_schools(db, schools)

        return {
            "inserted": inserted,
            "updated": updated,
            "total": inserted + updated,
            "with_coordinates": geo_count,
        }

    def refresh_private_schools_by_radius(
        self,
        center_lat: float,
        center_lng: float,
        radius_km: float = 30.0,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, int]:
        """Import private schools from the GIAS CSV within *radius_km* of a centre point.

        Unlike :meth:`refresh`, this does NOT filter by council. It scans the
        entire GIAS dataset and imports any independent school whose coordinates
        fall within the given radius.

        Parameters
        ----------
        center_lat, center_lng:
            WGS84 coordinates of the search centre (e.g. council centroid).
        radius_km:
            Maximum distance from the centre point (default 30 km).
        force_download:
            If True, bypass cache and re-download the CSV.
        db_path:
            Override database path. Uses config default if ``None``.

        Returns
        -------
        dict
            Statistics: {inserted, updated, total, with_coordinates}.
        """
        settings = get_settings()
        db = db_path or settings.SQLITE_PATH

        csv_path = self.download_csv(force=force_download)
        self._logger.info("Reading GIAS CSV for radius private school import: %s", csv_path)

        rows = _read_gias_csv(csv_path)

        # Filter to open private schools with valid coordinates within radius
        private_schools: list[School] = []
        skipped = 0
        for row in rows:
            if not _is_private(row):
                continue
            status = row.get(COL_STATUS, "").strip()
            if status not in _OPEN_STATUSES:
                continue

            school = _row_to_school(row)
            if school is None:
                skipped += 1
                continue
            if school.lat is None or school.lng is None:
                skipped += 1
                continue

            dist = _haversine_distance(center_lat, center_lng, school.lat, school.lng)
            if dist <= radius_km:
                private_schools.append(school)
            else:
                skipped += 1

        self._logger.info(
            "Found %d private schools within %.0f km (%d skipped)",
            len(private_schools),
            radius_km,
            skipped,
        )

        geo_count = sum(1 for s in private_schools if s.lat is not None)
        inserted, updated = self._upsert_schools(db, private_schools)

        return {
            "inserted": inserted,
            "updated": updated,
            "total": inserted + updated,
            "with_coordinates": geo_count,
        }

    def _upsert_schools(self, db_path: str, schools: list[School]) -> tuple[int, int]:
        """Upsert schools by URN into the database."""
        engine = create_engine(f"sqlite:///{db_path}")
        from src.db.models import Base

        Base.metadata.create_all(engine)

        inserted = 0
        updated_count = 0

        with Session(engine) as session:
            for school in schools:
                existing = session.query(School).filter_by(urn=school.urn).first()
                if existing is None:
                    session.add(school)
                    inserted += 1
                else:
                    # Update fields from GIAS (preserving agent-populated fields)
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
                    existing.is_private = school.is_private
                    existing.website = school.website
                    # Only update Ofsted if GIAS has data and existing doesn't
                    # (prefer Ofsted MI CSV data which is more current)
                    if school.ofsted_rating and not existing.ofsted_rating:
                        existing.ofsted_rating = school.ofsted_rating
                    if school.ofsted_date and not existing.ofsted_date:
                        existing.ofsted_date = school.ofsted_date
                    updated_count += 1

            session.commit()

        self._logger.info("Inserted %d, updated %d schools", inserted, updated_count)
        return inserted, updated_count
