"""Live GIAS (Get Information About Schools) data service.

Fetches fresh school data directly from the DfE's GIAS daily CSV extract
rather than relying on pre-cached data. This ensures Ofsted ratings,
school status, and other fields are always current.

The GIAS CSV is published daily at a predictable URL pattern:
    https://ea-edubase-api-prod.azurewebsites.net/edubase/edubasealldata{YYYYMMDD}.csv

No authentication is required.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from io import BytesIO

import httpx
import polars as pl

logger = logging.getLogger(__name__)

_GIAS_URL_TEMPLATE = "https://ea-edubase-api-prod.azurewebsites.net/edubase/edubasealldata{date}.csv"
_HTTP_TIMEOUT = 60.0
_USER_AGENT = "SchoolFinder/0.1 (+https://github.com/school-finder)"

# Milton Keynes LA code in GIAS
_MK_LA_CODE = "826"


async def fetch_gias_csv(target_date: date | None = None) -> pl.DataFrame:
    """Download and parse the GIAS daily CSV extract.

    Tries today's date first, then falls back to the previous 3 days
    in case today's extract hasn't been published yet.

    Returns a Polars DataFrame with all schools in the extract.
    """
    dates_to_try = []
    base = target_date or date.today()
    for offset in range(4):
        dates_to_try.append(base - timedelta(days=offset))

    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        for dt in dates_to_try:
            url = _GIAS_URL_TEMPLATE.format(date=dt.strftime("%Y%m%d"))
            logger.info("Trying GIAS CSV: %s", url)
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                logger.info("Successfully fetched GIAS CSV for %s", dt)
                return pl.read_csv(
                    BytesIO(resp.content),
                    encoding="utf-8-sig",
                    ignore_errors=True,
                    infer_schema_length=0,  # read everything as strings
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.debug("GIAS CSV not available for %s, trying earlier date", dt)
                    continue
                raise

    raise RuntimeError("Could not fetch GIAS CSV for any of the last 4 days")


def filter_council(df: pl.DataFrame, la_code: str = _MK_LA_CODE) -> pl.DataFrame:
    """Filter GIAS data to a specific Local Authority."""
    la_col = "LA (code)" if "LA (code)" in df.columns else "LA(code)"
    return df.filter(pl.col(la_col) == la_code)


def extract_school_updates(df: pl.DataFrame) -> list[dict]:
    """Extract key fields from GIAS data as a list of dicts.

    Returns one dict per school with fields mapped to our database schema.
    """
    results = []
    for row in df.iter_rows(named=True):
        urn = row.get("URN", "")
        status = row.get("EstablishmentStatus (name)", "")
        if status not in ("Open", "Open, but proposed to close"):
            continue

        ofsted_rating = row.get("OfstedRating (name)", "")
        ofsted_date = row.get("OfstedLastInsp", "")

        results.append(
            {
                "urn": urn,
                "name": row.get("EstablishmentName", ""),
                "type_of_establishment": row.get("TypeOfEstablishment (name)", ""),
                "phase": row.get("PhaseOfEducation (name)", ""),
                "gender_policy": row.get("Gender (name)", ""),
                "faith": row.get("ReligiousCharacter (name)", ""),
                "age_range_from": _safe_int(row.get("StatutoryLowAge", "")),
                "age_range_to": _safe_int(row.get("StatutoryHighAge", "")),
                "postcode": row.get("Postcode", ""),
                "website": row.get("SchoolWebsite", ""),
                "ofsted_rating": ofsted_rating if ofsted_rating else None,
                "ofsted_date": ofsted_date if ofsted_date else None,
                "number_of_pupils": _safe_int(row.get("NumberOfPupils", "")),
                "status": status,
            }
        )

    return results


async def get_fresh_ofsted_data(la_code: str = _MK_LA_CODE) -> list[dict]:
    """Fetch latest Ofsted ratings for all schools in a council from GIAS.

    Returns a list of dicts with URN, name, ofsted_rating, and ofsted_date.
    This is the primary endpoint for keeping Ofsted data current.
    """
    df = await fetch_gias_csv()
    council_df = filter_council(df, la_code)
    schools = extract_school_updates(council_df)
    return [
        {
            "urn": s["urn"],
            "name": s["name"],
            "ofsted_rating": s["ofsted_rating"],
            "ofsted_date": s["ofsted_date"],
        }
        for s in schools
        if s["ofsted_rating"]
    ]


def _safe_int(val: str) -> int | None:
    """Convert a string to int, returning None for empty or invalid values."""
    if not val or not val.strip():
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None
