"""Shared base class for government data services.

Provides HTTP downloading with retry logic, caching, and common utilities
used by GIAS, Ofsted, and EES services.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path("./data/cache/gov_data")
_HTTP_TIMEOUT = 120.0
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_USER_AGENT = "SchoolFinder/1.0 (Education Data Import)"


class BaseGovDataService:
    """Base class for government data fetching services.

    Provides HTTP download with retries, disk-based caching with TTL,
    and common file handling utilities.

    Parameters
    ----------
    cache_dir:
        Directory for cached downloads.
    cache_ttl_hours:
        How many hours a cached file remains valid before re-downloading.
    """

    def __init__(
        self,
        cache_dir: Path | str = _DEFAULT_CACHE_DIR,
        cache_ttl_hours: int = 24,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self._logger = logging.getLogger(f"{__name__}.{type(self).__name__}")

    def download(
        self,
        url: str,
        filename: str | None = None,
        force: bool = False,
    ) -> Path:
        """Download a file, using cache if available and fresh.

        Parameters
        ----------
        url:
            URL to download.
        filename:
            Optional filename for the cached file. If not provided, a hash
            of the URL is used.
        force:
            If True, bypass the cache and always re-download.

        Returns
        -------
        Path
            Path to the downloaded (or cached) file.
        """
        if filename is None:
            url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
            filename = f"{url_hash}.dat"

        cache_path = self.cache_dir / filename

        if not force and self._is_cache_fresh(cache_path):
            self._logger.info("Using cached file: %s", cache_path)
            return cache_path

        self._logger.info("Downloading %s ...", url)

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                with httpx.Client(
                    timeout=_HTTP_TIMEOUT,
                    follow_redirects=True,
                    headers={"User-Agent": _USER_AGENT},
                ) as client:
                    response = client.get(url)
                    response.raise_for_status()

                cache_path.write_bytes(response.content)
                size_mb = len(response.content) / 1_048_576
                self._logger.info("Downloaded %.1f MB -> %s", size_mb, cache_path)
                return cache_path

            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                backoff = _BACKOFF_BASE**attempt
                self._logger.warning(
                    "Download failed (attempt %d/%d): %s – retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                    backoff,
                )
                time.sleep(backoff)

        msg = f"Failed to download {url} after {_MAX_RETRIES} attempts"
        self._logger.error(msg)
        if last_exc:
            raise type(last_exc)(msg) from last_exc
        raise RuntimeError(msg)

    def download_with_fallback(
        self,
        urls: list[str],
        filename: str | None = None,
        force: bool = False,
    ) -> Path:
        """Try downloading from multiple URLs, returning the first success.

        Parameters
        ----------
        urls:
            List of URLs to try in order.
        filename:
            Optional filename for the cached file.
        force:
            If True, bypass cache.

        Returns
        -------
        Path
            Path to the downloaded file.

        Raises
        ------
        RuntimeError
            If all URLs fail.
        """
        last_exc: Exception | None = None
        for url in urls:
            try:
                return self.download(url, filename=filename, force=force)
            except Exception as exc:
                self._logger.warning("URL failed: %s (%s)", url, exc)
                last_exc = exc

        msg = f"All {len(urls)} download URLs failed"
        raise RuntimeError(msg) from last_exc

    def _is_cache_fresh(self, path: Path) -> bool:
        """Check if a cached file exists and is within the TTL."""
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        age = datetime.now() - mtime
        return age < self.cache_ttl
