"""Admissions Criteria Scraper Agent.

For each school belonging to the configured council, this agent visits the
school's website, searches for an admissions or oversubscription criteria page,
and extracts the ranked priority categories that determine how places are
allocated.  Extracted criteria are stored in the ``admissions_criteria`` table
via SQLAlchemy.

Enhanced with:
- Multi-link discovery (tries all admissions links, not just the first)
- Deeper crawling (homepage → admissions page → criteria subpage)
- Table parsing (criteria presented in HTML tables)
- Unordered list parsing (``<ul>`` elements alongside ``<ol>``)
- Definition list parsing (``<dl>``/``<dt>``/``<dd>`` elements)
- Common URL path guessing for school CMS platforms
- EHCP/SEN category recognition
- Relaxed heuristic matching to catch more varied criteria descriptions

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
from urllib.parse import urljoin, urlparse

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
    "admissions policy",
    "admissions criteria",
    "school places",
    "apply for a place",
    "new parents",
    "new starters",
    "prospective parents",
    "key information",
    "policies",
]

_ADMISSIONS_LINK_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _ADMISSIONS_LINK_KEYWORDS),
    flags=re.IGNORECASE,
)

# More specific keywords that indicate the link is directly about criteria.
_CRITERIA_SPECIFIC_KEYWORDS: list[str] = [
    "oversubscription",
    "criteria",
    "admissions policy",
    "admissions criteria",
    "how places are allocated",
    "how we allocate",
    "priority",
]

_CRITERIA_SPECIFIC_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _CRITERIA_SPECIFIC_KEYWORDS),
    flags=re.IGNORECASE,
)

# Common URL paths for admissions pages on school CMS platforms.
_COMMON_ADMISSIONS_PATHS: list[str] = [
    "/admissions",
    "/admissions-policy",
    "/admissions/admissions-policy",
    "/key-information/admissions",
    "/parents/admissions",
    "/information/admissions",
    "/about-us/admissions",
    "/about/admissions",
    "/join-us",
    "/joining-us",
    "/joining-our-school",
    "/how-to-apply",
    "/apply",
    "/school-policies/admissions",
    "/policies/admissions-policy",
    "/page/?title=Admissions",
    "/page/?title=Admissions+Policy",
]

# ---------------------------------------------------------------------------
# Known category names mapped to canonical labels.
# Order matters: the first match wins.
# ---------------------------------------------------------------------------
_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"look(?:ed)[\s-]*after|child(?:ren)?\s+in\s+care|LAC|previously\s+in\s+care"
            r"|care\s+order|special\s+guardianship",
            re.IGNORECASE,
        ),
        "Looked-after children",
    ),
    (
        re.compile(
            r"EHCP|EHC\s+plan|education[\s,]+health\s+and\s+care"
            r"|special\s+educational\s+need|SEN\s+provision|statement\s+of\s+SEN",
            re.IGNORECASE,
        ),
        "EHCP/SEN",
    ),
    (
        re.compile(
            r"medical|social\s+need|health|exceptional\s+circumstances"
            r"|compelling\s+need|professional\s+evidence|social\s+grounds",
            re.IGNORECASE,
        ),
        "Medical/social need",
    ),
    (re.compile(r"sibling|brother|sister|brothers?\s+or\s+sisters?", re.IGNORECASE), "Siblings"),
    (re.compile(r"staff|employee|teacher|member\s+of\s+staff", re.IGNORECASE), "Children of staff"),
    (
        re.compile(
            r"faith|church|worship|baptis|catholic|christian|muslim|jewish|hindu|sikh|religious"
            r"|congregation|practising|parish|diocese|communion",
            re.IGNORECASE,
        ),
        "Faith",
    ),
    (
        re.compile(
            r"feeder\s+school|linked\s+school|partner\s+school|associated\s+school"
            r"|named\s+(?:primary|junior)\s+school|attend(?:s|ing)?\s+(?:a\s+)?(?:partner|feeder|linked)",
            re.IGNORECASE,
        ),
        "Feeder school",
    ),
    (
        re.compile(
            r"catchment|designated\s+area|priority\s+area|defined\s+area"
            r"|within\s+the\s+(?:school|designated)\s+area|home\s+area",
            re.IGNORECASE,
        ),
        "Catchment area",
    ),
    (
        re.compile(
            r"distance|nearest|proximity|closest|home\s+to\s+school"
            r"|straight[\s-]*line|walking\s+distance|nearest\s+school",
            re.IGNORECASE,
        ),
        "Distance",
    ),
    (
        re.compile(r"random|ballot|lottery|drawing\s+of\s+lots", re.IGNORECASE),
        "Random allocation",
    ),
    (
        re.compile(r"banding|aptitude|ability\s+(?:test|assessment)", re.IGNORECASE),
        "Banding/aptitude",
    ),
]

# Pattern to detect SIF (Supplementary Information Form) mentions.
_SIF_PATTERN: re.Pattern[str] = re.compile(
    r"supplementary\s+information\s+form|SIF|additional\s+form|supplementary\s+form",
    flags=re.IGNORECASE,
)


class AdmissionsCriteriaAgent(BaseAgent):
    """Scrape admissions oversubscription criteria for schools in a council.

    The agent:

    1. Queries the database for all schools belonging to the council.
    2. For each school that has a website URL, fetches the homepage and
       searches for links to an admissions or oversubscription criteria page.
    3. Follows multiple admissions links and crawls subpages.
    4. Tries common URL path patterns for school CMS platforms.
    5. If an admissions page is found, fetches it and parses the ranked
       priority categories using multiple strategies (ordered lists,
       unordered lists, tables, definition lists, numbered text, sections).
    6. Persists results in the ``admissions_criteria`` table.

    Parameters
    ----------
    council:
        Council name, e.g. ``"Milton Keynes"``.
    cache_dir:
        Directory for cached HTTP responses.
    delay:
        Seconds to wait between HTTP requests.
    max_depth:
        Maximum link-following depth (default 2: homepage → admissions → subpage).
    """

    def __init__(
        self,
        council: str,
        cache_dir: str = "./data/cache",
        delay: float = 1.0,
        max_depth: int = 2,
    ) -> None:
        super().__init__(council=council, cache_dir=cache_dir, delay=delay)
        self.max_depth = max_depth

    async def run(self) -> None:
        """Execute the admissions criteria data-collection pipeline."""
        self._logger.info("Starting admissions criteria agent for council=%r", self.council)

        schools = self._load_schools()
        if not schools:
            self._logger.warning("No schools found in DB for council=%r", self.council)
            return

        self._logger.info("Found %d schools for council=%r", len(schools), self.council)

        success_count = 0
        for school_id, school_name, school_website in schools:
            if not school_website:
                self._logger.debug("School %r (id=%d) has no website – skipping", school_name, school_id)
                continue

            self._logger.info("Processing school %r (id=%d)", school_name, school_id)
            criteria = await self._discover_criteria(school_id, school_name, school_website)

            if criteria:
                self._save_to_db(school_id, criteria)
                self._logger.info("Saved %d criteria records for school %r", len(criteria), school_name)
                success_count += 1
            else:
                self._logger.info("No admissions criteria found for school %r", school_name)

        self._logger.info(
            "Admissions criteria agent complete: %d/%d schools with criteria",
            success_count,
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
    # Admissions criteria discovery (enhanced multi-stage)
    # ------------------------------------------------------------------

    async def _discover_criteria(
        self,
        school_id: int,
        school_name: str,
        website_url: str,
    ) -> list[dict[str, object]]:
        """Fetch a school's website and look for admissions criteria.

        Enhanced strategy:
        1. Fetch homepage, find ALL admissions-related links (scored by relevance).
        2. Try each link in order of relevance, parsing for criteria.
        3. For each admissions page, look for deeper subpage links.
        4. Try common URL path patterns for school CMS platforms.
        5. Fall back to parsing the homepage text.
        """
        base_url = website_url if website_url.startswith(("http://", "https://")) else f"https://{website_url}"
        visited: set[str] = set()

        # Step 1: Fetch homepage
        try:
            homepage_html = await self.fetch_page(website_url)
        except Exception:
            self._logger.exception("Failed to fetch homepage for school %r", school_name)
            return []

        homepage_soup = self.parse_html(homepage_html)
        visited.add(base_url)

        # Step 2: Find ALL admissions-related links, sorted by relevance.
        admissions_links = self._find_all_admissions_links(homepage_soup, base_url)
        self._logger.debug("Found %d admissions links for school %r", len(admissions_links), school_name)

        # Step 3: Try each admissions link.
        for link_url in admissions_links:
            if link_url in visited:
                continue
            visited.add(link_url)

            try:
                page_html = await self.fetch_page(link_url)
            except Exception:
                self._logger.debug("Failed to fetch %s for school %r", link_url, school_name)
                continue

            page_soup = self.parse_html(page_html)
            criteria = self._parse_criteria(school_id, page_soup)
            if criteria:
                return criteria

            # Step 3a: Look for deeper subpage links within this admissions page.
            if self.max_depth >= 2:
                subpage_links = self._find_criteria_subpage_links(page_soup, link_url)
                for sub_url in subpage_links[:5]:
                    if sub_url in visited:
                        continue
                    visited.add(sub_url)

                    try:
                        sub_html = await self.fetch_page(sub_url)
                    except Exception:
                        self._logger.debug("Failed to fetch subpage %s", sub_url)
                        continue

                    sub_soup = self.parse_html(sub_html)
                    criteria = self._parse_criteria(school_id, sub_soup)
                    if criteria:
                        return criteria

        # Step 4: Try common URL path patterns.
        parsed_base = urlparse(base_url)
        base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
        for path in _COMMON_ADMISSIONS_PATHS:
            guess_url = f"{base_origin}{path}"
            if guess_url in visited:
                continue
            visited.add(guess_url)

            try:
                guess_html = await self.fetch_page(guess_url)
            except Exception:
                continue

            guess_soup = self.parse_html(guess_html)
            criteria = self._parse_criteria(school_id, guess_soup)
            if criteria:
                self._logger.info("Found criteria via URL pattern %s for %r", path, school_name)
                return criteria

        # Step 5: Fall back to parsing the homepage directly.
        self._logger.debug("Falling back to homepage text for %r", school_name)
        return self._parse_criteria(school_id, homepage_soup)

    def _find_all_admissions_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Find ALL admissions-related links, sorted by relevance score.

        Higher scores for links with more specific criteria keywords.
        Returns unique absolute URLs, most relevant first.
        """
        scored_links: list[tuple[int, str]] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            link_text = anchor.get_text(separator=" ", strip=True).lower()
            href_lower = href.lower()

            # Skip non-content links
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue

            combined = f"{link_text} {href_lower}"
            score = 0

            if _ADMISSIONS_LINK_PATTERN.search(combined):
                score += 1

            # Boost for criteria-specific terms
            if _CRITERIA_SPECIFIC_PATTERN.search(combined):
                score += 5

            # Boost for URL path hints
            if any(kw in href_lower for kw in ["admission", "criteria", "oversubscription", "policy"]):
                score += 2

            if score > 0:
                absolute_url = urljoin(base_url, href)
                # Skip PDFs and document links
                if absolute_url.lower().endswith((".pdf", ".doc", ".docx")):
                    continue
                scored_links.append((score, absolute_url))

        # Sort by score descending, deduplicate
        scored_links.sort(key=lambda x: x[0], reverse=True)
        seen: set[str] = set()
        result: list[str] = []
        for _score, url in scored_links:
            if url not in seen:
                seen.add(url)
                result.append(url)

        return result[:10]  # Limit to top 10

    def _find_criteria_subpage_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Find links within an admissions page that may lead to criteria content."""
        links: list[str] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            link_text = anchor.get_text(separator=" ", strip=True).lower()
            href_lower = href.lower()

            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue

            combined = f"{link_text} {href_lower}"

            # Look for criteria-specific subpage links
            if any(
                kw in combined
                for kw in [
                    "oversubscription",
                    "criteria",
                    "priority",
                    "how places",
                    "how we allocate",
                    "policy",
                    "admissions policy",
                    "admissions arrangement",
                    "key information",
                ]
            ):
                absolute_url = urljoin(base_url, href)
                if not absolute_url.lower().endswith((".pdf", ".doc", ".docx")):
                    links.append(absolute_url)

        return links

    # ------------------------------------------------------------------
    # Criteria parsing (enhanced with more strategies)
    # ------------------------------------------------------------------

    def _parse_criteria(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Extract oversubscription criteria from a parsed HTML page.

        Tries 6 strategies in order of reliability:
        1. Ordered lists (``<ol>``)
        2. Unordered lists (``<ul>``) within admissions-related sections
        3. Tables with criteria columns
        4. Definition lists (``<dl>``/``<dt>``/``<dd>``)
        5. Numbered text patterns in page content
        6. Section headings followed by list/paragraph content
        """
        # Strategy 1: Ordered lists
        criteria = self._parse_from_ordered_lists(school_id, soup)
        if criteria:
            return criteria

        # Strategy 2: Unordered lists in admissions sections
        criteria = self._parse_from_unordered_lists(school_id, soup)
        if criteria:
            return criteria

        # Strategy 3: Tables
        criteria = self._parse_from_tables(school_id, soup)
        if criteria:
            return criteria

        # Strategy 4: Definition lists
        criteria = self._parse_from_definition_lists(school_id, soup)
        if criteria:
            return criteria

        # Strategy 5: Numbered text
        criteria = self._parse_from_numbered_text(school_id, soup)
        if criteria:
            return criteria

        # Strategy 6: Sections with headings
        criteria = self._parse_from_sections(school_id, soup)
        if criteria:
            return criteria

        return []

    def _parse_from_ordered_lists(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Extract criteria from ``<ol>`` elements."""
        for ol in soup.find_all("ol"):
            items = ol.find_all("li")
            if len(items) < 2:
                continue

            combined_text = " ".join(li.get_text(separator=" ", strip=True) for li in items)
            if not self._text_looks_like_criteria(combined_text):
                continue

            criteria = self._build_criteria_from_items(
                school_id,
                [li.get_text(separator=" ", strip=True) for li in items],
            )
            if criteria:
                self._logger.info(
                    "Extracted %d criteria from <ol> for school_id=%d",
                    len(criteria),
                    school_id,
                )
                return criteria

        return []

    def _parse_from_unordered_lists(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Extract criteria from ``<ul>`` elements within admissions context.

        Many school websites use unordered lists for criteria, especially
        when the priorities are not strictly numbered.
        """
        # Look for <ul> elements that follow or are near admissions headings.
        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b"]):
            heading_text = heading.get_text(separator=" ", strip=True).lower()
            if not any(
                kw in heading_text
                for kw in [
                    "oversubscription",
                    "criteria",
                    "priority",
                    "how places",
                    "admissions",
                    "allocated",
                    "order of priority",
                ]
            ):
                continue

            # Find the next <ul> or <ol> after this heading.
            sibling = heading.find_next_sibling()
            while sibling:
                if isinstance(sibling, Tag) and sibling.name in ("h1", "h2", "h3", "h4"):
                    break  # Hit next section

                if isinstance(sibling, Tag) and sibling.name in ("ul", "ol"):
                    items = sibling.find_all("li")
                    if len(items) >= 2:
                        combined = " ".join(li.get_text(separator=" ", strip=True) for li in items)
                        if self._text_looks_like_criteria(combined):
                            criteria = self._build_criteria_from_items(
                                school_id,
                                [li.get_text(separator=" ", strip=True) for li in items],
                            )
                            if criteria:
                                self._logger.info(
                                    "Extracted %d criteria from <ul> for school_id=%d",
                                    len(criteria),
                                    school_id,
                                )
                                return criteria

                # Also check for lists nested inside divs/sections.
                if isinstance(sibling, Tag):
                    nested_lists = sibling.find_all(["ul", "ol"])
                    for lst in nested_lists:
                        items = lst.find_all("li")
                        if len(items) >= 2:
                            combined = " ".join(li.get_text(separator=" ", strip=True) for li in items)
                            if self._text_looks_like_criteria(combined):
                                criteria = self._build_criteria_from_items(
                                    school_id,
                                    [li.get_text(separator=" ", strip=True) for li in items],
                                )
                                if criteria:
                                    self._logger.info(
                                        "Extracted %d criteria from nested list for school_id=%d",
                                        len(criteria),
                                        school_id,
                                    )
                                    return criteria

                sibling = sibling.find_next_sibling()

        return []

    def _parse_from_tables(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Extract criteria from HTML tables.

        Some schools present criteria as:
        | Priority | Category | Description |
        | 1        | LAC      | Children who are... |
        """
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 3:  # Header + at least 2 data rows
                continue

            # Check headers for criteria-related columns
            header_row = rows[0]
            headers = [th.get_text(separator=" ", strip=True).lower() for th in header_row.find_all(["th", "td"])]

            # Identify relevant columns
            priority_col = None
            category_col = None
            description_col = None

            for i, h in enumerate(headers):
                if any(kw in h for kw in ["priority", "rank", "order", "criterion", "#", "no"]):
                    priority_col = i
                elif any(kw in h for kw in ["category", "type", "group"]):
                    category_col = i
                elif any(kw in h for kw in ["description", "detail", "criteria", "requirement"]):
                    description_col = i

            # If no explicit columns, check if the table content looks like criteria
            if priority_col is None and category_col is None and description_col is None:
                # Try treating it as a 2-column table (rank, description)
                all_text = " ".join(
                    td.get_text(separator=" ", strip=True) for row in rows for td in row.find_all(["td", "th"])
                )
                if not self._text_looks_like_criteria(all_text):
                    continue

                # Parse as simple rows
                criteria: list[dict[str, object]] = []
                rank = 1
                for row in rows[1:]:
                    cells = [td.get_text(separator=" ", strip=True) for td in row.find_all(["td", "th"])]
                    if not cells:
                        continue

                    # Use the longest cell as the description
                    description = max(cells, key=len) if cells else ""
                    if len(description) < 10:
                        continue

                    criteria.append(self._build_single_criterion(school_id, rank, description))
                    rank += 1

                if len(criteria) >= 2:
                    self._logger.info(
                        "Extracted %d criteria from table for school_id=%d",
                        len(criteria),
                        school_id,
                    )
                    return criteria
                continue

            # Parse with identified columns
            criteria = []
            for rank_num, row in enumerate(rows[1:], start=1):
                cells = [td.get_text(separator=" ", strip=True) for td in row.find_all(["td", "th"])]
                if not cells:
                    continue

                # Get description from the best column
                if description_col is not None and description_col < len(cells):
                    description = cells[description_col]
                elif category_col is not None and category_col < len(cells):
                    description = cells[category_col]
                else:
                    description = max(cells, key=len) if cells else ""

                if len(description) < 5:
                    continue

                criteria.append(self._build_single_criterion(school_id, rank_num, description))

            if len(criteria) >= 2:
                combined = " ".join(c["description"] for c in criteria)
                if self._text_looks_like_criteria(str(combined)):
                    self._logger.info(
                        "Extracted %d criteria from table for school_id=%d",
                        len(criteria),
                        school_id,
                    )
                    return criteria

        return []

    def _parse_from_definition_lists(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Extract criteria from ``<dl>``/``<dt>``/``<dd>`` elements.

        Some schools use definition lists:
        <dl>
            <dt>Priority 1</dt>
            <dd>Looked-after children...</dd>
        </dl>
        """
        for dl in soup.find_all("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")

            if len(dts) < 2:
                continue

            items: list[str] = []
            for dt, dd in zip(dts, dds):
                dt_text = dt.get_text(separator=" ", strip=True)
                dd_text = dd.get_text(separator=" ", strip=True) if dd else ""
                combined = f"{dt_text}: {dd_text}" if dd_text else dt_text
                items.append(combined)

            combined_text = " ".join(items)
            if not self._text_looks_like_criteria(combined_text):
                continue

            criteria = self._build_criteria_from_items(school_id, items)
            if criteria:
                self._logger.info(
                    "Extracted %d criteria from <dl> for school_id=%d",
                    len(criteria),
                    school_id,
                )
                return criteria

        return []

    def _parse_from_numbered_text(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Extract criteria from numbered text patterns."""
        text = soup.get_text(separator="\n", strip=True)

        # Match numbered items with various formats.
        numbered_pattern = re.compile(
            r"^\s*(?:"
            r"(?:priority|criterion|category|criteria)\s*"
            r")?\s*(?:\(?(\d+|[a-z]|[ivxlc]+)[.):\]]\)?)\s+(.+)",
            re.IGNORECASE | re.MULTILINE,
        )

        matches = list(numbered_pattern.finditer(text))
        if len(matches) < 2:
            return []

        combined = " ".join(m.group(2) for m in matches)
        if not self._text_looks_like_criteria(combined):
            return []

        criteria: list[dict[str, object]] = []
        for rank, match in enumerate(matches, start=1):
            item_text = match.group(2).strip()
            if not item_text:
                continue

            criteria.append(self._build_single_criterion(school_id, rank, item_text))

        if criteria:
            self._logger.info(
                "Extracted %d criteria from numbered text for school_id=%d",
                len(criteria),
                school_id,
            )

        return criteria

    def _parse_from_sections(self, school_id: int, soup: BeautifulSoup) -> list[dict[str, object]]:
        """Extract criteria from section headings followed by content."""
        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
            heading_text = heading.get_text(separator=" ", strip=True).lower()

            _heading_keywords = [
                "oversubscription",
                "admission criteria",
                "admissions criteria",
                "priority",
                "how places are allocated",
                "how we allocate",
                "order of priority",
                "allocation criteria",
                "criteria for",
            ]
            if not any(kw in heading_text for kw in _heading_keywords):
                continue

            items_text: list[str] = []
            sibling = heading.find_next_sibling()
            while sibling and not (isinstance(sibling, Tag) and sibling.name in ("h1", "h2", "h3", "h4")):
                if isinstance(sibling, Tag):
                    # Check for list items
                    lis = sibling.find_all("li")
                    if lis:
                        for li in lis:
                            item = li.get_text(separator=" ", strip=True)
                            if item and len(item) > 5:
                                items_text.append(item)
                    else:
                        p_text = sibling.get_text(separator=" ", strip=True)
                        if p_text and len(p_text) > 10:
                            items_text.append(p_text)

                sibling = sibling.find_next_sibling()

            if len(items_text) < 2:
                continue

            combined = " ".join(items_text)
            if not self._text_looks_like_criteria(combined):
                continue

            criteria = self._build_criteria_from_items(school_id, items_text)
            if criteria:
                self._logger.info(
                    "Extracted %d criteria from section for school_id=%d",
                    len(criteria),
                    school_id,
                )
                return criteria

        return []

    # ------------------------------------------------------------------
    # Criterion building helpers
    # ------------------------------------------------------------------

    def _build_criteria_from_items(
        self,
        school_id: int,
        items: list[str],
    ) -> list[dict[str, object]]:
        """Build criteria records from a list of text items."""
        criteria: list[dict[str, object]] = []
        for rank, text in enumerate(items, start=1):
            text = text.strip()
            if not text:
                continue
            criteria.append(self._build_single_criterion(school_id, rank, text))

        return criteria

    def _build_single_criterion(
        self,
        school_id: int,
        rank: int,
        description: str,
    ) -> dict[str, object]:
        """Build a single criterion record dict."""
        # Strip leading numbering that might have been captured
        cleaned = re.sub(r"^\s*(?:\d+[.):\]]\s*|[a-z][.)]\s*)", "", description, flags=re.IGNORECASE).strip()
        if not cleaned:
            cleaned = description

        category = self._classify_category(cleaned)
        religious_req = self._extract_religious_requirement(cleaned)
        requires_sif = bool(_SIF_PATTERN.search(cleaned))

        return {
            "school_id": school_id,
            "priority_rank": rank,
            "category": category,
            "description": cleaned[:2000],
            "religious_requirement": religious_req,
            "requires_sif": requires_sif,
            "notes": None,
        }

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    def _text_looks_like_criteria(self, text: str) -> bool:
        """Heuristic check: does this text look like admissions criteria?

        Returns ``True`` if the text mentions at least two of the standard
        UK admissions priority categories. Uses a relaxed threshold to catch
        more varied descriptions.
        """
        matches = 0
        for pattern, _category in _CATEGORY_PATTERNS:
            if pattern.search(text):
                matches += 1
            if matches >= 2:
                return True
        return False

    def _classify_category(self, text: str) -> str:
        """Classify a criterion description into a canonical category name."""
        for pattern, category in _CATEGORY_PATTERNS:
            if pattern.search(text):
                return category
        return "Other"

    def _extract_religious_requirement(self, text: str) -> str | None:
        """Extract religious requirement details from criterion text."""
        # Only extract for faith-related criteria.
        faith_pattern = _CATEGORY_PATTERNS[5][0]  # The "Faith" pattern
        if not faith_pattern.search(text):
            return None

        requirements: list[str] = []

        attendance_match = re.search(
            r"((?:regular|weekly|fortnightly|monthly|twice\s+monthly)\s+"
            r"(?:church|worship|attendance|mass|service)[^.;]*)",
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
            r"((?:priest|vicar|minister|imam|rabbi|clergy|rector)\s*(?:'s)?\s+reference[^.;]*)",
            text,
            re.IGNORECASE,
        )
        if reference_match:
            requirements.append(reference_match.group(1).strip())

        communion_match = re.search(
            r"((?:first\s+)?communion[^.;]*|confirmation[^.;]{0,50})",
            text,
            re.IGNORECASE,
        )
        if communion_match:
            requirements.append(communion_match.group(1).strip())

        if requirements:
            return "; ".join(requirements)

        return "Faith-based criterion (see description for details)"

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_to_db(self, school_id: int, records: list[dict[str, object]]) -> None:
        """Write parsed criteria records to the ``admissions_criteria`` table.

        Any existing criteria for the given school are deleted first so that
        re-running the agent produces a clean replacement rather than
        duplicates.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
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
    """Parse command-line arguments for the admissions criteria agent."""
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
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Maximum link-following depth from homepage (default: 2).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for the admissions criteria agent."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    agent = AdmissionsCriteriaAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
        max_depth=args.max_depth,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
