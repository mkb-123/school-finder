from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository
from src.schemas.school import CompareResponse, SchoolDetailResponse, SchoolResponse

router = APIRouter(tags=["compare"])


@router.get("/api/compare", response_model=CompareResponse)
async def compare_schools(
    ids: Annotated[str, Query(description="Comma-separated school IDs to compare")],
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> CompareResponse:
    """Compare multiple schools side by side."""
    from src.schemas.school import OfstedTrajectoryResponse, ParkingRatingSummary
    from src.services.ofsted_trajectory import calculate_trajectory

    school_ids = [int(id_str.strip()) for id_str in ids.split(",") if id_str.strip()]

    details: list[SchoolDetailResponse] = []
    for school_id in school_ids:
        school = await repo.get_school_by_id(school_id)
        if school is None:
            continue

        clubs = await repo.get_clubs_for_school(school_id)
        holiday_clubs = await repo.get_holiday_clubs_for_school(school_id)
        performance = await repo.get_performance_for_school(school_id)
        term_dates = await repo.get_term_dates_for_school(school_id)
        admissions = await repo.get_admissions_history(school_id)
        admissions_criteria = await repo.get_admissions_criteria_for_school(school_id)
        private_details = await repo.get_private_school_details(school_id)
        class_sizes = await repo.get_class_sizes(school_id)
        uniform = await repo.get_uniform_for_school(school_id)

        # Get Ofsted trajectory
        ofsted_history = await repo.get_ofsted_history(school_id)
        trajectory_data = calculate_trajectory(ofsted_history)
        ofsted_trajectory = (
            OfstedTrajectoryResponse(school_id=school_id, history=ofsted_history, **trajectory_data)
            if ofsted_history
            else None
        )

        # Calculate parking summary
        parking_ratings = await repo.get_parking_ratings_for_school(school_id)
        parking_summary = None
        if parking_ratings:

            def _avg(field: str) -> float | None:
                values = [getattr(r, field) for r in parking_ratings if getattr(r, field) is not None]
                return sum(values) / len(values) if values else None

            avg_dropoff = _avg("dropoff_chaos")
            avg_pickup = _avg("pickup_chaos")
            avg_parking = _avg("parking_availability")
            avg_congestion = _avg("road_congestion")
            avg_restrictions = _avg("restrictions_hazards")

            all_scores = [avg_dropoff, avg_pickup, avg_parking, avg_congestion, avg_restrictions]
            valid_scores = [s for s in all_scores if s is not None]
            overall = sum(valid_scores) / len(valid_scores) if valid_scores else None

            parking_summary = ParkingRatingSummary(
                school_id=school_id,
                total_ratings=len(parking_ratings),
                avg_dropoff_chaos=avg_dropoff,
                avg_pickup_chaos=avg_pickup,
                avg_parking_availability=avg_parking,
                avg_road_congestion=avg_congestion,
                avg_restrictions_hazards=avg_restrictions,
                overall_chaos_score=overall,
            )

        base = SchoolResponse.model_validate(school, from_attributes=True)
        details.append(
            SchoolDetailResponse(
                **base.model_dump(),
                clubs=clubs,
                holiday_clubs=holiday_clubs,
                performance=performance,
                term_dates=term_dates,
                admissions_history=admissions,
                admissions_criteria=admissions_criteria,
                private_details=private_details,
                class_sizes=class_sizes,
                parking_summary=parking_summary,
                uniform=uniform,
                ofsted_trajectory=ofsted_trajectory,
            )
        )

    return CompareResponse(schools=details)
