"""Agent: School Ethos Extraction Agent.

For each school belonging to the configured council, this agent visits the
school's website and extracts or generates a concise ethos statement
(mission, vision, values) for display in the school finder application.

Usage
-----
::

    python -m src.agents.ethos --council "Milton Keynes"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import School

logger = logging.getLogger(__name__)

# Keywords commonly found near ethos/mission/vision statements on school websites
_ETHOS_KEYWORDS: list[str] = [
    "ethos",
    "mission",
    "vision",
    "values",
    "aims",
    "our school",
    "we believe",
    "motto",
    "philosophy",
    "commitment",
    "principles",
]

# Regex pattern for identifying ethos-related content sections
_ETHOS_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in _ETHOS_KEYWORDS),
    flags=re.IGNORECASE,
)

# Common pages that might contain ethos information
_COMMON_ETHOS_PATHS: list[str] = [
    "/about",
    "/about-us",
    "/about-the-school",
    "/our-school",
    "/our-vision",
    "/our-ethos",
    "/mission",
    "/values",
    "/welcome",
]


class EthosAgent(BaseAgent):
    """Extract school ethos one-liners from school websites.

    The agent:

    1. Queries the database for all schools belonging to the council.
    2. For each school that has a website URL, fetches the homepage and
       relevant "about" pages.
    3. Extracts or generates a concise ethos statement using heuristics
       and text extraction.
    4. Updates the ``School.ethos`` field in the database.

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
        """Execute the ethos data-collection pipeline.

        Steps
        -----
        1. Load the list of schools from the database.
        2. Iterate over each school's website.
        3. Extract or generate ethos statement.
        4. Update the database with the ethos field.
        """
        self._logger.info("Starting ethos agent for council=%r", self.council)

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
            ethos = await self._extract_ethos(school_id, school_name, school_website)

            if ethos:
                self._save_ethos_to_db(school_id, ethos)
                self._logger.info("Saved ethos for school %r: %r", school_name, ethos[:80] + "...")
            else:
                self._logger.debug("No ethos found for school %r", school_name)

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
    # Ethos extraction
    # ------------------------------------------------------------------

    async def _extract_ethos(
        self,
        school_id: int,
        school_name: str,
        website_url: str,
    ) -> str | None:
        """Fetch a school's website and extract ethos statement.

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
        str | None
            Extracted ethos statement (one-liner, max 500 chars) or None if
            extraction failed.
        """
        # Try homepage first
        ethos = await self._try_extract_from_url(website_url, school_name)
        if ethos:
            return ethos

        # Try common about pages
        for path in _COMMON_ETHOS_PATHS:
            url = website_url.rstrip("/") + path
            ethos = await self._try_extract_from_url(url, school_name)
            if ethos:
                return ethos

        # Fall back to generating a generic statement
        self._logger.warning("Could not extract ethos from website for %r, generating fallback", school_name)
        return self._generate_fallback_ethos(school_name)

    async def _try_extract_from_url(self, url: str, school_name: str) -> str | None:
        """Attempt to extract ethos from a specific URL.

        Parameters
        ----------
        url:
            URL to fetch and parse.
        school_name:
            School name for logging.

        Returns
        -------
        str | None
            Extracted ethos or None if not found/failed.
        """
        try:
            html = await self.fetch_page(url)
        except Exception:
            self._logger.debug("Failed to fetch %s for school %r", url, school_name)
            return None

        soup = self.parse_html(html)
        return self._parse_ethos(soup)

    def _parse_ethos(self, soup: object) -> str | None:
        """Extract structured ethos statement from parsed HTML.

        Uses heuristics to identify ethos-related sections and extract
        a concise one-liner.

        Parameters
        ----------
        soup:
            A :class:`~bs4.BeautifulSoup` document tree.

        Returns
        -------
        str | None
            Extracted ethos statement or None if not found.
        """
        # Strategy 0: Look specifically for motto patterns (highest priority)
        motto = self._extract_motto(soup)
        if motto:
            return self._clean_ethos(motto)

        # Strategy 1: Look for meta description tag
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            content = str(meta_desc.get("content", "")).strip()
            if content and len(content) >= 50 and not self._is_generic_welcome(content):
                return self._clean_ethos(content)

        # Strategy 2: Look for headings containing ethos keywords
        for heading in soup.find_all(["h1", "h2", "h3"]):
            heading_text = heading.get_text(strip=True)
            if _ETHOS_PATTERN.search(heading_text):
                # Get the next paragraph or div after this heading
                next_elem = heading.find_next(["p", "div"])
                if next_elem:
                    text = next_elem.get_text(strip=True)
                    if text and len(text) >= 30 and not self._is_generic_welcome(text):
                        # Try to extract motto if embedded
                        embedded_motto = self._extract_motto_from_text(text)
                        if embedded_motto:
                            return self._clean_ethos(embedded_motto)
                        return self._clean_ethos(text)

        # Strategy 3: Look for sections/divs with ethos-related classes or IDs
        for elem in soup.find_all(["div", "section"]):
            elem_class = " ".join(elem.get("class", []))
            elem_id = elem.get("id", "")
            combined = (elem_class + " " + elem_id).lower()

            if _ETHOS_PATTERN.search(combined):
                text = elem.get_text(separator=" ", strip=True)
                # Get first substantial paragraph (skip welcome messages)
                paragraphs = [
                    p.strip() for p in text.split("\n") if len(p.strip()) >= 30 and not self._is_generic_welcome(p)
                ]
                if paragraphs:
                    # Try to extract motto if embedded
                    embedded_motto = self._extract_motto_from_text(paragraphs[0])
                    if embedded_motto:
                        return self._clean_ethos(embedded_motto)
                    return self._clean_ethos(paragraphs[0])

        # Strategy 4: Search all paragraph text for ethos keywords (skip welcomes)
        candidates = []
        for para in soup.find_all("p"):
            text = para.get_text(strip=True)
            if _ETHOS_PATTERN.search(text) and len(text) >= 30 and not self._is_generic_welcome(text):
                candidates.append((len(text), text))  # Store with length for sorting

        # Prefer shorter, more concise statements
        if candidates:
            candidates.sort(key=lambda x: x[0])  # Sort by length (shortest first)
            # Try to extract motto from shortest candidate
            for _, text in candidates[:3]:  # Check top 3 shortest
                embedded_motto = self._extract_motto_from_text(text)
                if embedded_motto:
                    return self._clean_ethos(embedded_motto)
            # Fall back to shortest candidate
            return self._clean_ethos(candidates[0][1])

        return None

    def _extract_motto(self, soup: object) -> str | None:
        """Look for explicit motto statements in the HTML.

        Searches for patterns like:
        - "Our motto is: [motto]"
        - "School motto: [motto]"
        - Quoted text near motto keywords
        """
        motto_patterns = [
            r"(?:our\s+)?motto\s+is[:\s]+['\"]?([^'\"\.]+)['\"]?",
            r"school\s+motto[:\s]+['\"]?([^'\"\.]+)['\"]?",
            r"['\"]([^'\"]{20,100})['\"]",  # Quoted text (20-100 chars)
        ]

        # Search all text for motto patterns
        all_text = soup.get_text(separator=" ", strip=True)
        for pattern in motto_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                motto = match.group(1).strip()
                if 20 <= len(motto) <= 150:  # Reasonable motto length
                    return motto

        return None

    def _extract_motto_from_text(self, text: str) -> str | None:
        """Extract just the motto from a paragraph that contains it.

        Example: "At our school, our motto is: 'Excellence for all'. We believe..."
        Returns: "Excellence for all"
        """
        motto_patterns = [
            r"(?:our\s+)?motto\s+is[:\s]+['\"]?([^'\"\.]+)['\"]?",
            r"school\s+motto[:\s]+['\"]?([^'\"\.]+)['\"]?",
        ]

        for pattern in motto_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                motto = match.group(1).strip()
                # Clean up any trailing text
                motto = re.split(r"[.!?]\s+[A-Z]", motto)[0]  # Stop at next sentence
                if 10 <= len(motto) <= 150:
                    return motto

        return None

    def _is_generic_welcome(self, text: str) -> bool:
        """Check if text is a generic welcome/intro message rather than actual ethos.

        Returns True if text contains headteacher welcome phrases.
        """
        welcome_patterns = [
            r"welcome\s+to\s+(our\s+)?school",
            r"(i|we)\s+(would\s+like\s+to\s+)?wish\s+you",
            r"(headteacher|head\s+teacher|principal)",
            r"(i\s+am\s+)?(proud|pleased|delighted)\s+to",
            r"my\s+name\s+is",
            r"please\s+do\s+not\s+hesitate",
            r"take\s+a\s+look\s+around",
        ]

        text_lower = text.lower()
        for pattern in welcome_patterns:
            if re.search(pattern, text_lower):
                return True

        return False

    def _clean_ethos(self, text: str) -> str:
        """Clean and truncate ethos text to create a one-liner.

        Parameters
        ----------
        text:
            Raw extracted text.

        Returns
        -------
        str
            Cleaned and truncated ethos statement (max 500 chars).
        """
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Remove common prefixes
        text = re.sub(r"^(Our\s+)?(ethos|mission|vision|values?)(\s+is)?:?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(At\s+\w+\s+School,?\s+)", "", text, flags=re.IGNORECASE)

        # Take only the first sentence or two if too long
        if len(text) > 500:
            # Try to break at sentence boundaries
            sentences = re.split(r"[.!?]\s+", text)
            text = sentences[0]
            if len(text) < 100 and len(sentences) > 1:
                text = sentences[0] + ". " + sentences[1]

        # Hard truncate at 500 chars
        if len(text) > 500:
            text = text[:497] + "..."

        return text.strip()

    def _generate_fallback_ethos(self, school_name: str) -> str:
        """Generate a generic fallback ethos when extraction fails.

        Parameters
        ----------
        school_name:
            Name of the school.

        Returns
        -------
        str
            Generic ethos statement.
        """
        return (
            f"{school_name} is committed to providing high-quality education "
            "and supporting every child to reach their full potential."
        )

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_ethos_to_db(self, school_id: int, ethos: str) -> None:
        """Update the School table with the extracted ethos.

        Parameters
        ----------
        school_id:
            Database primary key of the school.
        ethos:
            Extracted ethos statement.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            stmt = update(School).where(School.id == school_id).values(ethos=ethos)
            session.execute(stmt)
            session.commit()
            self._logger.debug("Updated ethos for school_id=%d", school_id)


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the ethos agent.

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
        description="Extract school ethos one-liners from school websites.",
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
    """CLI entry point for the ethos agent.

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
    agent = EthosAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
