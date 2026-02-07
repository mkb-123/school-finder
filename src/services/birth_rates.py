"""Birth rate and population data service for demand forecasting.

Uses the ONS (Office for National Statistics) API and published datasets
to provide birth rate data that can be used to predict future school
demand in a local authority area.

ONS API base: https://api.beta.ons.gov.uk/v1
No authentication required.

Birth data is available at Local Authority level (e.g. Milton Keynes = E06000042).
Ward-level data is not publicly available via API but LA-level trends
combined with housing development data can give useful demand signals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_ONS_BASE = "https://api.beta.ons.gov.uk/v1"
_HTTP_TIMEOUT = 30.0
_USER_AGENT = "SchoolFinder/0.1 (+https://github.com/school-finder)"

# ONS geography code for Milton Keynes
_MK_GEOGRAPHY_CODE = "E06000042"


@dataclass
class BirthYearData:
    """Birth data for a single year in a local authority."""

    year: int
    live_births: int
    geography_code: str
    geography_name: str


@dataclass
class DemandForecast:
    """School demand forecast based on birth rate trends."""

    reception_year: int  # Academic year these children would start Reception
    estimated_children: int
    trend: str  # "increasing", "stable", "decreasing"
    trend_pct_change: float  # Year-on-year % change
    notes: str


async def list_ons_datasets(search: str | None = None) -> list[dict]:
    """List available datasets from the ONS API.

    Parameters
    ----------
    search:
        Optional search term to filter datasets.
    """
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        url = f"{_ONS_BASE}/datasets"
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])

        if search:
            search_lower = search.lower()
            items = [
                item
                for item in items
                if search_lower in (item.get("title", "") or "").lower()
                or search_lower in (item.get("description", "") or "").lower()
            ]

        return items


async def get_population_estimates(
    geography_code: str = _MK_GEOGRAPHY_CODE,
) -> list[dict]:
    """Fetch mid-year population estimates for a local authority.

    These estimates include components of change (births, deaths,
    internal/international migration) which are useful for demand
    forecasting.
    """
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        # Try the population estimates dataset
        url = f"{_ONS_BASE}/datasets"
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

        # Find population-related datasets
        results = []
        for item in data.get("items", []):
            title = (item.get("title", "") or "").lower()
            if "population" in title or "birth" in title:
                results.append(
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "description": item.get("description", "")[:200],
                    }
                )

        return results


def estimate_reception_demand(
    birth_data: list[BirthYearData],
) -> list[DemandForecast]:
    """Estimate future Reception year demand from birth rate data.

    Children born in academic year X (Sep-Aug) typically start
    Reception in academic year X+4/X+5.

    For example:
    - Born Sep 2020 - Aug 2021 -> Start Reception Sep 2025 (2025/2026)
    - Born Sep 2021 - Aug 2022 -> Start Reception Sep 2026 (2026/2027)

    Parameters
    ----------
    birth_data:
        Historical birth data by calendar year for the local authority.

    Returns
    -------
    list[DemandForecast]
        Estimated demand for upcoming Reception years.
    """
    if not birth_data or len(birth_data) < 2:
        return []

    sorted_data = sorted(birth_data, key=lambda x: x.year)
    forecasts = []

    for i, bd in enumerate(sorted_data):
        # Children born in year X start Reception in year X+4 or X+5
        # Use X+5 as the academic year start (conservative)
        reception_year = bd.year + 5

        # Calculate trend
        if i > 0:
            prev = sorted_data[i - 1].live_births
            pct_change = ((bd.live_births - prev) / prev * 100) if prev > 0 else 0

            if pct_change > 2:
                trend = "increasing"
            elif pct_change < -2:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            pct_change = 0.0
            trend = "stable"

        notes = f"Based on {bd.live_births} births in {bd.geography_name} during calendar year {bd.year}."

        forecasts.append(
            DemandForecast(
                reception_year=reception_year,
                estimated_children=bd.live_births,
                trend=trend,
                trend_pct_change=round(pct_change, 1),
                notes=notes,
            )
        )

    return forecasts


async def get_mk_birth_summary() -> dict:
    """Get a summary of birth rate data for Milton Keynes.

    Returns available ONS datasets and any cached birth data.
    This is the main entry point for the birth rate feature.
    """
    datasets = await get_population_estimates(_MK_GEOGRAPHY_CODE)

    return {
        "geography_code": _MK_GEOGRAPHY_CODE,
        "geography_name": "Milton Keynes",
        "available_datasets": datasets,
        "note": (
            "Birth data at Local Authority level is available from ONS. "
            "Ward-level birth data requires a bespoke data request from ONS. "
            "LA-level trends combined with housing development data can "
            "indicate future school demand pressure."
        ),
    }
