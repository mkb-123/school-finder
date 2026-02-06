"""Decision support API endpoints.

Provides scoring, pros/cons generation, and "what if" scenario endpoints
for the decision support page.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.schemas.decision import (
    DecisionScoreResponse,
    ProsConsResponse,
    SchoolScoreComponentResponse,
    ScoredSchoolResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from src.services.decision import (
    SchoolData,
    ScoredSchool,
    WeightedScorer,
    WhatIfScenario,
    apply_what_if,
    generate_pros_cons,
    school_data_from_orm,
)

router = APIRouter(tags=["decision"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_weights(weights_str: str | None) -> dict[str, float] | None:
    """Parse a ``key:value,key:value`` weight string into a dict.

    Example input: ``"distance:0.3,ofsted:0.3,clubs:0.2,fees:0.2"``
    """
    if not weights_str:
        return None
    result: dict[str, float] = {}
    for pair in weights_str.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        key, _, val = pair.partition(":")
        try:
            result[key.strip()] = float(val.strip())
        except ValueError:
            continue
    return result or None


async def _load_school_data(
    school_ids: list[int],
    repo: SchoolRepository,
) -> list[SchoolData]:
    """Load schools from the repository and convert to SchoolData."""
    school_data_list: list[SchoolData] = []
    for sid in school_ids:
        school = await repo.get_school_by_id(sid)
        if school is None:
            continue
        clubs = await repo.get_clubs_for_school(sid)
        sd = school_data_from_orm(school, clubs)
        school_data_list.append(sd)
    return school_data_list


def _scored_to_response(scored: ScoredSchool) -> ScoredSchoolResponse:
    """Convert an internal ScoredSchool to a Pydantic response."""
    return ScoredSchoolResponse(
        school_id=scored.school.id,
        school_name=scored.school.name,
        composite_score=scored.composite_score,
        component_scores=SchoolScoreComponentResponse(**scored.component_scores),
        ofsted_rating=scored.school.ofsted_rating,
        distance_km=scored.school.distance_km,
        is_private=scored.school.is_private,
        has_breakfast_club=scored.school.has_breakfast_club,
        has_afterschool_club=scored.school.has_afterschool_club,
        annual_fee=scored.school.annual_fee,
        postcode=scored.school.postcode,
        school_type=scored.school.school_type,
        faith=scored.school.faith,
        age_range_from=scored.school.age_range_from,
        age_range_to=scored.school.age_range_to,
        gender_policy=scored.school.gender_policy,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/decision/score", response_model=DecisionScoreResponse)
async def score_schools(
    school_ids: Annotated[
        str,
        Query(
            description="Comma-separated school IDs to score (e.g. '1,2,3')",
        ),
    ],
    weights: Annotated[
        str | None,
        Query(
            description="Comma-separated key:value weights (e.g. 'distance:0.3,ofsted:0.3,clubs:0.2,fees:0.2')",
        ),
    ] = None,
    repo: SchoolRepository = Depends(get_school_repository),
) -> DecisionScoreResponse:
    """Score and rank schools by weighted composite score."""
    ids = [int(s.strip()) for s in school_ids.split(",") if s.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="At least one school_id is required")

    parsed_weights = _parse_weights(weights)
    scorer = WeightedScorer(parsed_weights)

    school_data_list = await _load_school_data(ids, repo)
    if not school_data_list:
        raise HTTPException(status_code=404, detail="No schools found for the given IDs")

    ranked = scorer.rank_schools(school_data_list)

    return DecisionScoreResponse(
        schools=[_scored_to_response(s) for s in ranked],
        weights_used=scorer.weights,
    )


@router.get("/api/decision/pros-cons", response_model=ProsConsResponse)
async def get_pros_cons(
    school_id: Annotated[int, Query(description="School ID to generate pros/cons for")],
    repo: SchoolRepository = Depends(get_school_repository),
) -> ProsConsResponse:
    """Generate auto-generated pros and cons for a single school."""
    school = await repo.get_school_by_id(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    clubs = await repo.get_clubs_for_school(school_id)
    sd = school_data_from_orm(school, clubs)
    pros, cons = generate_pros_cons(sd)

    return ProsConsResponse(
        school_id=sd.id,
        school_name=sd.name,
        pros=pros,
        cons=cons,
    )


@router.post("/api/decision/what-if", response_model=WhatIfResponse)
async def what_if_scenario(
    request: WhatIfRequest,
    repo: SchoolRepository = Depends(get_school_repository),
) -> WhatIfResponse:
    """Apply 'what if' constraints and re-rank schools.

    Accepts a list of school IDs, optional weight overrides, and
    scenario filters.  Returns a re-ranked list of schools that
    pass the constraints.
    """
    if not request.school_ids:
        raise HTTPException(status_code=400, detail="At least one school_id is required")

    school_data_list = await _load_school_data(request.school_ids, repo)
    if not school_data_list:
        raise HTTPException(status_code=404, detail="No schools found for the given IDs")

    scenario = WhatIfScenario(
        max_distance_km=request.max_distance_km,
        min_rating=request.min_rating,
        include_faith=request.include_faith,
        max_annual_fee=request.max_annual_fee,
    )

    filtered = apply_what_if(school_data_list, scenario)
    scorer = WeightedScorer(request.weights)
    ranked = scorer.rank_schools(filtered)

    filters_applied: dict[str, str | float | bool | None] = {
        "max_distance_km": request.max_distance_km,
        "min_rating": request.min_rating,
        "include_faith": request.include_faith,
        "max_annual_fee": request.max_annual_fee,
    }

    return WhatIfResponse(
        schools=[_scored_to_response(s) for s in ranked],
        weights_used=scorer.weights,
        filters_applied=filters_applied,
    )
