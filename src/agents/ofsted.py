"""Ofsted Specialist Agent.

Downloads publicly available Ofsted inspection data from gov.uk, processes it
with Polars, matches records to schools by URN, and updates the ofsted_rating
and ofsted_date fields in the schools table.

The agent fetches data from:
- Ofsted Management Information (monthly inspection outcomes)
- Ofsted Data View (detailed school inspection reports)

Usage
-----
::

    python -m src.agents.ofsted --council "Milton Keynes"

Examples
--------
To fetch and update Ofsted ratings for Milton Keynes schools::

    python -m src.agents.ofsted --council "Milton Keynes"

To force re-download even if cached::

    python -m src.agents.ofsted --council "Milton Keynes" --force-download
"""

from __future__ import annotations

import logging
import pathlib
from datetime import datetime

import polars as pl
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import School

logger = logging.getLogger(__name__)

# Public download URLs for Ofsted datasets
# Note: The actual CSV download URL may change. This is the landing page URL.
_OFSTED_MI_LANDING_URL = (
    "https://www.gov.uk/government/statistical-data-sets/"
    "monthly-management-information-ofsteds-school-inspections-outcomes"
)

# Direct download link to the latest Ofsted MI CSV (as of Feb 2026)
# This URL typically changes monthly - the agent should scrape the landing page
# to find the current download link
_OFSTED_MI_CSV_URL = (
    "https://assets.publishing.service.gov.uk/media/"
    "65f8b5e8d3d6e4001357e8a1/Management_information_-_schools_-_latest_month.csv"
)


class OfstedAgent(BaseAgent):
    """Collect Ofsted inspection ratings and dates for schools.

    The agent:

    1. Downloads the Ofsted management information CSV from gov.uk.
    2. Reads the CSV with Polars and filters to schools in the configured council.
    3. Matches rows to existing schools by URN.
    4. Updates the ofsted_rating and ofsted_date fields in the schools table.

    Parameters
    ----------
    council:
        Council name, e.g. ``"Milton Keynes"``.
    cache_dir:
        Directory for cached HTTP responses and downloaded CSVs.
    delay:
        Seconds to wait between HTTP requests.
    force_download:
        If True, re-download even if cached.
    """

    def __init__(
        self,
        council: str,
        cache_dir: str = "./data/cache",
        delay: float = 1.0,
        force_download: bool = False,
    ) -> None:
        super().__init__(council=council, cache_dir=cache_dir, delay=delay)
        self._csv_dir = self.cache_dir / "csv"
        self._csv_dir.mkdir(parents=True, exist_ok=True)
        self._force_download = force_download

    async def run(self) -> None:
        """Execute the Ofsted data-collection pipeline.

        Steps
        -----
        1. Load the URN-to-school_id mapping from the database.
        2. Download and process the Ofsted MI CSV.
        3. Update schools table with Ofsted ratings and dates.
        """
        self._logger.info("Starting Ofsted agent for council=%r", self.council)

        urn_map = self._load_urn_map()
        if not urn_map:
            self._logger.warning("No schools with URNs found in DB for council=%r", self.council)
            return

        self._logger.info("Loaded %d school URNs for council=%r", len(urn_map), self.council)

        # Download and process Ofsted CSV
        updates = await self._process_ofsted(urn_map)
        if updates:
            self._update_schools(updates)
            self._logger.info("Updated %d schools with Ofsted data", len(updates))
        else:
            self._logger.warning("No Ofsted updates to apply")

    # ------------------------------------------------------------------
    # Database reads
    # ------------------------------------------------------------------

    def _load_urn_map(self) -> dict[str, int]:
        """Load a mapping of URN -> school_id for the configured council.

        Returns
        -------
        dict[str, int]
            Keys are URN strings, values are the database primary key.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            stmt = select(School.id, School.urn).where(
                School.council == self.council,
                School.urn.is_not(None),
            )
            rows = session.execute(stmt).all()

        return {str(urn): school_id for school_id, urn in rows}

    # ------------------------------------------------------------------
    # Ofsted processing
    # ------------------------------------------------------------------

    async def _process_ofsted(self, urn_map: dict[str, int]) -> list[dict[str, object]]:
        """Download and parse the Ofsted management information CSV.

        Parameters
        ----------
        urn_map:
            Mapping of URN strings to database school IDs.

        Returns
        -------
        list[dict[str, object]]
            Update records with keys: school_id, ofsted_rating, ofsted_date.
        """
        csv_path = self._csv_dir / "ofsted_mi_latest.csv"

        # Check if we need to download
        if csv_path.exists() and not self._force_download:
            self._logger.info("Using cached Ofsted MI CSV: %s", csv_path)
        else:
            self._logger.info("Downloading Ofsted MI CSV from gov.uk...")
            try:
                # First, try the direct CSV URL
                content = await self.fetch_page(_OFSTED_MI_CSV_URL)
                csv_path.write_text(content, encoding="utf-8")
                self._logger.info("Downloaded and saved Ofsted MI CSV")
            except Exception as exc:
                self._logger.error("Failed to download Ofsted CSV: %s", exc)
                # In a production implementation, we would scrape the landing page
                # to find the current download link
                self._logger.info("Attempting to scrape landing page for download link...")
                try:
                    landing_html = await self.fetch_page(_OFSTED_MI_LANDING_URL)
                    csv_url = self._extract_csv_url_from_landing_page(landing_html)
                    if csv_url:
                        self._logger.info("Found CSV URL: %s", csv_url)
                        content = await self.fetch_page(csv_url)
                        csv_path.write_text(content, encoding="utf-8")
                        self._logger.info("Downloaded Ofsted CSV from landing page link")
                    else:
                        self._logger.error("Could not find CSV download link in landing page")
                        return []
                except Exception as landing_exc:
                    self._logger.error("Failed to fetch landing page: %s", landing_exc)
                    return []

        if not csv_path.exists():
            self._logger.error("No Ofsted CSV available")
            return []

        return self._parse_ofsted_csv(csv_path, urn_map)

    def _parse_ofsted_csv(
        self,
        csv_path: pathlib.Path,
        urn_map: dict[str, int],
    ) -> list[dict[str, object]]:
        """Read the Ofsted CSV with Polars and extract rating updates.

        The Ofsted MI CSV typically contains columns like:
        - URN
        - School name
        - Local authority
        - Overall effectiveness (rating)
        - Inspection date
        - Inspection type

        Parameters
        ----------
        csv_path:
            Path to the downloaded CSV file.
        urn_map:
            Mapping of URN strings to database school IDs.

        Returns
        -------
        list[dict[str, object]]
            Dicts with keys: school_id, ofsted_rating, ofsted_date.
        """
        self._logger.info("Parsing Ofsted CSV from %s", csv_path)

        try:
            # Read the CSV with Polars
            df = pl.read_csv(
                csv_path,
                ignore_errors=True,
                truncate_ragged_lines=True,
                infer_schema_length=10000,
            )
            self._logger.info("Ofsted CSV shape: %s, columns: %s", df.shape, df.columns)

            # Identify the relevant columns (column names may vary)
            # Common column names in Ofsted MI CSV:
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
                    "Inspection date",
                    "InspectionDate",
                    "Inspection Date",
                    "Publication date",
                    "Inspection end date",
                ],
            )
            la_col = self._find_column(
                df,
                [
                    "Local authority",
                    "LocalAuthority",
                    "Local Authority",
                    "LA",
                ],
            )

            if not urn_col:
                self._logger.error("Could not find URN column in Ofsted CSV")
                return []

            # Filter to our council and known URNs
            df_filtered = df.filter(pl.col(urn_col).cast(str).is_in(list(urn_map.keys())))

            if la_col:
                # Further filter by local authority if column exists
                council_lower = self.council.lower()
                df_filtered = df_filtered.filter(pl.col(la_col).str.to_lowercase().str.contains(council_lower))

            self._logger.info(
                "Found %d schools matching council '%s' in Ofsted CSV",
                len(df_filtered),
                self.council,
            )

            # Extract updates
            updates = []
            for row in df_filtered.iter_rows(named=True):
                urn_str = str(row[urn_col]).strip()
                school_id = urn_map.get(urn_str)

                if school_id is None:
                    continue

                # Extract rating
                rating = None
                if rating_col and row.get(rating_col):
                    rating_raw = str(row[rating_col]).strip()
                    # Normalize rating names
                    rating = self._normalize_rating(rating_raw)

                # Extract date
                ofsted_date = None
                if date_col and row.get(date_col):
                    date_str = str(row[date_col]).strip()
                    ofsted_date = self._parse_date(date_str)

                if rating or ofsted_date:
                    updates.append(
                        {
                            "school_id": school_id,
                            "ofsted_rating": rating,
                            "ofsted_date": ofsted_date,
                        }
                    )

            self._logger.info("Extracted %d Ofsted updates", len(updates))
            return updates

        except Exception:
            self._logger.exception("Failed to parse Ofsted CSV at %s", csv_path)
            return []

    def _find_column(self, df: pl.DataFrame, candidates: list[str]) -> str | None:
        """Find the first matching column name from a list of candidates.

        Parameters
        ----------
        df:
            The DataFrame to search.
        candidates:
            List of possible column names to look for.

        Returns
        -------
        str | None
            The first matching column name, or None if no match found.
        """
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        return None

    def _normalize_rating(self, rating_raw: str) -> str | None:
        """Normalize Ofsted rating to standard values.

        Parameters
        ----------
        rating_raw:
            Raw rating string from CSV.

        Returns
        -------
        str | None
            Normalized rating or None if invalid.
        """
        rating_lower = rating_raw.lower().strip()

        # Map variations to standard ratings
        if "outstanding" in rating_lower or rating_lower == "1":
            return "Outstanding"
        elif "good" in rating_lower or rating_lower == "2":
            return "Good"
        elif "requires improvement" in rating_lower or "improvement" in rating_lower or rating_lower == "3":
            return "Requires Improvement"
        elif "inadequate" in rating_lower or "serious weaknesses" in rating_lower or rating_lower == "4":
            return "Inadequate"

        return None

    def _parse_date(self, date_str: str) -> str | None:
        """Parse a date string into ISO format YYYY-MM-DD.

        Parameters
        ----------
        date_str:
            Date string to parse.

        Returns
        -------
        str | None
            ISO formatted date string or None if parsing fails.
        """
        # Try common date formats
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

        self._logger.warning("Could not parse date: %r", date_str)
        return None

    def _extract_csv_url_from_landing_page(self, html: str) -> str | None:
        """Extract the CSV download URL from the Ofsted MI landing page.

        Parameters
        ----------
        html:
            HTML content of the landing page.

        Returns
        -------
        str | None:
            The CSV download URL, or None if not found.
        """
        soup = self.parse_html(html)

        # Look for links containing "Management_information" and ending in .csv
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "Management_information" in href and href.endswith(".csv"):
                # Handle relative URLs
                if href.startswith("http"):
                    return href
                elif href.startswith("/"):
                    return f"https://assets.publishing.service.gov.uk{href}"
                else:
                    return f"https://assets.publishing.service.gov.uk/{href}"

        # Fallback: look for any CSV link with "school" or "inspection" in the URL
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.endswith(".csv") and ("school" in href.lower() or "inspection" in href.lower()):
                if href.startswith("http"):
                    return href
                elif href.startswith("/"):
                    return f"https://assets.publishing.service.gov.uk{href}"

        return None

    # ------------------------------------------------------------------
    # Database updates
    # ------------------------------------------------------------------

    def _update_schools(self, updates: list[dict[str, object]]) -> None:
        """Update schools table with Ofsted ratings and dates.

        Parameters
        ----------
        updates:
            Update dicts with keys: school_id, ofsted_rating, ofsted_date.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            for update_data in updates:
                school_id = update_data["school_id"]
                rating = update_data.get("ofsted_rating")
                ofsted_date = update_data.get("ofsted_date")

                # Build update statement
                stmt = update(School).where(School.id == school_id)
                values = {}

                if rating:
                    values["ofsted_rating"] = rating
                if ofsted_date:
                    values["ofsted_date"] = ofsted_date

                if values:
                    session.execute(stmt.values(**values))

            session.commit()
            self._logger.info("Committed %d Ofsted updates", len(updates))


if __name__ == "__main__":
    from src.agents.base_agent import run_agent_cli

    run_agent_cli(
        OfstedAgent,
        "Download Ofsted inspection data and update school ratings.",
        extra_args_fn=lambda p: (
            p.add_argument("--force-download", action="store_true", help="Force re-download even if cached."),
        ),
    )
