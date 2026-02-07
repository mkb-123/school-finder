"""Bus Routes Agent: School transport / bus route data collection.

For each school belonging to the configured council, this agent visits the
school's website and searches for pages mentioning school bus services,
transport options, or bus routes.  Extracted route data is stored in the
``bus_routes`` table via SQLAlchemy.

Usage
-----
::

    python -m src.agents.bus_routes --council "Milton Keynes"
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
from src.db.models import BusRoute, School

logger = logging.getLogger(__name__)

# Patterns used to identify transport-related pages within a school website.
_TRANSPORT_KEYWORDS: list[str] = [
    "school bus",
    "bus route",
    "bus service",
    "bus transport",
    "travel to school",
    "transport to school",
    "school transport",
    "dedicated bus",
    "school coach",
    "home to school transport",
]

# Regex compiled once for matching transport keywords in page text.
_TRANSPORT_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _TRANSPORT_KEYWORDS),
    flags=re.IGNORECASE,
)


class BusRoutesAgent(BaseAgent):
    """Discover bus/transport routes for schools in a council.

    The agent:

    1. Queries the database for all schools belonging to the council.
    2. For each school that has a website URL, fetches the site and
       searches for transport-related pages.
    3. Parses route details (name, provider, type, eligibility, cost,
       schedule).
    4. Persists results in the ``bus_routes`` table.

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
        """Execute the bus routes data-collection pipeline.

        Steps
        -----
        1. Load the list of schools from the database.
        2. Iterate over each school's website.
        3. Discover and parse transport/bus route pages.
        4. Persist to the database.
        """
        self._logger.info("Starting bus routes agent for council=%r", self.council)

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
            routes = await self._discover_routes(school_id, school_name, school_website)

            if routes:
                self._save_to_db(routes)
                self._logger.info("Saved %d bus route records for school %r", len(routes), school_name)
            else:
                self._logger.debug("No bus routes found for school %r", school_name)

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
    # Route discovery
    # ------------------------------------------------------------------

    async def _discover_routes(
        self,
        school_id: int,
        school_name: str,
        website_url: str,
    ) -> list[dict[str, object]]:
        """Fetch a school's website and look for bus/transport information.

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
            Parsed route records ready for persistence.  Each dict contains
            keys matching :class:`~src.db.models.BusRoute` columns.
        """
        try:
            html = await self.fetch_page(website_url)
        except Exception:
            self._logger.exception("Failed to fetch website for school %r", school_name)
            return []

        soup = self.parse_html(html)
        page_text = soup.get_text(separator=" ", strip=True)

        if not _TRANSPORT_PATTERN.search(page_text):
            self._logger.debug("No transport keywords found on homepage of %r", school_name)
            return []

        # Try to find dedicated transport page links
        transport_links = self._find_transport_links(soup, website_url)
        if transport_links:
            # Fetch and parse each linked transport page
            all_routes: list[dict[str, object]] = []
            for link_url in transport_links:
                try:
                    link_html = await self.fetch_page(link_url)
                    link_soup = self.parse_html(link_html)
                    routes = self._parse_routes(school_id, link_soup)
                    all_routes.extend(routes)
                except Exception:
                    self._logger.exception("Failed to fetch transport link %s for school %r", link_url, school_name)
            if all_routes:
                return all_routes

        # Fall back to parsing the homepage itself
        return self._parse_routes(school_id, soup)

    def _find_transport_links(self, soup: object, base_url: str) -> list[str]:
        """Find links to dedicated transport/bus pages from the homepage.

        Parameters
        ----------
        soup:
            A :class:`~bs4.BeautifulSoup` document tree of the homepage.
        base_url:
            The base URL for resolving relative links.

        Returns
        -------
        list[str]
            Absolute URLs to transport-related pages.
        """
        from urllib.parse import urljoin

        link_keywords = re.compile(
            r"school\s*bus|transport|bus\s*route|bus\s*service|travel\s*to\s*school",
            flags=re.IGNORECASE,
        )

        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            anchor_text = anchor.get_text(strip=True)
            href = anchor["href"]

            if link_keywords.search(anchor_text) or link_keywords.search(href):
                absolute_url = urljoin(base_url, href)
                if absolute_url not in links:
                    links.append(absolute_url)

        return links[:5]  # Limit to avoid excessive crawling

    def _parse_routes(self, school_id: int, soup: object) -> list[dict[str, object]]:
        """Extract structured bus route data from the parsed HTML.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        soup:
            A :class:`~bs4.BeautifulSoup` document tree.

        Returns
        -------
        list[dict[str, object]]
            Parsed route dicts.  Each contains keys matching
            :class:`~src.db.models.BusRoute` columns:
            ``school_id``, ``route_name``, ``provider``, ``route_type``,
            ``distance_eligibility_km``, ``year_groups_eligible``,
            ``eligibility_notes``, ``is_free``, ``cost_per_term``,
            ``cost_per_year``, ``cost_notes``, ``operates_days``,
            ``morning_departure_time``, ``afternoon_departure_time``,
            ``booking_url``, ``notes``.
        """
        routes: list[dict[str, object]] = []

        text = soup.get_text(separator="\n", strip=True)
        sections = text.split("\n")

        # Track whether we have found at least one route mention so we can
        # create a generic record when no structured data is available.
        found_route_section = False

        # Pattern to detect named routes (e.g. "Route 1", "Route A – Bletchley")
        route_name_pattern = re.compile(
            r"(route\s+[a-z0-9]+(?:\s*[-–—:]\s*\S.*)?)",
            flags=re.IGNORECASE,
        )

        # Pattern to detect provider names (e.g. "operated by Arriva", "provider: Stagecoach")
        provider_pattern = re.compile(
            r"(?:operated\s+by|provider[:\s]+|run\s+by)\s+([A-Z][\w\s&'-]+)",
            flags=re.IGNORECASE,
        )

        # Distance eligibility (e.g. "2 miles", "3km", "3.0 kilometres")
        distance_pattern = re.compile(
            r"(\d+\.?\d*)\s*(?:miles?|mi)\b|(\d+\.?\d*)\s*(?:km|kilometres?|kilometers?)\b",
            flags=re.IGNORECASE,
        )

        # Cost patterns
        cost_term_pattern = re.compile(r"£(\d+\.?\d*)\s*(?:per\s+)?term", flags=re.IGNORECASE)
        cost_year_pattern = re.compile(r"£(\d+\.?\d*)\s*(?:per\s+)?(?:year|annum|annually)", flags=re.IGNORECASE)
        free_pattern = re.compile(r"\bfree\s+(?:school\s+)?(?:bus|transport)\b", flags=re.IGNORECASE)

        # Time patterns (HH:MM with optional am/pm)
        time_pattern = re.compile(
            r"(\d{1,2})[:\.](\d{2})\s*(am|pm)?",
            flags=re.IGNORECASE,
        )

        # Year group patterns
        year_group_pattern = re.compile(
            r"(?:year(?:s)?\s+(\d+)\s*[-–to]+\s*(\d+))|(?:reception|nursery|sixth\s+form)",
            flags=re.IGNORECASE,
        )

        for i, line in enumerate(sections):
            line_lower = line.lower()

            # Check if this line references a bus route or transport service
            is_route_line = False
            route_name = None

            route_match = route_name_pattern.search(line)
            if route_match:
                is_route_line = True
                route_name = route_match.group(1).strip()
            elif any(
                kw in line_lower
                for kw in [
                    "school bus",
                    "bus service",
                    "dedicated bus",
                    "school coach",
                    "bus route",
                    "transport service",
                ]
            ):
                is_route_line = True

            if not is_route_line:
                continue

            found_route_section = True

            # Default route name if none extracted
            if not route_name:
                route_name = "School Bus Service"

            # Build context from surrounding lines for detail extraction
            context = " ".join(sections[max(0, i - 2) : min(len(sections), i + 8)])

            # Extract provider
            provider = None
            provider_match = provider_pattern.search(context)
            if provider_match:
                provider = provider_match.group(1).strip()

            # Determine route type
            route_type = "dedicated"
            if any(kw in context.lower() for kw in ["public bus", "public transport", "public service"]):
                route_type = "public"

            # Extract distance eligibility
            distance_km = None
            dist_match = distance_pattern.search(context)
            if dist_match:
                if dist_match.group(1):
                    # Miles — convert to km
                    distance_km = round(float(dist_match.group(1)) * 1.60934, 2)
                elif dist_match.group(2):
                    distance_km = float(dist_match.group(2))

            # Extract year groups
            year_groups = None
            yg_match = year_group_pattern.search(context)
            if yg_match:
                if yg_match.group(1) and yg_match.group(2):
                    year_groups = f"Year {yg_match.group(1)}-{yg_match.group(2)}"
                else:
                    year_groups = yg_match.group(0).strip()

            # Extract eligibility notes — grab the sentence containing "eligible" or "eligibility"
            eligibility_notes = None
            eligibility_match = re.search(
                r"[^.]*(?:eligible|eligibility|entitled|entitlement)[^.]*\.",
                context,
                flags=re.IGNORECASE,
            )
            if eligibility_match:
                eligibility_notes = eligibility_match.group(0).strip()

            # Cost extraction
            is_free = bool(free_pattern.search(context))
            cost_per_term = None
            cost_per_year = None
            cost_notes = None

            ct_match = cost_term_pattern.search(context)
            if ct_match:
                cost_per_term = float(ct_match.group(1))

            cy_match = cost_year_pattern.search(context)
            if cy_match:
                cost_per_year = float(cy_match.group(1))

            # Grab any sentence mentioning cost/price/fee as cost_notes
            cost_note_match = re.search(
                r"[^.]*(?:cost|price|fee|charge|£)[^.]*\.",
                context,
                flags=re.IGNORECASE,
            )
            if cost_note_match:
                cost_notes = cost_note_match.group(0).strip()

            # Schedule
            operates_days = None
            if re.search(r"mon(?:day)?\s*[-–to]+\s*fri(?:day)?", context, flags=re.IGNORECASE):
                operates_days = "Mon-Fri"

            # Times — attempt to find morning and afternoon departure times
            morning_time = None
            afternoon_time = None
            time_matches = time_pattern.findall(context)
            if len(time_matches) >= 2:
                morning_time = self._normalise_time(time_matches[0])
                afternoon_time = self._normalise_time(time_matches[1])
            elif len(time_matches) == 1:
                # Single time — guess morning if before noon
                t = self._normalise_time(time_matches[0])
                if t and int(t.split(":")[0]) < 12:
                    morning_time = t
                else:
                    afternoon_time = t

            # Booking URL — look for links near the context
            booking_url = None
            for anchor in soup.find_all("a", href=True):
                anchor_text = anchor.get_text(strip=True).lower()
                href_lower = anchor["href"].lower()
                if any(kw in anchor_text or kw in href_lower for kw in ["book", "apply", "register"]):
                    if any(kw in anchor_text or kw in href_lower for kw in ["bus", "transport"]):
                        booking_url = anchor["href"]
                        break

            # Build route record — only include fields we actually found
            routes.append(
                {
                    "school_id": school_id,
                    "route_name": route_name,
                    "provider": provider,
                    "route_type": route_type,
                    "distance_eligibility_km": distance_km,
                    "year_groups_eligible": year_groups,
                    "eligibility_notes": eligibility_notes,
                    "is_free": is_free,
                    "cost_per_term": cost_per_term,
                    "cost_per_year": cost_per_year,
                    "cost_notes": cost_notes,
                    "operates_days": operates_days,
                    "morning_departure_time": morning_time,
                    "afternoon_departure_time": afternoon_time,
                    "booking_url": booking_url,
                    "notes": line[:500] if line else None,
                }
            )

        # If transport keywords were found on the page but no structured routes
        # could be extracted, create a single generic record so we know the
        # school mentions transport without fabricating details.
        if not routes and not found_route_section:
            full_text = soup.get_text(separator=" ", strip=True)
            if _TRANSPORT_PATTERN.search(full_text):
                # Extract any useful context around the first mention
                match = _TRANSPORT_PATTERN.search(full_text)
                if match:
                    start = max(0, match.start() - 100)
                    end = min(len(full_text), match.end() + 200)
                    snippet = full_text[start:end].strip()

                    routes.append(
                        {
                            "school_id": school_id,
                            "route_name": "School Transport Service",
                            "provider": None,
                            "route_type": "dedicated",
                            "distance_eligibility_km": None,
                            "year_groups_eligible": None,
                            "eligibility_notes": None,
                            "is_free": False,
                            "cost_per_term": None,
                            "cost_per_year": None,
                            "cost_notes": None,
                            "operates_days": None,
                            "morning_departure_time": None,
                            "afternoon_departure_time": None,
                            "booking_url": None,
                            "notes": snippet[:500] if snippet else None,
                        }
                    )

        self._logger.info("Extracted %d bus routes for school_id=%d", len(routes), school_id)
        return routes

    @staticmethod
    def _normalise_time(time_tuple: tuple[str, str, str]) -> str | None:
        """Convert a regex time match tuple into an ``HH:MM`` string.

        Parameters
        ----------
        time_tuple:
            A 3-element tuple of ``(hour, minute, am_pm)`` as captured
            by the time regex pattern.

        Returns
        -------
        str | None
            A normalised ``HH:MM`` string, or ``None`` on parse failure.
        """
        try:
            hour = int(time_tuple[0])
            minute = int(time_tuple[1])
            am_pm = time_tuple[2].lower() if time_tuple[2] else ""

            if am_pm == "pm" and hour < 12:
                hour += 12
            elif am_pm == "am" and hour == 12:
                hour = 0

            return f"{hour:02d}:{minute:02d}"
        except (ValueError, IndexError):
            return None

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_to_db(self, records: list[dict[str, object]]) -> None:
        """Write parsed bus route records to the ``bus_routes`` table.

        Uses a synchronous SQLAlchemy session for simplicity.

        Parameters
        ----------
        records:
            Parsed route dicts as returned by :meth:`_parse_routes`.
        """
        from datetime import time as time_obj

        def parse_time(time_str: str | None) -> time_obj | None:
            """Convert time string like '08:15' to datetime.time object."""
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
                route = BusRoute(
                    school_id=record["school_id"],
                    route_name=str(record.get("route_name", "School Bus Service")),
                    provider=record.get("provider"),
                    route_type=str(record.get("route_type", "dedicated")),
                    distance_eligibility_km=record.get("distance_eligibility_km"),
                    year_groups_eligible=record.get("year_groups_eligible"),
                    eligibility_notes=record.get("eligibility_notes"),
                    is_free=bool(record.get("is_free", False)),
                    cost_per_term=record.get("cost_per_term"),
                    cost_per_year=record.get("cost_per_year"),
                    cost_notes=record.get("cost_notes"),
                    operates_days=record.get("operates_days"),
                    morning_departure_time=parse_time(record.get("morning_departure_time")),
                    afternoon_departure_time=parse_time(record.get("afternoon_departure_time")),
                    booking_url=record.get("booking_url"),
                    notes=record.get("notes"),
                )
                session.add(route)
            session.commit()
            self._logger.info("Committed %d bus route rows", len(records))


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the bus routes agent.

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
        description="Discover bus routes and transport services for schools in a council.",
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
    """CLI entry point for the bus routes agent.

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
    agent = BusRoutesAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
