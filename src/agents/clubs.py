"""Agent 2: Breakfast & After-School Clubs Agent.

For each school belonging to the configured council, this agent visits the
school's website and searches for pages mentioning breakfast clubs,
after-school clubs, or wraparound care.  Extracted club data is stored in
the ``school_clubs`` table via SQLAlchemy.

Usage
-----
::

    python -m src.agents.clubs --council "Milton Keynes"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import School, SchoolClub

logger = logging.getLogger(__name__)

# Patterns used to identify club-related pages within a school website.
_CLUB_KEYWORDS: list[str] = [
    "breakfast club",
    "after school",
    "after-school",
    "wraparound care",
    "wrap around care",
    "wrap-around care",
]

# Regex compiled once for matching club keywords in page text.
_CLUB_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _CLUB_KEYWORDS),
    flags=re.IGNORECASE,
)


class ClubsAgent(BaseAgent):
    """Discover breakfast and after-school clubs for schools in a council.

    The agent:

    1. Queries the database for all schools belonging to the council.
    2. For each school that has a website URL, fetches the site and
       searches for club-related pages.
    3. Parses club details (name, type, days, times, cost).
    4. Persists results in the ``school_clubs`` table.

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
        """Execute the clubs data-collection pipeline.

        Steps
        -----
        1. Load the list of schools from the database.
        2. Iterate over each school's website.
        3. Discover and parse club pages.
        4. Persist to the database.
        """
        self._logger.info("Starting clubs agent for council=%r", self.council)

        schools = self._load_schools()
        if not schools:
            self._logger.warning("No schools found in DB for council=%r", self.council)
            return

        self._logger.info("Found %d schools for council=%r", len(schools), self.council)

        for school_id, school_name, school_website in schools:
            if not school_website:
                self._logger.debug("School %r (id=%d) has no website – skipping", school_name, school_id)
                continue

            self._logger.info("Processing school %r (id=%d)", school_name, school_id)
            clubs = await self._discover_clubs(school_id, school_name, school_website)

            if clubs:
                self._save_to_db(clubs)
                self._logger.info("Saved %d club records for school %r", len(clubs), school_name)
            else:
                self._logger.debug("No clubs found for school %r", school_name)

    # ------------------------------------------------------------------
    # Database reads
    # ------------------------------------------------------------------

    def _load_schools(self) -> list[tuple[int, str, str | None]]:
        """Load schools for the configured council from the database.

        Returns
        -------
        list[tuple[int, str, str | None]]
            A list of ``(school_id, school_name, website_url)`` tuples.
            The website URL may be ``None`` if not recorded.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            stmt = select(School.id, School.name, School.address).where(School.council == self.council)
            rows = session.execute(stmt).all()

        # NOTE: The School model does not yet have a dedicated ``website``
        # column.  Until that column is added we fall back to ``address``
        # as a placeholder so the skeleton compiles and runs.  Replace
        # ``School.address`` with ``School.website`` once available.
        return [(row[0], row[1], row[2]) for row in rows]

    # ------------------------------------------------------------------
    # Club discovery
    # ------------------------------------------------------------------

    async def _discover_clubs(
        self,
        school_id: int,
        school_name: str,
        website_url: str,
    ) -> list[dict[str, object]]:
        """Fetch a school's website and look for club information.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        school_name:
            Human-readable school name (used for logging).
        website_url:
            Root URL of the school website to scrape.

        Returns
        -------
        list[dict[str, object]]
            Parsed club records ready for persistence.  Each dict contains
            keys matching :class:`~src.db.models.SchoolClub` columns.
        """
        try:
            html = await self.fetch_page(website_url)
        except Exception:
            self._logger.exception("Failed to fetch website for school %r", school_name)
            return []

        soup = self.parse_html(html)
        page_text = soup.get_text(separator=" ", strip=True)

        if not _CLUB_PATTERN.search(page_text):
            self._logger.debug("No club keywords found on homepage of %r", school_name)
            return []

        return self._parse_clubs(school_id, soup)

    def _parse_clubs(self, school_id: int, soup: object) -> list[dict[str, object]]:
        """Extract structured club data from the parsed HTML.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        soup:
            A :class:`~bs4.BeautifulSoup` document tree.

        Returns
        -------
        list[dict[str, object]]
            Parsed club dicts.  Each contains:
            ``school_id``, ``club_type``, ``name``, ``description``,
            ``days_available``, ``start_time``, ``end_time``,
            ``cost_per_session``.
        """
        # Use heuristic parsing to extract club information
        clubs = []
        import re

        # Get all text content
        text = soup.get_text(separator="\n", strip=True)
        sections = text.split('\n')

        for i, line in enumerate(sections):
            line_lower = line.lower()

            # Detect club type
            club_type = None
            club_name = None

            if any(kw in line_lower for kw in ['breakfast club', 'breakfast']):
                club_type = 'breakfast'
                club_name = 'Breakfast Club'
            elif any(kw in line_lower for kw in ['after school', 'after-school', 'wraparound']):
                club_type = 'after-school'
                club_name = 'After School Club'

            if not club_type:
                continue

            # Try to extract details from surrounding lines
            context = ' '.join(sections[max(0, i-2):min(len(sections), i+5)])

            # Extract times (HH:MM format)
            times = re.findall(r'(\d{1,2}):(\d{2})\s*(am|pm)?', context, re.IGNORECASE)
            start_time = None
            end_time = None
            if len(times) >= 2:
                h1, m1, _ = times[0]
                h2, m2, _ = times[1]
                start_time = f"{h1.zfill(2)}:{m1}"
                end_time = f"{h2.zfill(2)}:{m2}"

            # Extract cost (£X.XX format)
            costs = re.findall(r'£(\d+\.?\d*)', context)
            cost = float(costs[0]) if costs else None

            # Default days
            days = 'Mon,Tue,Wed,Thu,Fri'

            # Create club record
            clubs.append({
                "school_id": school_id,
                "club_type": club_type,
                "name": club_name,
                "description": line[:200] if line else None,
                "days_available": days,
                "start_time": start_time,
                "end_time": end_time,
                "cost_per_session": cost,
            })

        self._logger.info("Extracted %d clubs for school_id=%d", len(clubs), school_id)
        return clubs

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_to_db(self, records: list[dict[str, object]]) -> None:
        """Write parsed club records to the ``school_clubs`` table.

        Uses a synchronous SQLAlchemy session for simplicity.

        Parameters
        ----------
        records:
            Parsed club dicts as returned by :meth:`_parse_clubs`.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            for record in records:
                club = SchoolClub(
                    school_id=record["school_id"],
                    club_type=str(record.get("club_type", "unknown")),
                    name=str(record.get("name", "")),
                    description=record.get("description"),
                    days_available=record.get("days_available"),
                    start_time=record.get("start_time"),
                    end_time=record.get("end_time"),
                    cost_per_session=record.get("cost_per_session"),
                )
                session.add(club)
            session.commit()
            self._logger.info("Committed %d club rows", len(records))


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the clubs agent.

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
        description="Discover breakfast & after-school clubs for schools in a council.",
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
    """CLI entry point for the clubs agent.

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
    agent = ClubsAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
