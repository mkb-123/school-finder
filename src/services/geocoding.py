"""Geocoding service using the postcodes.io API (free, no API key required).

Provides postcode-to-coordinate lookup, validation, and full postcode info
including council / local authority data for UK postcodes.
"""

from __future__ import annotations

import httpx


class PostcodeNotFoundError(Exception):
    """Raised when a postcode cannot be found or is invalid."""

    def __init__(self, postcode: str) -> None:
        self.postcode = postcode
        super().__init__(f"Postcode not found: {postcode}")


class GeocodingServiceError(Exception):
    """Raised when the geocoding service encounters a network or unexpected error."""


# ---------------------------------------------------------------------------
# Default API base URL -- override via config / environment variable
# ---------------------------------------------------------------------------
_DEFAULT_API_BASE_URL = "https://api.postcodes.io"


def _get_api_base_url() -> str:
    """Return the postcodes.io API base URL from config (if available) or the default.

    Tries to import ``src.config.settings`` and read ``POSTCODES_IO_BASE_URL``.
    Falls back to the hard-coded default when the config module is not yet set up.
    """
    try:
        from src.config import settings  # type: ignore[import-untyped]

        url: str = getattr(settings, "POSTCODES_IO_BASE_URL", _DEFAULT_API_BASE_URL)
        return url
    except Exception:  # noqa: BLE001
        return _DEFAULT_API_BASE_URL


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def geocode_postcode(postcode: str) -> tuple[float, float]:
    """Geocode a UK postcode and return its latitude and longitude.

    Parameters
    ----------
    postcode:
        A UK postcode string (e.g. ``"MK9 1AB"``).

    Returns
    -------
    tuple[float, float]
        A ``(latitude, longitude)`` pair.

    Raises
    ------
    PostcodeNotFoundError
        If the postcode does not exist or is invalid.
    GeocodingServiceError
        If there is a network or unexpected error communicating with the API.
    """
    info = await get_postcode_info(postcode)
    return (info["latitude"], info["longitude"])


async def validate_postcode(postcode: str) -> bool:
    """Check whether a UK postcode is valid according to postcodes.io.

    Parameters
    ----------
    postcode:
        A UK postcode string.

    Returns
    -------
    bool
        ``True`` if the postcode is valid, ``False`` otherwise.
    """
    base_url = _get_api_base_url()
    url = f"{base_url}/postcodes/{postcode}/validate"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return bool(data.get("result", False))
    except httpx.HTTPStatusError as exc:
        raise GeocodingServiceError(
            f"HTTP error while validating postcode '{postcode}': {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise GeocodingServiceError(f"Network error while validating postcode '{postcode}': {exc}") from exc


async def get_postcode_info(postcode: str) -> dict:
    """Fetch full postcode information from postcodes.io.

    The returned dictionary includes keys such as ``latitude``, ``longitude``,
    ``admin_district`` (council / local authority name), ``parish``,
    ``parliamentary_constituency``, and many more.

    Parameters
    ----------
    postcode:
        A UK postcode string (e.g. ``"MK9 1AB"``).

    Returns
    -------
    dict
        The ``result`` object from the postcodes.io response.

    Raises
    ------
    PostcodeNotFoundError
        If the postcode does not exist or is invalid (HTTP 404).
    GeocodingServiceError
        If there is a network or unexpected error communicating with the API.
    """
    base_url = _get_api_base_url()
    url = f"{base_url}/postcodes/{postcode}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)

            if response.status_code == 404:
                raise PostcodeNotFoundError(postcode)

            response.raise_for_status()
            data = response.json()

            result = data.get("result")
            if result is None:
                raise PostcodeNotFoundError(postcode)

            return result

    except PostcodeNotFoundError:
        # Re-raise without wrapping
        raise
    except httpx.HTTPStatusError as exc:
        raise GeocodingServiceError(
            f"HTTP error while fetching postcode '{postcode}': {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise GeocodingServiceError(f"Network error while fetching postcode '{postcode}': {exc}") from exc
