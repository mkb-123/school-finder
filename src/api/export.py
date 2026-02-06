"""Export API endpoints for generating downloadable reports."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.services.catchment import haversine_distance
from src.services.decision import generate_pros_cons, school_data_from_orm
from src.services.pdf_export import generate_comparison_pdf

router = APIRouter(tags=["export"])


@router.get("/api/export/pdf")
async def export_schools_pdf(
    school_ids: Annotated[
        str,
        Query(description="Comma-separated school IDs to include in the PDF"),
    ],
    lat: Annotated[float | None, Query(description="User latitude for distance calculation")] = None,
    lng: Annotated[float | None, Query(description="User longitude for distance calculation")] = None,
    repo: SchoolRepository = Depends(get_school_repository),
) -> Response:
    """Export a school comparison as a downloadable PDF."""
    ids = [int(s.strip()) for s in school_ids.split(",") if s.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="At least one school_id is required")

    school_dicts = []
    for sid in ids:
        school = await repo.get_school_by_id(sid)
        if school is None:
            continue

        clubs = await repo.get_clubs_for_school(sid)
        performance = await repo.get_performance_for_school(sid)
        private_details = await repo.get_private_school_details(sid)

        distance_km = None
        if lat is not None and lng is not None and school.lat is not None and school.lng is not None:
            distance_km = round(haversine_distance(lat, lng, school.lat, school.lng), 2)

        # Generate pros/cons
        sd = school_data_from_orm(school, clubs, distance_km=distance_km)
        pros, cons = generate_pros_cons(sd)

        school_dict = {
            "name": school.name,
            "type": school.type,
            "ofsted_rating": school.ofsted_rating,
            "address": school.address,
            "postcode": school.postcode,
            "distance_km": distance_km,
            "age_range_from": school.age_range_from,
            "age_range_to": school.age_range_to,
            "gender_policy": school.gender_policy,
            "faith": school.faith,
            "is_private": school.is_private,
            "clubs": [{"club_type": c.club_type, "name": c.name} for c in clubs],
            "performance": [{"metric_type": p.metric_type, "metric_value": p.metric_value} for p in performance[:5]],
            "private_details": [
                {"termly_fee": pd.termly_fee, "annual_fee": pd.annual_fee, "fee_age_group": pd.fee_age_group}
                for pd in private_details
            ],
            "pros": pros,
            "cons": cons,
        }
        school_dicts.append(school_dict)

    if not school_dicts:
        raise HTTPException(status_code=404, detail="No schools found for the given IDs")

    pdf_bytes = generate_comparison_pdf(school_dicts)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=school-comparison.pdf"},
    )
