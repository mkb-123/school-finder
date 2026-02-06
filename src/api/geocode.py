from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query

from src.config import get_settings
from src.schemas.school import GeocodeResponse

router = APIRouter(tags=["geocode"])


@router.get("/api/geocode", response_model=GeocodeResponse)
async def geocode_postcode(
    postcode: str = Query(..., description="UK postcode to geocode"),
) -> GeocodeResponse:
    """Proxy postcode geocoding requests to postcodes.io."""
    settings = get_settings()
    url = f"{settings.POSTCODES_IO_BASE}/postcodes/{postcode}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail="Postcode lookup failed",
        )

    data = response.json()
    result = data.get("result", {})

    return GeocodeResponse(
        postcode=result.get("postcode", postcode),
        lat=result.get("latitude", 0.0),
        lng=result.get("longitude", 0.0),
    )
