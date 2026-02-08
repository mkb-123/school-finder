from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.db.base import SchoolFilters, SchoolRepository
from src.db.factory import get_school_repository
from src.schemas.filters import PrivateSchoolFilterParams
from src.schemas.school import (
    BursaryResponse,
    BursarySchoolEntry,
    CurriculumResponse,
    EntryAssessmentResponse,
    FacilityResponse,
    FeeComparisonEntry,
    FeeComparisonResponse,
    HiddenCostItem,
    ISIInspectionResponse,
    OpenDayResponse,
    PrivateSchoolDetailsResponse,
    PrivateSchoolResultsResponse,
    ScholarshipResponse,
    ScholarshipSchoolEntry,
    SchoolDetailResponse,
    SchoolResponse,
    SiblingDiscountResponse,
    TrueAnnualCostResponse,
    UpcomingOpenDayEntry,
    UpcomingOpenDaysResponse,
)

router = APIRouter(tags=["private-schools"])


def _to_private_filters(params: PrivateSchoolFilterParams) -> SchoolFilters:
    """Convert private school API filter params to the repository's filter dataclass.

    Private schools are not scoped to a single council — they are returned
    from all nearby areas that were imported during seeding.
    """
    return SchoolFilters(
        age=params.age,
        gender=params.gender,
        is_private=True,
        max_fee=params.max_fee,
        min_fee=params.min_fee,
        has_transport=params.has_transport,
        has_bursaries=params.has_bursaries,
        has_scholarships=params.has_scholarships,
        entry_point=params.entry_point,
        search=params.search,
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


@router.get(
    "/api/private-schools/compare/fees",
    response_model=FeeComparisonResponse,
)
async def compare_private_school_fees(
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> FeeComparisonResponse:
    """Compare fees across all nearby private schools side by side.

    Returns fee tiers, bursary/scholarship availability, and transport info
    for every private school in the database (imported by radius during seeding).
    """
    schools = await repo.get_all_private_schools_with_fees()
    entries = []
    for school in schools:
        details = school.private_details
        termly_fees = [d.termly_fee for d in details if d.termly_fee is not None]
        transport_flags = [d.provides_transport for d in details if d.provides_transport is not None]

        entries.append(
            FeeComparisonEntry(
                school_id=school.id,
                school_name=school.name,
                age_range_from=school.age_range_from,
                age_range_to=school.age_range_to,
                gender_policy=school.gender_policy,
                faith=school.faith,
                fee_tiers=[PrivateSchoolDetailsResponse.model_validate(d, from_attributes=True) for d in details],
                min_termly_fee=min(termly_fees) if termly_fees else None,
                max_termly_fee=max(termly_fees) if termly_fees else None,
                provides_transport=(any(transport_flags) if transport_flags else None),
                has_bursaries=len(school.bursaries) > 0,
                has_scholarships=len(school.scholarships) > 0,
            )
        )
    return FeeComparisonResponse(schools=entries)


# ---------------------------------------------------------------------------
# Discovery / aggregate endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/api/private-schools/upcoming-open-days",
    response_model=UpcomingOpenDaysResponse,
)
async def list_upcoming_open_days(
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> UpcomingOpenDaysResponse:
    """List all upcoming open days across all private schools, sorted by date."""
    rows = await repo.get_upcoming_open_days()
    entries = [
        UpcomingOpenDayEntry(
            school_id=school.id,
            school_name=school.name,
            event_date=open_day.event_date,
            event_time=open_day.event_time,
            event_type=open_day.event_type,
            registration_required=open_day.registration_required,
            booking_url=open_day.booking_url,
            description=open_day.description,
        )
        for open_day, school in rows
    ]
    return UpcomingOpenDaysResponse(open_days=entries)


@router.get(
    "/api/private-schools/with-scholarships",
    response_model=list[ScholarshipSchoolEntry],
)
async def list_private_schools_with_scholarships(
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[ScholarshipSchoolEntry]:
    """List all private schools that offer scholarships, with scholarship details."""
    schools = await repo.get_private_schools_with_scholarships()
    entries = []
    for school in schools:
        termly_fees = [d.termly_fee for d in school.private_details if d.termly_fee is not None]
        transport_flags = [d.provides_transport for d in school.private_details if d.provides_transport is not None]
        entries.append(
            ScholarshipSchoolEntry(
                school_id=school.id,
                school_name=school.name,
                age_range_from=school.age_range_from,
                age_range_to=school.age_range_to,
                gender_policy=school.gender_policy,
                min_termly_fee=min(termly_fees) if termly_fees else None,
                max_termly_fee=max(termly_fees) if termly_fees else None,
                provides_transport=any(transport_flags) if transport_flags else None,
                scholarships=school.scholarships,
            )
        )
    return entries


@router.get(
    "/api/private-schools/with-bursaries",
    response_model=list[BursarySchoolEntry],
)
async def list_private_schools_with_bursaries(
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[BursarySchoolEntry]:
    """List all private schools that offer bursaries, with bursary details."""
    schools = await repo.get_private_schools_with_bursaries()
    entries = []
    for school in schools:
        termly_fees = [d.termly_fee for d in school.private_details if d.termly_fee is not None]
        transport_flags = [d.provides_transport for d in school.private_details if d.provides_transport is not None]
        entries.append(
            BursarySchoolEntry(
                school_id=school.id,
                school_name=school.name,
                age_range_from=school.age_range_from,
                age_range_to=school.age_range_to,
                gender_policy=school.gender_policy,
                min_termly_fee=min(termly_fees) if termly_fees else None,
                max_termly_fee=max(termly_fees) if termly_fees else None,
                provides_transport=any(transport_flags) if transport_flags else None,
                bursaries=school.bursaries,
            )
        )
    return entries


@router.get("/api/private-schools/{school_id}", response_model=SchoolDetailResponse)
async def get_private_school(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> SchoolDetailResponse:
    """Get full details for a private school including bursaries, scholarships, etc."""
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
    bursaries = await repo.get_bursaries_for_school(school_id)
    scholarships = await repo.get_scholarships_for_school(school_id)
    entry_assessments = await repo.get_entry_assessments_for_school(school_id)
    open_days = await repo.get_open_days_for_school(school_id)
    sibling_discounts = await repo.get_sibling_discounts_for_school(school_id)
    curricula = await repo.get_curricula_for_school(school_id)
    facilities = await repo.get_facilities_for_school(school_id)
    isi_inspections = await repo.get_isi_inspections_for_school(school_id)
    private_results = await repo.get_private_results_for_school(school_id)

    base = SchoolResponse.model_validate(school, from_attributes=True)
    return SchoolDetailResponse(
        **base.model_dump(),
        clubs=clubs,
        performance=performance,
        term_dates=term_dates,
        admissions_history=admissions,
        private_details=private_details,
        bursaries=bursaries,
        scholarships=scholarships,
        entry_assessments=entry_assessments,
        open_days=open_days,
        sibling_discounts=sibling_discounts,
        curricula=curricula,
        facilities=facilities,
        isi_inspections=isi_inspections,
        private_results=private_results,
    )


# ---------------------------------------------------------------------------
# Sub-resource endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/api/private-schools/{school_id}/fees",
    response_model=list[PrivateSchoolDetailsResponse],
)
async def get_private_school_fees(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[PrivateSchoolDetailsResponse]:
    """Get fee tiers for a private school (one per age group)."""
    school = await repo.get_school_by_id(school_id)
    if school is None or not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")
    return await repo.get_private_school_details(school_id)


@router.get(
    "/api/private-schools/{school_id}/bursaries",
    response_model=list[BursaryResponse],
)
async def get_private_school_bursaries(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[BursaryResponse]:
    """Get bursary (means-tested financial aid) information for a private school."""
    school = await repo.get_school_by_id(school_id)
    if school is None or not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")
    return await repo.get_bursaries_for_school(school_id)


@router.get(
    "/api/private-schools/{school_id}/scholarships",
    response_model=list[ScholarshipResponse],
)
async def get_private_school_scholarships(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[ScholarshipResponse]:
    """Get scholarship (merit-based award) information for a private school."""
    school = await repo.get_school_by_id(school_id)
    if school is None or not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")
    return await repo.get_scholarships_for_school(school_id)


@router.get(
    "/api/private-schools/{school_id}/entry-assessments",
    response_model=list[EntryAssessmentResponse],
)
async def get_private_school_entry_assessments(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[EntryAssessmentResponse]:
    """Get entry assessment details (e.g. 4+, 7+, 11+) for a private school."""
    school = await repo.get_school_by_id(school_id)
    if school is None or not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")
    return await repo.get_entry_assessments_for_school(school_id)


@router.get(
    "/api/private-schools/{school_id}/open-days",
    response_model=list[OpenDayResponse],
)
async def get_private_school_open_days(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[OpenDayResponse]:
    """Get open day and taster day events for a private school."""
    school = await repo.get_school_by_id(school_id)
    if school is None or not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")
    return await repo.get_open_days_for_school(school_id)


@router.get(
    "/api/private-schools/{school_id}/sibling-discounts",
    response_model=list[SiblingDiscountResponse],
)
async def get_private_school_sibling_discounts(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[SiblingDiscountResponse]:
    """Get sibling discount information for a private school."""
    school = await repo.get_school_by_id(school_id)
    if school is None or not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")
    return await repo.get_sibling_discounts_for_school(school_id)


@router.get(
    "/api/private-schools/{school_id}/curriculum",
    response_model=list[CurriculumResponse],
)
async def get_private_school_curriculum(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[CurriculumResponse]:
    """Get curriculum and qualification offerings for a private school."""
    school = await repo.get_school_by_id(school_id)
    if school is None or not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")
    return await repo.get_curricula_for_school(school_id)


@router.get(
    "/api/private-schools/{school_id}/facilities",
    response_model=list[FacilityResponse],
)
async def get_private_school_facilities(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[FacilityResponse]:
    """Get facilities available at a private school."""
    school = await repo.get_school_by_id(school_id)
    if school is None or not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")
    return await repo.get_facilities_for_school(school_id)


@router.get(
    "/api/private-schools/{school_id}/inspections",
    response_model=list[ISIInspectionResponse],
)
async def get_private_school_inspections(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[ISIInspectionResponse]:
    """Get ISI inspection results for a private school.

    Most UK independent schools are inspected by ISI rather than Ofsted.
    """
    school = await repo.get_school_by_id(school_id)
    if school is None or not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")
    return await repo.get_isi_inspections_for_school(school_id)


@router.get(
    "/api/private-schools/{school_id}/results",
    response_model=list[PrivateSchoolResultsResponse],
)
async def get_private_school_results(
    school_id: int,
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[PrivateSchoolResultsResponse]:
    """Get exam results and university destination data for a private school."""
    school = await repo.get_school_by_id(school_id)
    if school is None or not school.is_private:
        raise HTTPException(status_code=404, detail="School not found")
    return await repo.get_private_results_for_school(school_id)


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
