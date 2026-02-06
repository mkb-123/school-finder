from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Query

from src.config import get_settings
from src.schemas.school import GeocodeResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["geocode"])

# ---------------------------------------------------------------------------
# Local fallback lookup for common Milton Keynes postcodes.  Used when the
# external postcodes.io API is unreachable (e.g. in offline / CI envs).
# ---------------------------------------------------------------------------
_FALLBACK_POSTCODES: dict[str, tuple[float, float]] = {
    "MK9 1AB": (52.0430, -0.7594),
    "MK9 2FE": (52.0400, -0.7700),
    "MK7 7WH": (52.0135, -0.7325),
    "MK3 7ND": (52.0005, -0.7750),
    "MK14 6BN": (52.0585, -0.7750),
    "MK3 6EW": (51.9960, -0.7600),
    "MK2 3HQ": (52.0090, -0.7345),
    "MK16 0BJ": (52.0850, -0.7060),
    "MK8 0PT": (52.0250, -0.8100),
    "MK5 7ZP": (52.0070, -0.8050),
    "MK10 9JQ": (52.0400, -0.7080),
    "MK12 5BT": (52.0550, -0.7900),
    "MK6 5EN": (52.0280, -0.7550),
    "MK2 2RL": (51.9980, -0.7280),
    "MK8 8LH": (52.0300, -0.8150),
    "MK5 8AT": (52.0080, -0.7900),
    "MK10 9EA": (52.0370, -0.7050),
    "MK10 7AB": (52.0500, -0.7200),
    "MK16 8EP": (52.0870, -0.7100),
    "MK13 0BH": (52.0620, -0.7850),
    "MK4 2JT": (52.0020, -0.8000),
    "MK6 2TG": (52.0310, -0.7500),
    "MK4 4TD": (52.0030, -0.8200),
    "MK12 5HG": (52.0530, -0.7920),
    "MK9 4BE": (52.0410, -0.7610),
    "MK3 5ND": (51.9990, -0.7710),
    "MK14 6BQ": (52.0590, -0.7730),
    "MK3 6DP": (51.9970, -0.7560),
    "MK2 2HB": (52.0060, -0.7250),
    "MK10 7ED": (52.0480, -0.7150),
    "MK9 3": (52.0430, -0.7594),
}


def _normalise_postcode(postcode: str) -> str:
    """Normalise a UK postcode: uppercase and ensure a space before the last 3 characters.

    Handles input with or without spaces, e.g. ``"mk58dx"`` -> ``"MK5 8DX"``.
    """
    cleaned = "".join(postcode.upper().split())
    if len(cleaned) >= 4:
        return f"{cleaned[:-3]} {cleaned[-3:]}"
    return cleaned


def _fallback_lookup(postcode: str) -> GeocodeResponse | None:
    key = _normalise_postcode(postcode)
    if key in _FALLBACK_POSTCODES:
        lat, lng = _FALLBACK_POSTCODES[key]
        return GeocodeResponse(postcode=key, lat=lat, lng=lng)
    # Try matching just the outward code (e.g. "MK9")
    outward = key.split()[0] if " " in key else key
    for fb_key, (lat, lng) in _FALLBACK_POSTCODES.items():
        if fb_key.startswith(outward):
            return GeocodeResponse(postcode=key, lat=lat, lng=lng)
    return None


@router.get("/api/geocode", response_model=GeocodeResponse)
async def geocode_postcode(
    postcode: str = Query(..., description="UK postcode to geocode"),
) -> GeocodeResponse:
    """Proxy postcode geocoding requests to postcodes.io.

    Falls back to a small built-in lookup table when the external service is
    unavailable (offline development, CI, firewalled environments, etc.).
    """
    settings = get_settings()
    clean = _normalise_postcode(postcode)
    url = f"{settings.POSTCODES_IO_BASE}/postcodes/{clean}"

    # --- Try the external API first ---
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)

        if response.status_code == 200:
            data = response.json()
            result = data.get("result") or {}
            lat = result.get("latitude")
            lng = result.get("longitude")
            if lat is None or lng is None:
                logger.warning("postcodes.io returned 200 but missing coordinates for %s", clean)
            else:
                return GeocodeResponse(
                    postcode=result.get("postcode", clean),
                    lat=lat,
                    lng=lng,
                )

        # Non-200 from postcodes.io – fall through to local lookup
        logger.warning("postcodes.io returned %s for %s", response.status_code, clean)
    except Exception:
        logger.warning("postcodes.io unreachable – using local fallback for %s", clean)

    # --- Fallback to local data ---
    fallback = _fallback_lookup(clean)
    if fallback is not None:
        return fallback

    raise HTTPException(
        status_code=404,
        detail=f"Postcode '{clean}' not found (external API unavailable and no local fallback)",
    )
