"""Agent 1: Term Times Agent.

Fetches and parses school term dates from council websites.  For councils
that publish term dates centrally (e.g. Milton Keynes Council), the agent
scrapes the council page and applies the parsed dates to **all non-private
schools** in that council (maintained schools, academies, and free schools
all default to council dates).

For academies and free schools that may set their own dates, the agent also
attempts to fetch term dates from the individual school website.  If
school-specific dates are found they **replace** the council defaults for
that school.

Results are stored in the ``school_term_dates`` table via SQLAlchemy.

Usage
-----
::

    python -m src.agents.term_times --council "Milton Keynes"
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
import re
import sys
from datetime import date

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import School, SchoolTermDate

logger = logging.getLogger(__name__)

# Known council term-dates page URLs.  Extend this mapping as new councils
# are supported.
_COUNCIL_URLS: dict[str, str] = {
    "Milton Keynes": "https://www.milton-keynes.gov.uk/schools-and-lifelong-learning/school-term-dates",
}

# Keywords that indicate a page contains term date information.
_TERM_KEYWORDS: list[str] = [
    "term dates",
    "term times",
    "academic calendar",
    "school calendar",
    "academic year",
]

_TERM_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _TERM_KEYWORDS),
    flags=re.IGNORECASE,
)


class TermTimesAgent(BaseAgent):
    """Scrape school term dates for a given council and persist them.

    The agent:

    1. Loads all non-private schools for the council from the database.
    2. Resolves the council's term-dates page URL and parses council-level
       dates.
    3. Applies council dates to every non-private school.
    4. For academies and free schools that have a website, attempts to fetch
       school-specific term dates.  If found, these override the council
       defaults for that school.
    5. Writes the records into the ``school_term_dates`` table.

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
        """Execute the full term-times collection pipeline.

        Steps
        -----
        1. Load schools from the database.
        2. Fetch and parse council-level term dates.
        3. For academies/free schools, try school-specific websites.
        4. Persist all records to the database.
        """
        self._logger.info("Starting term-times agent for council=%r", self.council)

        # Step 1: Load schools from DB.
        schools = self._load_schools()
        if not schools:
            self._logger.warning(
                "No non-private schools found in DB for council=%r – skipping",
                self.council,
            )
            return

        self._logger.info(
            "Loaded %d non-private schools for council=%r",
            len(schools),
            self.council,
        )

        # Step 2: Fetch council-level term dates.
        council_records: list[dict[str, object]] = []
        url = self._resolve_council_url()
        if url is not None:
            html = await self.fetch_page(url)
            soup = self.parse_html(html)
            council_records = self._parse_term_dates(soup)
            self._logger.info(
                "Parsed %d council-level term-date records for council=%r",
                len(council_records),
                self.council,
            )
        else:
            self._logger.warning(
                "No known term-dates URL for council=%r – will attempt school websites only",
                self.council,
            )

        # Step 3: Build per-school records.
        #
        # Start by applying council dates to ALL non-private schools.  Then
        # for academies/free schools that have a website, attempt to find
        # school-specific dates that override the council defaults.
        all_records: list[dict[str, object]] = []

        # Identify which schools are academies/free schools (they *might*
        # set their own dates).
        academy_types = {"academy", "free"}

        for school_id, school_name, school_type, school_website in schools:
            is_academy = (school_type or "").lower() in academy_types

            # Try school-specific dates for academies/free schools.
            school_specific: list[dict[str, object]] = []
            if is_academy and school_website:
                school_specific = await self._fetch_school_term_dates(school_id, school_name, school_website)

            if school_specific:
                # School-specific dates found – use those instead of council
                # defaults.
                self._logger.info(
                    "Using %d school-specific term-date records for %r (id=%d)",
                    len(school_specific),
                    school_name,
                    school_id,
                )
                all_records.extend(school_specific)
            elif council_records:
                # Fall back to council dates – stamp with this school's ID.
                for rec in council_records:
                    school_rec = dict(rec)
                    school_rec["school_id"] = school_id
                    all_records.append(school_rec)
            else:
                self._logger.debug(
                    "No term dates available for school %r (id=%d)",
                    school_name,
                    school_id,
                )

        # Step 4: Persist.
        if all_records:
            self._save_to_db(all_records)
            self._logger.info(
                "Saved %d total term-date records for council=%r",
                len(all_records),
                self.council,
            )
        else:
            self._logger.warning("No term-date records to save for council=%r", self.council)

    # ------------------------------------------------------------------
    # Database reads
    # ------------------------------------------------------------------

    def _load_schools(self) -> list[tuple[int, str, str | None, str | None]]:
        """Load all non-private schools for the configured council.

        Returns
        -------
        list[tuple[int, str, str | None, str | None]]
            A list of ``(school_id, school_name, school_type, website_url)``
            tuples.  Private schools are excluded.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            stmt = (
                select(School.id, School.name, School.type, School.website)
                .where(School.council == self.council)
                .where(School.is_private == False)  # noqa: E712
            )
            rows = session.execute(stmt).all()

        return [(row[0], row[1], row[2], row[3]) for row in rows]

    # ------------------------------------------------------------------
    # URL resolution
    # ------------------------------------------------------------------

    def _resolve_council_url(self) -> str | None:
        """Return the term-dates page URL for the configured council.

        Returns
        -------
        str | None
            The URL if the council is known, otherwise ``None``.
        """
        return _COUNCIL_URLS.get(self.council)

    # ------------------------------------------------------------------
    # Council-level parsing
    # ------------------------------------------------------------------

    def _parse_term_dates(self, soup: object) -> list[dict[str, object]]:
        """Parse term date records from the fetched council HTML.

        The returned records do **not** yet have a ``school_id`` set; the
        caller is responsible for stamping them with the correct school ID
        before persistence.

        Parameters
        ----------
        soup:
            A :class:`~bs4.BeautifulSoup` document tree of the council
            term-dates page.

        Returns
        -------
        list[dict[str, object]]
            A list of dicts each containing keys that map to
            :class:`~src.db.models.SchoolTermDate` columns:
            ``term_name``, ``start_date``, ``end_date``,
            ``half_term_start``, ``half_term_end``, ``academic_year``.
        """
        if self.council == "Milton Keynes":
            return self._parse_milton_keynes_term_dates(soup)
        else:
            self._logger.warning("No parser implemented for council: %s", self.council)
            return []

    def _parse_milton_keynes_term_dates(self, soup: object) -> list[dict[str, object]]:
        """Parse Milton Keynes Council term dates HTML.

        Parameters
        ----------
        soup:
            BeautifulSoup document tree of the MK term dates page.

        Returns
        -------
        list[dict[str, object]]
            List of term date records (without school_id).
        """
        records: list[dict[str, object]] = []

        # MK Council typically uses tables with term names and dates.
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                cell_texts = [cell.get_text(strip=True) for cell in cells]
                joined = " ".join(cell_texts)

                # Try to identify term names and dates.
                term_match = re.search(
                    r"(Autumn|Spring|Summer).*?(\d{4}/\d{4})?",
                    joined,
                    re.IGNORECASE,
                )
                if not term_match:
                    continue

                term_name = term_match.group(1)
                academic_year = term_match.group(2) if term_match.group(2) else "2025/2026"

                # Extract dates (DD/MM/YYYY format common in UK).
                dates_found = re.findall(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", joined)

                if len(dates_found) >= 2:
                    try:
                        start_date = self._parse_uk_date(dates_found[0])
                        end_date = self._parse_uk_date(dates_found[1])

                        half_term_start = None
                        half_term_end = None
                        if len(dates_found) >= 4:
                            half_term_start = self._parse_uk_date(dates_found[2])
                            half_term_end = self._parse_uk_date(dates_found[3])

                        records.append(
                            {
                                "academic_year": academic_year,
                                "term_name": term_name,
                                "start_date": start_date,
                                "end_date": end_date,
                                "half_term_start": half_term_start,
                                "half_term_end": half_term_end,
                            }
                        )
                    except ValueError as exc:
                        self._logger.warning("Could not parse dates: %s", exc)
                        continue

        return records

    # ------------------------------------------------------------------
    # School-specific term date fetching
    # ------------------------------------------------------------------

    async def _fetch_school_term_dates(
        self,
        school_id: int,
        school_name: str,
        website_url: str,
    ) -> list[dict[str, object]]:
        """Attempt to find term dates on an individual school's website.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        school_name:
            Human-readable school name (for logging).
        website_url:
            Root URL of the school website to scrape.

        Returns
        -------
        list[dict[str, object]]
            Parsed term-date records with ``school_id`` set, or an empty
            list if no term dates could be extracted.
        """
        try:
            html = await self.fetch_page(website_url)
        except Exception:
            self._logger.debug(
                "Failed to fetch website for school %r (id=%d) – skipping",
                school_name,
                school_id,
            )
            return []

        soup = self.parse_html(html)
        page_text = soup.get_text(separator=" ", strip=True)

        # Check if the homepage mentions term dates at all.
        if not _TERM_PATTERN.search(page_text):
            self._logger.debug("No term-date keywords found on homepage of %r", school_name)
            return []

        # Try to find links to a dedicated term-dates page.
        term_links = self._find_term_date_links(soup, website_url)

        for link in term_links:
            try:
                sub_html = await self.fetch_page(link)
            except Exception:
                self._logger.debug(
                    "Failed to fetch term-dates sub-page %s for school %r",
                    link,
                    school_name,
                )
                continue

            sub_soup = self.parse_html(sub_html)
            records = self._parse_school_page_term_dates(sub_soup)
            if records:
                # Stamp with school_id and return.
                for rec in records:
                    rec["school_id"] = school_id
                return records

        # Fall back to parsing the homepage itself.
        records = self._parse_school_page_term_dates(soup)
        if records:
            for rec in records:
                rec["school_id"] = school_id
        return records

    def _find_term_date_links(self, soup: object, base_url: str) -> list[str]:
        """Extract links from the page that likely lead to term-date info.

        Parameters
        ----------
        soup:
            BeautifulSoup document tree.
        base_url:
            The base URL of the page, used to resolve relative links.

        Returns
        -------
        list[str]
            Absolute URLs that are likely term-date pages.
        """
        from urllib.parse import urljoin

        links: list[str] = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            text = a_tag.get_text(strip=True).lower()

            if _TERM_PATTERN.search(text) or _TERM_PATTERN.search(href.lower()):
                absolute = urljoin(base_url, href)
                if absolute not in links:
                    links.append(absolute)

        # Limit to a reasonable number to avoid excessive requests.
        return links[:5]

    def _parse_school_page_term_dates(self, soup: object) -> list[dict[str, object]]:
        """Parse term dates from a school website page.

        This is a generic parser that looks for tables and structured date
        patterns.  Only dates that are **actually present** on the page are
        extracted.  If no parseable dates are found, returns an empty list.

        Parameters
        ----------
        soup:
            BeautifulSoup document tree.

        Returns
        -------
        list[dict[str, object]]
            Parsed term-date records (without ``school_id``).
        """
        records: list[dict[str, object]] = []

        # Strategy 1: Look for tables (most common format).
        tables = soup.find_all("table")
        for table in tables:
            table_records = self._extract_term_dates_from_table(table)
            records.extend(table_records)

        if records:
            return records

        # Strategy 2: Look for structured text with term names and dates
        # in definition lists, paragraphs, or list items.
        text_records = self._extract_term_dates_from_text(soup)
        records.extend(text_records)

        return records

    def _extract_term_dates_from_table(self, table: object) -> list[dict[str, object]]:
        """Extract term dates from an HTML table element.

        Parameters
        ----------
        table:
            A BeautifulSoup ``<table>`` element.

        Returns
        -------
        list[dict[str, object]]
            Parsed term-date records.
        """
        records: list[dict[str, object]] = []

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            cell_texts = [cell.get_text(strip=True) for cell in cells]
            joined = " ".join(cell_texts)

            # Look for a term name.
            term_match = re.search(
                r"(Autumn|Spring|Summer)\s*(term)?\s*(\d)?",
                joined,
                re.IGNORECASE,
            )
            if not term_match:
                continue

            term_name = term_match.group(1).capitalize()
            term_number = term_match.group(3)
            if term_number:
                term_name = f"{term_name} {term_number}"

            # Extract an academic year if present.
            year_match = re.search(r"(\d{4})[/-](\d{2,4})", joined)
            if year_match:
                y1 = year_match.group(1)
                y2 = year_match.group(2)
                if len(y2) == 2:
                    y2 = y1[:2] + y2
                academic_year = f"{y1}/{y2}"
            else:
                academic_year = "2025/2026"

            # Extract UK-format dates.
            dates_found = re.findall(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", joined)

            if len(dates_found) >= 2:
                try:
                    start_date = self._parse_uk_date(dates_found[0])
                    end_date = self._parse_uk_date(dates_found[1])

                    half_term_start = None
                    half_term_end = None
                    if len(dates_found) >= 4:
                        half_term_start = self._parse_uk_date(dates_found[2])
                        half_term_end = self._parse_uk_date(dates_found[3])

                    records.append(
                        {
                            "academic_year": academic_year,
                            "term_name": term_name,
                            "start_date": start_date,
                            "end_date": end_date,
                            "half_term_start": half_term_start,
                            "half_term_end": half_term_end,
                        }
                    )
                except ValueError as exc:
                    self._logger.debug("Could not parse dates in table row: %s", exc)
                    continue

        return records

    def _extract_term_dates_from_text(self, soup: object) -> list[dict[str, object]]:
        """Extract term dates from unstructured text (paragraphs, lists).

        Parameters
        ----------
        soup:
            BeautifulSoup document tree.

        Returns
        -------
        list[dict[str, object]]
            Parsed term-date records.
        """
        records: list[dict[str, object]] = []

        # Get all text blocks that might contain term info.
        blocks = soup.find_all(["p", "li", "dd", "div", "span"])
        text_lines = [block.get_text(strip=True) for block in blocks]

        current_term: str | None = None
        current_year: str = "2025/2026"

        for line in text_lines:
            # Check for a term heading.
            term_match = re.search(
                r"(Autumn|Spring|Summer)\s*(term)?\s*(\d)?\s*(\d{4}[/-]\d{2,4})?",
                line,
                re.IGNORECASE,
            )
            if term_match:
                term_name = term_match.group(1).capitalize()
                term_number = term_match.group(3)
                if term_number:
                    term_name = f"{term_name} {term_number}"
                current_term = term_name

                if term_match.group(4):
                    year_part = term_match.group(4)
                    parts = re.split(r"[/-]", year_part)
                    if len(parts) == 2:
                        y2 = parts[1]
                        if len(y2) == 2:
                            y2 = parts[0][:2] + y2
                        current_year = f"{parts[0]}/{y2}"

            if current_term is None:
                continue

            # Extract dates from this line.
            dates_found = re.findall(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", line)

            if len(dates_found) >= 2:
                try:
                    start_date = self._parse_uk_date(dates_found[0])
                    end_date = self._parse_uk_date(dates_found[1])

                    half_term_start = None
                    half_term_end = None
                    if len(dates_found) >= 4:
                        half_term_start = self._parse_uk_date(dates_found[2])
                        half_term_end = self._parse_uk_date(dates_found[3])

                    records.append(
                        {
                            "academic_year": current_year,
                            "term_name": current_term,
                            "start_date": start_date,
                            "end_date": end_date,
                            "half_term_start": half_term_start,
                            "half_term_end": half_term_end,
                        }
                    )
                    # Reset so we don't duplicate.
                    current_term = None
                except ValueError as exc:
                    self._logger.debug("Could not parse dates in text: %s", exc)
                    continue

        return records

    # ------------------------------------------------------------------
    # Date parsing
    # ------------------------------------------------------------------

    def _parse_uk_date(self, date_str: str) -> datetime.date:
        """Parse a UK format date string (DD/MM/YYYY or DD-MM-YYYY).

        Parameters
        ----------
        date_str:
            A date string in one of the supported UK formats.

        Returns
        -------
        datetime.date
            The parsed date.

        Raises
        ------
        ValueError
            If the string does not match any supported format.
        """
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
            try:
                return datetime.datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Could not parse date: {date_str!r}")

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_to_db(self, records: list[dict[str, object]]) -> None:
        """Write parsed term-date records to the ``school_term_dates`` table.

        Before inserting, any existing term-date rows for the affected
        schools are deleted so the agent is idempotent (re-running it
        replaces stale data rather than duplicating rows).

        Uses a synchronous SQLAlchemy session for simplicity -- the agents
        are IO-bound on HTTP, not on local DB writes.

        Parameters
        ----------
        records:
            Parsed term-date dicts.  Each must include ``school_id``,
            ``academic_year``, ``term_name``, ``start_date``, ``end_date``,
            and optionally ``half_term_start`` and ``half_term_end``.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        # Collect the distinct school IDs we are about to write.
        school_ids = {rec["school_id"] for rec in records}

        with Session(engine) as session:
            # Delete existing rows for these schools so re-runs are clean.
            if school_ids:
                session.execute(delete(SchoolTermDate).where(SchoolTermDate.school_id.in_(school_ids)))
                self._logger.info(
                    "Cleared existing term-date rows for %d schools",
                    len(school_ids),
                )

            for record in records:
                term_date = SchoolTermDate(
                    school_id=record["school_id"],
                    academic_year=str(record.get("academic_year", "")),
                    term_name=str(record.get("term_name", "")),
                    start_date=record["start_date"],
                    end_date=record["end_date"],
                    half_term_start=record.get("half_term_start"),
                    half_term_end=record.get("half_term_end"),
                )
                session.add(term_date)

            session.commit()
            self._logger.info(
                "Committed %d term-date rows for %d schools",
                len(records),
                len(school_ids),
            )


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the term-times agent.

    Parameters
    ----------
    argv:
        Argument list.  Defaults to ``sys.argv[1:]`` when ``None``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments containing at least ``council``.
    """
    parser = argparse.ArgumentParser(
        description="Fetch and store school term dates for a council.",
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
    """CLI entry point for the term-times agent.

    Parameters
    ----------
    argv:
        Optional argument list for testing; defaults to ``sys.argv[1:]``.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    agent = TermTimesAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
