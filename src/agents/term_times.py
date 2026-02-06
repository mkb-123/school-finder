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
        # TODO: implement parsing for {council}
        # Each council page has a different layout so parsing logic must be
        # tailored per council.  The expected return format is a list of dicts:
        #
        #   [
        #       {
        #           "academic_year": "2025/2026",
        #           "term_name": "Autumn 1",
        #           "start_date": datetime.date(2025, 9, 3),
        #           "end_date": datetime.date(2025, 10, 24),
        #           "half_term_start": datetime.date(2025, 10, 27),
        #           "half_term_end": datetime.date(2025, 10, 31),
        #       },
        #       ...
        #   ]
        self._logger.info("TODO: implement parsing for %s", self.council)
        return []

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
