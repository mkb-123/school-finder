"""Absence & Attendance Policy Scraper Agent.

For each school belonging to the configured council, this agent visits the
school's website and searches for pages mentioning attendance policies,
absence procedures, term-time holiday policies, and fining information.
Extracted policy data is stored in the ``absence_policies`` table via
SQLAlchemy.

Usage
-----
::

    python -m src.agents.absence_policies --council "Milton Keynes"
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import AbsencePolicy, School

logger = logging.getLogger(__name__)

# Keywords used to identify attendance/absence-related pages on a school website.
_ABSENCE_KEYWORDS: list[str] = [
    "attendance",
    "absence",
    "absent",
    "term time holiday",
    "term-time holiday",
    "unauthorised absence",
    "unauthorized absence",
    "penalty notice",
    "fixed penalty",
    "fines for absence",
    "leave of absence",
]

# Regex compiled once for matching absence keywords in page text.
_ABSENCE_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _ABSENCE_KEYWORDS),
    flags=re.IGNORECASE,
)

# Common URL paths where schools publish attendance/absence policies.
_COMMON_POLICY_PATHS: list[str] = [
    "/attendance",
    "/absence-policy",
    "/policies/attendance",
    "/policies/absence",
    "/attendance-policy",
    "/parents/attendance",
    "/key-information/attendance",
    "/key-information/policies/attendance",
]

# Pattern to detect fine amounts (e.g. £160, £80, £60).
_FINE_AMOUNT_PATTERN: re.Pattern[str] = re.compile(
    r"£(\d+(?:\.\d{1,2})?)\s*(?:per parent|per carer|fine|penalty)",
    flags=re.IGNORECASE,
)

# Pattern to detect fining threshold in days.
_THRESHOLD_DAYS_PATTERN: re.Pattern[str] = re.compile(
    r"(\d+)\s*(?:sessions?|days?)\s*(?:of\s+)?(?:unauthorised|un-authorised)?\s*(?:absence|missed)",
    flags=re.IGNORECASE,
)

# Phrases that indicate the school is strict about term-time holidays.
_STRICT_INDICATORS: list[str] = [
    "will not authorise",
    "will not be authorised",
    "cannot authorise",
    "cannot be authorised",
    "not authorise any",
    "no holidays will be authorised",
    "no leave of absence",
    "unable to authorise",
    "holiday will not",
    "holidays are not authorised",
    "not grant leave",
    "leave will not be granted",
    "zero tolerance",
]

_STRICT_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(phrase) for phrase in _STRICT_INDICATORS),
    flags=re.IGNORECASE,
)

# Phrases that indicate the school may authorise holidays in exceptional circumstances.
_EXCEPTIONAL_PATTERN: re.Pattern[str] = re.compile(
    r"exceptional\s+circumstances?",
    flags=re.IGNORECASE,
)


class AbsencePoliciesAgent(BaseAgent):
    """Collect absence/attendance policy information for schools in a council.

    The agent:

    1. Queries the database for all schools belonging to the council.
    2. For each school that has a website URL, fetches the site and
       searches for attendance/absence-related pages.
    3. Parses policy details (fines, strictness, holiday policy text).
    4. Persists results in the ``absence_policies`` table.

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
        """Execute the absence policy data-collection pipeline.

        Steps
        -----
        1. Load the list of schools from the database.
        2. Iterate over each school's website.
        3. Discover and parse absence/attendance policy pages.
        4. Persist to the database.
        """
        self._logger.info("Starting absence policies agent for council=%r", self.council)

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
            policy = await self._discover_policy(school_id, school_name, school_website)

            if policy:
                self._save_to_db([policy])
                self._logger.info("Saved absence policy record for school %r", school_name)
            else:
                self._logger.debug("No absence policy found for school %r", school_name)

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
    # Policy discovery
    # ------------------------------------------------------------------

    async def _discover_policy(
        self,
        school_id: int,
        school_name: str,
        website_url: str,
    ) -> dict[str, object] | None:
        """Fetch a school's website and look for absence/attendance policy information.

        The method first checks the homepage for absence-related keywords or
        links.  If keywords are found on the homepage, it parses that page.
        Otherwise, it tries a set of common URL paths where schools typically
        publish their attendance policy.

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
        dict[str, object] | None
            Parsed policy record ready for persistence, or ``None`` if no
            attendance policy information could be found.  Dict keys match
            :class:`~src.db.models.AbsencePolicy` columns.
        """
        # Normalise the base URL.
        if not website_url.startswith(("http://", "https://")):
            website_url = f"https://{website_url}"
        base_url = website_url.rstrip("/")

        # Step 1: Try to fetch the homepage and look for absence-related content.
        try:
            html = await self.fetch_page(base_url)
        except Exception:
            self._logger.exception("Failed to fetch homepage for school %r", school_name)
            return None

        soup = self.parse_html(html)
        page_text = soup.get_text(separator=" ", strip=True)

        # Check if the homepage itself contains relevant content.
        if _ABSENCE_PATTERN.search(page_text):
            self._logger.debug("Found absence keywords on homepage of %r", school_name)
            policy = self._parse_policy(school_id, soup, base_url)
            if policy:
                return policy

        # Step 2: Look for links on the homepage that point to policy pages.
        policy_url = self._find_policy_link(soup, base_url)
        if policy_url:
            self._logger.debug("Found policy link %s for school %r", policy_url, school_name)
            try:
                policy_html = await self.fetch_page(policy_url)
                policy_soup = self.parse_html(policy_html)
                policy = self._parse_policy(school_id, policy_soup, policy_url)
                if policy:
                    return policy
            except Exception:
                self._logger.debug("Failed to fetch policy link %s for school %r", policy_url, school_name)

        # Step 3: Try common URL paths.
        for path in _COMMON_POLICY_PATHS:
            candidate_url = base_url + path
            try:
                candidate_html = await self.fetch_page(candidate_url)
            except Exception:
                self._logger.debug("Path %s not found for school %r", path, school_name)
                continue

            candidate_soup = self.parse_html(candidate_html)
            candidate_text = candidate_soup.get_text(separator=" ", strip=True)

            if _ABSENCE_PATTERN.search(candidate_text):
                self._logger.debug("Found absence content at %s for school %r", candidate_url, school_name)
                policy = self._parse_policy(school_id, candidate_soup, candidate_url)
                if policy:
                    return policy

        return None

    def _find_policy_link(self, soup: object, base_url: str) -> str | None:
        """Search the parsed homepage for a link to an attendance/absence policy page.

        Parameters
        ----------
        soup:
            A :class:`~bs4.BeautifulSoup` document tree of the homepage.
        base_url:
            The base URL of the school website, used to resolve relative links.

        Returns
        -------
        str | None
            The absolute URL of the policy page, or ``None`` if no relevant
            link was found.
        """
        for link in soup.find_all("a", href=True):
            link_text = link.get_text(strip=True).lower()
            href = link["href"].lower()

            if any(kw in link_text or kw in href for kw in ["attendance", "absence", "absence-policy"]):
                raw_href = link["href"]
                if raw_href.startswith(("http://", "https://")):
                    return raw_href
                return urljoin(base_url, raw_href)

        return None

    def _parse_policy(
        self,
        school_id: int,
        soup: object,
        source_url: str,
    ) -> dict[str, object] | None:
        """Extract structured absence policy data from the parsed HTML.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        soup:
            A :class:`~bs4.BeautifulSoup` document tree.
        source_url:
            The URL from which the page was fetched (stored for provenance).

        Returns
        -------
        dict[str, object] | None
            Parsed policy dict with keys matching
            :class:`~src.db.models.AbsencePolicy` columns, or ``None`` if
            insufficient policy content was found.
        """
        text = soup.get_text(separator="\n", strip=True)

        # Only proceed if we have meaningful attendance/absence content.
        absence_matches = _ABSENCE_PATTERN.findall(text)
        if len(absence_matches) < 2:
            # A single mention is likely incidental (e.g. a nav link); require
            # at least two mentions to consider the page substantive.
            return None

        # --- Determine whether the school issues fines ---
        issues_fines = False
        fine_amount: float | None = None
        fining_threshold_days: int | None = None

        fine_keywords = re.compile(
            r"penalty\s+notice|fixed\s+penalty|fine|fined|fining|£\d+\s*per\s*parent",
            flags=re.IGNORECASE,
        )
        if fine_keywords.search(text):
            issues_fines = True

            # Try to extract the fine amount.
            fine_match = _FINE_AMOUNT_PATTERN.search(text)
            if fine_match:
                try:
                    fine_amount = float(fine_match.group(1))
                except (ValueError, TypeError):
                    pass

            # Try to extract the fining threshold in days/sessions.
            threshold_match = _THRESHOLD_DAYS_PATTERN.search(text)
            if threshold_match:
                try:
                    fining_threshold_days = int(threshold_match.group(1))
                except (ValueError, TypeError):
                    pass

        # --- Determine strictness level ---
        strictness_level: str | None = None
        if _STRICT_PATTERN.search(text):
            strictness_level = "strict"
        elif _ABSENCE_PATTERN.search(text):
            strictness_level = "moderate"

        # --- Check whether holidays are ever authorised ---
        authorises_holidays = False
        # If the school mentions exceptional circumstances, they may grant leave.
        if _EXCEPTIONAL_PATTERN.search(text) and strictness_level != "strict":
            authorises_holidays = True

        # --- Extract term-time holiday policy text ---
        term_time_holiday_policy = self._extract_holiday_policy_text(text)

        # --- Extract exceptional circumstances description ---
        exceptional_circumstances = self._extract_exceptional_circumstances(text)

        # --- Extract a policy summary (key excerpts) ---
        policy_text = self._extract_policy_summary(text)

        if not policy_text and not term_time_holiday_policy and not issues_fines:
            # We found the page but could not extract any useful structured data.
            return None

        return {
            "school_id": school_id,
            "strictness_level": strictness_level,
            "issues_fines": issues_fines,
            "fining_threshold_days": fining_threshold_days,
            "fine_amount": fine_amount,
            "term_time_holiday_policy": term_time_holiday_policy,
            "authorises_holidays": authorises_holidays,
            # Leave absence rates as NULL — populated by the EES importer, not this scraper.
            "unauthorised_absence_rate": None,
            "overall_absence_rate": None,
            "policy_text": policy_text,
            "exceptional_circumstances": exceptional_circumstances,
            "source_url": source_url,
        }

    # ------------------------------------------------------------------
    # Text extraction helpers
    # ------------------------------------------------------------------

    def _extract_holiday_policy_text(self, text: str) -> str | None:
        """Extract sentences related to term-time holiday policy.

        Scans the full page text for sentences mentioning holidays, leave of
        absence, or term-time absence and returns them joined as a single
        string.

        Parameters
        ----------
        text:
            The full text content of the page.

        Returns
        -------
        str | None
            Relevant sentences, or ``None`` if nothing was found.
        """
        holiday_pattern = re.compile(
            r"[^.]*(?:term.time\s+holiday|leave\s+of\s+absence|holiday\s+during\s+term|"
            r"holiday\s+in\s+term\s+time|absence\s+during\s+term)[^.]*\.",
            flags=re.IGNORECASE,
        )
        matches = holiday_pattern.findall(text)
        if not matches:
            return None

        # Deduplicate and limit length.
        seen: set[str] = set()
        unique: list[str] = []
        for m in matches:
            cleaned = m.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                unique.append(cleaned)

        result = " ".join(unique)
        # Cap at a reasonable length to avoid storing entire pages.
        return result[:2000] if result else None

    def _extract_exceptional_circumstances(self, text: str) -> str | None:
        """Extract text describing what the school considers exceptional circumstances.

        Parameters
        ----------
        text:
            The full text content of the page.

        Returns
        -------
        str | None
            Relevant text, or ``None`` if nothing was found.
        """
        exceptional_pattern = re.compile(
            r"[^.]*exceptional\s+circumstances?[^.]*\.",
            flags=re.IGNORECASE,
        )
        matches = exceptional_pattern.findall(text)
        if not matches:
            return None

        seen: set[str] = set()
        unique: list[str] = []
        for m in matches:
            cleaned = m.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                unique.append(cleaned)

        result = " ".join(unique)
        return result[:2000] if result else None

    def _extract_policy_summary(self, text: str) -> str | None:
        """Extract key sentences from the attendance policy as a summary.

        Looks for sentences containing core attendance policy language and
        returns them as a concatenated summary.

        Parameters
        ----------
        text:
            The full text content of the page.

        Returns
        -------
        str | None
            Key policy excerpts, or ``None`` if nothing substantive was found.
        """
        summary_keywords = re.compile(
            r"[^.]*(?:attendance\s+target|attendance\s+is\s+expected|"
            r"regular\s+attendance|good\s+attendance|"
            r"unauthorised\s+absence|persistent\s+absence|"
            r"penalty\s+notice|fixed\s+penalty|"
            r"school\s+expects\s+all|"
            r"attendance\s+policy|absence\s+policy)[^.]*\.",
            flags=re.IGNORECASE,
        )
        matches = summary_keywords.findall(text)
        if not matches:
            return None

        seen: set[str] = set()
        unique: list[str] = []
        for m in matches:
            cleaned = m.strip()
            if cleaned and cleaned not in seen and len(cleaned) > 20:
                seen.add(cleaned)
                unique.append(cleaned)

        result = " ".join(unique[:10])  # Limit to 10 key sentences.
        return result[:3000] if result else None

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_to_db(self, records: list[dict[str, object]]) -> None:
        """Write parsed absence policy records to the ``absence_policies`` table.

        Uses a synchronous SQLAlchemy session for simplicity.

        Parameters
        ----------
        records:
            Parsed policy dicts as returned by :meth:`_parse_policy`.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            for record in records:
                policy = AbsencePolicy(
                    school_id=record["school_id"],
                    strictness_level=record.get("strictness_level"),
                    issues_fines=record.get("issues_fines", False),
                    fining_threshold_days=record.get("fining_threshold_days"),
                    fine_amount=record.get("fine_amount"),
                    term_time_holiday_policy=record.get("term_time_holiday_policy"),
                    authorises_holidays=record.get("authorises_holidays", False),
                    unauthorised_absence_rate=record.get("unauthorised_absence_rate"),
                    overall_absence_rate=record.get("overall_absence_rate"),
                    policy_text=record.get("policy_text"),
                    exceptional_circumstances=record.get("exceptional_circumstances"),
                    source_url=record.get("source_url"),
                )
                session.add(policy)
            session.commit()
            self._logger.info("Committed %d absence policy rows", len(records))


if __name__ == "__main__":
    from src.agents.base_agent import run_agent_cli

    run_agent_cli(AbsencePoliciesAgent, "Scrape absence and fining policies for schools in a council.")
