"""Council Admissions Data Agent.

Scrapes council websites for bulk admissions data published in annual
admissions booklets and allocation profile pages.  Councils like Milton Keynes
publish parent guides containing per-school allocation data (places offered,
applications received, last distance offered, vacancies) in HTML tables or
structured pages.

This agent targets the council's admissions landing page, discovers links to
annual allocation data pages or tables, and extracts per-school admissions
history in bulk — far more efficiently than scraping each school individually.

Usage
-----
::

    python -m src.agents.council_admissions --council "Milton Keynes"
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

# Known council admissions page URLs by council name.
_COUNCIL_ADMISSIONS_URLS: dict[str, list[str]] = {
    "Milton Keynes": [
        "https://www.milton-keynes.gov.uk/schools-and-lifelong-learning/school-admissions",
        "https://www.milton-keynes.gov.uk/school-admissions",
    ],
}

# Keywords for finding allocation data links on council pages.
_ALLOCATION_LINK_KEYWORDS: list[str] = [
    "allocation",
    "allocation profile",
    "offer day",
    "parent guide",
    "admissions booklet",
    "places offered",
    "school places",
    "admissions data",
    "admissions statistics",
    "last distance",
    "secondary admissions",
    "primary admissions",
    "results",
    "outcomes",
]

_ALLOCATION_LINK_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _ALLOCATION_LINK_KEYWORDS),
    flags=re.IGNORECASE,
)

# Academic year pattern
_ACADEMIC_YEAR_PATTERN = re.compile(
    r"(20[12]\d)\s*[/\-]\s*(20[12]\d|[12]\d)",
)

# Distance patterns
_DISTANCE_MILES_PATTERN = re.compile(
    r"(\d+\.?\d*)\s*(?:miles?|mi)\b",
    re.IGNORECASE,
)
_DISTANCE_KM_PATTERN = re.compile(
    r"(\d+\.?\d*)\s*(?:km|kilometres?|kilometers?)\b",
    re.IGNORECASE,
)


class CouncilAdmissionsAgent(BaseAgent):
    """Scrape council websites for bulk admissions allocation data.

    This agent targets the council's main admissions pages rather than
    individual school websites.  Councils publish annual allocation profiles
    containing data for all schools in the area, making this much more
    efficient than per-school scraping.

    Parameters
    ----------
    council:
        Council name, e.g. ``"Milton Keynes"``.
    cache_dir:
        Directory for cached HTTP responses.
    delay:
        Seconds to wait between HTTP requests.
    """

    def __init__(
        self,
        council: str,
        cache_dir: str = "./data/cache",
        delay: float = 1.0,
    ) -> None:
        super().__init__(council=council, cache_dir=cache_dir, delay=delay)

    async def run(self) -> None:
        """Execute the council admissions data-collection pipeline."""
        self._logger.info("Starting council admissions agent for council=%r", self.council)

        # Load school name -> ID mapping for matching
        school_map = self._load_school_map()
        if not school_map:
            self._logger.warning("No schools found in DB for council=%r", self.council)
            return

        self._logger.info("Loaded %d schools for matching", len(school_map))

        # Get council admissions page URLs
        council_urls = _COUNCIL_ADMISSIONS_URLS.get(self.council, [])
        if not council_urls:
            self._logger.warning(
                "No known admissions URLs for council=%r. "
                "Add URLs to _COUNCIL_ADMISSIONS_URLS in council_admissions.py",
                self.council,
            )
            return

        visited: set[str] = set()
        total_records = 0

        # Visit each council admissions page
        for url in council_urls:
            if url in visited:
                continue
            visited.add(url)

            try:
                page_html = await self.fetch_page(url)
            except Exception:
                self._logger.exception("Failed to fetch council page %s", url)
                continue

            page_soup = self.parse_html(page_html)

            # Try to extract data directly from this page
            records = self._parse_allocation_tables(page_soup, url, school_map)
            if records:
                saved = self._save_records(records)
                total_records += saved
                self._logger.info("Extracted %d records from %s", saved, url)

            # Find links to allocation data subpages
            allocation_links = self._find_allocation_links(page_soup, url)
            self._logger.info("Found %d allocation data links on %s", len(allocation_links), url)

            for link_url in allocation_links:
                if link_url in visited:
                    continue
                visited.add(link_url)

                # Skip PDFs (can't parse in this agent)
                if link_url.lower().endswith(".pdf"):
                    self._logger.debug("Skipping PDF link: %s", link_url)
                    continue

                try:
                    sub_html = await self.fetch_page(link_url)
                except Exception:
                    self._logger.debug("Failed to fetch %s", link_url)
                    continue

                sub_soup = self.parse_html(sub_html)
                records = self._parse_allocation_tables(sub_soup, link_url, school_map)
                if records:
                    saved = self._save_records(records)
                    total_records += saved
                    self._logger.info("Extracted %d records from %s", saved, link_url)

                # Look one level deeper
                deeper_links = self._find_allocation_links(sub_soup, link_url)
                for deep_url in deeper_links[:5]:
                    if deep_url in visited:
                        continue
                    visited.add(deep_url)

                    if deep_url.lower().endswith(".pdf"):
                        continue

                    try:
                        deep_html = await self.fetch_page(deep_url)
                    except Exception:
                        continue

                    deep_soup = self.parse_html(deep_html)
                    records = self._parse_allocation_tables(deep_soup, deep_url, school_map)
                    if records:
                        saved = self._save_records(records)
                        total_records += saved
                        self._logger.info("Extracted %d records from %s", saved, deep_url)

        self._logger.info(
            "Council admissions agent complete: %d total records saved",
            total_records,
        )

    # ------------------------------------------------------------------
    # Database reads
    # ------------------------------------------------------------------

    def _load_school_map(self) -> dict[str, int]:
        """Load a mapping of normalised school names to IDs.

        Returns a dict where keys are lowercase normalised school names
        and values are database primary key IDs.  Multiple name variants
        are registered for each school to support fuzzy matching.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        school_map: dict[str, int] = {}
        with Session(engine) as session:
            stmt = select(School.id, School.name).where(School.council == self.council)
            rows = session.execute(stmt).all()

        for school_id, name in rows:
            # Register multiple name variants for matching
            variants = self._generate_name_variants(name)
            for variant in variants:
                school_map[variant] = school_id

        return school_map

    def _generate_name_variants(self, name: str) -> list[str]:
        """Generate normalised name variants for fuzzy matching."""
        variants: list[str] = []
        lower = name.lower().strip()
        variants.append(lower)

        # Without common suffixes
        for suffix in [
            " primary school",
            " school",
            " academy",
            " and nursery",
            " ce school",
            " c of e school",
            " church of england school",
            " rc school",
            " catholic school",
            " catholic primary school",
            " first school",
            " combined school",
            " infant school",
            " junior school",
            " secondary school",
            " high school",
            " middle school",
            " preparatory school",
        ]:
            if lower.endswith(suffix):
                stripped = lower[: -len(suffix)].strip()
                if stripped:
                    variants.append(stripped)

        # With "the" prefix removed
        if lower.startswith("the "):
            no_the = lower[4:]
            variants.append(no_the)
            # Also try without suffix after removing "the"
            for suffix in [" school", " academy"]:
                if no_the.endswith(suffix):
                    stripped = no_the[: -len(suffix)].strip()
                    if stripped:
                        variants.append(stripped)

        # Handle "St." / "St" / "Saint" variants
        for prefix in ["st.", "st ", "saint "]:
            if lower.startswith(prefix):
                for replacement in ["st.", "st ", "saint "]:
                    variant = replacement + lower[len(prefix) :]
                    if variant not in variants:
                        variants.append(variant)

        return variants

    # ------------------------------------------------------------------
    # Link discovery
    # ------------------------------------------------------------------

    def _find_allocation_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Find links to allocation data pages on a council website."""
        scored_links: list[tuple[int, str]] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            link_text = anchor.get_text(separator=" ", strip=True).lower()
            href_lower = href.lower()

            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue

            combined = f"{link_text} {href_lower}"
            score = 0

            if _ALLOCATION_LINK_PATTERN.search(combined):
                score += 1
                # Boost for year-specific links
                if _ACADEMIC_YEAR_PATTERN.search(combined):
                    score += 3
                # Boost for allocation-specific
                if "allocation" in combined:
                    score += 3
                if "last distance" in combined:
                    score += 4
                if "profile" in combined:
                    score += 2
                if "primary" in combined or "secondary" in combined:
                    score += 1

            if score > 0:
                absolute_url = urljoin(base_url, href)
                scored_links.append((score, absolute_url))

        scored_links.sort(key=lambda x: x[0], reverse=True)
        seen: set[str] = set()
        result: list[str] = []
        for _score, url in scored_links:
            if url not in seen:
                seen.add(url)
                result.append(url)

        return result[:20]

    # ------------------------------------------------------------------
    # Table parsing
    # ------------------------------------------------------------------

    def _parse_allocation_tables(
        self,
        soup: BeautifulSoup,
        source_url: str,
        school_map: dict[str, int],
    ) -> list[dict[str, object]]:
        """Parse allocation data tables from a council page.

        Council pages typically have tables with columns like:
        School | PAN | Applications | Last Distance | Vacancies | ...

        Or per-school allocation profiles in repeated sections.
        """
        records: list[dict[str, object]] = []

        # Try table-based extraction
        for table in soup.find_all("table"):
            table_records = self._parse_single_allocation_table(table, source_url, school_map)
            records.extend(table_records)

        # Try section-based extraction (each school as a section)
        if not records:
            records = self._parse_school_sections(soup, source_url, school_map)

        return records

    def _parse_single_allocation_table(
        self,
        table: Tag,
        source_url: str,
        school_map: dict[str, int],
    ) -> list[dict[str, object]]:
        """Parse a single HTML table for per-school allocation data."""
        rows = table.find_all("tr")
        if len(rows) < 2:
            return []

        # Identify columns from header
        header_row = rows[0]
        headers = [th.get_text(separator=" ", strip=True).lower() for th in header_row.find_all(["th", "td"])]

        if not headers:
            return []

        col_map = self._identify_allocation_columns(headers)

        # Must have at least a school name column
        if "school" not in col_map:
            return []

        # Try to detect the academic year from the page context
        page_text = table.find_parent().get_text(separator=" ", strip=True) if table.find_parent() else ""
        academic_year = self._detect_academic_year(page_text)

        records: list[dict[str, object]] = []
        for row in rows[1:]:
            cells = [td.get_text(separator=" ", strip=True) for td in row.find_all(["td", "th"])]
            if not cells:
                continue

            school_col = col_map["school"]
            if school_col >= len(cells):
                continue

            school_name = cells[school_col].strip()
            if not school_name:
                continue

            # Match to a known school
            school_id = self._match_school(school_name, school_map)
            if school_id is None:
                self._logger.debug("Could not match school name: %r", school_name)
                continue

            record: dict[str, object] = {
                "school_id": school_id,
                "academic_year": academic_year or "Unknown",
                "source_url": source_url,
            }

            # Extract data from identified columns
            if "places" in col_map and col_map["places"] < len(cells):
                record["places_offered"] = self._extract_integer(cells[col_map["places"]])

            if "applications" in col_map and col_map["applications"] < len(cells):
                record["applications_received"] = self._extract_integer(cells[col_map["applications"]])

            if "distance" in col_map and col_map["distance"] < len(cells):
                record["last_distance_offered_km"] = self._extract_distance_km(cells[col_map["distance"]])

            if "waiting_list" in col_map and col_map["waiting_list"] < len(cells):
                record["waiting_list_offers"] = self._extract_integer(cells[col_map["waiting_list"]])

            if "appeals_heard" in col_map and col_map["appeals_heard"] < len(cells):
                record["appeals_heard"] = self._extract_integer(cells[col_map["appeals_heard"]])

            if "appeals_upheld" in col_map and col_map["appeals_upheld"] < len(cells):
                record["appeals_upheld"] = self._extract_integer(cells[col_map["appeals_upheld"]])

            if "vacancies" in col_map and col_map["vacancies"] < len(cells):
                vac_text = cells[col_map["vacancies"]].strip().lower()
                record["had_vacancies"] = vac_text in ("yes", "y", "true", "✓", "✔")

            if "description" in col_map and col_map["description"] < len(cells):
                record["allocation_description"] = cells[col_map["description"]].strip()

            # Detect intake year from context
            if "intake" in col_map and col_map["intake"] < len(cells):
                record["intake_year"] = cells[col_map["intake"]].strip()

            # Only add if we have at least one data field
            data_fields = [
                "places_offered",
                "applications_received",
                "last_distance_offered_km",
                "waiting_list_offers",
                "appeals_heard",
                "appeals_upheld",
            ]
            if any(record.get(f) is not None for f in data_fields):
                records.append(record)

        if records:
            self._logger.info("Extracted %d records from allocation table", len(records))

        return records

    def _parse_school_sections(
        self,
        soup: BeautifulSoup,
        source_url: str,
        school_map: dict[str, int],
    ) -> list[dict[str, object]]:
        """Parse allocation data from repeated school sections.

        Some council pages present data per school in sections like:
        ## School Name
        PAN: 60, Applications: 120, Last distance: 1.2 miles
        """
        records: list[dict[str, object]] = []

        for heading in soup.find_all(["h2", "h3", "h4"]):
            heading_text = heading.get_text(separator=" ", strip=True)

            # Try to match the heading text to a school name
            school_id = self._match_school(heading_text, school_map)
            if school_id is None:
                continue

            # Collect section text
            section_text = self._collect_section_text(heading)
            if not section_text:
                continue

            # Look for allocation data in the section
            academic_year = self._detect_academic_year(section_text) or "Unknown"
            record = self._extract_from_text_block(school_id, academic_year, section_text, source_url)
            if record:
                records.append(record)

        return records

    def _identify_allocation_columns(self, headers: list[str]) -> dict[str, int]:
        """Map header names to column indices for allocation tables."""
        col_map: dict[str, int] = {}

        for i, header in enumerate(headers):
            h = header.strip()

            if any(kw in h for kw in ["school", "name", "establishment"]):
                if "school" not in col_map:
                    col_map["school"] = i

            elif any(kw in h for kw in ["pan", "admission number", "places", "capacity", "offered"]):
                if "places" not in col_map:
                    col_map["places"] = i

            elif any(kw in h for kw in ["application", "applicant", "preference", "first preference"]):
                if "applications" not in col_map:
                    col_map["applications"] = i

            elif any(kw in h for kw in ["distance", "last", "furthest", "cutoff", "cut-off"]):
                if "distance" not in col_map:
                    col_map["distance"] = i

            elif any(kw in h for kw in ["waiting", "wait list"]):
                if "waiting_list" not in col_map:
                    col_map["waiting_list"] = i

            elif "appeal" in h and any(kw in h for kw in ["heard", "lodged", "total"]):
                if "appeals_heard" not in col_map:
                    col_map["appeals_heard"] = i

            elif "appeal" in h and any(kw in h for kw in ["upheld", "success"]):
                if "appeals_upheld" not in col_map:
                    col_map["appeals_upheld"] = i

            elif any(kw in h for kw in ["vacanc", "surplus"]):
                if "vacancies" not in col_map:
                    col_map["vacancies"] = i

            elif any(kw in h for kw in ["description", "detail", "note", "allocation"]):
                if "description" not in col_map:
                    col_map["description"] = i

            elif any(kw in h for kw in ["intake", "year group", "entry"]):
                if "intake" not in col_map:
                    col_map["intake"] = i

        return col_map

    # ------------------------------------------------------------------
    # School name matching
    # ------------------------------------------------------------------

    def _match_school(self, raw_name: str, school_map: dict[str, int]) -> int | None:
        """Match a raw school name to a database ID using fuzzy matching."""
        lower = raw_name.lower().strip()

        # Direct match
        if lower in school_map:
            return school_map[lower]

        # Try variants
        variants = self._generate_name_variants(raw_name)
        for variant in variants:
            if variant in school_map:
                return school_map[variant]

        # Try substring matching (for cases like "Denbigh" matching "Denbigh School")
        for key, school_id in school_map.items():
            # Match if the raw name is a substantial part of a known name
            if lower in key or key in lower:
                # Ensure it's not a trivially short match
                shorter = min(len(lower), len(key))
                if shorter >= 4:
                    return school_id

        return None

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
        """Extract admissions data from a text block."""
        record: dict[str, object] = {
            "school_id": school_id,
            "academic_year": academic_year,
            "source_url": source_url,
        }

        # Extract distance
        dist = self._extract_distance_km(text)
        if dist is not None:
            record["last_distance_offered_km"] = dist

        # Extract places
        places_match = re.search(
            r"(?:PAN|admission\s+number|places?(?:\s+offered)?)\s*[=:]\s*(\d+)",
            text,
            re.IGNORECASE,
        )
        if places_match:
            record["places_offered"] = int(places_match.group(1))

        # Extract applications
        apps_match = re.search(
            r"(\d+)\s*(?:applications?|applicants?)",
            text,
            re.IGNORECASE,
        )
        if apps_match:
            record["applications_received"] = int(apps_match.group(1))

        # Extract waiting list
        wl_match = re.search(
            r"(\d+)\s*(?:from|off|via)\s*(?:the\s+)?waiting\s+list",
            text,
            re.IGNORECASE,
        )
        if wl_match:
            record["waiting_list_offers"] = int(wl_match.group(1))

        # Extract appeals
        appeals_match = re.search(r"(\d+)\s*appeals?\s*(?:heard|lodged)", text, re.IGNORECASE)
        if appeals_match:
            record["appeals_heard"] = int(appeals_match.group(1))

        upheld_match = re.search(r"(\d+)\s*(?:appeals?\s*)?(?:upheld|successful)", text, re.IGNORECASE)
        if upheld_match:
            record["appeals_upheld"] = int(upheld_match.group(1))

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
        while sibling and not (isinstance(sibling, Tag) and sibling.name in ("h1", "h2", "h3", "h4")):
            if isinstance(sibling, Tag):
                text = sibling.get_text(separator=" ", strip=True)
                if text:
                    parts.append(text)
            sibling = sibling.find_next_sibling() if sibling else None
        return " ".join(parts)

    def _detect_academic_year(self, text: str) -> str | None:
        """Detect the academic year from surrounding text."""
        match = _ACADEMIC_YEAR_PATTERN.search(text)
        if match:
            return self._normalise_academic_year(match.group(0))
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

    def _extract_distance_km(self, text: str) -> float | None:
        """Extract a distance value, converting to km if needed."""
        km_match = _DISTANCE_KM_PATTERN.search(text)
        if km_match:
            try:
                return round(float(km_match.group(1)), 3)
            except ValueError:
                pass

        miles_match = _DISTANCE_MILES_PATTERN.search(text)
        if miles_match:
            try:
                return round(float(miles_match.group(1)) * MILES_TO_KM, 3)
            except ValueError:
                pass

        return None

    def _extract_integer(self, text: str) -> int | None:
        """Extract an integer from text."""
        cleaned = text.replace(",", "").strip()
        match = re.search(r"(\d+)", cleaned)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_records(self, records: list[dict[str, object]]) -> int:
        """Save allocation records, merging with existing data."""
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        saved = 0
        with Session(engine) as session:
            for record in records:
                school_id = record["school_id"]
                academic_year = str(record.get("academic_year", ""))

                if not academic_year or academic_year == "Unknown":
                    continue

                # Check for existing record
                stmt = select(AdmissionsHistory).where(
                    AdmissionsHistory.school_id == school_id,
                    AdmissionsHistory.academic_year == academic_year,
                )
                existing = session.execute(stmt).scalar_one_or_none()

                if existing:
                    # Merge NULL fields
                    updated = False
                    for db_field, record_field in [
                        ("places_offered", "places_offered"),
                        ("applications_received", "applications_received"),
                        ("last_distance_offered_km", "last_distance_offered_km"),
                        ("waiting_list_offers", "waiting_list_offers"),
                        ("appeals_heard", "appeals_heard"),
                        ("appeals_upheld", "appeals_upheld"),
                        ("allocation_description", "allocation_description"),
                        ("had_vacancies", "had_vacancies"),
                        ("intake_year", "intake_year"),
                    ]:
                        if getattr(existing, db_field) is None and record.get(record_field) is not None:
                            setattr(existing, db_field, record[record_field])
                            updated = True

                    if updated:
                        saved += 1
                else:
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
        description="Scrape council websites for bulk admissions allocation data.",
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for the council admissions agent."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    agent = CouncilAdmissionsAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
