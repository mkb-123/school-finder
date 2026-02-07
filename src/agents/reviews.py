"""School Reviews Agent: Ofsted report scraper.

For each school belonging to the configured council, this agent visits the
Ofsted report page at ``https://reports.ofsted.gov.uk/provider/{urn}`` and
extracts the overall rating, key strengths, areas for improvement, and
inspection date.  Extracted review data is stored in the ``school_reviews``
table via SQLAlchemy.

Usage
-----
::

    python -m src.agents.reviews --council "Milton Keynes"
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
import re
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import School, SchoolReview

logger = logging.getLogger(__name__)

# Base URL for Ofsted provider report pages.
_OFSTED_PROVIDER_URL = "https://reports.ofsted.gov.uk/provider/{urn}"

# Mapping from Ofsted rating text to the 1-4 numeric scale.
_RATING_MAP: dict[str, float] = {
    "outstanding": 1.0,
    "good": 2.0,
    "requires improvement": 3.0,
    "inadequate": 4.0,
}

# Patterns for extracting the overall effectiveness rating from the page.
_RATING_PATTERN: re.Pattern[str] = re.compile(
    r"overall\s+effectiveness[:\s]*(\d)",
    flags=re.IGNORECASE,
)

# Alternative pattern: looks for rating text near "Overall effectiveness".
_RATING_TEXT_PATTERN: re.Pattern[str] = re.compile(
    r"(?:overall\s+effectiveness|overall\s+rating)[:\s]*(outstanding|good|requires\s+improvement|inadequate)",
    flags=re.IGNORECASE,
)

# Pattern for extracting inspection dates (e.g. "12 March 2024", "5 January 2023").
_DATE_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
    flags=re.IGNORECASE,
)


class ReviewsAgent(BaseAgent):
    """Collect school reviews from Ofsted report pages for a council.

    The agent:

    1. Queries the database for all schools belonging to the council.
    2. For each school that has a URN, fetches the Ofsted report page.
    3. Parses the overall rating, key strengths, areas for improvement,
       and inspection date.
    4. Persists results in the ``school_reviews`` table.

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
        """Execute the reviews data-collection pipeline.

        Steps
        -----
        1. Load the list of schools from the database.
        2. Iterate over each school with a URN.
        3. Fetch and parse the Ofsted report page.
        4. Persist review records to the database.
        """
        self._logger.info("Starting reviews agent for council=%r", self.council)

        schools = self._load_schools()
        if not schools:
            self._logger.warning("No schools found in DB for council=%r", self.council)
            return

        self._logger.info("Found %d schools for council=%r", len(schools), self.council)

        for school_id, school_name, school_website, school_urn in schools:
            if not school_urn:
                self._logger.debug("School %r (id=%d) has no URN - skipping", school_name, school_id)
                continue

            self._logger.info("Processing school %r (id=%d, urn=%s)", school_name, school_id, school_urn)
            review = await self._fetch_review(school_id, school_name, school_urn)

            if review:
                self._save_to_db([review])
                self._logger.info("Saved review for school %r", school_name)
            else:
                self._logger.debug("No review data extracted for school %r", school_name)

    # ------------------------------------------------------------------
    # Database reads
    # ------------------------------------------------------------------

    def _load_schools(self) -> list[tuple[int, str, str | None, str | None]]:
        """Load schools for the configured council from the database.

        Returns
        -------
        list[tuple[int, str, str | None, str | None]]
            A list of ``(school_id, school_name, website_url, urn)`` tuples.
            The website URL and URN may be ``None`` if not recorded.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            stmt = select(School.id, School.name, School.website, School.urn).where(School.council == self.council)
            rows = session.execute(stmt).all()

        return [(row[0], row[1], row[2], row[3]) for row in rows]

    # ------------------------------------------------------------------
    # Ofsted report fetching and parsing
    # ------------------------------------------------------------------

    async def _fetch_review(
        self,
        school_id: int,
        school_name: str,
        urn: str,
    ) -> dict[str, object] | None:
        """Fetch an Ofsted report page and extract review data.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        school_name:
            Human-readable school name (used for logging).
        urn:
            The school's unique reference number, used to build the Ofsted URL.

        Returns
        -------
        dict[str, object] | None
            A parsed review record ready for persistence, or ``None`` if the
            page could not be fetched or no meaningful data was extracted.
            The dict contains keys matching :class:`~src.db.models.SchoolReview`
            columns.
        """
        url = _OFSTED_PROVIDER_URL.format(urn=urn)

        try:
            html = await self.fetch_page(url)
        except Exception:
            self._logger.warning(
                "Failed to fetch Ofsted page for school %r (urn=%s) - skipping",
                school_name,
                urn,
            )
            return None

        return self._parse_review(school_id, school_name, html, url)

    def _parse_review(
        self,
        school_id: int,
        school_name: str,
        html: str,
        source_url: str,
    ) -> dict[str, object] | None:
        """Extract review data from a parsed Ofsted report page.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        school_name:
            Human-readable school name (used for logging).
        html:
            Raw HTML of the Ofsted report page.
        source_url:
            The URL that was fetched (for logging/diagnostics).

        Returns
        -------
        dict[str, object] | None
            Parsed review dict, or ``None`` if no useful data could be
            extracted. Contains: ``school_id``, ``source``, ``rating``,
            ``snippet``, ``review_date``.
        """
        soup = self.parse_html(html)
        page_text = soup.get_text(separator=" ", strip=True)

        # --- Extract numeric rating ---
        rating = self._extract_rating(page_text)

        # --- Extract inspection date ---
        review_date = self._extract_inspection_date(soup, page_text)

        # --- Extract key findings / strengths snippet ---
        snippet = self._extract_snippet(soup, page_text)

        # If we could not extract any meaningful data, skip this school.
        if rating is None and snippet is None and review_date is None:
            self._logger.debug("No review data found on Ofsted page for school %r", school_name)
            return None

        return {
            "school_id": school_id,
            "source": "Ofsted",
            "rating": rating,
            "snippet": snippet[:500] if snippet else None,
            "review_date": review_date,
        }

    def _extract_rating(self, page_text: str) -> float | None:
        """Extract the Ofsted overall effectiveness rating from page text.

        Tries two strategies:

        1. A numeric pattern like ``"Overall effectiveness: 2"``.
        2. A textual pattern like ``"Overall effectiveness: Good"``.

        Parameters
        ----------
        page_text:
            The full text content of the Ofsted page.

        Returns
        -------
        float | None
            The rating on a 1-4 scale, or ``None`` if not found.
        """
        # Strategy 1: numeric rating (1-4).
        match = _RATING_PATTERN.search(page_text)
        if match:
            try:
                value = int(match.group(1))
                if 1 <= value <= 4:
                    return float(value)
            except ValueError:
                pass

        # Strategy 2: textual rating.
        match = _RATING_TEXT_PATTERN.search(page_text)
        if match:
            rating_text = match.group(1).strip().lower()
            # Normalise "requires improvement" variants.
            rating_text = re.sub(r"\s+", " ", rating_text)
            if rating_text in _RATING_MAP:
                return _RATING_MAP[rating_text]

        # Strategy 3: look for standalone rating keywords in common page structures.
        # Ofsted pages often have the rating in heading or badge elements.
        for keyword, value in _RATING_MAP.items():
            # Only match if the keyword appears near "overall" context to avoid
            # false positives from sub-judgement ratings.
            pattern = re.compile(
                rf"overall[^.]*?{re.escape(keyword)}",
                flags=re.IGNORECASE,
            )
            if pattern.search(page_text):
                return value

        return None

    def _extract_inspection_date(self, soup: object, page_text: str) -> datetime.date | None:
        """Extract the most recent inspection date from the Ofsted page.

        Looks for date strings in common formats used on Ofsted report pages.
        When multiple dates are found, returns the most recent one, as it is
        most likely the latest inspection date.

        Parameters
        ----------
        soup:
            A :class:`~bs4.BeautifulSoup` document tree.
        page_text:
            The full text content of the page.

        Returns
        -------
        datetime.date | None
            The inspection date, or ``None`` if not found.
        """
        dates: list[datetime.date] = []

        for match in _DATE_PATTERN.finditer(page_text):
            try:
                day = int(match.group(1))
                month_str = match.group(2)
                year = int(match.group(3))

                month = datetime.datetime.strptime(month_str, "%B").month
                parsed = datetime.date(year, month, day)

                # Sanity check: ignore dates far in the future or before Ofsted existed.
                if datetime.date(1990, 1, 1) <= parsed <= datetime.date.today():
                    dates.append(parsed)
            except (ValueError, OverflowError):
                continue

        if dates:
            # Return the most recent date found.
            return max(dates)

        return None

    def _extract_snippet(self, soup: object, page_text: str) -> str | None:
        """Extract key findings or strengths text from the Ofsted page.

        Searches for common section headings used on Ofsted report pages
        such as "What is it like to attend this school?", "Key findings",
        or "What the school does well".

        Parameters
        ----------
        soup:
            A :class:`~bs4.BeautifulSoup` document tree.
        page_text:
            The full text content of the page.

        Returns
        -------
        str | None
            The extracted snippet text (up to 500 characters), or ``None``
            if no relevant section was found.
        """
        # Section headings commonly found on Ofsted report pages.
        snippet_headings = [
            "what is it like to attend this school",
            "key findings",
            "what the school does well",
            "strengths",
            "overall effectiveness",
        ]

        # Strategy 1: look for heading elements followed by paragraph content.
        for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
            heading_text = heading.get_text(strip=True).lower()
            for target in snippet_headings:
                if target in heading_text:
                    # Collect text from the next sibling paragraphs.
                    paragraphs = []
                    sibling = heading.find_next_sibling()
                    while sibling and sibling.name not in ("h1", "h2", "h3", "h4"):
                        text = sibling.get_text(strip=True)
                        if text:
                            paragraphs.append(text)
                        sibling = sibling.find_next_sibling()
                        # Limit to a reasonable amount of text.
                        if sum(len(p) for p in paragraphs) > 500:
                            break

                    if paragraphs:
                        return " ".join(paragraphs)[:500]

        # Strategy 2: regex-based extraction from the full page text.
        for target in snippet_headings:
            pattern = re.compile(
                rf"{re.escape(target)}\s*[:\-]?\s*(.{{50,500}}?)(?:\.|$)",
                flags=re.IGNORECASE | re.DOTALL,
            )
            match = pattern.search(page_text)
            if match:
                snippet = match.group(1).strip()
                if snippet:
                    return snippet[:500]

        return None

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_to_db(self, records: list[dict[str, object]]) -> None:
        """Write parsed review records to the ``school_reviews`` table.

        Uses a synchronous SQLAlchemy session for simplicity.

        Parameters
        ----------
        records:
            Parsed review dicts as returned by :meth:`_parse_review`.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            for record in records:
                review = SchoolReview(
                    school_id=record["school_id"],
                    source=str(record.get("source", "Ofsted")),
                    rating=record.get("rating"),
                    snippet=record.get("snippet"),
                    review_date=record.get("review_date"),
                )
                session.add(review)
            session.commit()
            self._logger.info("Committed %d review rows", len(records))


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the reviews agent.

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
        description="Collect school reviews from Ofsted report pages for a council.",
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
    """CLI entry point for the reviews agent.

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
    agent = ReviewsAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
