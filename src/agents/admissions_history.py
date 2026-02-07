"""Admissions History Scraper Agent.

For each school belonging to the configured council, this agent visits the
school's website, searches for pages containing historical admissions data,
and extracts metrics such as:

- Last distance offered (in miles or km)
- Number of applications received vs places offered (PAN)
- Waiting list movement (how many came off the waiting list)
- Appeals heard and upheld
- Whether the school had vacancies

Results are stored in the ``admissions_history`` table via SQLAlchemy.

Usage
-----
::

    python -m src.agents.admissions_history --council "Milton Keynes"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import AdmissionsHistory, School

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MILES_TO_KM = 1.60934

# Keywords for discovering admissions data pages from school homepages.
_ADMISSIONS_DATA_LINK_KEYWORDS: list[str] = [
    "admission",
    "admissions",
    "allocation",
    "oversubscription",
    "last distance",
    "how places are allocated",
    "published admission number",
    "intake",
    "places offered",
    "apply",
    "application data",
    "admissions data",
    "admissions information",
]

_ADMISSIONS_DATA_LINK_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _ADMISSIONS_DATA_LINK_KEYWORDS),
    flags=re.IGNORECASE,
)

# Patterns for sub-page links within an admissions page that may contain data.
_DATA_SUBPAGE_KEYWORDS: list[str] = [
    "data",
    "statistics",
    "historical",
    "previous year",
    "allocation",
    "last distance",
    "appeals",
    "waiting list",
    "numbers",
    "places",
    "pan",
    "published admission",
]

_DATA_SUBPAGE_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _DATA_SUBPAGE_KEYWORDS),
    flags=re.IGNORECASE,
)

# Academic year patterns (e.g. "2024/2025", "2024-2025", "2024/25", "2024-25")
_ACADEMIC_YEAR_PATTERN = re.compile(
    r"(20[12]\d)\s*[/\-]\s*(20[12]\d|[12]\d)",
)

# Distance patterns: "0.87 miles", "1.2km", "1.34 kilometres", "2.567 miles"
_DISTANCE_MILES_PATTERN = re.compile(
    r"(\d+\.?\d*)\s*(?:miles?|mi)\b",
    re.IGNORECASE,
)
_DISTANCE_KM_PATTERN = re.compile(
    r"(\d+\.?\d*)\s*(?:km|kilometres?|kilometers?)\b",
    re.IGNORECASE,
)

# Number of applications / places patterns
_APPLICATIONS_PATTERN = re.compile(
    r"(\d+)\s*(?:applications?|applicants?|preferences?|requests?)\s*(?:received|made)?",
    re.IGNORECASE,
)
_PLACES_PATTERN = re.compile(
    r"(?:PAN|published\s+admission\s+number|places?\s+(?:available|offered)|intake|capacity)\s*(?:of|:|\s)\s*(\d+)",
    re.IGNORECASE,
)
_PLACES_PATTERN_ALT = re.compile(
    r"(\d+)\s*(?:places?\s+(?:were\s+)?offered|places?\s+available)",
    re.IGNORECASE,
)

# Waiting list patterns
_WAITING_LIST_PATTERN = re.compile(
    r"(\d+)\s*(?:children|pupils|applicants?|places?)?\s*(?:were\s+)?(?:offered\s+(?:a\s+)?)?(?:places?\s+)?(?:from|off|via)\s+(?:the\s+)?waiting\s+list",
    re.IGNORECASE,
)
_WAITING_LIST_PATTERN_ALT = re.compile(
    r"waiting\s+list\s*(?:offers?|places?|movement)?\s*:?\s*(\d+)",
    re.IGNORECASE,
)

# Appeals patterns
_APPEALS_HEARD_PATTERN = re.compile(
    r"(\d+)\s*appeals?\s*(?:were\s+)?(?:heard|lodged|submitted|received|made)",
    re.IGNORECASE,
)
_APPEALS_HEARD_PATTERN_ALT = re.compile(
    r"appeals?\s*(?:heard|lodged|submitted|received|made)\s*:?\s*(\d+)",
    re.IGNORECASE,
)
_APPEALS_UPHELD_PATTERN = re.compile(
    r"(\d+)\s*(?:appeals?\s*)?(?:were\s+)?(?:upheld|successful|granted|won|allowed)",
    re.IGNORECASE,
)
_APPEALS_UPHELD_PATTERN_ALT = re.compile(
    r"(?:upheld|successful|granted|won|allowed)\s*:?\s*(\d+)",
    re.IGNORECASE,
)

# Year group / intake year patterns
_INTAKE_YEAR_PATTERN = re.compile(
    r"(Year\s*(?:R|Reception|\d{1,2})|Reception|Nursery|Sixth\s+Form|Year\s+7)",
    re.IGNORECASE,
)


class AdmissionsHistoryAgent(BaseAgent):
    """Scrape historical admissions data for schools in a council.

    The agent:

    1. Queries the database for all schools belonging to the council.
    2. For each school that has a website URL, fetches the homepage and
       searches for links to admissions data pages.
    3. If data pages are found, fetches and parses them for historical
       admissions metrics (last distance, applications, places, appeals, etc.).
    4. Persists results in the ``admissions_history`` table, merging with
       existing data where possible.

    Parameters
    ----------
    council:
        Council name, e.g. ``"Milton Keynes"``.
    cache_dir:
        Directory for cached HTTP responses.
    delay:
        Seconds to wait between HTTP requests.
    max_depth:
        Maximum link-following depth from the homepage (default 2).
    """

    def __init__(
        self,
        council: str,
        cache_dir: str = "./data/cache",
        delay: float = 1.0,
        max_depth: int = 2,
    ) -> None:
        super().__init__(council=council, cache_dir=cache_dir, delay=delay)
        self.max_depth = max_depth

    async def run(self) -> None:
        """Execute the admissions history data-collection pipeline."""
        self._logger.info("Starting admissions history agent for council=%r", self.council)

        schools = self._load_schools()
        if not schools:
            self._logger.warning("No schools found in DB for council=%r", self.council)
            return

        self._logger.info("Found %d schools for council=%r", len(schools), self.council)

        total_records = 0
        for school_id, school_name, school_website in schools:
            if not school_website:
                self._logger.debug("School %r (id=%d) has no website – skipping", school_name, school_id)
                continue

            self._logger.info("Processing school %r (id=%d)", school_name, school_id)
            records = await self._discover_admissions_data(school_id, school_name, school_website)

            if records:
                saved = self._save_to_db(school_id, records)
                self._logger.info("Saved %d history records for school %r", saved, school_name)
                total_records += saved
            else:
                self._logger.debug("No admissions history found for school %r", school_name)

        self._logger.info(
            "Admissions history agent complete: %d new records across %d schools",
            total_records,
            len(schools),
        )

    # ------------------------------------------------------------------
    # Database reads
    # ------------------------------------------------------------------

    def _load_schools(self) -> list[tuple[int, str, str | None]]:
        """Load schools for the configured council from the database.

        Returns a list of ``(school_id, school_name, website_url)`` tuples.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            stmt = select(School.id, School.name, School.website).where(School.council == self.council)
            rows = session.execute(stmt).all()

        return [(row[0], row[1], row[2]) for row in rows]

    def _load_existing_records(self, school_id: int) -> set[str]:
        """Load existing academic_year values for a school.

        Returns a set of academic year strings that already have data.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            stmt = select(AdmissionsHistory.academic_year).where(AdmissionsHistory.school_id == school_id)
            rows = session.execute(stmt).all()

        return {row[0] for row in rows}

    # ------------------------------------------------------------------
    # Discovery and page crawling
    # ------------------------------------------------------------------

    async def _discover_admissions_data(
        self,
        school_id: int,
        school_name: str,
        website_url: str,
    ) -> list[dict[str, object]]:
        """Fetch school website and discover admissions history data.

        Follows a multi-level strategy:
        1. Fetch homepage, find admissions-related links.
        2. Fetch admissions pages, look for data subpage links.
        3. Parse all found pages for historical admissions data.
        """
        try:
            homepage_html = await self.fetch_page(website_url)
        except Exception:
            self._logger.exception("Failed to fetch homepage for school %r", school_name)
            return []

        homepage_soup = self.parse_html(homepage_html)
        base_url = website_url if website_url.startswith(("http://", "https://")) else f"https://{website_url}"

        all_records: list[dict[str, object]] = []

        # Strategy 1: Parse the homepage itself for any admissions data.
        records = self._parse_admissions_data(school_id, homepage_soup, base_url)
        all_records.extend(records)

        # Strategy 2: Find admissions-related links and fetch those pages.
        admissions_urls = self._find_admissions_links(homepage_soup, base_url)
        visited = {base_url}

        for url in admissions_urls[:5]:  # Limit to avoid over-crawling
            if url in visited:
                continue
            visited.add(url)

            try:
                page_html = await self.fetch_page(url)
            except Exception:
                self._logger.debug("Failed to fetch %s for school %r", url, school_name)
                continue

            page_soup = self.parse_html(page_html)
            records = self._parse_admissions_data(school_id, page_soup, url)
            all_records.extend(records)

            # Strategy 3: Look for data subpages within admissions pages.
            if self.max_depth >= 2:
                subpage_urls = self._find_data_subpage_links(page_soup, url)
                for sub_url in subpage_urls[:3]:
                    if sub_url in visited:
                        continue
                    visited.add(sub_url)

                    try:
                        sub_html = await self.fetch_page(sub_url)
                    except Exception:
                        self._logger.debug("Failed to fetch subpage %s", sub_url)
                        continue

                    sub_soup = self.parse_html(sub_html)
                    records = self._parse_admissions_data(school_id, sub_soup, sub_url)
                    all_records.extend(records)

        # Deduplicate by academic_year, keeping the record with the most populated fields.
        return self._deduplicate_records(all_records)

    def _find_admissions_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Find all admissions-related links on a page.

        Returns a list of absolute URLs, sorted by relevance (links with
        more specific admissions keywords ranked higher).
        """
        scored_links: list[tuple[int, str]] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            link_text = anchor.get_text(separator=" ", strip=True).lower()
            href_lower = href.lower()

            # Skip non-content links
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue

            # Score the link by keyword match quality
            score = 0
            combined = f"{link_text} {href_lower}"

            if _ADMISSIONS_DATA_LINK_PATTERN.search(combined):
                score += 1
                # Boost for more specific terms
                if "data" in combined or "statistic" in combined:
                    score += 3
                if "last distance" in combined or "allocation" in combined:
                    score += 4
                if "appeal" in combined:
                    score += 2
                if "waiting list" in combined:
                    score += 2
                if "historical" in combined or "previous" in combined:
                    score += 2
                if "admission" in combined:
                    score += 1

            if score > 0:
                absolute_url = urljoin(base_url, href)
                # Skip PDF links (can't parse easily)
                if absolute_url.lower().endswith(".pdf"):
                    self._logger.debug("Skipping PDF link: %s", absolute_url)
                    continue
                scored_links.append((score, absolute_url))

        # Sort by score descending, deduplicate
        scored_links.sort(key=lambda x: x[0], reverse=True)
        seen: set[str] = set()
        result: list[str] = []
        for _score, url in scored_links:
            if url not in seen:
                seen.add(url)
                result.append(url)

        return result

    def _find_data_subpage_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Find data subpage links within an admissions page."""
        links: list[str] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            link_text = anchor.get_text(separator=" ", strip=True).lower()
            href_lower = href.lower()

            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue

            combined = f"{link_text} {href_lower}"
            if _DATA_SUBPAGE_PATTERN.search(combined):
                absolute_url = urljoin(base_url, href)
                if not absolute_url.lower().endswith(".pdf"):
                    links.append(absolute_url)

        return links

    # ------------------------------------------------------------------
    # Data parsing
    # ------------------------------------------------------------------

    def _parse_admissions_data(
        self,
        school_id: int,
        soup: BeautifulSoup,
        source_url: str,
    ) -> list[dict[str, object]]:
        """Extract admissions history data from a parsed HTML page.

        Tries multiple strategies:
        1. Table-based extraction (most structured data is in tables)
        2. Section-based extraction (headings + paragraphs per year)
        3. Inline text extraction (data scattered in page text)
        """
        records: list[dict[str, object]] = []

        # Strategy 1: Parse tables
        table_records = self._parse_from_tables(school_id, soup, source_url)
        records.extend(table_records)

        # Strategy 2: Parse sections with year headings
        if not records:
            section_records = self._parse_from_year_sections(school_id, soup, source_url)
            records.extend(section_records)

        # Strategy 3: Parse inline text (whole-page scan)
        if not records:
            inline_records = self._parse_from_inline_text(school_id, soup, source_url)
            records.extend(inline_records)

        return records

    def _parse_from_tables(
        self,
        school_id: int,
        soup: BeautifulSoup,
        source_url: str,
    ) -> list[dict[str, object]]:
        """Extract admissions data from HTML tables.

        Many schools present admissions history as a table with columns like:
        Year | PAN | Applications | Last Distance | Waiting List | Appeals
        """
        records: list[dict[str, object]] = []

        for table in soup.find_all("table"):
            table_records = self._parse_single_table(school_id, table, source_url)
            records.extend(table_records)

        return records

    def _parse_single_table(
        self,
        school_id: int,
        table: Tag,
        source_url: str,
    ) -> list[dict[str, object]]:
        """Parse a single HTML table for admissions data."""
        rows = table.find_all("tr")
        if len(rows) < 2:  # Need at least header + 1 data row
            return []

        # Try to identify column meanings from the header row.
        header_row = rows[0]
        headers = [th.get_text(separator=" ", strip=True).lower() for th in header_row.find_all(["th", "td"])]

        if not headers:
            return []

        # Map column indices to data fields.
        col_map = self._identify_columns(headers)

        # If we can't identify at least a year column and one data column, skip.
        if "year" not in col_map and not any(_ACADEMIC_YEAR_PATTERN.search(h) for h in headers):
            # Maybe the headers themselves are years (transposed table).
            return self._parse_transposed_table(school_id, table, headers, source_url)

        if not col_map:
            return []

        records: list[dict[str, object]] = []
        for row in rows[1:]:
            cells = [td.get_text(separator=" ", strip=True) for td in row.find_all(["td", "th"])]
            if not cells or len(cells) <= 1:
                continue

            record = self._extract_record_from_row(school_id, cells, col_map, source_url)
            if record and record.get("academic_year"):
                records.append(record)

        if records:
            self._logger.info(
                "Extracted %d records from table for school_id=%d",
                len(records),
                school_id,
            )

        return records

    def _identify_columns(self, headers: list[str]) -> dict[str, int]:
        """Map header names to column indices and data field names."""
        col_map: dict[str, int] = {}

        for i, header in enumerate(headers):
            h = header.lower().strip()

            # Year column
            if any(kw in h for kw in ["year", "academic", "intake"]):
                if "year" not in col_map:
                    col_map["year"] = i

            # PAN / places
            if any(kw in h for kw in ["pan", "admission number", "places", "capacity", "offered"]):
                if "places" not in col_map:
                    col_map["places"] = i

            # Applications
            if any(kw in h for kw in ["application", "applicant", "preference", "request"]):
                if "applications" not in col_map:
                    col_map["applications"] = i

            # Last distance
            if any(kw in h for kw in ["distance", "last", "furthest", "cutoff", "cut-off"]):
                if "distance" not in col_map:
                    col_map["distance"] = i

            # Waiting list
            if any(kw in h for kw in ["waiting", "wait"]):
                if "waiting_list" not in col_map:
                    col_map["waiting_list"] = i

            # Appeals heard
            if "appeal" in h and any(kw in h for kw in ["heard", "lodged", "submitted", "received", "total"]):
                if "appeals_heard" not in col_map:
                    col_map["appeals_heard"] = i
            elif "appeal" in h and any(kw in h for kw in ["upheld", "success", "granted", "won"]):
                if "appeals_upheld" not in col_map:
                    col_map["appeals_upheld"] = i
            elif "appeal" in h and "appeals_heard" not in col_map:
                col_map["appeals_heard"] = i

        return col_map

    def _parse_transposed_table(
        self,
        school_id: int,
        table: Tag,
        headers: list[str],
        source_url: str,
    ) -> list[dict[str, object]]:
        """Handle transposed tables where years are column headers.

        Some schools present data like:
            Metric     | 2022/23 | 2023/24 | 2024/25
            PAN        | 60      | 60      | 60
            Distance   | 1.2mi   | 1.1mi   | 0.9mi
        """
        year_cols: dict[int, str] = {}
        for i, header in enumerate(headers):
            year_match = _ACADEMIC_YEAR_PATTERN.search(header)
            if year_match:
                year_cols[i] = self._normalise_academic_year(year_match.group(0))

        if not year_cols:
            return []

        # Build records by reading row labels and cell values.
        rows = table.find_all("tr")
        year_data: dict[str, dict[str, object]] = {yr: {} for yr in year_cols.values()}

        for row in rows[1:]:  # Skip header row
            cells = [td.get_text(separator=" ", strip=True) for td in row.find_all(["td", "th"])]
            if not cells:
                continue

            row_label = cells[0].lower() if cells else ""

            for col_idx, year in year_cols.items():
                if col_idx >= len(cells):
                    continue

                cell_text = cells[col_idx].strip()
                if not cell_text or cell_text == "-" or cell_text.lower() == "n/a":
                    continue

                if any(kw in row_label for kw in ["pan", "places", "capacity", "admission number", "offered"]):
                    num = self._extract_integer(cell_text)
                    if num is not None:
                        year_data[year]["places_offered"] = num

                elif any(kw in row_label for kw in ["application", "applicant", "preference"]):
                    num = self._extract_integer(cell_text)
                    if num is not None:
                        year_data[year]["applications_received"] = num

                elif any(kw in row_label for kw in ["distance", "furthest", "last", "cutoff"]):
                    dist = self._extract_distance_km(cell_text)
                    if dist is not None:
                        year_data[year]["last_distance_offered_km"] = dist

                elif any(kw in row_label for kw in ["waiting", "wait"]):
                    num = self._extract_integer(cell_text)
                    if num is not None:
                        year_data[year]["waiting_list_offers"] = num

                elif "appeal" in row_label and any(kw in row_label for kw in ["heard", "lodged", "total", "received"]):
                    num = self._extract_integer(cell_text)
                    if num is not None:
                        year_data[year]["appeals_heard"] = num

                elif "appeal" in row_label and any(kw in row_label for kw in ["upheld", "success", "won"]):
                    num = self._extract_integer(cell_text)
                    if num is not None:
                        year_data[year]["appeals_upheld"] = num

        records: list[dict[str, object]] = []
        for year, data in year_data.items():
            if data:  # Only add years that have at least some data
                record: dict[str, object] = {
                    "school_id": school_id,
                    "academic_year": year,
                    "places_offered": data.get("places_offered"),
                    "applications_received": data.get("applications_received"),
                    "last_distance_offered_km": data.get("last_distance_offered_km"),
                    "waiting_list_offers": data.get("waiting_list_offers"),
                    "appeals_heard": data.get("appeals_heard"),
                    "appeals_upheld": data.get("appeals_upheld"),
                    "source_url": source_url,
                }
                records.append(record)

        if records:
            self._logger.info(
                "Extracted %d records from transposed table for school_id=%d",
                len(records),
                school_id,
            )

        return records

    def _extract_record_from_row(
        self,
        school_id: int,
        cells: list[str],
        col_map: dict[str, int],
        source_url: str,
    ) -> dict[str, object] | None:
        """Extract an admissions record from a single table row."""
        record: dict[str, object] = {
            "school_id": school_id,
            "source_url": source_url,
        }

        # Extract academic year
        year_idx = col_map.get("year")
        if year_idx is not None and year_idx < len(cells):
            year_text = cells[year_idx]
            year_match = _ACADEMIC_YEAR_PATTERN.search(year_text)
            if year_match:
                record["academic_year"] = self._normalise_academic_year(year_match.group(0))
            else:
                # Try plain 4-digit year
                plain_year = re.search(r"(20[12]\d)", year_text)
                if plain_year:
                    yr = int(plain_year.group(1))
                    record["academic_year"] = f"{yr}/{yr + 1}"
                else:
                    return None
        else:
            return None

        # Extract places offered
        places_idx = col_map.get("places")
        if places_idx is not None and places_idx < len(cells):
            record["places_offered"] = self._extract_integer(cells[places_idx])

        # Extract applications received
        apps_idx = col_map.get("applications")
        if apps_idx is not None and apps_idx < len(cells):
            record["applications_received"] = self._extract_integer(cells[apps_idx])

        # Extract last distance
        dist_idx = col_map.get("distance")
        if dist_idx is not None and dist_idx < len(cells):
            record["last_distance_offered_km"] = self._extract_distance_km(cells[dist_idx])

        # Extract waiting list offers
        wl_idx = col_map.get("waiting_list")
        if wl_idx is not None and wl_idx < len(cells):
            record["waiting_list_offers"] = self._extract_integer(cells[wl_idx])

        # Extract appeals heard
        ah_idx = col_map.get("appeals_heard")
        if ah_idx is not None and ah_idx < len(cells):
            record["appeals_heard"] = self._extract_integer(cells[ah_idx])

        # Extract appeals upheld
        au_idx = col_map.get("appeals_upheld")
        if au_idx is not None and au_idx < len(cells):
            record["appeals_upheld"] = self._extract_integer(cells[au_idx])

        # Only return if we have at least one data field beyond the year
        data_fields = [
            "places_offered",
            "applications_received",
            "last_distance_offered_km",
            "waiting_list_offers",
            "appeals_heard",
            "appeals_upheld",
        ]
        if any(record.get(f) is not None for f in data_fields):
            return record

        return None

    def _parse_from_year_sections(
        self,
        school_id: int,
        soup: BeautifulSoup,
        source_url: str,
    ) -> list[dict[str, object]]:
        """Parse admissions data from sections with year-based headings.

        Many school websites organise admissions data under headings like:
        ## 2024/2025 Intake
        PAN: 60, Applications: 120, Last distance offered: 1.2 miles
        """
        records: list[dict[str, object]] = []

        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
            heading_text = heading.get_text(separator=" ", strip=True)
            year_match = _ACADEMIC_YEAR_PATTERN.search(heading_text)

            if not year_match:
                continue

            academic_year = self._normalise_academic_year(year_match.group(0))

            # Gather text from following siblings until next heading
            section_text = self._collect_section_text(heading)

            if not section_text:
                continue

            # Check if this section relates to admissions
            combined = heading_text.lower() + " " + section_text.lower()
            if not any(
                kw in combined
                for kw in [
                    "admission",
                    "allocation",
                    "distance",
                    "places",
                    "pan",
                    "application",
                    "appeal",
                    "waiting",
                    "oversubscri",
                ]
            ):
                continue

            record = self._extract_from_text_block(school_id, academic_year, section_text, source_url)
            if record:
                records.append(record)

        if records:
            self._logger.info(
                "Extracted %d records from year sections for school_id=%d",
                len(records),
                school_id,
            )

        return records

    def _parse_from_inline_text(
        self,
        school_id: int,
        soup: BeautifulSoup,
        source_url: str,
    ) -> list[dict[str, object]]:
        """Parse admissions data from inline page text.

        Scans the full page text for year-contextual admissions data mentions.
        This is the fallback strategy when no structured tables or sections
        are found.
        """
        text = soup.get_text(separator="\n", strip=True)
        lines = text.split("\n")

        # Look for paragraphs that contain both a year reference and admissions data.
        records: list[dict[str, object]] = []
        current_year: str | None = None

        for line in lines:
            year_match = _ACADEMIC_YEAR_PATTERN.search(line)
            if year_match:
                current_year = self._normalise_academic_year(year_match.group(0))

            if current_year and self._line_has_admissions_data(line):
                record = self._extract_from_text_block(school_id, current_year, line, source_url)
                if record:
                    records.append(record)
                    current_year = None  # Reset to avoid double-counting

        return self._deduplicate_records(records)

    # ------------------------------------------------------------------
    # Text extraction helpers
    # ------------------------------------------------------------------

    def _extract_from_text_block(
        self,
        school_id: int,
        academic_year: str,
        text: str,
        source_url: str,
    ) -> dict[str, object] | None:
        """Extract admissions data fields from a block of text."""
        record: dict[str, object] = {
            "school_id": school_id,
            "academic_year": academic_year,
            "source_url": source_url,
        }

        # Extract distance
        dist = self._extract_distance_from_text(text)
        if dist is not None:
            record["last_distance_offered_km"] = dist

        # Extract places / PAN
        places_match = _PLACES_PATTERN.search(text)
        if not places_match:
            places_match = _PLACES_PATTERN_ALT.search(text)
        if places_match:
            record["places_offered"] = int(places_match.group(1))

        # Extract applications
        apps_match = _APPLICATIONS_PATTERN.search(text)
        if apps_match:
            record["applications_received"] = int(apps_match.group(1))

        # Extract waiting list
        wl_match = _WAITING_LIST_PATTERN.search(text)
        if not wl_match:
            wl_match = _WAITING_LIST_PATTERN_ALT.search(text)
        if wl_match:
            record["waiting_list_offers"] = int(wl_match.group(1))

        # Extract appeals heard
        ah_match = _APPEALS_HEARD_PATTERN.search(text)
        if not ah_match:
            ah_match = _APPEALS_HEARD_PATTERN_ALT.search(text)
        if ah_match:
            record["appeals_heard"] = int(ah_match.group(1))

        # Extract appeals upheld
        au_match = _APPEALS_UPHELD_PATTERN.search(text)
        if not au_match:
            au_match = _APPEALS_UPHELD_PATTERN_ALT.search(text)
        if au_match:
            record["appeals_upheld"] = int(au_match.group(1))

        # Extract intake year
        intake_match = _INTAKE_YEAR_PATTERN.search(text)
        if intake_match:
            record["intake_year"] = self._normalise_intake_year(intake_match.group(1))

        # Check for vacancies
        if re.search(r"vacanc(?:y|ies)", text, re.IGNORECASE):
            if re.search(r"no\s+vacanc|without\s+vacanc|0\s+vacanc", text, re.IGNORECASE):
                record["had_vacancies"] = False
            else:
                record["had_vacancies"] = True

        # Only return if we got at least one data field
        data_fields = [
            "places_offered",
            "applications_received",
            "last_distance_offered_km",
            "waiting_list_offers",
            "appeals_heard",
            "appeals_upheld",
        ]
        if any(record.get(f) is not None for f in data_fields):
            return record

        return None

    def _collect_section_text(self, heading: Tag) -> str:
        """Collect text from elements following a heading until the next heading."""
        parts: list[str] = []
        sibling = heading.find_next_sibling()

        while sibling and not (isinstance(sibling, Tag) and sibling.name in ("h1", "h2", "h3", "h4", "h5")):
            if isinstance(sibling, Tag):
                text = sibling.get_text(separator=" ", strip=True)
                if text:
                    parts.append(text)
            sibling = sibling.find_next_sibling() if sibling else None

        return " ".join(parts)

    def _line_has_admissions_data(self, line: str) -> bool:
        """Check if a line contains admissions-related data."""
        lower = line.lower()
        return any(
            kw in lower
            for kw in [
                "distance",
                "places",
                "pan",
                "application",
                "appeal",
                "waiting list",
                "oversubscri",
                "admission number",
            ]
        )

    # ------------------------------------------------------------------
    # Value extraction helpers
    # ------------------------------------------------------------------

    def _extract_distance_km(self, text: str) -> float | None:
        """Extract a distance value from text, converting to km if needed."""
        return self._extract_distance_from_text(text)

    def _extract_distance_from_text(self, text: str) -> float | None:
        """Extract distance from a text string, returning value in km."""
        # Try km first
        km_match = _DISTANCE_KM_PATTERN.search(text)
        if km_match:
            try:
                return round(float(km_match.group(1)), 3)
            except ValueError:
                pass

        # Try miles
        miles_match = _DISTANCE_MILES_PATTERN.search(text)
        if miles_match:
            try:
                return round(float(miles_match.group(1)) * MILES_TO_KM, 3)
            except ValueError:
                pass

        # Try bare decimal in a distance context
        if any(kw in text.lower() for kw in ["distance", "furthest", "cutoff"]):
            bare_num = re.search(r"(\d+\.\d+)", text)
            if bare_num:
                val = float(bare_num.group(1))
                # Heuristic: if < 10, likely miles; values are rarely > 10km
                if val < 10:
                    return round(val * MILES_TO_KM, 3)

        return None

    def _extract_integer(self, text: str) -> int | None:
        """Extract an integer from text, ignoring commas and non-numeric characters."""
        cleaned = text.replace(",", "").strip()
        match = re.search(r"(\d+)", cleaned)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    def _normalise_academic_year(self, raw: str) -> str:
        """Normalise an academic year string to YYYY/YYYY format."""
        match = _ACADEMIC_YEAR_PATTERN.search(raw)
        if not match:
            return raw

        start_year = int(match.group(1))
        end_part = match.group(2)

        if len(end_part) == 2:
            end_year = int(f"{str(start_year)[:2]}{end_part}")
        else:
            end_year = int(end_part)

        return f"{start_year}/{end_year}"

    def _normalise_intake_year(self, raw: str) -> str:
        """Normalise intake year names (e.g. 'reception' -> 'Year R')."""
        lower = raw.lower().strip()
        if "reception" in lower or lower == "year r":
            return "Year R"
        if "nursery" in lower:
            return "Nursery"
        if "sixth" in lower:
            return "Sixth Form"
        # Match "Year 7", "Year 1", etc.
        year_match = re.search(r"year\s*(\d+)", lower)
        if year_match:
            return f"Year {year_match.group(1)}"
        return raw.strip()

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _deduplicate_records(self, records: list[dict[str, object]]) -> list[dict[str, object]]:
        """Deduplicate records by academic_year, keeping the most complete one."""
        by_year: dict[str, list[dict[str, object]]] = {}
        for record in records:
            year = str(record.get("academic_year", ""))
            if year:
                by_year.setdefault(year, []).append(record)

        result: list[dict[str, object]] = []
        for year, year_records in by_year.items():
            # Pick the record with the most non-None data fields
            best = max(year_records, key=lambda r: self._count_data_fields(r))

            # Merge: fill in missing fields from other records
            for other in year_records:
                if other is best:
                    continue
                for key, value in other.items():
                    if key not in ("school_id", "academic_year", "source_url") and value is not None:
                        if best.get(key) is None:
                            best[key] = value

            result.append(best)

        return result

    def _count_data_fields(self, record: dict[str, object]) -> int:
        """Count the number of non-None data fields in a record."""
        data_fields = [
            "places_offered",
            "applications_received",
            "last_distance_offered_km",
            "waiting_list_offers",
            "appeals_heard",
            "appeals_upheld",
            "allocation_description",
            "intake_year",
        ]
        return sum(1 for f in data_fields if record.get(f) is not None)

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_to_db(self, school_id: int, records: list[dict[str, object]]) -> int:
        """Write parsed admissions history records to the database.

        Merges with existing data: if a record for the same school + year
        already exists, updates any NULL fields with newly discovered values.
        Does not overwrite existing non-NULL data.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        saved = 0
        with Session(engine) as session:
            for record in records:
                academic_year = str(record.get("academic_year", ""))
                if not academic_year:
                    continue

                # Check for existing record
                stmt = select(AdmissionsHistory).where(
                    AdmissionsHistory.school_id == school_id,
                    AdmissionsHistory.academic_year == academic_year,
                )
                existing = session.execute(stmt).scalar_one_or_none()

                if existing:
                    # Merge: fill in NULL fields with new data
                    updated = False
                    merge_fields = [
                        ("places_offered", "places_offered"),
                        ("applications_received", "applications_received"),
                        ("last_distance_offered_km", "last_distance_offered_km"),
                        ("waiting_list_offers", "waiting_list_offers"),
                        ("appeals_heard", "appeals_heard"),
                        ("appeals_upheld", "appeals_upheld"),
                        ("allocation_description", "allocation_description"),
                        ("had_vacancies", "had_vacancies"),
                        ("intake_year", "intake_year"),
                    ]
                    for db_field, record_field in merge_fields:
                        if getattr(existing, db_field) is None and record.get(record_field) is not None:
                            setattr(existing, db_field, record[record_field])
                            updated = True

                    if updated:
                        saved += 1
                        self._logger.debug(
                            "Merged data into existing record for school_id=%d, year=%s",
                            school_id,
                            academic_year,
                        )
                else:
                    # Insert new record
                    new_record = AdmissionsHistory(
                        school_id=school_id,
                        academic_year=academic_year,
                        places_offered=record.get("places_offered"),
                        applications_received=record.get("applications_received"),
                        last_distance_offered_km=record.get("last_distance_offered_km"),
                        waiting_list_offers=record.get("waiting_list_offers"),
                        appeals_heard=record.get("appeals_heard"),
                        appeals_upheld=record.get("appeals_upheld"),
                        allocation_description=record.get("allocation_description"),
                        had_vacancies=record.get("had_vacancies"),
                        intake_year=record.get("intake_year"),
                        source_url=record.get("source_url"),
                    )
                    session.add(new_record)
                    saved += 1

            session.commit()

        return saved


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape historical admissions data for schools in a council.",
    )
    parser.add_argument(
        "--council",
        required=True,
        help='Council name, e.g. "Milton Keynes".',
    )
    parser.add_argument(
        "--cache-dir",
        default="./data/cache",
        help="Directory for cached HTTP responses (default: ./data/cache).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between HTTP requests (default: 1.0).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Maximum link-following depth from homepage (default: 2).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for the admissions history agent."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    agent = AdmissionsHistoryAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
        max_depth=args.max_depth,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
