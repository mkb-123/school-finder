"""DfE Explore Education Statistics (EES) API service.

Fetches school performance data (KS2 SATs, KS4 GCSEs, Progress 8, etc.)
directly from the DfE's public REST API.

API base: https://api.education.gov.uk/statistics/v1
No authentication required.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_EES_BASE = "https://api.education.gov.uk/statistics/v1"
_HTTP_TIMEOUT = 30.0
_USER_AGENT = "SchoolFinder/0.1 (+https://github.com/school-finder)"


async def list_publications(search: str | None = None) -> list[dict]:
    """List available publications from the EES API.

    Parameters
    ----------
    search:
        Optional search term to filter publications (e.g. "key stage 4").
    """
    params = {}
    if search:
        params["search"] = search

    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        resp = await client.get(f"{_EES_BASE}/publications", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", data) if isinstance(data, dict) else data


async def get_publication_datasets(publication_id: str) -> list[dict]:
    """Get available datasets for a specific publication."""
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        resp = await client.get(f"{_EES_BASE}/publications/{publication_id}/data-sets")
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", data) if isinstance(data, dict) else data


async def query_dataset(dataset_id: str, filters: dict | None = None) -> dict:
    """Query a specific dataset with optional filters.

    Parameters
    ----------
    dataset_id:
        The EES dataset ID.
    filters:
        Optional dict of filter criteria to POST to the query endpoint.
    """
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        if filters:
            resp = await client.post(
                f"{_EES_BASE}/data-sets/{dataset_id}/query",
                json=filters,
            )
        else:
            resp = await client.get(f"{_EES_BASE}/data-sets/{dataset_id}/query")
        resp.raise_for_status()
        return resp.json()


async def search_performance_data(search_term: str = "key stage") -> list[dict]:
    """Search for school performance publications.

    Returns a list of publication summaries matching the search.
    """
    return await list_publications(search=search_term)
