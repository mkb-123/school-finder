"""Ofsted inspection data service.

Downloads the monthly Management Information CSV from GOV.UK, parses it with
Polars, and updates school records with real Ofsted ratings and inspection dates.

Consolidates the previous two parallel implementations (src/agents/ofsted.py
and src/data/import_ofsted_data.py) into a single service.

Data source: https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import httpx
import polars as pl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import School
from src.services.gov_data.base import BaseGovDataService

logger = logging.getLogger(__name__)

# Ofsted numeric codes to human-readable ratings
OFSTED_RATINGS = {
    "1": "Outstanding",
    "2": "Good",
    "3": "Requires Improvement",
    "4": "Inadequate",
}


class OfstedService(BaseGovDataService):
    """Fetch and import Ofsted inspection ratings from the official monthly CSV.

    Usage::

        service = OfstedService()
        stats = service.refresh(council="Milton Keynes")
    """

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        cache_ttl_hours: int | None = None,
    ) -> None:
        settings = get_settings()
        super().__init__(
            cache_dir=cache_dir or Path("./data/cache/ofsted"),
            cache_ttl_hours=cache_ttl_hours or settings.OFSTED_CACHE_TTL_HOURS,
        )
        self._landing_url = settings.OFSTED_MI_LANDING_URL

    def download_csv(self, force: bool = False) -> Path:
        """Download the latest Ofsted management information CSV.

        First tries to scrape the landing page for the current download link.
        Falls back to a known recent URL pattern if scraping fails.

        Returns
        -------
        Path
            Path to the downloaded CSV file.
        """
        filename = "ofsted_mi_latest.csv"
        cache_path = self.cache_dir / filename

        if not force and self._is_cache_fresh(cache_path):
            self._logger.info("Using cached Ofsted CSV: %s", cache_path)
            return cache_path

        # Try to find the current CSV URL from the landing page
        csv_url = self._find_csv_url_from_landing_page()

        if csv_url:
            self._logger.info("Found Ofsted CSV URL: %s", csv_url)
            return self.download(csv_url, filename=filename, force=True)

        # Fallback: try common URL patterns
        self._logger.warning("Could not find CSV URL from landing page, trying known patterns")
        fallback_urls = self._build_fallback_urls()
        return self.download_with_fallback(fallback_urls, filename=filename, force=True)

    def _find_csv_url_from_landing_page(self) -> str | None:
        """Scrape the Ofsted MI landing page for the CSV download link."""
        try:
            with httpx.Client(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "SchoolFinder/1.0"},
            ) as client:
                response = client.get(self._landing_url)
                response.raise_for_status()

            html = response.text

            # Look for CSV links in the page
            # Pattern: links to assets.publishing.service.gov.uk containing
            # "Management_information" and ending in .csv
            csv_pattern = re.compile(
                r'href="(https?://assets\.publishing\.service\.gov\.uk/[^"]*'
                r'Management_information[^"]*\.csv)"',
                re.IGNORECASE,
            )
            matches = csv_pattern.findall(html)
            if matches:
                return matches[0]

            # Broader pattern: any CSV link with "school" or "inspection"
            broad_pattern = re.compile(
                r'href="(https?://assets\.publishing\.service\.gov\.uk/[^"]*\.csv)"',
                re.IGNORECASE,
            )
            matches = broad_pattern.findall(html)
            for url in matches:
                if "school" in url.lower() or "inspection" in url.lower():
                    return url

        except Exception as exc:
            self._logger.warning("Failed to scrape Ofsted landing page: %s", exc)

        return None

    def _build_fallback_urls(self) -> list[str]:
        """Build fallback Ofsted CSV URLs based on known patterns."""
        # The URL pattern includes an asset ID that changes. We try a known
        # recent one as a last resort.
        return [
            "https://assets.publishing.service.gov.uk/media/"
            "696611308d599f4c09e1ffa9/"
            "Management_information_-_state-funded_schools_-_latest_inspections_as_at_31_Dec_2025.csv",
        ]

    def refresh(
        self,
        council: str | None = None,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, int]:
        """Download Ofsted CSV and update school ratings.

        Parameters
        ----------
        council:
            Optional council name to filter. If None, updates all matched schools.
        force_download:
            If True, bypass cache.
        db_path:
            Override database path.

        Returns
        -------
        dict
            Statistics: {updated, skipped, not_found}.
        """
        settings = get_settings()
        db = db_path or settings.SQLITE_PATH

        csv_path = self.download_csv(force=force_download)
        updates = self._parse_csv(csv_path, council)
        stats = self._apply_updates(db, updates)

        self._logger.info(
            "Ofsted refresh complete: %d updated, %d skipped, %d not found",
            stats["updated"],
            stats["skipped"],
            stats["not_found"],
        )
        return stats

    def _parse_csv(
        self,
        csv_path: Path,
        council: str | None = None,
    ) -> list[dict[str, str | None]]:
        """Parse the Ofsted MI CSV and extract rating updates.

        Returns a list of dicts with keys: urn, rating, date.
        """
        self._logger.info("Parsing Ofsted CSV: %s", csv_path)

        df = pl.read_csv(
            csv_path,
            encoding="utf8-lossy",
            ignore_errors=True,
            truncate_ragged_lines=True,
            infer_schema_length=10000,
        )
        self._logger.info("Ofsted CSV: %d rows, %d columns", df.height, df.width)

        # Find relevant columns (names vary between releases)
        urn_col = self._find_column(df, ["URN", "urn", "Urn"])
        rating_col = self._find_column(
            df,
            [
                "Overall effectiveness",
                "OverallEffectiveness",
                "Overall Effectiveness",
                "Rating",
            ],
        )
        date_col = self._find_column(
            df,
            [
                "Publication date",
                "Inspection date",
                "InspectionDate",
                "Inspection end date",
            ],
        )
        la_col = self._find_column(
            df,
            ["Local authority", "LocalAuthority", "Local Authority", "LA"],
        )

        if not urn_col:
            self._logger.error("Could not find URN column in Ofsted CSV. Columns: %s", df.columns)
            return []

        # Filter by council if specified
        if council and la_col:
            council_lower = council.lower()
            df = df.filter(pl.col(la_col).str.to_lowercase().str.contains(council_lower))
            self._logger.info("Filtered to '%s': %d rows", council, df.height)

        updates = []
        for row in df.iter_rows(named=True):
            urn = str(row.get(urn_col, "")).strip()
            if not urn:
                continue

            rating = None
            if rating_col and row.get(rating_col):
                rating_raw = str(row[rating_col]).strip()
                rating = self._normalize_rating(rating_raw)

            ofsted_date = None
            if date_col and row.get(date_col):
                date_str = str(row[date_col]).strip()
                ofsted_date = self._parse_date(date_str)

            if rating or ofsted_date:
                updates.append({"urn": urn, "rating": rating, "date": ofsted_date})

        self._logger.info("Extracted %d Ofsted updates from CSV", len(updates))
        return updates

    def _apply_updates(self, db_path: str, updates: list[dict[str, str | None]]) -> dict[str, int]:
        """Apply Ofsted updates to the database by matching on URN."""
        engine = create_engine(f"sqlite:///{db_path}")
        stats = {"updated": 0, "skipped": 0, "not_found": 0}

        with Session(engine) as session:
            # Build URN -> school_id lookup
            urn_map: dict[str, int] = {}
            for school_id, urn in session.query(School.id, School.urn).filter(School.urn.is_not(None)):
                urn_map[str(urn)] = school_id

            for update in updates:
                urn = update["urn"]
                school_id = urn_map.get(urn)

                if school_id is None:
                    stats["not_found"] += 1
                    continue

                rating = update.get("rating")
                ofsted_date = update.get("date")

                if not rating:
                    stats["skipped"] += 1
                    continue

                school = session.get(School, school_id)
                if school:
                    school.ofsted_rating = rating
                    if ofsted_date:
                        school.ofsted_date = ofsted_date
                    stats["updated"] += 1

            session.commit()

        return stats

    @staticmethod
    def _find_column(df: pl.DataFrame, candidates: list[str]) -> str | None:
        """Find the first matching column name from candidates."""
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        return None

    @staticmethod
    def _normalize_rating(rating_raw: str) -> str | None:
        """Normalize Ofsted rating to standard values."""
        rating_lower = rating_raw.lower().strip()

        # Check numeric codes first
        if rating_lower in OFSTED_RATINGS:
            return OFSTED_RATINGS[rating_lower]

        if "outstanding" in rating_lower:
            return "Outstanding"
        if "good" in rating_lower:
            return "Good"
        if "requires improvement" in rating_lower or "improvement" in rating_lower:
            return "Requires Improvement"
        if "inadequate" in rating_lower or "serious weaknesses" in rating_lower:
            return "Inadequate"

        return None

    @staticmethod
    def _parse_date(date_str: str) -> str | None:
        """Parse a date string into ISO format YYYY-MM-DD."""
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d %B %Y",
            "%d %b %Y",
            "%Y/%m/%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None
