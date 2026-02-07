"""Shared base class for all data-collection agents.

Provides common functionality including HTTP fetching with rate limiting,
disk-based response caching, HTML parsing, and retry logic with exponential
backoff.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import pathlib
from abc import ABC, abstractmethod

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = "./data/cache"
_DEFAULT_DELAY = 1.0
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_HTTP_TIMEOUT = 30.0
_USER_AGENT = "SchoolFinder/0.1 (+https://github.com/school-finder)"


class BaseAgent(ABC):
    """Abstract base class that every data-collection agent inherits from.

    Subclasses must implement the :meth:`run` coroutine which serves as the
    main entry point for the agent's data-collection pipeline.

    Parameters
    ----------
    council:
        Name of the council the agent is collecting data for
        (e.g. ``"Milton Keynes"``).
    cache_dir:
        Directory where raw HTTP responses are cached on disk.
    delay:
        Minimum number of seconds to wait between successive HTTP requests
        to respect rate limits.
    """

    def __init__(
        self,
        council: str,
        cache_dir: str = _DEFAULT_CACHE_DIR,
        delay: float = _DEFAULT_DELAY,
    ) -> None:
        self.council = council
        self.cache_dir = pathlib.Path(cache_dir)
        self.delay = delay

        # Ensure the cache directory exists.
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Timestamp of the last HTTP request, used for rate limiting.
        self._last_request_time: float = 0.0

        self._logger = logging.getLogger(f"{__name__}.{type(self).__name__}")
        self._logger.info("Initialised %s for council=%r", type(self).__name__, council)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def run(self) -> None:
        """Execute the agent's main data-collection pipeline.

        Subclasses must override this method with the concrete scraping,
        parsing, and database-writing logic.
        """

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def fetch_page(self, url: str) -> str:
        """Fetch a URL, returning the response body as a string.

        Behaviour:
        * Returns a cached response when one exists on disk.
        * Respects the configured ``self.delay`` between live HTTP requests.
        * Retries up to 3 times with exponential backoff on transient network
          errors.

        Parameters
        ----------
        url:
            The URL to fetch.

        Returns
        -------
        str
            The response body text.

        Raises
        ------
        httpx.HTTPStatusError
            If the server returns an error status after all retries.
        httpx.TransportError
            If a network-level error persists after all retries.
        """
        # Normalize URL: prepend https:// if no protocol specified
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Check the disk cache first.
        cached = await self.fetch_cached(url)
        if cached is not None:
            self._logger.debug("Cache hit for %s", url)
            return cached

        # Rate-limit: wait until self.delay seconds have elapsed since the
        # previous request.
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self.delay:
            wait = self.delay - elapsed
            self._logger.debug("Rate-limiting: sleeping %.2fs", wait)
            await asyncio.sleep(wait)

        # Retry loop with exponential backoff.
        last_exc: BaseException | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                self._logger.info("Fetching %s (attempt %d/%d)", url, attempt + 1, _MAX_RETRIES)
                async with httpx.AsyncClient(
                    timeout=_HTTP_TIMEOUT,
                    follow_redirects=True,
                    headers={"User-Agent": _USER_AGENT},
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()

                self._last_request_time = asyncio.get_event_loop().time()
                content = response.text

                # Persist to disk cache.
                self.save_cache(url, content)
                return content

            except httpx.HTTPStatusError as exc:
                # Don't retry client errors (4xx) — the page simply doesn't exist.
                if 400 <= exc.response.status_code < 500:
                    self._logger.debug(
                        "Client error %d for %s – not retrying",
                        exc.response.status_code,
                        url,
                    )
                    raise
                last_exc = exc
                backoff = _BACKOFF_BASE**attempt
                self._logger.warning(
                    "Server error %d for %s (attempt %d/%d) – retrying in %.1fs",
                    exc.response.status_code,
                    url,
                    attempt + 1,
                    _MAX_RETRIES,
                    backoff,
                )
                await asyncio.sleep(backoff)
            except httpx.TransportError as exc:
                last_exc = exc
                backoff = _BACKOFF_BASE**attempt
                self._logger.warning(
                    "Transport error for %s (attempt %d/%d): %s – retrying in %.1fs",
                    url,
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)

        # All retries exhausted.
        msg = f"Failed to fetch {url} after {_MAX_RETRIES} attempts"
        self._logger.error(msg)
        raise RuntimeError(msg) from last_exc

    async def fetch_cached(self, url: str) -> str | None:
        """Return the cached response for *url*, or ``None`` if not cached.

        Parameters
        ----------
        url:
            The URL whose cached response should be looked up.

        Returns
        -------
        str | None
            The cached response text, or ``None`` when no cache entry exists.
        """
        cache_path = self._cache_path(url)
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")
        return None

    def save_cache(self, url: str, content: str) -> None:
        """Persist a response body to the disk cache.

        The cache filename is derived from a SHA-256 hash of the URL so that
        arbitrary URLs map to safe, unique filenames.

        Parameters
        ----------
        url:
            The URL that was fetched.
        content:
            The response body to cache.
        """
        cache_path = self._cache_path(url)
        cache_path.write_text(content, encoding="utf-8")
        self._logger.debug("Cached response for %s -> %s", url, cache_path)

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse an HTML string into a :class:`~bs4.BeautifulSoup` tree.

        Uses the ``lxml`` parser for speed and robustness.

        Parameters
        ----------
        html:
            Raw HTML string to parse.

        Returns
        -------
        BeautifulSoup
            The parsed document tree.
        """
        return BeautifulSoup(html, "lxml")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_path(self, url: str) -> pathlib.Path:
        """Return the cache file path for a given URL.

        The filename is the hex-encoded SHA-256 digest of the URL with an
        ``.html`` extension.
        """
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.html"
