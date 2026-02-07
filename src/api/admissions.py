"""Admissions API endpoints.

Provides endpoints for:
- Historical admissions data (places, applications, distances)
- Admissions likelihood estimation
- Live data refresh from GIAS
- Birth rate / demand forecasting
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from src.services.birth_rates import get_mk_birth_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admissions", tags=["admissions"])


@router.get("/birth-rates")
async def birth_rates() -> dict:
    """Get birth rate summary and demand forecasting data for Milton Keynes.

    Uses the ONS API to find available population/birth datasets
    and provides demand forecasting based on historical birth rates.
    """
    try:
        return await get_mk_birth_summary()
    except Exception as exc:
        logger.error("Error fetching birth rate data: %s", exc)
        raise HTTPException(status_code=502, detail="Could not fetch birth rate data from ONS") from exc


@router.get("/refresh-ofsted")
async def refresh_ofsted() -> dict:
    """Refresh Ofsted ratings from the latest GIAS daily extract.

    Fetches the most recent GIAS CSV and returns updated Ofsted data
    for all Milton Keynes schools. This data can then be used to update
    the local database.
    """
    from src.services.gias_live import get_fresh_ofsted_data

    try:
        ofsted_data = await get_fresh_ofsted_data()
        return {
            "count": len(ofsted_data),
            "schools": ofsted_data,
            "source": "GIAS daily extract",
        }
    except Exception as exc:
        logger.error("Error fetching GIAS data: %s", exc)
        raise HTTPException(status_code=502, detail="Could not fetch GIAS data") from exc


@router.get("/performance-sources")
async def performance_sources(
    search: str = Query(default="key stage", description="Search term for DfE publications"),
) -> dict:
    """Search for available school performance data from the DfE EES API.

    Returns available publications and datasets matching the search term.
    """
    from src.services.dfe_performance import search_performance_data

    try:
        publications = await search_performance_data(search)
        return {
            "count": len(publications),
            "publications": publications,
            "api_base": "https://api.education.gov.uk/statistics/v1",
        }
    except Exception as exc:
        logger.error("Error fetching DfE performance data: %s", exc)
        raise HTTPException(status_code=502, detail="Could not fetch DfE performance data") from exc
