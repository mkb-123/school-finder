"""Test data helpers for seed-dependent tests.

These provide the hardcoded Milton Keynes school list and stub functions
that the old seed.py used to export. The school list is hand-curated test
data (real school names, real coordinates) used only in test fixtures.

The disabled generators (_generate_test_clubs etc.) are kept as no-op stubs
since the old seed.py had already disabled them.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from src.db.models import (
    PrivateSchoolDetails,
    School,
    SchoolClub,
    SchoolTermDate,
)


def _generate_test_schools(council: str) -> list[School]:
    """Return a set of hardcoded Milton Keynes schools for testing.

    These are real school names and approximate coordinates, used only
    in the test suite to exercise the API and repository layer.
    """
    # fmt: off
    mk_schools = [
        ("136730", "Shenley Brook End School", "MK5 7ZT", 52.0070, -0.8050, 11, 18, "Secondary", "Mixed", None, "Good", "2023-05-17", False, "Academies"),
        ("135665", "The Milton Keynes Academy", "MK6 5LA", 52.0330, -0.7450, 11, 18, "Secondary", "Mixed", None, "Good", "2023-09-20", False, "Academies"),
        ("136468", "Denbigh School", "MK5 6EX", 52.0115, -0.7920, 11, 18, "Secondary", "Mixed", None, "Good", "2022-11-09", False, "Academies"),
        ("148835", "Stantonbury School", "MK14 6BN", 52.0585, -0.7750, 11, 19, "Secondary", "Mixed", None, "Requires Improvement", "2024-01-22", False, "Academies"),
        ("138439", "Sir Herbert Leon Academy", "MK2 3HQ", 52.0090, -0.7345, 11, 16, "Secondary", "Mixed", None, "Good", "2023-06-21", False, "Academies"),
        ("137052", "Ousedale School", "MK16 0BJ", 52.0850, -0.7060, 11, 18, "Secondary", "Mixed", None, "Good", "2022-09-14", False, "Academies"),
        ("136844", "The Hazeley Academy", "MK8 0PT", 52.0250, -0.8100, 11, 18, "Secondary", "Mixed", None, "Good", "2021-12-01", False, "Academies"),
        ("145736", "Lord Grey Academy", "MK3 6EW", 51.9960, -0.7600, 11, 18, "Secondary", "Mixed", None, "Good", "2024-02-07", False, "Academies"),
        ("136454", "Oakgrove School", "MK10 9JQ", 52.0400, -0.7080, 4, 18, "All-through", "Mixed", None, "Good", "2022-06-29", False, "Academies"),
        ("110532", "The Radcliffe School", "MK12 5BT", 52.0550, -0.7900, 11, 19, "Secondary", "Mixed", None, "Good", "2023-10-04", False, "Local authority maintained schools"),
        ("110517", "St Paul's Catholic School", "MK6 5EN", 52.0280, -0.7550, 11, 19, "Secondary", "Mixed", "Roman Catholic", "Outstanding", "2022-01-19", False, "Local authority maintained schools"),
        ("147860", "Watling Academy", "MK8 1AG", 52.0230, -0.8200, 11, 18, "Secondary", "Mixed", None, "Outstanding", "2024-03-13", False, "Free schools"),
        ("136842", "Walton High", "MK7 7WH", 52.0135, -0.7325, 11, 18, "Secondary", "Mixed", None, "Good", "2023-03-15", False, "Academies"),
        ("145063", "Kents Hill Park School", "MK7 6HB", 52.0200, -0.7150, 3, 16, "All-through", "Mixed", None, "Good", "2023-07-05", False, "Free schools"),
        ("149106", "Glebe Farm School", "MK17 8FU", 52.0050, -0.7180, 4, 16, "All-through", "Mixed", None, "Good", "2024-01-10", False, "Free schools"),
        ("110401", "Abbeys Primary School", "MK3 6PS", 51.9950, -0.7390, 4, 7, "Primary", "Mixed", None, "Good", "2023-03-01", False, "Local authority maintained schools"),
        ("110394", "Caroline Haslett Primary School", "MK5 7DF", 52.0130, -0.8030, 4, 11, "Primary", "Mixed", None, "Outstanding", "2025-02-25", False, "Local authority maintained schools"),
        ("134072", "Broughton Fields Primary School", "MK10 9LS", 52.0500, -0.7200, 4, 11, "Primary", "Mixed", None, "Good", "2022-04-27", False, "Local authority maintained schools"),
        ("140734", "Middleton Primary School", "MK10 9EN", 52.0370, -0.7050, 4, 11, "Primary", "Mixed", None, "Outstanding", "2023-07-12", False, "Academies"),
        ("131718", "Portfields Primary School", "MK16 8PS", 52.0870, -0.7100, 4, 11, "Primary", "Mixed", None, "Good", "2023-09-20", False, "Local authority maintained schools"),
        ("110348", "Simpson School", "MK6 3AZ", 52.0220, -0.7400, 4, 11, "Primary", "Mixed", None, "Good", "2023-01-18", False, "Local authority maintained schools"),
        ("137061", "Two Mile Ash School", "MK8 8LH", 52.0300, -0.8150, 4, 11, "Primary", "Mixed", None, "Good", "2023-02-08", False, "Academies"),
        ("139861", "Loughton School", "MK5 8DN", 52.0080, -0.7900, 7, 11, "Primary", "Mixed", None, "Outstanding", "2021-11-24", False, "Academies"),
        ("136853", "Oxley Park Academy", "MK4 4TA", 52.0030, -0.8200, 4, 11, "Primary", "Mixed", None, "Outstanding", "2021-09-30", False, "Academies"),
        ("110355", "Falconhurst School", "MK6 5AX", 52.0260, -0.7420, 3, 7, "Primary", "Mixed", None, "Good", "2023-04-05", False, "Local authority maintained schools"),
        ("110400", "Glastonbury Thorn School", "MK5 6BX", 52.0150, -0.7990, 4, 11, "Primary", "Mixed", None, "Good", "2023-01-25", False, "Local authority maintained schools"),
        ("110395", "Green Park School", "MK16 0NH", 52.0880, -0.7230, 4, 11, "Primary", "Mixed", None, "Good", "2022-06-15", False, "Local authority maintained schools"),
        ("110404", "Cold Harbour Church of England School", "MK3 7PD", 51.9950, -0.7370, 4, 7, "Primary", "Mixed", "Church of England", "Good", "2023-06-21", False, "Local authority maintained schools"),
        ("110399", "Cedars Primary School", "MK16 0DT", 52.0870, -0.7210, 4, 11, "Primary", "Mixed", None, "Good", "2022-10-05", False, "Local authority maintained schools"),
        ("143766", "Fairfields Primary School", "MK11 4BA", 52.0350, -0.8280, 4, 11, "Primary", "Mixed", None, "Good", "2023-09-14", False, "Free schools"),
        ("132787", "Long Meadow School", "MK5 7XX", 52.0060, -0.8120, 3, 11, "Primary", "Mixed", None, "Good", "2022-11-23", False, "Local authority maintained schools"),
        ("135271", "Brooklands Farm Primary School", "MK10 7EU", 52.0360, -0.7160, 4, 11, "Primary", "Mixed", None, "Outstanding", "2022-03-16", False, "Local authority maintained schools"),
        ("143265", "Chestnuts Primary School", "MK3 5EN", 51.9960, -0.7530, 4, 11, "Primary", "Mixed", None, "Good", "2023-11-08", False, "Academies"),
        ("145043", "Jubilee Wood Primary School", "MK6 2LB", 52.0290, -0.7480, 4, 11, "Primary", "Mixed", None, "Good", "2023-05-10", False, "Academies"),
        ("134424", "Holmwood School", "MK8 9AB", 52.0280, -0.8100, 3, 7, "Primary", "Mixed", None, "Good", "2023-03-22", False, "Academies"),
        ("148229", "Holne Chase Primary School", "MK3 5HP", 51.9970, -0.7600, 4, 11, "Primary", "Mixed", None, "Good", "2023-11-07", False, "Academies"),
        ("138933", "Rickley Park Primary School", "MK3 6EW", 51.9960, -0.7640, 4, 11, "Primary", "Mixed", None, "Good", "2023-10-18", False, "Academies"),
        ("110380", "Priory Common School", "MK13 9EZ", 52.0590, -0.7900, 3, 7, "Primary", "Mixed", None, "Good", "2022-05-11", False, "Local authority maintained schools"),
        ("151293", "Tickford Park Primary School", "MK16 9DH", 52.0860, -0.7190, 4, 11, "Primary", "Mixed", None, "Good", "2023-12-06", False, "Local authority maintained schools"),
        ("146009", "Old Stratford Primary School", "MK19 6AZ", 52.0680, -0.8350, 4, 11, "Primary", "Mixed", None, "Good", "2023-02-15", False, "Academies"),
        ("144357", "Knowles Primary School", "MK2 2HB", 52.0040, -0.7320, 3, 11, "Primary", "Mixed", None, "Good", "2023-08-09", False, "Academies"),
        ("139449", "Heronsgate School", "MK7 7BW", 52.0170, -0.7250, 4, 11, "Primary", "Mixed", None, "Good", "2022-07-13", False, "Academies"),
        ("149061", "Deanshanger Primary School", "MK19 6HJ", 52.0580, -0.8570, 4, 11, "Primary", "Mixed", None, "Good", "2023-04-19", False, "Local authority maintained schools"),
        ("110246", "Olney Infant Academy", "MK46 5AD", 52.1530, -0.7010, 4, 7, "Primary", "Mixed", None, "Good", "2023-01-25", False, "Academies"),
        ("143263", "Olney Middle School", "MK46 4BJ", 52.1540, -0.6990, 8, 12, "Middle deemed secondary", "Mixed", None, "Good", "2022-06-08", False, "Academies"),
        ("110290", "Hanslope Primary School", "MK19 7BL", 52.1120, -0.8080, 4, 11, "Primary", "Mixed", None, "Good", "2023-03-08", False, "Local authority maintained schools"),
        ("110291", "Haversham Village School", "MK19 7DT", 52.0950, -0.7560, 4, 11, "Primary", "Mixed", None, "Good", "2022-04-27", False, "Local authority maintained schools"),
        ("110292", "Castlethorpe First School", "MK19 7EW", 52.1050, -0.8220, 4, 9, "Primary", "Mixed", None, "Outstanding", "2021-10-13", False, "Local authority maintained schools"),
        ("110293", "Sherington Church of England School", "MK16 9NF", 52.1190, -0.7350, 4, 11, "Primary", "Mixed", "Church of England", "Good", "2023-05-17", False, "Local authority maintained schools"),
        ("110294", "Russell Street School", "MK11 1BT", 52.0560, -0.8460, 4, 11, "Primary", "Mixed", None, "Good", "2022-11-02", False, "Local authority maintained schools"),
        ("110295", "Wyvern School", "MK12 5HU", 52.0600, -0.8050, 4, 11, "Primary", "Mixed", None, "Good", "2023-06-28", False, "Local authority maintained schools"),
        ("110366", "Great Linford Primary School", "MK14 5BL", 52.0680, -0.7650, 4, 11, "Primary", "Mixed", None, "Good", "2023-02-22", False, "Local authority maintained schools"),
        ("110381", "Giffard Park Primary School", "MK14 5PY", 52.0640, -0.7520, 4, 11, "Primary", "Mixed", None, "Good", "2022-10-12", False, "Local authority maintained schools"),
        ("110346", "New Bradwell School", "MK13 0BH", 52.0620, -0.7850, 3, 11, "Primary", "Mixed", None, "Requires Improvement", "2024-05-15", False, "Local authority maintained schools"),
        ("148193", "Water Hall Primary School", "MK2 3QF", 52.0030, -0.7280, 3, 11, "Primary", "Mixed", None, "Good", "2023-07-05", False, "Academies"),
        ("138715", "Shepherdswell Academy", "MK6 3NP", 52.0310, -0.7340, 4, 11, "Primary", "Mixed", None, "Good", "2022-06-22", False, "Academies"),
        ("110352", "Southwood School", "MK14 7AR", 52.0560, -0.7720, 4, 11, "Primary", "Mixed", None, "Good", "2023-11-15", False, "Local authority maintained schools"),
        ("110353", "Stanton School", "MK13 7BE", 52.0610, -0.7800, 4, 11, "Primary", "Mixed", None, "Good", "2022-03-09", False, "Local authority maintained schools"),
        ("131397", "Wavendon Gate School", "MK7 7HL", 52.0080, -0.7150, 4, 11, "Primary", "Mixed", None, "Good", "2023-05-24", False, "Local authority maintained schools"),
        ("110357", "Whitehouse Primary School", "MK8 1AG", 52.0250, -0.8250, 4, 11, "Primary", "Mixed", None, "Good", "2023-08-16", False, "Free schools"),
        ("135270", "Newton Leys Primary School", "MK3 5GG", 51.9880, -0.7480, 3, 11, "Primary", "Mixed", None, "Good", "2023-10-25", False, "Local authority maintained schools"),
        ("110359", "Drayton Park School", "MK2 3HJ", 52.0010, -0.7350, 4, 11, "Primary", "Mixed", None, "Good", "2022-09-21", False, "Local authority maintained schools"),
        ("110580", "Romans Field School", "MK3 7AW", 51.9920, -0.7590, 4, 11, "Primary", "Mixed", None, "Good", "2023-04-12", False, "Local authority maintained schools"),
        ("110565", "Milton Keynes Preparatory School", "MK3 7EG", 51.9970, -0.7560, 3, 13, "Primary", "Mixed", None, None, "2023-08-15", True, "Independent schools"),
        ("110567", "The Webber Independent School", "MK14 6DP", 52.0590, -0.7730, 0, 16, "All-through", "Mixed", None, None, "2022-05-20", True, "Independent schools"),
        ("110549", "Thornton College", "MK17 0HJ", 51.9580, -0.9160, 3, 19, "All-through", "Girls", "Roman Catholic", None, "", True, "Independent schools"),
        ("110536", "Akeley Wood Senior School", "MK18 5AE", 52.0170, -0.9710, 11, 18, "Secondary", "Mixed", None, None, "", True, "Independent schools"),
        ("122138", "Akeley Wood Junior School", "MK18 5AE", 52.0170, -0.9710, 4, 11, "Primary", "Mixed", None, None, "", True, "Independent schools"),
        ("133920", "Broughton Manor Preparatory School", "MK10 9AA", 52.0480, -0.7140, 3, 11, "Primary", "Mixed", None, None, "", True, "Independent schools"),
        ("110563", "The Grove Independent School", "MK5 8HD", 52.0100, -0.7920, 2, 13, "Primary", "Mixed", None, None, "", True, "Independent schools"),
        ("148420", "KWS Milton Keynes", "MK2 3HU", 52.0070, -0.7300, 7, 18, "Secondary", "Mixed", None, None, "", True, "Independent special schools"),
    ]
    # fmt: on

    schools: list[School] = []
    for row in mk_schools:
        (
            urn, name, postcode, lat, lng, age_from, age_to, phase,
            gender, faith, ofsted, ofsted_date_str, is_private_val, _type_group,
        ) = row
        ofsted_date_val = None
        if ofsted_date_str:
            try:
                ofsted_date_val = datetime.strptime(ofsted_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        school_type = "private" if is_private_val else "state"
        website = f"https://www.{name.lower().replace(' ', '')}.org.uk"
        ofsted_rating_val = ofsted if ofsted != "Not applicable" else None

        phase_lower = phase.lower() if phase else ""
        if "secondary" in phase_lower or "16 plus" in phase_lower:
            catchment = 3.0
        elif "primary" in phase_lower or "nursery" in phase_lower:
            catchment = 1.5
        else:
            catchment = 2.0

        schools.append(
            School(
                urn=urn,
                name=name,
                type=school_type,
                council=council,
                address=f"{name}, Milton Keynes",
                postcode=postcode,
                lat=lat,
                lng=lng,
                catchment_radius_km=catchment,
                gender_policy=gender,
                faith=faith,
                age_range_from=age_from,
                age_range_to=age_to,
                ofsted_rating=ofsted_rating_val,
                ofsted_date=ofsted_date_val,
                is_private=is_private_val,
                prospectus_url=f"{website}/prospectus",
                website=website,
                ethos="",
            )
        )
    return schools


def _generate_test_clubs(schools: list[School]) -> list[SchoolClub]:
    """Stub: returns empty list. Club data comes from the clubs agent."""
    return []


def _generate_test_term_dates(schools: list[School]) -> list[SchoolTermDate]:
    """Stub: returns empty list. Term dates come from the term_times agent."""
    return []


def _generate_test_performance(schools: list[School], session: Session) -> int:
    """Stub: returns 0. Performance data comes from the EES API."""
    return 0


def _generate_test_admissions(schools: list[School], session: Session) -> int:
    """Stub: returns 0. Admissions data comes from the EES API."""
    return 0


def _seed_term_dates(session: Session, council: str) -> int:
    """Stub: returns 0. Term dates come from the term_times agent."""
    return 0


def _generate_private_school_details(session: Session) -> int:
    """Seed private school details using the production function."""
    from src.db.seed import _seed_private_school_details

    return _seed_private_school_details(session)
