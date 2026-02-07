"""Holiday Clubs Agent.

For each school belonging to the configured council, this agent visits the
school's website and searches for pages mentioning holiday clubs, holiday
camps, holiday activities, holiday provision, or HAF (Holiday Activities and
Food) programmes.  Extracted holiday club data is stored in the
``holiday_clubs`` table via SQLAlchemy.

Usage
-----
::

    python -m src.agents.holiday_clubs --council "Milton Keynes"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from urllib.parse import urljoin

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import HolidayClub, School

logger = logging.getLogger(__name__)

# Patterns used to identify holiday-club-related pages within a school website.
_HOLIDAY_CLUB_KEYWORDS: list[str] = [
    "holiday club",
    "holiday camp",
    "holiday activity",
    "holiday activities",
    "holiday provision",
    "holiday childcare",
    "holiday programme",
    "holiday program",
    "holiday scheme",
    "holiday care",
    "haf programme",
    "haf program",
    "holiday activities and food",
]

# Regex compiled once for matching holiday club keywords in page text.
_HOLIDAY_CLUB_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _HOLIDAY_CLUB_KEYWORDS),
    flags=re.IGNORECASE,
)

# Pattern for extracting age ranges like "ages 4-11", "4 to 11 years", "aged 5-12"
_AGE_RANGE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:ages?d?|children)\s*(\d{1,2})\s*(?:to|-|–)\s*(\d{1,2})",
    flags=re.IGNORECASE,
)

# Pattern for extracting costs like "£25 per day", "£100 per week", "£30/day"
_COST_PER_DAY_PATTERN: re.Pattern[str] = re.compile(
    r"£(\d+\.?\d*)\s*(?:per\s*day|/\s*day|a\s*day|daily)",
    flags=re.IGNORECASE,
)
_COST_PER_WEEK_PATTERN: re.Pattern[str] = re.compile(
    r"£(\d+\.?\d*)\s*(?:per\s*week|/\s*week|a\s*week|weekly)",
    flags=re.IGNORECASE,
)

# Pattern for extracting times like "8:00am - 6:00pm", "08:00 to 18:00"
_TIME_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{1,2})[:\.](\d{2})\s*(am|pm)?\s*(?:to|-|–|until)\s*(\d{1,2})[:\.](\d{2})\s*(am|pm)?",
    flags=re.IGNORECASE,
)

# Pattern for extracting booking URLs
_BOOKING_URL_PATTERN: re.Pattern[str] = re.compile(
    r"(?:book|register|sign\s*up|enrol)",
    flags=re.IGNORECASE,
)

# Keywords suggesting the school runs the club itself
_SCHOOL_RUN_INDICATORS: list[str] = [
    "our holiday club",
    "school holiday club",
    "we offer",
    "we run",
    "we provide",
    "run by the school",
    "run by our",
    "school-run",
    "school run holiday",
    "on-site holiday",
    "on site holiday",
]


class HolidayClubsAgent(BaseAgent):
    """Discover holiday club/activity provision for schools in a council.

    The agent:

    1. Queries the database for all schools belonging to the council.
    2. For each school that has a website URL, fetches the site and
       searches for holiday-club-related pages.
    3. Parses holiday club details (provider, ages, times, costs).
    4. Persists results in the ``holiday_clubs`` table.

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
        """Execute the holiday clubs data-collection pipeline.

        Steps
        -----
        1. Load the list of schools from the database.
        2. Iterate over each school's website.
        3. Discover and parse holiday club pages.
        4. Persist to the database.
        """
        self._logger.info("Starting holiday clubs agent for council=%r", self.council)

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
            clubs = await self._discover_holiday_clubs(school_id, school_name, school_website)

            if clubs:
                self._save_to_db(clubs)
                self._logger.info("Saved %d holiday club records for school %r", len(clubs), school_name)
            else:
                self._logger.debug("No holiday clubs found for school %r", school_name)

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
            stmt = select(School.id, School.name, School.website).where(School.council == self.council)
            rows = session.execute(stmt).all()

        return [(row[0], row[1], row[2]) for row in rows]

    # ------------------------------------------------------------------
    # Holiday club discovery
    # ------------------------------------------------------------------

    async def _discover_holiday_clubs(
        self,
        school_id: int,
        school_name: str,
        website_url: str,
    ) -> list[dict[str, object]]:
        """Fetch a school's website and look for holiday club information.

        The method first checks the homepage for holiday club keywords.  If
        keywords are found, it also follows any internal links that appear
        to lead to dedicated holiday club pages, giving more context for
        extraction.

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
            Parsed holiday club records ready for persistence.  Each dict
            contains keys matching :class:`~src.db.models.HolidayClub` columns.
        """
        try:
            html = await self.fetch_page(website_url)
        except Exception:
            self._logger.exception("Failed to fetch website for school %r", school_name)
            return []

        soup = self.parse_html(html)
        page_text = soup.get_text(separator=" ", strip=True)

        # Check homepage for holiday club keywords
        if not _HOLIDAY_CLUB_PATTERN.search(page_text):
            # Also check links — some schools only mention holiday clubs in
            # navigation links without the keyword appearing in page body text.
            link_texts = " ".join(a.get_text(strip=True) for a in soup.find_all("a", href=True))
            if not _HOLIDAY_CLUB_PATTERN.search(link_texts):
                self._logger.debug("No holiday club keywords found on homepage of %r", school_name)
                return []

        # Try to find and follow dedicated holiday club sub-pages for richer data.
        sub_page_text = await self._fetch_holiday_club_subpages(soup, website_url, school_name)

        # Combine homepage and sub-page text for parsing.
        combined_text = page_text
        if sub_page_text:
            combined_text = page_text + "\n" + sub_page_text

        return self._parse_holiday_clubs(school_id, school_name, soup, combined_text)

    async def _fetch_holiday_club_subpages(
        self,
        soup: object,
        base_url: str,
        school_name: str,
    ) -> str:
        """Follow links from the homepage that appear to lead to holiday club pages.

        Parameters
        ----------
        soup:
            Parsed homepage HTML.
        base_url:
            The school's homepage URL, used to resolve relative links.
        school_name:
            School name for logging.

        Returns
        -------
        str
            Combined text content from any discovered sub-pages.
        """
        sub_texts: list[str] = []

        for a_tag in soup.find_all("a", href=True):
            link_text = a_tag.get_text(strip=True).lower()
            href = a_tag["href"]

            if not _HOLIDAY_CLUB_PATTERN.search(link_text) and not _HOLIDAY_CLUB_PATTERN.search(href):
                continue

            # Resolve relative URLs.
            full_url = urljoin(base_url, href)

            # Skip external links, mailto, tel, and anchors.
            if full_url.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue

            try:
                sub_html = await self.fetch_page(full_url)
                sub_soup = self.parse_html(sub_html)
                sub_texts.append(sub_soup.get_text(separator=" ", strip=True))
                self._logger.debug("Fetched holiday club sub-page %s for %r", full_url, school_name)
            except Exception:
                self._logger.debug("Failed to fetch sub-page %s for %r", full_url, school_name)

        return "\n".join(sub_texts)

    def _parse_holiday_clubs(
        self,
        school_id: int,
        school_name: str,
        soup: object,
        combined_text: str,
    ) -> list[dict[str, object]]:
        """Extract structured holiday club data from the combined page text.

        This method uses heuristic pattern matching to extract provider names,
        age ranges, costs, times, and booking URLs.  It never fabricates data
        -- if a field cannot be parsed from the page, it is left as ``None``.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        school_name:
            Human-readable school name (used for provider name fallback).
        soup:
            A :class:`~bs4.BeautifulSoup` document tree of the homepage.
        combined_text:
            The combined text from the homepage and any sub-pages.

        Returns
        -------
        list[dict[str, object]]
            Parsed holiday club dicts.  Each contains keys matching the
            :class:`~src.db.models.HolidayClub` columns.
        """
        clubs: list[dict[str, object]] = []

        # Split into sections/paragraphs for context-aware parsing.
        sections = combined_text.split("\n")

        # Track whether we have already created a record to avoid duplicates
        # from repeated mentions of the same club across homepage and sub-pages.
        found_providers: set[str] = set()

        for i, line in enumerate(sections):
            if not _HOLIDAY_CLUB_PATTERN.search(line):
                continue

            # Gather surrounding context (lines before and after).
            context = " ".join(sections[max(0, i - 3) : min(len(sections), i + 8)])

            # --- Provider name ---
            # Try to extract a specific provider name from the context.
            provider_name = self._extract_provider_name(context, school_name)

            # Skip if we already recorded this provider for this school.
            provider_key = provider_name.lower().strip()
            if provider_key in found_providers:
                continue
            found_providers.add(provider_key)

            # --- Is school-run? ---
            is_school_run = self._detect_school_run(context)

            # --- Age range ---
            age_from: int | None = None
            age_to: int | None = None
            age_match = _AGE_RANGE_PATTERN.search(context)
            if age_match:
                try:
                    age_from = int(age_match.group(1))
                    age_to = int(age_match.group(2))
                except (ValueError, IndexError):
                    pass

            # --- Times ---
            start_time: str | None = None
            end_time: str | None = None
            time_match = _TIME_PATTERN.search(context)
            if time_match:
                start_time, end_time = self._parse_time_match(time_match)

            # --- Costs ---
            cost_per_day: float | None = None
            cost_per_week: float | None = None
            day_cost_match = _COST_PER_DAY_PATTERN.search(context)
            if day_cost_match:
                try:
                    cost_per_day = float(day_cost_match.group(1))
                except ValueError:
                    pass
            week_cost_match = _COST_PER_WEEK_PATTERN.search(context)
            if week_cost_match:
                try:
                    cost_per_week = float(week_cost_match.group(1))
                except ValueError:
                    pass

            # --- Booking URL ---
            booking_url = self._extract_booking_url(soup, context)

            # --- Available weeks ---
            available_weeks = self._extract_available_weeks(context)

            # --- Description ---
            # Use the matched line itself (trimmed) as the description.
            description = line.strip()[:500] if line.strip() else None

            clubs.append(
                {
                    "school_id": school_id,
                    "provider_name": provider_name,
                    "is_school_run": is_school_run,
                    "description": description,
                    "age_from": age_from,
                    "age_to": age_to,
                    "start_time": start_time,
                    "end_time": end_time,
                    "cost_per_day": cost_per_day,
                    "cost_per_week": cost_per_week,
                    "available_weeks": available_weeks,
                    "booking_url": booking_url,
                }
            )

        self._logger.info("Extracted %d holiday clubs for school_id=%d", len(clubs), school_id)
        return clubs

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_provider_name(context: str, school_name: str) -> str:
        """Attempt to extract a holiday club provider name from surrounding text.

        Looks for patterns like "provided by X", "run by X", or a capitalised
        name directly before/after "holiday club".  Falls back to the school
        name if no provider can be identified.

        Parameters
        ----------
        context:
            Surrounding text block for the holiday club mention.
        school_name:
            The school's name, used as a fallback provider name.

        Returns
        -------
        str
            The best-guess provider name.
        """
        # Try "provided by <Name>", "run by <Name>", "delivered by <Name>"
        provider_match = re.search(
            r"(?:provided|run|delivered|operated|managed|organised|organized)\s+by\s+([A-Z][A-Za-z\s&']+?)(?:\.|,|\s{2,}|$)",
            context,
        )
        if provider_match:
            name = provider_match.group(1).strip()
            if len(name) > 2:
                return name

        # Try "X Holiday Club" where X is a capitalised name
        named_club_match = re.search(
            r"([A-Z][A-Za-z\s&']{2,30}?)\s+(?:Holiday\s+Club|Holiday\s+Camp|Holiday\s+Activities)",
            context,
        )
        if named_club_match:
            name = named_club_match.group(1).strip()
            # Avoid returning generic words like "Our" or "The"
            if name.lower() not in {"our", "the", "a", "this", "school"}:
                return name

        # Fallback: use the school name
        return school_name

    @staticmethod
    def _detect_school_run(context: str) -> bool:
        """Determine whether the holiday club appears to be run by the school.

        Parameters
        ----------
        context:
            Surrounding text block for the holiday club mention.

        Returns
        -------
        bool
            ``True`` if the text suggests the school runs the club itself.
        """
        context_lower = context.lower()
        for indicator in _SCHOOL_RUN_INDICATORS:
            if indicator in context_lower:
                return True

        # If text mentions an external provider name, it is likely not school-run.
        external_match = re.search(
            r"(?:provided|run|delivered|operated)\s+by\s+",
            context_lower,
        )
        if external_match:
            return False

        # Default: unknown, assume not school-run to avoid false positives.
        return False

    @staticmethod
    def _parse_time_match(match: re.Match) -> tuple[str | None, str | None]:
        """Convert a time regex match into ``(start_time, end_time)`` strings.

        Parameters
        ----------
        match:
            A regex match from ``_TIME_PATTERN``.

        Returns
        -------
        tuple[str | None, str | None]
            Start and end times in ``"HH:MM"`` format, or ``None`` if
            parsing fails.
        """
        try:
            h1, m1, ampm1, h2, m2, ampm2 = match.groups()
            h1, m1, h2, m2 = int(h1), int(m1), int(h2), int(m2)

            # Adjust for AM/PM if present.
            if ampm1 and ampm1.lower() == "pm" and h1 < 12:
                h1 += 12
            if ampm1 and ampm1.lower() == "am" and h1 == 12:
                h1 = 0
            if ampm2 and ampm2.lower() == "pm" and h2 < 12:
                h2 += 12
            if ampm2 and ampm2.lower() == "am" and h2 == 12:
                h2 = 0

            start_time = f"{h1:02d}:{m1:02d}"
            end_time = f"{h2:02d}:{m2:02d}"
            return start_time, end_time
        except (ValueError, AttributeError):
            return None, None

    @staticmethod
    def _extract_booking_url(soup: object, context: str) -> str | None:
        """Try to find a booking URL from the page HTML.

        Looks for ``<a>`` tags whose text or href suggests a booking page
        related to holiday clubs.

        Parameters
        ----------
        soup:
            Parsed HTML document tree.
        context:
            Surrounding text for the holiday club mention (not used directly,
            but kept for potential future heuristics).

        Returns
        -------
        str | None
            A booking URL if found, otherwise ``None``.
        """
        for a_tag in soup.find_all("a", href=True):
            link_text = a_tag.get_text(strip=True).lower()
            href = a_tag["href"].lower()

            # Check if the link text or href mentions booking AND holiday.
            has_booking = _BOOKING_URL_PATTERN.search(link_text) or _BOOKING_URL_PATTERN.search(href)
            has_holiday = _HOLIDAY_CLUB_PATTERN.search(link_text) or _HOLIDAY_CLUB_PATTERN.search(href)

            if has_booking and has_holiday:
                url = a_tag["href"]
                if not url.startswith(("mailto:", "tel:", "javascript:", "#")):
                    return url

        # Also check for any link that just mentions booking in a holiday context.
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].lower()
            if "holiday" in href and ("book" in href or "register" in href):
                url = a_tag["href"]
                if not url.startswith(("mailto:", "tel:", "javascript:", "#")):
                    return url

        return None

    @staticmethod
    def _extract_available_weeks(context: str) -> str | None:
        """Try to determine which holiday periods the club operates during.

        Looks for mentions of specific holiday periods (Easter, summer,
        half-term, Christmas, etc.) in the surrounding text.

        Parameters
        ----------
        context:
            Surrounding text block for the holiday club mention.

        Returns
        -------
        str | None
            A comma-separated string of holiday periods (e.g.
            ``"Easter, Summer, October half-term"``), or ``None`` if
            nothing can be determined.
        """
        context_lower = context.lower()
        periods: list[str] = []

        period_keywords = [
            ("Easter", ["easter"]),
            ("Summer", ["summer holiday", "summer break", "summer"]),
            ("Christmas", ["christmas", "winter break"]),
            ("February half-term", ["february half", "feb half"]),
            ("May half-term", ["may half", "whitsun"]),
            ("October half-term", ["october half", "oct half", "autumn half"]),
        ]

        for period_name, keywords in period_keywords:
            for kw in keywords:
                if kw in context_lower:
                    if period_name not in periods:
                        periods.append(period_name)
                    break

        return ", ".join(periods) if periods else None

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_to_db(self, records: list[dict[str, object]]) -> None:
        """Write parsed holiday club records to the ``holiday_clubs`` table.

        Uses a synchronous SQLAlchemy session for simplicity.

        Parameters
        ----------
        records:
            Parsed holiday club dicts as returned by
            :meth:`_parse_holiday_clubs`.
        """
        from datetime import time as time_obj

        def parse_time(time_str: str | None) -> time_obj | None:
            """Convert time string like '10:30' to datetime.time object."""
            if not time_str:
                return None
            try:
                parts = time_str.split(":")
                if len(parts) >= 2:
                    hour = int(parts[0])
                    minute = int(parts[1])
                    return time_obj(hour, minute)
            except (ValueError, AttributeError):
                pass
            return None

        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            for record in records:
                club = HolidayClub(
                    school_id=record["school_id"],
                    provider_name=str(record.get("provider_name", "")),
                    is_school_run=bool(record.get("is_school_run", False)),
                    description=record.get("description"),
                    age_from=record.get("age_from"),
                    age_to=record.get("age_to"),
                    start_time=parse_time(record.get("start_time")),
                    end_time=parse_time(record.get("end_time")),
                    cost_per_day=record.get("cost_per_day"),
                    cost_per_week=record.get("cost_per_week"),
                    available_weeks=record.get("available_weeks"),
                    booking_url=record.get("booking_url"),
                )
                session.add(club)
            session.commit()
            self._logger.info("Committed %d holiday club rows", len(records))


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the holiday clubs agent.

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
        description="Discover holiday clubs/activities for schools in a council.",
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
    """CLI entry point for the holiday clubs agent.

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
    agent = HolidayClubsAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
