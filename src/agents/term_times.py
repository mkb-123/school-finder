"""Agent 1: Term Times Agent.

Fetches and parses school term dates from council websites.  For councils
that publish term dates centrally (e.g. Milton Keynes Council), the agent
scrapes the council page.  For academies or free schools that set their
own dates it falls back to checking individual school websites.

Results are stored in the ``school_term_dates`` table via SQLAlchemy.

Usage
-----
::

    python -m src.agents.term_times --council "Milton Keynes"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import SchoolTermDate

logger = logging.getLogger(__name__)

# Known council term-dates page URLs.  Extend this mapping as new councils
# are supported.
_COUNCIL_URLS: dict[str, str] = {
    "Milton Keynes": "https://www.milton-keynes.gov.uk/schools-and-lifelong-learning/school-term-dates",
}


class TermTimesAgent(BaseAgent):
    """Scrape school term dates for a given council and persist them.

    The agent:

    1. Resolves the council's term-dates page URL.
    2. Fetches the page (with caching and rate limiting via :class:`BaseAgent`).
    3. Parses the HTML to extract structured term date records.
    4. Writes the records into the ``school_term_dates`` table.

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
        1. Look up the council URL.
        2. Fetch and parse the page.
        3. Extract term date records.
        4. Persist to the database.
        """
        self._logger.info("Starting term-times agent for council=%r", self.council)

        url = self._resolve_council_url()
        if url is None:
            self._logger.warning("No known term-dates URL for council=%r – skipping", self.council)
            return

        html = await self.fetch_page(url)
        soup = self.parse_html(html)
        records = self._parse_term_dates(soup)

        if records:
            self._save_to_db(records)
            self._logger.info("Saved %d term-date records for council=%r", len(records), self.council)
        else:
            self._logger.warning("No term-date records extracted for council=%r", self.council)

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
    # Parsing
    # ------------------------------------------------------------------

    def _parse_term_dates(self, soup: object) -> list[dict[str, object]]:
        """Parse term date records from the fetched HTML.

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
        # Parse based on council-specific layout
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
            List of term date records.
        """
        import re

        records = []

        # Look for tables or structured date information
        # MK Council typically uses tables with term names and dates
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                # Extract text from cells
                cell_texts = [cell.get_text(strip=True) for cell in cells]

                # Try to identify term names and dates
                term_match = re.search(r"(Autumn|Spring|Summer).*?(\d{4}/\d{4})?", " ".join(cell_texts), re.IGNORECASE)
                if not term_match:
                    continue

                term_name = term_match.group(1)
                academic_year = term_match.group(2) if term_match.group(2) else "2025/2026"

                # Extract dates (DD/MM/YYYY format common in UK)
                dates_found = re.findall(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", " ".join(cell_texts))

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
                    except Exception as e:
                        self._logger.warning("Could not parse dates: %s", e)
                        continue

        return records

    def _parse_uk_date(self, date_str: str) -> date:
        """Parse a UK format date string (DD/MM/YYYY or DD-MM-YYYY)."""
        from datetime import datetime

        for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Could not parse date: {date_str}")

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_to_db(self, records: list[dict[str, object]]) -> None:
        """Write parsed term-date records to the ``school_term_dates`` table.

        Uses a synchronous SQLAlchemy session for simplicity – the agents are
        IO-bound on HTTP, not on local DB writes.

        Parameters
        ----------
        records:
            Parsed term-date dicts as returned by :meth:`_parse_term_dates`.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            for record in records:
                term_date = SchoolTermDate(
                    school_id=record.get("school_id", 0),
                    academic_year=str(record.get("academic_year", "")),
                    term_name=str(record.get("term_name", "")),
                    start_date=record["start_date"],
                    end_date=record["end_date"],
                    half_term_start=record.get("half_term_start"),
                    half_term_end=record.get("half_term_end"),
                )
                session.add(term_date)
            session.commit()
            self._logger.info("Committed %d term-date rows", len(records))


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
