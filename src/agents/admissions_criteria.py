"""Admissions Criteria Scraper Agent.

For each school belonging to the configured council, this agent visits the
school's website, searches for an admissions or oversubscription criteria page,
and extracts the ranked priority categories that determine how places are
allocated.  Extracted criteria are stored in the ``admissions_criteria`` table
via SQLAlchemy.

Usage
-----
::

    python -m src.agents.admissions_criteria --council "Milton Keynes"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import AdmissionsCriteria, School

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keywords used to locate admissions-related links on school homepages.
# ---------------------------------------------------------------------------
_ADMISSIONS_LINK_KEYWORDS: list[str] = [
    "admission",
    "admissions",
    "apply",
    "places",
    "oversubscription",
    "oversubscribed",
    "intake",
    "entry requirements",
    "joining us",
    "joining our school",
    "how to apply",
]

_ADMISSIONS_LINK_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _ADMISSIONS_LINK_KEYWORDS),
    flags=re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Known category names mapped to canonical labels.
# Order matters: the first match wins.
# ---------------------------------------------------------------------------
_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"look(?:ed)[\s-]*after|child(?:ren)?\s+in\s+care|LAC|previously\s+in\s+care",
            re.IGNORECASE,
        ),
        "Looked-after children",
    ),
    (
        re.compile(r"medical|social\s+need|health|exceptional\s+circumstances", re.IGNORECASE),
        "Medical/social need",
    ),
    (re.compile(r"sibling|brother|sister", re.IGNORECASE), "Siblings"),
    (re.compile(r"staff|employee|teacher", re.IGNORECASE), "Children of staff"),
    (
        re.compile(
            r"faith|church|worship|baptis|catholic|christian|muslim|jewish|hindu|sikh|religious",
            re.IGNORECASE,
        ),
        "Faith",
    ),
    (
        re.compile(
            r"feeder\s+school|linked\s+school|partner\s+school|associated\s+school",
            re.IGNORECASE,
        ),
        "Feeder school",
    ),
    (
        re.compile(r"catchment|designated\s+area|priority\s+area|defined\s+area", re.IGNORECASE),
        "Catchment area",
    ),
    (
        re.compile(r"distance|nearest|proximity|closest|home\s+to\s+school", re.IGNORECASE),
        "Distance",
    ),
    (
        re.compile(r"random|ballot|lottery|drawing\s+of\s+lots", re.IGNORECASE),
        "Random allocation",
    ),
]

# Pattern to detect SIF (Supplementary Information Form) mentions.
_SIF_PATTERN: re.Pattern[str] = re.compile(
    r"supplementary\s+information\s+form|SIF|additional\s+form",
    flags=re.IGNORECASE,
)


class AdmissionsCriteriaAgent(BaseAgent):
    """Scrape admissions oversubscription criteria for schools in a council.

    The agent:

    1. Queries the database for all schools belonging to the council.
    2. For each school that has a website URL, fetches the homepage and
       searches for links to an admissions or oversubscription criteria page.
    3. If an admissions page is found, fetches it and parses the ranked
       priority categories.
    4. Persists results in the ``admissions_criteria`` table.

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
        """Execute the admissions criteria data-collection pipeline.

        Steps
        -----
        1. Load the list of schools from the database.
        2. Iterate over each school's website.
        3. Discover and parse admissions criteria pages.
        4. Persist to the database.
        """
        self._logger.info("Starting admissions criteria agent for council=%r", self.council)

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
            criteria = await self._discover_criteria(school_id, school_name, school_website)

            if criteria:
                self._save_to_db(school_id, criteria)
                self._logger.info("Saved %d criteria records for school %r", len(criteria), school_name)
            else:
                self._logger.debug("No admissions criteria found for school %r", school_name)

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
    # Admissions criteria discovery
    # ------------------------------------------------------------------

    async def _discover_criteria(
        self,
        school_id: int,
        school_name: str,
        website_url: str,
    ) -> list[dict[str, object]]:
        """Fetch a school's website and look for admissions criteria.

        The method first loads the homepage and looks for links whose text or
        href contains admissions-related keywords.  If a suitable link is
        found, the linked page is fetched and parsed for oversubscription
        criteria.  If no link is found, the homepage text itself is checked
        for inline criteria content.

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
            Parsed criteria records ready for persistence.  Each dict contains
            keys matching :class:`~src.db.models.AdmissionsCriteria` columns.
        """
        try:
            homepage_html = await self.fetch_page(website_url)
        except Exception:
            self._logger.exception("Failed to fetch homepage for school %r", school_name)
            return []

        homepage_soup = self.parse_html(homepage_html)

        # Normalise the base URL for resolving relative links.
        base_url = website_url if website_url.startswith(("http://", "https://")) else f"https://{website_url}"

        # Step 1: Find an admissions-related link on the homepage.
        admissions_url = self._find_admissions_link(homepage_soup, base_url)

        if admissions_url:
            self._logger.info("Found admissions page link: %s", admissions_url)
            try:
                admissions_html = await self.fetch_page(admissions_url)
            except Exception:
                self._logger.exception("Failed to fetch admissions page %s for school %r", admissions_url, school_name)
                # Fall back to parsing the homepage instead.
                return self._parse_criteria(school_id, homepage_soup)

            admissions_soup = self.parse_html(admissions_html)
            criteria = self._parse_criteria(school_id, admissions_soup)

            # If the dedicated admissions page yielded nothing, try the homepage.
            if not criteria:
                self._logger.debug(
                    "Admissions page yielded no criteria for %r; trying homepage",
                    school_name,
                )
                criteria = self._parse_criteria(school_id, homepage_soup)
            return criteria

        # Step 2: No admissions link found – try parsing the homepage directly.
        self._logger.debug("No admissions link found for %r; checking homepage text", school_name)
        return self._parse_criteria(school_id, homepage_soup)

    def _find_admissions_link(self, soup: BeautifulSoup, base_url: str) -> str | None:
        """Search a parsed HTML page for a link to an admissions criteria page.

        Parameters
        ----------
        soup:
            Parsed HTML of the school homepage.
        base_url:
            The school's base URL, used to resolve relative hrefs.

        Returns
        -------
        str | None
            Absolute URL to the admissions page, or ``None`` if no suitable
            link was found.
        """
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            link_text = anchor.get_text(separator=" ", strip=True).lower()

            # Check both the link text and the href for admissions keywords.
            if _ADMISSIONS_LINK_PATTERN.search(link_text) or _ADMISSIONS_LINK_PATTERN.search(href):
                # Resolve relative URLs.
                absolute_url = urljoin(base_url, href)
                return absolute_url

        return None

    # ------------------------------------------------------------------
    # Criteria parsing
    # ------------------------------------------------------------------

    def _parse_criteria(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Extract oversubscription criteria from a parsed HTML page.

        The parser looks for ordered lists (``<ol>``) and numbered patterns
        in the page text that describe priority categories.  Each criterion
        is classified into a canonical category and assigned a priority rank.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        soup:
            A :class:`~bs4.BeautifulSoup` document tree (typically the
            admissions page, or the homepage as a fallback).

        Returns
        -------
        list[dict[str, object]]
            Parsed criteria dicts.  Each contains:
            ``school_id``, ``priority_rank``, ``category``, ``description``,
            ``religious_requirement``, ``requires_sif``, ``notes``.
        """
        # Strategy 1: Look for ordered lists that appear to contain criteria.
        criteria = self._parse_from_ordered_lists(school_id, soup)
        if criteria:
            return criteria

        # Strategy 2: Look for numbered items in the page text.
        criteria = self._parse_from_numbered_text(school_id, soup)
        if criteria:
            return criteria

        # Strategy 3: Look for sections/divs with admissions-related headings
        # and extract list items from them.
        criteria = self._parse_from_sections(school_id, soup)
        if criteria:
            return criteria

        return []

    def _parse_from_ordered_lists(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Try to extract criteria from ``<ol>`` elements.

        Searches for ordered lists that follow an admissions-related heading
        or contain admissions-related text.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        soup:
            Parsed HTML document.

        Returns
        -------
        list[dict[str, object]]
            Parsed criteria, or an empty list if nothing suitable was found.
        """
        for ol in soup.find_all("ol"):
            items = ol.find_all("li")
            if len(items) < 2:
                continue

            # Check whether the list looks like admissions criteria.
            combined_text = " ".join(li.get_text(separator=" ", strip=True) for li in items)
            if not self._text_looks_like_criteria(combined_text):
                continue

            criteria: list[dict[str, object]] = []
            for rank, li in enumerate(items, start=1):
                text = li.get_text(separator=" ", strip=True)
                if not text:
                    continue

                category = self._classify_category(text)
                religious_req = self._extract_religious_requirement(text)
                requires_sif = bool(_SIF_PATTERN.search(text))

                criteria.append(
                    {
                        "school_id": school_id,
                        "priority_rank": rank,
                        "category": category,
                        "description": text[:2000],
                        "religious_requirement": religious_req,
                        "requires_sif": requires_sif,
                        "notes": None,
                    }
                )

            if criteria:
                self._logger.info(
                    "Extracted %d criteria from <ol> for school_id=%d",
                    len(criteria),
                    school_id,
                )
                return criteria

        return []

    def _parse_from_numbered_text(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Try to extract criteria from numbered text patterns.

        Looks for lines matching patterns like ``1.``, ``(a)``, ``i)``
        followed by criterion descriptions.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        soup:
            Parsed HTML document.

        Returns
        -------
        list[dict[str, object]]
            Parsed criteria, or an empty list if nothing suitable was found.
        """
        text = soup.get_text(separator="\n", strip=True)

        # Match numbered items: "1.", "1)", "(1)", "a.", "a)", "(a)", "i.", etc.
        numbered_pattern = re.compile(
            r"^\s*(?:\(?(\d+|[a-z]|[ivxlc]+)[.)]\)?)\s+(.+)",
            re.IGNORECASE | re.MULTILINE,
        )

        matches = list(numbered_pattern.finditer(text))
        if len(matches) < 2:
            return []

        # Check that the numbered items look like admissions criteria.
        combined = " ".join(m.group(2) for m in matches)
        if not self._text_looks_like_criteria(combined):
            return []

        criteria: list[dict[str, object]] = []
        for rank, match in enumerate(matches, start=1):
            item_text = match.group(2).strip()
            if not item_text:
                continue

            category = self._classify_category(item_text)
            religious_req = self._extract_religious_requirement(item_text)
            requires_sif = bool(_SIF_PATTERN.search(item_text))

            criteria.append(
                {
                    "school_id": school_id,
                    "priority_rank": rank,
                    "category": category,
                    "description": item_text[:2000],
                    "religious_requirement": religious_req,
                    "requires_sif": requires_sif,
                    "notes": None,
                }
            )

        if criteria:
            self._logger.info(
                "Extracted %d criteria from numbered text for school_id=%d",
                len(criteria),
                school_id,
            )

        return criteria

    def _parse_from_sections(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Try to extract criteria from section headings followed by list items.

        Looks for ``<h2>``/``<h3>``/``<h4>`` headings with admissions-related
        text, then extracts any ``<li>`` or ``<p>`` children within the next
        sibling container.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        soup:
            Parsed HTML document.

        Returns
        -------
        list[dict[str, object]]
            Parsed criteria, or an empty list if nothing suitable was found.
        """
        for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
            heading_text = heading.get_text(separator=" ", strip=True).lower()

            _heading_keywords = [
                "oversubscription",
                "admission criteria",
                "admissions criteria",
                "priority",
                "how places are allocated",
            ]
            if not any(kw in heading_text for kw in _heading_keywords):
                continue

            # Gather content from the next sibling elements until the next heading.
            items_text: list[str] = []
            sibling = heading.find_next_sibling()
            while sibling and not (isinstance(sibling, Tag) and sibling.name in ("h1", "h2", "h3", "h4")):
                # Check for list items inside this sibling.
                lis = sibling.find_all("li") if isinstance(sibling, Tag) else []
                if lis:
                    for li in lis:
                        item = li.get_text(separator=" ", strip=True)
                        if item:
                            items_text.append(item)
                elif isinstance(sibling, Tag):
                    # Grab paragraph text that might contain numbered items.
                    p_text = sibling.get_text(separator=" ", strip=True)
                    if p_text and len(p_text) > 10:
                        items_text.append(p_text)

                sibling = sibling.find_next_sibling()

            if len(items_text) < 2:
                continue

            # Verify these look like admissions criteria.
            combined = " ".join(items_text)
            if not self._text_looks_like_criteria(combined):
                continue

            criteria: list[dict[str, object]] = []
            for rank, item in enumerate(items_text, start=1):
                category = self._classify_category(item)
                religious_req = self._extract_religious_requirement(item)
                requires_sif = bool(_SIF_PATTERN.search(item))

                criteria.append(
                    {
                        "school_id": school_id,
                        "priority_rank": rank,
                        "category": category,
                        "description": item[:2000],
                        "religious_requirement": religious_req,
                        "requires_sif": requires_sif,
                        "notes": None,
                    }
                )

            if criteria:
                self._logger.info(
                    "Extracted %d criteria from section for school_id=%d",
                    len(criteria),
                    school_id,
                )
                return criteria

        return []

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    def _text_looks_like_criteria(self, text: str) -> bool:
        """Heuristic check: does this text look like admissions criteria?

        Returns ``True`` if the text mentions at least two of the standard
        UK admissions priority categories (looked-after children, siblings,
        distance, faith, etc.).

        Parameters
        ----------
        text:
            Combined text of the candidate criteria items.

        Returns
        -------
        bool
        """
        matches = 0
        for pattern, _category in _CATEGORY_PATTERNS:
            if pattern.search(text):
                matches += 1
            if matches >= 2:
                return True
        return False

    def _classify_category(self, text: str) -> str:
        """Classify a criterion description into a canonical category name.

        Parameters
        ----------
        text:
            The description text of a single admissions criterion.

        Returns
        -------
        str
            A canonical category name, or ``"Other"`` if no pattern matches.
        """
        for pattern, category in _CATEGORY_PATTERNS:
            if pattern.search(text):
                return category
        return "Other"

    def _extract_religious_requirement(self, text: str) -> str | None:
        """Extract religious requirement details from criterion text.

        If the criterion mentions specific religious practice requirements
        (e.g. weekly church attendance, baptism, etc.), this method extracts
        a concise description.

        Parameters
        ----------
        text:
            The description text of a single admissions criterion.

        Returns
        -------
        str | None
            A description of the religious requirement, or ``None`` if the
            criterion is not faith-related.
        """
        # Only extract religious requirements for faith-related criteria.
        faith_pattern = _CATEGORY_PATTERNS[4][0]  # The "Faith" pattern
        if not faith_pattern.search(text):
            return None

        # Try to extract specific requirements.
        requirements: list[str] = []

        attendance_match = re.search(
            r"((?:regular|weekly|fortnightly|monthly)\s+(?:church|worship|attendance|mass)[^.;]*)",
            text,
            re.IGNORECASE,
        )
        if attendance_match:
            requirements.append(attendance_match.group(1).strip())

        baptism_match = re.search(
            r"(baptis(?:m|ed)\s+certificate[^.;]*|baptis(?:m|ed)[^.;]{0,50})",
            text,
            re.IGNORECASE,
        )
        if baptism_match:
            requirements.append(baptism_match.group(1).strip())

        reference_match = re.search(
            r"((?:priest|vicar|minister|imam|rabbi|clergy)\s*(?:'s)?\s+reference[^.;]*)",
            text,
            re.IGNORECASE,
        )
        if reference_match:
            requirements.append(reference_match.group(1).strip())

        if requirements:
            return "; ".join(requirements)

        # Generic faith requirement.
        return "Faith-based criterion (see description for details)"

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_to_db(self, school_id: int, records: list[dict[str, object]]) -> None:
        """Write parsed criteria records to the ``admissions_criteria`` table.

        Any existing criteria for the given school are deleted first so that
        re-running the agent produces a clean replacement rather than
        duplicates.

        Uses a synchronous SQLAlchemy session for simplicity.

        Parameters
        ----------
        school_id:
            The school whose criteria are being saved.
        records:
            Parsed criteria dicts as returned by :meth:`_parse_criteria`.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            # Remove existing criteria for this school to avoid duplicates.
            session.execute(delete(AdmissionsCriteria).where(AdmissionsCriteria.school_id == school_id))

            for record in records:
                criterion = AdmissionsCriteria(
                    school_id=record["school_id"],
                    priority_rank=int(record["priority_rank"]),
                    category=str(record["category"]),
                    description=str(record["description"]),
                    religious_requirement=record.get("religious_requirement"),
                    requires_sif=bool(record.get("requires_sif", False)),
                    notes=record.get("notes"),
                )
                session.add(criterion)
            session.commit()
            self._logger.info("Committed %d criteria rows for school_id=%d", len(records), school_id)


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the admissions criteria agent.

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
        description="Scrape admissions oversubscription criteria for schools in a council.",
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
    """CLI entry point for the admissions criteria agent.

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
    agent = AdmissionsCriteriaAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
