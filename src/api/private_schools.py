from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.db.base import SchoolFilters, SchoolRepository
from src.db.factory import get_school_repository
from src.schemas.filters import PrivateSchoolFilterParams
from src.schemas.school import HiddenCostItem, SchoolDetailResponse, SchoolResponse, TrueAnnualCostResponse

router = APIRouter(tags=["private-schools"])


def _to_private_filters(params: PrivateSchoolFilterParams) -> SchoolFilters:
    """Convert private school API filter params to the repository's filter dataclass."""
    return SchoolFilters(
        council=params.council,
        age=params.age,
        gender=params.gender,
        is_private=True,
        max_fee=params.max_fee,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/api/private-schools", response_model=list[SchoolResponse])
async def list_private_schools(
    filters: Annotated[PrivateSchoolFilterParams, Query()],
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[SchoolResponse]:
    """List private/independent schools with optional filters."""
    school_filters = _to_private_filters(filters)
    schools = await repo.find_schools_by_filters(school_filters)
    return schools


@router.get("/api/private-schools/{school_id}", response_model=SchoolDetailResponse)
async def get_private_school(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> SchoolDetailResponse:
    """Get full details for a private school."""
    school = await repo.get_school_by_id(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    if not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")

    clubs = await repo.get_clubs_for_school(school_id)
    performance = await repo.get_performance_for_school(school_id)
    term_dates = await repo.get_term_dates_for_school(school_id)
    admissions = await repo.get_admissions_history(school_id)
    private_details = await repo.get_private_school_details(school_id)

    base = SchoolResponse.model_validate(school, from_attributes=True)
    return SchoolDetailResponse(
        **base.model_dump(),
        clubs=clubs,
        performance=performance,
        term_dates=term_dates,
        admissions_history=admissions,
        private_details=private_details,
    )


@router.get("/api/private-schools/{school_id}/true-cost", response_model=list[TrueAnnualCostResponse])
async def get_private_school_true_cost(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[TrueAnnualCostResponse]:
    """Get true annual cost breakdown including all hidden costs for a private school.

    Returns one breakdown per fee age group (e.g., Nursery, Junior, Senior).
    """
    school = await repo.get_school_by_id(school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    if not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")

    private_details = await repo.get_private_school_details(school_id)
    if not private_details:
        raise HTTPException(status_code=404, detail="No fee information available for this school")

    results = []
    for detail in private_details:
        hidden_cost_items = []
        compulsory_per_year = 0.0
        optional_per_year = 0.0
        one_time_total = 0.0

        # Lunches (per term, 3 terms per year)
        if detail.lunches_per_term:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="School lunches",
                    amount=detail.lunches_per_term,
                    frequency="per term",
                    compulsory=detail.lunches_compulsory,
                )
            )
            annual_lunches = detail.lunches_per_term * 3
            if detail.lunches_compulsory:
                compulsory_per_year += annual_lunches
            else:
                optional_per_year += annual_lunches

        # Trips (per term, 3 terms per year)
        if detail.trips_per_term:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="School trips and residentials",
                    amount=detail.trips_per_term,
                    frequency="per term",
                    compulsory=detail.trips_compulsory,
                )
            )
            annual_trips = detail.trips_per_term * 3
            if detail.trips_compulsory:
                compulsory_per_year += annual_trips
            else:
                optional_per_year += annual_trips

        # Exam fees (per year)
        if detail.exam_fees_per_year:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="Exam entry fees",
                    amount=detail.exam_fees_per_year,
                    frequency="per year",
                    compulsory=detail.exam_fees_compulsory,
                )
            )
            if detail.exam_fees_compulsory:
                compulsory_per_year += detail.exam_fees_per_year
            else:
                optional_per_year += detail.exam_fees_per_year

        # Textbooks (per year)
        if detail.textbooks_per_year:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="Textbooks and materials",
                    amount=detail.textbooks_per_year,
                    frequency="per year",
                    compulsory=detail.textbooks_compulsory,
                )
            )
            if detail.textbooks_compulsory:
                compulsory_per_year += detail.textbooks_per_year
            else:
                optional_per_year += detail.textbooks_per_year

        # Music tuition (per term, 3 terms per year)
        if detail.music_tuition_per_term:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="Individual music tuition",
                    amount=detail.music_tuition_per_term,
                    frequency="per term",
                    compulsory=detail.music_tuition_compulsory,
                )
            )
            annual_music = detail.music_tuition_per_term * 3
            if detail.music_tuition_compulsory:
                compulsory_per_year += annual_music
            else:
                optional_per_year += annual_music

        # Sports (per term, 3 terms per year)
        if detail.sports_per_term:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="Sports fixtures and transport",
                    amount=detail.sports_per_term,
                    frequency="per term",
                    compulsory=detail.sports_compulsory,
                )
            )
            annual_sports = detail.sports_per_term * 3
            if detail.sports_compulsory:
                compulsory_per_year += annual_sports
            else:
                optional_per_year += annual_sports

        # Uniform (per year)
        if detail.uniform_per_year:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="Uniform from designated suppliers",
                    amount=detail.uniform_per_year,
                    frequency="per year",
                    compulsory=detail.uniform_compulsory,
                )
            )
            if detail.uniform_compulsory:
                compulsory_per_year += detail.uniform_per_year
            else:
                optional_per_year += detail.uniform_per_year

        # Registration fee (one-time)
        if detail.registration_fee:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="Registration fee",
                    amount=detail.registration_fee,
                    frequency="one-time",
                    compulsory=True,
                )
            )
            one_time_total += detail.registration_fee

        # Deposit (one-time, often refundable)
        if detail.deposit_fee:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="Deposit (often refundable)",
                    amount=detail.deposit_fee,
                    frequency="one-time",
                    compulsory=True,
                )
            )
            one_time_total += detail.deposit_fee

        # Insurance (per year)
        if detail.insurance_per_year:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="School insurance levy",
                    amount=detail.insurance_per_year,
                    frequency="per year",
                    compulsory=detail.insurance_compulsory,
                )
            )
            if detail.insurance_compulsory:
                compulsory_per_year += detail.insurance_per_year
            else:
                optional_per_year += detail.insurance_per_year

        # Building fund (per year)
        if detail.building_fund_per_year:
            hidden_cost_items.append(
                HiddenCostItem(
                    name="Building/development fund",
                    amount=detail.building_fund_per_year,
                    frequency="per year",
                    compulsory=detail.building_fund_compulsory,
                )
            )
            if detail.building_fund_compulsory:
                compulsory_per_year += detail.building_fund_per_year
            else:
                optional_per_year += detail.building_fund_per_year

        # Calculate true annual cost
        annual_fee = detail.annual_fee or (detail.termly_fee * 3 if detail.termly_fee else 0.0)
        true_annual_cost = annual_fee + compulsory_per_year
        total_with_optional = true_annual_cost + optional_per_year

        results.append(
            TrueAnnualCostResponse(
                school_id=school_id,
                school_name=school.name,
                fee_age_group=detail.fee_age_group,
                termly_fee=detail.termly_fee,
                annual_fee=detail.annual_fee,
                hidden_cost_items=hidden_cost_items,
                compulsory_hidden_costs_per_year=compulsory_per_year,
                optional_hidden_costs_per_year=optional_per_year,
                one_time_costs=one_time_total,
                true_annual_cost=true_annual_cost,
                total_with_optional=total_with_optional,
                notes=detail.hidden_costs_notes,
            )
        )

    return results
