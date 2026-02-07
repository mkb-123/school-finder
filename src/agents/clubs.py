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

import logging
import re
from urllib.parse import urljoin, urlparse

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import School, SchoolClub

logger = logging.getLogger(__name__)

# Keywords that indicate a page might contain club information.
_CLUB_LINK_KEYWORDS: list[str] = [
    "breakfast club",
    "breakfast",
    "after school",
    "after-school",
    "afterschool",
    "wraparound",
    "wrap around",
    "wrap-around",
    "extended services",
    "childcare",
    "before and after",
    "clubs",
]

# Regex for finding club keywords in page text.
_CLUB_TEXT_PATTERN: re.Pattern[str] = re.compile(
    r"breakfast\s+club|after[\s-]?school\s+club|wraparound\s+care|wrap[\s-]?around\s+care|"
    r"before\s+and\s+after\s+school|extended\s+services|childcare",
    flags=re.IGNORECASE,
)

# Common URL path segments where schools put club info.
_COMMON_CLUB_PATHS: list[str] = [
    "/breakfast-club",
    "/after-school-club",
    "/after-school-clubs",
    "/wraparound-care",
    "/wrap-around-care",
    "/wraparound",
    "/extended-services",
    "/clubs",
    "/parents/clubs",
    "/parents/wraparound-care",
    "/parents/breakfast-club",
    "/before-and-after-school-club",
    "/before-after-school",
]

# Time pattern: matches HH:MM with optional am/pm, and HH.MM with optional am/pm
_TIME_PATTERN = re.compile(
    r"(\d{1,2})[:\.](\d{2})\s*(am|pm|AM|PM)?",
)

# Time range pattern: e.g. "7:30am - 8:45am", "07:30 to 08:45", "7.30am-8.45am"
_TIME_RANGE_PATTERN = re.compile(
    r"(\d{1,2})[:\.](\d{2})\s*(am|pm|AM|PM)?\s*[-–—to]+\s*(\d{1,2})[:\.](\d{2})\s*(am|pm|AM|PM)?",
)

# Cost pattern: matches £X.XX or £X
_COST_PATTERN = re.compile(r"£\s*(\d+(?:\.\d{1,2})?)")

# Day patterns
_DAYS_PATTERN = re.compile(
    r"(monday\s*(?:to|-)\s*friday|mon(?:day)?[\s,]*(?:to|-)\s*fri(?:day)?|"
    r"every\s*day|all\s*week|"
    r"(?:mon|tue|wed|thu|fri)(?:day)?(?:\s*[,/&]\s*(?:mon|tue|wed|thu|fri)(?:day)?)+)",
    flags=re.IGNORECASE,
)

# Provider keywords
_KNOWN_PROVIDERS = [
    "fit for sport",
    "premier education",
    "camp beaumont",
    "extend",
    "kidslingo",
    "magic breakfast",
    "primary sports",
    "sports for schools",
    "aspire",
    "abc out of school",
    "active kids",
    "energy kidz",
    "superstars",
    "barracudas",
]


class ClubsAgent(BaseAgent):
    """Discover breakfast and after-school clubs for schools in a council.

    The agent:

    1. Queries the database for all schools belonging to the council.
    2. For each school that has a website URL, fetches the site and
       searches for club-related pages by following links.
    3. Parses club details (name, type, days, times, cost).
    4. Persists results in the ``school_clubs`` table, replacing any
       existing records for that school.

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
        """Execute the clubs data-collection pipeline."""
        self._logger.info("Starting clubs agent for council=%r", self.council)

        schools = self._load_schools()
        if not schools:
            self._logger.warning("No schools found in DB for council=%r", self.council)
            return

        self._logger.info("Found %d schools for council=%r", len(schools), self.council)

        total_clubs_found = 0
        schools_with_clubs = 0

        for school_id, school_name, school_website in schools:
            if not school_website:
                self._logger.debug("School %r (id=%d) has no website – skipping", school_name, school_id)
                continue

            self._logger.info("Processing school %r (id=%d)", school_name, school_id)
            clubs = await self._discover_clubs(school_id, school_name, school_website)

            if clubs:
                # Delete existing clubs for this school, then save new ones
                self._replace_clubs_in_db(school_id, clubs)
                total_clubs_found += len(clubs)
                schools_with_clubs += 1
                self._logger.info("Saved %d club records for school %r", len(clubs), school_name)
            else:
                self._logger.info("No clubs found for school %r", school_name)

        self._logger.info(
            "Clubs agent complete: found %d clubs across %d schools (of %d total)",
            total_clubs_found,
            schools_with_clubs,
            len(schools),
        )

    # ------------------------------------------------------------------
    # Database reads
    # ------------------------------------------------------------------

    def _load_schools(self) -> list[tuple[int, str, str | None]]:
        """Load schools for the configured council from the database."""
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            stmt = select(School.id, School.name, School.website).where(School.council == self.council)
            rows = session.execute(stmt).all()

        return [(row[0], row[1], row[2]) for row in rows]

    # ------------------------------------------------------------------
    # Club discovery - multi-page approach
    # ------------------------------------------------------------------

    async def _discover_clubs(
        self,
        school_id: int,
        school_name: str,
        website_url: str,
    ) -> list[dict[str, object]]:
        """Fetch a school's website and look for club information.

        This follows a multi-step approach:
        1. Fetch the homepage and look for links to club pages
        2. Try common URL patterns for club pages
        3. Fetch all discovered club pages
        4. Parse club details from all gathered content
        """
        # Normalise the base URL - always prefer HTTPS
        if not website_url.startswith(("http://", "https://")):
            website_url = f"https://{website_url}"
        elif website_url.startswith("http://"):
            website_url = "https://" + website_url[7:]
        website_url = website_url.rstrip("/")

        # Step 1: Fetch the homepage
        try:
            homepage_html = await self.fetch_page(website_url)
        except Exception:
            self._logger.warning("Failed to fetch homepage for school %r at %s", school_name, website_url)
            return []

        homepage_soup = self.parse_html(homepage_html)

        # Step 2: Find club-related links on the homepage
        club_page_urls = self._find_club_links(homepage_soup, website_url)

        # Step 3: Only try common URL patterns if no links were found on homepage
        if not club_page_urls:
            common_urls = self._generate_common_urls(website_url)
            club_page_urls.update(common_urls)

        self._logger.debug(
            "Found %d potential club page URLs for school %r",
            len(club_page_urls),
            school_name,
        )

        # Step 4: Gather all text from homepage + club pages
        all_club_text_sections: list[str] = []

        # Check homepage text for club info
        homepage_text = homepage_soup.get_text(separator="\n", strip=True)
        if _CLUB_TEXT_PATTERN.search(homepage_text):
            all_club_text_sections.append(homepage_text)

        # Fetch each club page and collect text
        visited_deeper: set[str] = set()
        for url in club_page_urls:
            page_html = await self._try_fetch(url)
            if page_html is None:
                continue

            page_soup = self.parse_html(page_html)
            page_text = page_soup.get_text(separator="\n", strip=True)

            if _CLUB_TEXT_PATTERN.search(page_text) or any(
                kw in page_text.lower() for kw in ["breakfast", "after school", "wraparound", "club"]
            ):
                all_club_text_sections.append(page_text)
                self._logger.debug("Found club content on page: %s", url)

                # Also follow links from club pages (one level deeper)
                deeper_links = self._find_club_links(page_soup, website_url)
                for deeper_url in deeper_links:
                    if deeper_url not in club_page_urls and deeper_url not in visited_deeper:
                        visited_deeper.add(deeper_url)
                        deeper_html = await self._try_fetch(deeper_url)
                        if deeper_html is None:
                            continue
                        deeper_soup = self.parse_html(deeper_html)
                        deeper_text = deeper_soup.get_text(separator="\n", strip=True)
                        if any(kw in deeper_text.lower() for kw in ["breakfast", "after school", "wraparound", "club"]):
                            all_club_text_sections.append(deeper_text)

        if not all_club_text_sections:
            return []

        # Step 5: Parse club details from all collected text
        combined_text = "\n\n---PAGE_BREAK---\n\n".join(all_club_text_sections)
        clubs = self._parse_clubs_from_text(school_id, combined_text)

        return clubs

    async def _try_fetch(self, url: str) -> str | None:
        """Try to fetch a URL, returning None on 4xx errors instead of raising."""
        try:
            return await self.fetch_page(url)
        except Exception:
            self._logger.debug("Could not fetch %s", url)
            return None

    def _find_club_links(self, soup: object, base_url: str) -> set[str]:
        """Extract URLs from anchor tags that look like they lead to club pages.

        Scans all <a> tags in the document for hrefs or link text containing
        club-related keywords.
        """
        club_urls: set[str] = set()
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc.lower().replace("www.", "")

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            link_text = anchor.get_text(strip=True).lower()
            href_lower = href.lower()

            # Check if link text or href contains club keywords
            is_club_link = any(kw in link_text for kw in _CLUB_LINK_KEYWORDS) or any(
                kw.replace(" ", "-") in href_lower or kw.replace(" ", "") in href_lower for kw in _CLUB_LINK_KEYWORDS
            )

            if not is_club_link:
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url + "/", href)

            # Only follow links on the same domain
            parsed_link = urlparse(full_url)
            link_domain = parsed_link.netloc.lower().replace("www.", "")

            if link_domain == base_domain or not parsed_link.netloc:
                club_urls.add(full_url)

        return club_urls

    def _generate_common_urls(self, base_url: str) -> set[str]:
        """Generate URLs for common club page paths to try."""
        urls: set[str] = set()
        for path in _COMMON_CLUB_PATHS:
            urls.add(f"{base_url}{path}")
        return urls

    # ------------------------------------------------------------------
    # Text parsing
    # ------------------------------------------------------------------

    def _parse_clubs_from_text(self, school_id: int, text: str) -> list[dict[str, object]]:
        """Extract structured club data from combined text content.

        Uses a section-based approach: splits text into logical sections,
        identifies club types, and extracts times/costs from each section.
        """
        clubs: list[dict[str, object]] = []
        found_breakfast = False
        found_afterschool = False

        # Split into paragraphs/sections
        lines = text.split("\n")

        # First pass: look for distinct club sections with details
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            line_lower = line_stripped.lower()

            # Get surrounding context (10 lines before and after)
            context_start = max(0, i - 5)
            context_end = min(len(lines), i + 15)
            context = " ".join(ln.strip() for ln in lines[context_start:context_end] if ln.strip())
            context_lower = context.lower()

            # Detect breakfast club mentions
            if not found_breakfast and any(
                kw in line_lower for kw in ["breakfast club", "breakfast session", "morning club", "early birds"]
            ):
                club = self._extract_club_details(
                    school_id=school_id,
                    club_type="breakfast",
                    default_name="Breakfast Club",
                    line=line_stripped,
                    context=context,
                    context_lower=context_lower,
                )
                if club:
                    clubs.append(club)
                    found_breakfast = True

            # Detect after-school club mentions
            elif not found_afterschool and any(
                kw in line_lower
                for kw in [
                    "after school club",
                    "after-school club",
                    "afterschool club",
                    "after school session",
                    "after-school session",
                    "tea time club",
                ]
            ):
                club = self._extract_club_details(
                    school_id=school_id,
                    club_type="after-school",
                    default_name="After School Club",
                    line=line_stripped,
                    context=context,
                    context_lower=context_lower,
                )
                if club:
                    clubs.append(club)
                    found_afterschool = True

        # Second pass: if we didn't find explicit club headings, look for
        # combined wraparound care sections
        if not found_breakfast and not found_afterschool:
            full_text_lower = text.lower()

            # Check for wraparound care as a combined service
            if "wraparound" in full_text_lower or "wrap around" in full_text_lower or "wrap-around" in full_text_lower:
                # Try to find breakfast and after-school within the wraparound section
                clubs.extend(self._parse_wraparound_section(school_id, text))
            elif "breakfast" in full_text_lower:
                # Even if not found as a heading, try to find breakfast club info
                club = self._extract_club_from_full_text(school_id, "breakfast", "Breakfast Club", text)
                if club:
                    clubs.append(club)
            if not found_afterschool and (
                "after school" in full_text_lower
                or "after-school" in full_text_lower
                or "afterschool" in full_text_lower
            ):
                club = self._extract_club_from_full_text(school_id, "after-school", "After School Club", text)
                if club:
                    clubs.append(club)

        # If still nothing found but the page mentions clubs generically
        if not clubs:
            full_lower = text.lower()
            if "breakfast" in full_lower and ("club" in full_lower or "care" in full_lower):
                clubs.append(
                    {
                        "school_id": school_id,
                        "club_type": "breakfast",
                        "name": "Breakfast Club",
                        "description": None,
                        "days_available": None,
                        "start_time": None,
                        "end_time": None,
                        "cost_per_session": None,
                    }
                )
            if ("after school" in full_lower or "after-school" in full_lower) and (
                "club" in full_lower or "care" in full_lower
            ):
                clubs.append(
                    {
                        "school_id": school_id,
                        "club_type": "after-school",
                        "name": "After School Club",
                        "description": None,
                        "days_available": None,
                        "start_time": None,
                        "end_time": None,
                        "cost_per_session": None,
                    }
                )

        self._logger.info("Extracted %d clubs for school_id=%d", len(clubs), school_id)
        return clubs

    def _extract_club_details(
        self,
        school_id: int,
        club_type: str,
        default_name: str,
        line: str,
        context: str,
        context_lower: str,
    ) -> dict[str, object] | None:
        """Extract detailed club info from a text section."""
        # Try to extract a more specific club name from the heading line
        name = default_name
        if ":" in line:
            # e.g. "Faraday Club: Breakfast and After School Club"
            parts = line.split(":")
            candidate = parts[0].strip()
            if len(candidate) > 3 and len(candidate) < 80:
                name = candidate

        # Extract time range
        start_time, end_time = self._extract_time_range(context, club_type)

        # Extract cost
        cost = self._extract_cost(context_lower, club_type)

        # Extract days
        days = self._extract_days(context_lower)

        # Build description from the line
        desc = line[:300] if line else None

        return {
            "school_id": school_id,
            "club_type": club_type,
            "name": name,
            "description": desc,
            "days_available": days,
            "start_time": start_time,
            "end_time": end_time,
            "cost_per_session": cost,
        }

    def _extract_club_from_full_text(
        self,
        school_id: int,
        club_type: str,
        default_name: str,
        text: str,
    ) -> dict[str, object] | None:
        """Try to extract club details by searching through all the text."""
        text_lower = text.lower()

        start_time, end_time = self._extract_time_range(text, club_type)
        cost = self._extract_cost(text_lower, club_type)
        days = self._extract_days(text_lower)

        return {
            "school_id": school_id,
            "club_type": club_type,
            "name": default_name,
            "description": None,
            "days_available": days,
            "start_time": start_time,
            "end_time": end_time,
            "cost_per_session": cost,
        }

    def _parse_wraparound_section(self, school_id: int, text: str) -> list[dict[str, object]]:
        """Parse a combined wraparound care section for both breakfast and after-school clubs."""
        clubs = []
        text_lower = text.lower()

        # Look for breakfast component
        if "breakfast" in text_lower:
            start_time, end_time = self._extract_time_range(text, "breakfast")
            cost = self._extract_cost(text_lower, "breakfast")
            days = self._extract_days(text_lower)

            clubs.append(
                {
                    "school_id": school_id,
                    "club_type": "breakfast",
                    "name": "Breakfast Club",
                    "description": "Part of wraparound care provision",
                    "days_available": days,
                    "start_time": start_time,
                    "end_time": end_time,
                    "cost_per_session": cost,
                }
            )

        # Look for after-school component
        if "after school" in text_lower or "after-school" in text_lower or "afterschool" in text_lower:
            start_time, end_time = self._extract_time_range(text, "after-school")
            cost = self._extract_cost(text_lower, "after-school")
            days = self._extract_days(text_lower)

            clubs.append(
                {
                    "school_id": school_id,
                    "club_type": "after-school",
                    "name": "After School Club",
                    "description": "Part of wraparound care provision",
                    "days_available": days,
                    "start_time": start_time,
                    "end_time": end_time,
                    "cost_per_session": cost,
                }
            )

        return clubs

    # ------------------------------------------------------------------
    # Detail extractors
    # ------------------------------------------------------------------

    def _extract_time_range(self, text: str, club_type: str) -> tuple[str | None, str | None]:
        """Extract start and end times from text, appropriate for the club type.

        For breakfast clubs, looks for morning times (typically 7:00-9:00).
        For after-school clubs, looks for afternoon times (typically 15:00-18:00).
        """
        # Find all time ranges in the text
        ranges = _TIME_RANGE_PATTERN.findall(text)

        for h1, m1, ampm1, h2, m2, ampm2 in ranges:
            start_h = int(h1)
            start_m = int(m1)
            end_h = int(h2)
            end_m = int(m2)

            # Apply AM/PM conversion
            start_h = self._apply_ampm(start_h, ampm1)
            end_h = self._apply_ampm(end_h, ampm2)

            # If no am/pm specified but times look like 12-hour format
            if not ampm1 and not ampm2:
                # Heuristic: if start < 10 and end < 10, it's probably morning
                # If start >= 1 and start <= 6 and end > start, probably afternoon
                if start_h >= 1 and start_h <= 6 and end_h >= 1 and end_h <= 6:
                    if club_type == "after-school":
                        start_h += 12
                        end_h += 12

            # Validate time range for club type
            if club_type == "breakfast":
                # Breakfast clubs typically run 7:00-9:00
                if 6 <= start_h <= 9 and 7 <= end_h <= 10:
                    return (
                        f"{start_h:02d}:{start_m:02d}",
                        f"{end_h:02d}:{end_m:02d}",
                    )
            elif club_type == "after-school":
                # After-school clubs typically run 15:00-18:00
                if 14 <= start_h <= 16 and 16 <= end_h <= 19:
                    return (
                        f"{start_h:02d}:{start_m:02d}",
                        f"{end_h:02d}:{end_m:02d}",
                    )

        # If no explicit range found, look for individual times
        times = _TIME_PATTERN.findall(text)
        morning_times = []
        afternoon_times = []

        for h, m, ampm in times:
            hour = int(h)
            minute = int(m)
            hour = self._apply_ampm(hour, ampm)

            if 6 <= hour <= 10:
                morning_times.append((hour, minute))
            elif 14 <= hour <= 19:
                afternoon_times.append((hour, minute))

        if club_type == "breakfast" and len(morning_times) >= 2:
            morning_times.sort()
            start = morning_times[0]
            end = morning_times[-1]
            if start != end:
                return (
                    f"{start[0]:02d}:{start[1]:02d}",
                    f"{end[0]:02d}:{end[1]:02d}",
                )

        if club_type == "after-school" and len(afternoon_times) >= 2:
            afternoon_times.sort()
            start = afternoon_times[0]
            end = afternoon_times[-1]
            if start != end:
                return (
                    f"{start[0]:02d}:{start[1]:02d}",
                    f"{end[0]:02d}:{end[1]:02d}",
                )

        return None, None

    @staticmethod
    def _apply_ampm(hour: int, ampm: str | None) -> int:
        """Convert 12-hour time to 24-hour format."""
        if not ampm:
            return hour
        ampm = ampm.lower()
        if ampm == "pm" and hour < 12:
            return hour + 12
        if ampm == "am" and hour == 12:
            return 0
        return hour

    def _extract_cost(self, text_lower: str, club_type: str) -> float | None:
        """Extract cost per session from text.

        Tries to find cost specifically associated with the club type,
        then falls back to any cost mentioned.
        """
        # Look for cost near club type keywords
        club_keywords = {
            "breakfast": ["breakfast"],
            "after-school": ["after school", "after-school", "afterschool"],
        }

        keywords = club_keywords.get(club_type, [])
        all_costs = _COST_PATTERN.findall(text_lower)

        # Try to find cost near a keyword mention
        for kw in keywords:
            # Find positions of keyword in text
            pos = 0
            while True:
                idx = text_lower.find(kw, pos)
                if idx == -1:
                    break

                # Look for cost within 200 chars of the keyword
                nearby_text = text_lower[max(0, idx - 100) : idx + 200]
                nearby_costs = _COST_PATTERN.findall(nearby_text)

                for cost_str in nearby_costs:
                    cost = float(cost_str)
                    # Reasonable cost per session: £1-£25
                    if 1.0 <= cost <= 25.0:
                        return cost

                pos = idx + 1

        # Fall back: find any reasonable cost
        for cost_str in all_costs:
            cost = float(cost_str)
            if club_type == "breakfast" and 1.0 <= cost <= 10.0:
                return cost
            if club_type == "after-school" and 3.0 <= cost <= 25.0:
                return cost

        return None

    def _extract_days(self, text_lower: str) -> str | None:
        """Extract days of availability from text."""
        match = _DAYS_PATTERN.search(text_lower)
        if match:
            days_text = match.group(0).lower()
            if "monday" in days_text and "friday" in days_text:
                return "Mon,Tue,Wed,Thu,Fri"
            if "mon" in days_text and "fri" in days_text:
                return "Mon,Tue,Wed,Thu,Fri"
            if "every day" in days_text or "all week" in days_text:
                return "Mon,Tue,Wed,Thu,Fri"

            # Parse individual day names
            day_map = {
                "mon": "Mon",
                "tue": "Tue",
                "wed": "Wed",
                "thu": "Thu",
                "fri": "Fri",
            }
            found_days = []
            for abbr, full in day_map.items():
                if abbr in days_text:
                    found_days.append(full)
            if found_days:
                return ",".join(found_days)

        return None

    def _extract_provider(self, text_lower: str) -> str | None:
        """Extract third-party provider name if mentioned."""
        for provider in _KNOWN_PROVIDERS:
            if provider in text_lower:
                return provider.title()
        return None

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _replace_clubs_in_db(self, school_id: int, records: list[dict[str, object]]) -> None:
        """Delete existing club records for a school and insert new ones.

        Uses a synchronous SQLAlchemy session for simplicity.
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
            # Delete existing clubs for this school
            session.execute(delete(SchoolClub).where(SchoolClub.school_id == school_id))

            # Insert new records
            for record in records:
                club = SchoolClub(
                    school_id=record["school_id"],
                    club_type=str(record.get("club_type", "unknown")),
                    name=str(record.get("name", "")),
                    description=record.get("description"),
                    days_available=record.get("days_available"),
                    start_time=parse_time(record.get("start_time")),
                    end_time=parse_time(record.get("end_time")),
                    cost_per_session=record.get("cost_per_session"),
                )
                session.add(club)
            session.commit()
            self._logger.info("Committed %d club rows for school_id=%d", len(records), school_id)


if __name__ == "__main__":
    from src.agents.base_agent import run_agent_cli

    run_agent_cli(ClubsAgent, "Discover breakfast & after-school clubs for schools in a council.")
