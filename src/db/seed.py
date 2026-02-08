"""Seed the school-finder database from government data sources.

Downloads real data from:
- GIAS (Get Information About Schools) for the school register
- Ofsted management information for inspection ratings
- EES API for performance data (KS2/KS4)

Usage::

    python -m src.db.seed --council "Milton Keynes"

The script caches downloaded files so that subsequent runs do not re-download.
To force a fresh download, pass ``--force-download``.

NO RANDOM DATA IS GENERATED. Fields without real data are left NULL.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import (
    Base,
    Bursary,
    ISIInspection,
    PrivateSchoolDetails,
    PrivateSchoolResults,
    Scholarship,
    School,
    SchoolClub,
    SiblingDiscount,
)
from src.services.gov_data.ees import EESService
from src.services.gov_data.gias import GIASService
from src.services.gov_data.ofsted import OfstedService

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "schools.db"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Private school details (real, researched fee data)
# ---------------------------------------------------------------------------
# These are hand-verified fee tiers for Milton Keynes independent schools.
# They are NOT randomly generated - each entry was researched from school
# websites and prospectuses.

from datetime import date, time  # noqa: E402

# ---------------------------------------------------------------------------
# Fee data: 2025-26 academic year, verified from school websites.
# Sources: thorntoncollege.com, akeleywoodschool.co.uk, mkps.co.uk
# Fees include VAT (20% applied from Jan 2025). Lunch costs noted separately.
# Schools without verified 2025-26 data retain their previously researched figures.
# ---------------------------------------------------------------------------

_PRIVATE_DETAIL_ROWS: list[tuple[str, str, float, float, float, time, time, bool, str | None, str | None]] = [
    # Thornton College (Girls boarding/day, Catholic)
    # Source: thorntoncollege.com/admissions/fees/ (Sept 2025 - July 2026)
    # Termly fees shown = tuition + lunch (lunches: £295-336/term)
    (
        "Thornton",
        "Reception & Year 1 (4-6)",
        5071.0,
        15213.0,
        4.5,
        time(8, 15),
        time(16, 0),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Thornton",
        "Year 2 (6-7)",
        5541.0,
        16623.0,
        4.5,
        time(8, 15),
        time(16, 0),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Thornton",
        "Years 4-6 (8-11)",
        6345.0,
        19035.0,
        4.5,
        time(8, 15),
        time(16, 15),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Thornton",
        "Senior & Sixth Form (11-18)",
        8088.0,
        24264.0,
        4.2,
        time(8, 15),
        time(16, 30),
        True,
        "Bus routes from MK, Buckingham, and Towcester. Boarding available: day boarder £10,512/term, weekly £12,498, termly £15,516.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    # Akeley Wood Senior School
    # Source: akeleywoodschool.co.uk/fees/ (2025-26)
    # Termly fees include compulsory lunch (£375/term)
    (
        "Akeley Wood Senior",
        "Years 7-8 (11-13)",
        7690.0,
        23070.0,
        5.0,
        time(8, 30),
        time(16, 15),
        True,
        "Dedicated school bus service covering most of North Bucks.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Akeley Wood Senior",
        "Years 9-11 (13-16)",
        7724.0,
        23172.0,
        5.0,
        time(8, 30),
        time(16, 15),
        True,
        "Dedicated school bus service covering most of North Bucks.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Akeley Wood Senior",
        "Sixth Form (16-18)",
        7346.0,
        22038.0,
        5.0,
        time(8, 30),
        time(16, 15),
        True,
        "Dedicated school bus service covering most of North Bucks.",
        "Follows own term dates. Three terms per year.",
    ),
    # Akeley Wood Junior School
    # Source: akeleywoodschool.co.uk/fees/ (2025-26)
    (
        "Akeley Wood Junior",
        "Reception & Years 1-2 (4-7)",
        5244.0,
        15732.0,
        4.8,
        time(8, 30),
        time(15, 30),
        True,
        "Shared bus service with Senior School.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Akeley Wood Junior",
        "Year 3 (7-8)",
        6039.0,
        18117.0,
        4.8,
        time(8, 30),
        time(15, 45),
        True,
        "Shared bus service with Senior School.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Akeley Wood Junior",
        "Years 4-6 (8-11)",
        6483.0,
        19449.0,
        4.8,
        time(8, 30),
        time(15, 45),
        True,
        "Shared bus service with Senior School.",
        "Follows own term dates. Three terms per year.",
    ),
    # MK Prep School
    # Source: mkps.co.uk/admissions/fees/ and supplementary PDFs (2025-26)
    (
        "Milton Keynes Prep",
        "Pre-Prep Class 3-4 (3-4)",
        5416.0,
        16248.0,
        3.5,
        time(8, 0),
        time(15, 30),
        False,
        None,
        "Open 46.4 weeks/year. Follows own term dates.",
    ),
    (
        "Milton Keynes Prep",
        "Pre-Prep Reception-Year 2 (5-7)",
        6064.0,
        18192.0,
        3.5,
        time(9, 0),
        time(15, 30),
        False,
        None,
        "Open 46.4 weeks/year. Follows own term dates.",
    ),
    (
        "Milton Keynes Prep",
        "Preparatory Years 3-6 (8-11)",
        6820.0,
        20460.0,
        3.5,
        time(8, 30),
        time(16, 0),
        False,
        None,
        "Open 46.4 weeks/year. Follows own term dates.",
    ),
    # Webber Independent (previously researched, no 2025-26 update available)
    (
        "Webber Independent",
        "Early Years (0-4)",
        3000.0,
        9000.0,
        3.0,
        time(8, 45),
        time(15, 30),
        False,
        None,
        "Follows own term dates, broadly aligned with state calendar.",
    ),
    (
        "Webber Independent",
        "Primary (4-11)",
        3500.0,
        10500.0,
        3.0,
        time(8, 45),
        time(15, 30),
        False,
        None,
        "Follows own term dates, broadly aligned with state calendar.",
    ),
    # Grove Independent (previously researched, no 2025-26 update available)
    (
        "Grove Independent",
        "Nursery (2-4)",
        3200.0,
        9600.0,
        3.2,
        time(8, 30),
        time(15, 30),
        False,
        "Limited minibus for local MK routes. Additional charge.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Grove Independent",
        "Infant (4-7)",
        3500.0,
        10500.0,
        3.2,
        time(8, 30),
        time(15, 30),
        False,
        "Limited minibus for local MK routes. Additional charge.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Grove Independent",
        "Junior (7-13)",
        3800.0,
        11400.0,
        3.2,
        time(8, 30),
        time(15, 30),
        False,
        "Limited minibus for local MK routes. Additional charge.",
        "Follows own term dates. Three terms per year.",
    ),
    # Broughton Manor Prep (previously researched, no 2025-26 update available)
    (
        "Broughton Manor",
        "Nursery (3-4)",
        3400.0,
        10200.0,
        3.8,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Broughton Manor",
        "Pre-prep (4-7)",
        3800.0,
        11400.0,
        3.8,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Broughton Manor",
        "Prep (7-11)",
        4200.0,
        12600.0,
        3.8,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    # KWS Milton Keynes (previously researched, no 2025-26 update available)
    (
        "KWS",
        "Primary (7-11)",
        3500.0,
        10500.0,
        4.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms per year.",
    ),
    (
        "KWS",
        "Secondary (11-16)",
        4200.0,
        12600.0,
        4.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms per year.",
    ),
    (
        "KWS",
        "Sixth Form (16-18)",
        4800.0,
        14400.0,
        4.0,
        time(8, 30),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms per year.",
    ),
]

# Hidden cost overrides for schools where we have verified data.
# Key: (name_fragment, fee_age_group_substring) -> dict of extra fields.
# Applied after PrivateSchoolDetails records are created.
_HIDDEN_COSTS: dict[tuple[str, str], dict] = {
    # Akeley Wood: lunch £375/term compulsory, registration £125, deposit £750
    ("Akeley Wood Senior", "Years 7-8"): {
        "lunches_per_term": 375.0,
        "lunches_compulsory": True,
        "registration_fee": 125.0,
        "deposit_fee": 750.0,
    },
    ("Akeley Wood Senior", "Years 9-11"): {
        "lunches_per_term": 375.0,
        "lunches_compulsory": True,
        "registration_fee": 125.0,
        "deposit_fee": 750.0,
    },
    ("Akeley Wood Senior", "Sixth Form"): {"registration_fee": 125.0, "deposit_fee": 750.0},
    ("Akeley Wood Junior", "Reception"): {
        "lunches_per_term": 375.0,
        "lunches_compulsory": True,
        "registration_fee": 125.0,
        "deposit_fee": 750.0,
    },
    ("Akeley Wood Junior", "Year 3"): {
        "lunches_per_term": 375.0,
        "lunches_compulsory": True,
        "registration_fee": 125.0,
        "deposit_fee": 750.0,
    },
    ("Akeley Wood Junior", "Years 4-6"): {
        "lunches_per_term": 375.0,
        "lunches_compulsory": True,
        "registration_fee": 125.0,
        "deposit_fee": 750.0,
    },
    # Thornton: lunches included in reported termly fee
    ("Thornton", "Reception"): {"lunches_per_term": 295.0, "lunches_compulsory": True},
    ("Thornton", "Year 2"): {"lunches_per_term": 315.0, "lunches_compulsory": True},
    ("Thornton", "Years 4-6"): {"lunches_per_term": 315.0, "lunches_compulsory": True},
    ("Thornton", "Senior"): {"lunches_per_term": 336.0, "lunches_compulsory": True},
    # MKPS: registration £100-250 depending on department
    ("Milton Keynes Prep", "Pre-Prep Class 3-4"): {"registration_fee": 150.0},
    ("Milton Keynes Prep", "Pre-Prep Reception"): {"registration_fee": 150.0},
    ("Milton Keynes Prep", "Preparatory"): {"registration_fee": 250.0},
}

# ---------------------------------------------------------------------------
# Scholarship data (verified from school websites)
# ---------------------------------------------------------------------------
# Source: thorntoncollege.com/admissions/scholarships/
# Source: mkps.co.uk/admissions/ (supplementary PDFs)

# (name_fragment, scholarship_type, value_description, value_percentage, entry_points,
#  assessment_method, notes, source_url)
_SCHOLARSHIP_ROWS: list[tuple[str, str, str | None, int | None, str | None, str | None, str | None, str | None]] = [
    # Thornton College - 6 scholarship types
    (
        "Thornton",
        "academic",
        "5-50% discount on fees",
        50,
        "Year 7, Year 12",
        "CAT4 assessment + taster day (Y7); Yellis test + interview (Y12)",
        "Available throughout the year; early application encouraged as places are limited.",
        "https://thorntoncollege.com/admissions/scholarships/",
    ),
    (
        "Thornton",
        "music",
        "5-50% discount on fees",
        50,
        "Year 7, Year 12",
        "25-minute audition: principal instrument, sight-reading, aural tests. Grade 3+ expected for Y7.",
        "Music scholars expected to play in orchestra, sing in choirs, and represent school in competitions.",
        "https://thorntoncollege.com/admissions/scholarships/",
    ),
    (
        "Thornton",
        "drama",
        "5-50% discount on fees",
        50,
        "Year 7, Year 12",
        "Two contrasting monologues (max 3 min each), workshop, interview with Head of Drama.",
        "Drama scholars expected to participate in school performances and attend Drama clubs.",
        "https://thorntoncollege.com/admissions/scholarships/",
    ),
    (
        "Thornton",
        "sport",
        "5-50% discount on fees",
        50,
        "Year 7, Year 12",
        "Fitness demonstration, team and individual skills, interview with Director of Sport.",
        "Y7 sports: Athletics, Cricket, Hockey, Netball. Also Dance, Equestrian, Football, Rugby, Swimming, Tennis.",
        "https://thorntoncollege.com/admissions/scholarships/",
    ),
    (
        "Thornton",
        "academic",
        "30-50% discount on day tuition and termly boarding accommodation",
        50,
        "Years 5-13 (termly boarding required)",
        "Baseline assessment score 134+. Y12: GCSE total 63 across 9 GCSEs with grade 8+ in A-Level subjects.",
        "Boarding Academic Scholarship. Must commit for duration of current Key Stage with continued boarding.",
        "https://thorntoncollege.com/admissions/scholarships/boarding-academic-scholarship/",
    ),
    (
        "Thornton",
        "all_rounder",
        "5-50% discount on fees",
        50,
        "Years 6, 7, 12",
        "Application reviewed; visit invited (overnight boarding stay if applicable).",
        "Sr Genevieve Award. Recognises Catholic values: forgiveness, respect, service, love.",
        "https://thorntoncollege.com/admissions/scholarships/sr-genevieve-award/",
    ),
    # MKPS scholarships (types confirmed, percentages not publicly published)
    (
        "Milton Keynes Prep",
        "academic",
        "Various % subject to eligibility",
        None,
        "Year 3+",
        None,
        "Applied to tuition element only. Continued award requires sustained achievement and good conduct.",
        "https://www.mkps.co.uk/admissions/",
    ),
    (
        "Milton Keynes Prep",
        "stem",
        "Various % subject to eligibility",
        None,
        "Year 3+",
        None,
        "Applied to tuition element only.",
        "https://www.mkps.co.uk/admissions/",
    ),
    (
        "Milton Keynes Prep",
        "sport",
        "Various % subject to eligibility",
        None,
        "Year 3+",
        None,
        "Applied to tuition element only.",
        "https://www.mkps.co.uk/admissions/",
    ),
    (
        "Milton Keynes Prep",
        "art",
        "Various % subject to eligibility",
        None,
        "Year 3+",
        None,
        "Applied to tuition element only.",
        "https://www.mkps.co.uk/admissions/",
    ),
    (
        "Milton Keynes Prep",
        "music",
        "Various % subject to eligibility",
        None,
        "Year 3+",
        None,
        "Applied to tuition element only.",
        "https://www.mkps.co.uk/admissions/",
    ),
]

# ---------------------------------------------------------------------------
# Bursary data (verified from school websites)
# ---------------------------------------------------------------------------

# (name_fragment, max_pct, min_pct, income_threshold, eligibility_notes,
#  percentage_of_pupils, notes, source_url)
_BURSARY_ROWS: list[
    tuple[str, int | None, int | None, float | None, str | None, float | None, str | None, str | None]
] = [
    # Thornton explicitly states: "We do not offer bursaries at Thornton College."
    # MKPS offers means-tested bursaries
    (
        "Milton Keynes Prep",
        None,  # max_pct not published
        None,  # min_pct not published
        None,  # income threshold not published
        "Children in Year 1 and above (age 7/8+). Means-tested with annual review. "
        "Applicants must complete detailed application with supporting evidence.",
        None,
        "Applied to tuition element only. Seldom available for younger children.",
        "https://www.mkps.co.uk/admissions/",
    ),
]

# ---------------------------------------------------------------------------
# Sibling discount data (verified from school websites)
# ---------------------------------------------------------------------------

# (name_fragment, 2nd_child_pct, 3rd_child_pct, 4th_child_pct,
#  conditions, stacks_with_bursary, notes, source_url)
_SIBLING_DISCOUNT_ROWS: list[
    tuple[str, float | None, float | None, float | None, str | None, bool | None, str | None, str | None]
] = [
    # Thornton College: 5% 2nd daughter, 10% 3rd daughter
    (
        "Thornton",
        5.0,
        10.0,
        None,
        "Girls-only school. Also: 2.5% discount for fees paid 3+ terms in advance. "
        "Up to 20% Armed Forces discount for CEA-eligible families.",
        None,
        "Source: thorntoncollege.com/admissions/fees/",
        "https://thorntoncollege.com/admissions/fees/",
    ),
    # Akeley Wood: 5%/10%/15%
    (
        "Akeley Wood",
        5.0,
        10.0,
        15.0,
        "Siblings must be in school concurrently.",
        None,
        "Source: akeleywoodschool.co.uk/fees/ (2025-26)",
        "https://akeleywoodschool.co.uk/fees/",
    ),
    # MKPS: 15%/30%, up to 50% for nursery twins
    (
        "Milton Keynes Prep",
        15.0,
        30.0,
        30.0,
        "Applied to tuition element on All Year Fees. 50% when 2 children both under 2 in nursery. "
        "Applied after other discounts/funding but before annual payment discount.",
        None,
        "Also: 5% annual payment discount, £1,000 referral discount, £1,500 Class 5 bonus. "
        "Source: MKPS supplementary info PDFs 2025-26.",
        "https://www.mkps.co.uk/admissions/fees/",
    ),
]

# ---------------------------------------------------------------------------
# ISI inspection data (verified from school websites)
# ---------------------------------------------------------------------------

# (name_fragment, inspection_date, overall_rating, achievement_rating,
#  personal_development_rating, compliance_met, inspection_type,
#  report_url, key_findings, recommendations, is_current)
_ISI_INSPECTION_ROWS: list[
    tuple[
        str, date, str | None, str | None, str | None, bool | None, str | None, str | None, str | None, str | None, bool
    ]
] = [
    # Thornton College
    (
        "Thornton",
        date(2025, 9, 25),
        "Met",
        None,
        None,
        True,
        "Regulatory Compliance",
        "https://www.thorntoncollege.com/wp-content/uploads/2025/11/Thornton-ISI-Inspection-Report-September-2025.pdf",
        "Met all statutory Independent School Standards and applicable regulatory requirements. "
        "From Sept 2023, ISI no longer issues overall quality grades.",
        None,
        True,
    ),
    (
        "Thornton",
        date(2022, 10, 1),
        "Excellent",
        "Excellent",
        None,
        True,
        "Educational Quality",
        "https://www.thorntoncollege.com/wp-content/uploads/2022/10/Thornton-College-Inspection-Report-2022.pdf",
        "Highest possible judgement. Compliance met in all areas.",
        None,
        False,
    ),
    (
        "Thornton",
        date(2019, 2, 1),
        "Met",
        None,
        None,
        True,
        "Regulatory Compliance",
        "https://www.thorntoncollege.com/wp-content/uploads/2022/09/Thornton_College_ISI-Regulatory-Compliance-Inspection-Report-2019.pdf",
        "All required standards met.",
        None,
        False,
    ),
]

# ---------------------------------------------------------------------------
# Exam results data (verified from school websites)
# ---------------------------------------------------------------------------
# Source: thorntoncollege.com/about-us/examination-results/

# (name_fragment, result_type, year, metric_name, metric_value, source_url, notes)
_RESULTS_ROWS: list[tuple[str, str, str, str, str, str | None, str | None]] = [
    # Thornton College GCSE results
    (
        "Thornton",
        "GCSE",
        "2024/2025",
        "% grades 9-8",
        "38%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
    (
        "Thornton",
        "GCSE",
        "2024/2025",
        "% grades 9-7",
        "50%",
        "https://thorntoncollege.com/about-us/examination-results/",
        "National average: 22%",
    ),
    (
        "Thornton",
        "GCSE",
        "2024/2025",
        "% grades 9-4",
        "93%",
        "https://thorntoncollege.com/about-us/examination-results/",
        "National average: 67%",
    ),
    (
        "Thornton",
        "GCSE",
        "2023/2024",
        "% grades 9-8",
        "24%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
    (
        "Thornton",
        "GCSE",
        "2023/2024",
        "% grades 9-7",
        "39%",
        "https://thorntoncollege.com/about-us/examination-results/",
        "National average: 23%",
    ),
    (
        "Thornton",
        "GCSE",
        "2023/2024",
        "% grades 9-4",
        "89%",
        "https://thorntoncollege.com/about-us/examination-results/",
        "National average: 70%",
    ),
    (
        "Thornton",
        "GCSE",
        "2022/2023",
        "% grades 9-7",
        "33%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
    (
        "Thornton",
        "GCSE",
        "2022/2023",
        "% grades 9-5",
        "76%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
    # Thornton College A-level results
    (
        "Thornton",
        "A-level",
        "2024/2025",
        "% A*/A",
        "45%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
    (
        "Thornton",
        "A-level",
        "2024/2025",
        "% A*-B",
        "77%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
    (
        "Thornton",
        "A-level",
        "2024/2025",
        "Pass rate",
        "100%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
    (
        "Thornton",
        "A-level",
        "2023/2024",
        "% A*/A",
        "33%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
    (
        "Thornton",
        "A-level",
        "2023/2024",
        "% A*-B",
        "45%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
    (
        "Thornton",
        "A-level",
        "2022/2023",
        "% A*/A",
        "23%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
    (
        "Thornton",
        "A-level",
        "2022/2023",
        "% A*-B",
        "35%",
        "https://thorntoncollege.com/about-us/examination-results/",
        None,
    ),
]


def _match_school(school_name: str, name_frag: str) -> bool:
    """Check if a name fragment matches a school name (case-insensitive)."""
    return name_frag.lower() in school_name.lower()


def _seed_private_school_details(session: Session) -> int:
    """Create PrivateSchoolDetails records for private schools using researched data.

    Matches schools by name fragment and creates fee-tier entries per school.
    Also applies hidden cost data where available.
    Returns the number of detail records inserted.
    """
    private_schools = session.query(School).filter_by(is_private=True).all()
    if not private_schools:
        return 0

    details_by_frag: dict[str, list] = {}
    for entry in _PRIVATE_DETAIL_ROWS:
        details_by_frag.setdefault(entry[0], []).append(entry)

    count = 0
    for school in private_schools:
        matched: list | None = None
        matched_frag: str = ""
        for frag, entries in details_by_frag.items():
            if _match_school(school.name, frag):
                matched = entries
                matched_frag = frag
                break
        if not matched:
            continue

        session.query(PrivateSchoolDetails).filter_by(school_id=school.id).delete()

        for entry in matched:
            (
                _,
                fee_age_group,
                termly_fee,
                annual_fee,
                fee_increase_pct,
                day_start,
                day_end,
                provides_transport,
                transport_notes,
                holiday_notes,
            ) = entry

            # Look up hidden cost overrides for this school + tier
            extra: dict = {}
            for (hc_frag, hc_tier_sub), hc_data in _HIDDEN_COSTS.items():
                if hc_frag == matched_frag and hc_tier_sub in fee_age_group:
                    extra = hc_data
                    break

            session.add(
                PrivateSchoolDetails(
                    school_id=school.id,
                    fee_age_group=fee_age_group,
                    termly_fee=termly_fee,
                    annual_fee=annual_fee,
                    fee_increase_pct=fee_increase_pct,
                    school_day_start=day_start,
                    school_day_end=day_end,
                    provides_transport=provides_transport,
                    transport_notes=transport_notes,
                    holiday_schedule_notes=holiday_notes,
                    **extra,
                )
            )
            count += 1
    session.commit()
    return count


def _seed_scholarships(session: Session) -> int:
    """Create Scholarship records from researched data. Returns count inserted."""
    private_schools = session.query(School).filter_by(is_private=True).all()
    if not private_schools:
        return 0

    count = 0
    for school in private_schools:
        matched = [r for r in _SCHOLARSHIP_ROWS if _match_school(school.name, r[0])]
        if not matched:
            continue

        session.query(Scholarship).filter_by(school_id=school.id).delete()

        for row in matched:
            _, s_type, val_desc, val_pct, entry_pts, assess, notes, source = row
            session.add(
                Scholarship(
                    school_id=school.id,
                    scholarship_type=s_type,
                    value_description=val_desc,
                    value_percentage=val_pct,
                    entry_points=entry_pts,
                    assessment_method=assess,
                    notes=notes,
                    source_url=source,
                )
            )
            count += 1
    session.commit()
    return count


def _seed_bursaries(session: Session) -> int:
    """Create Bursary records from researched data. Returns count inserted."""
    private_schools = session.query(School).filter_by(is_private=True).all()
    if not private_schools:
        return 0

    count = 0
    for school in private_schools:
        matched = [r for r in _BURSARY_ROWS if _match_school(school.name, r[0])]
        if not matched:
            continue

        session.query(Bursary).filter_by(school_id=school.id).delete()

        for row in matched:
            _, max_pct, min_pct, income_thresh, elig_notes, pct_pupils, notes, source = row
            session.add(
                Bursary(
                    school_id=school.id,
                    max_percentage=max_pct,
                    min_percentage=min_pct,
                    income_threshold=income_thresh,
                    eligibility_notes=elig_notes,
                    percentage_of_pupils=pct_pupils,
                    notes=notes,
                    source_url=source,
                )
            )
            count += 1
    session.commit()
    return count


def _seed_sibling_discounts(session: Session) -> int:
    """Create SiblingDiscount records from researched data. Returns count inserted."""
    private_schools = session.query(School).filter_by(is_private=True).all()
    if not private_schools:
        return 0

    count = 0
    for school in private_schools:
        matched = [r for r in _SIBLING_DISCOUNT_ROWS if _match_school(school.name, r[0])]
        if not matched:
            continue

        session.query(SiblingDiscount).filter_by(school_id=school.id).delete()

        for row in matched:
            _, pct2, pct3, pct4, conditions, stacks, notes, source = row
            session.add(
                SiblingDiscount(
                    school_id=school.id,
                    second_child_percent=pct2,
                    third_child_percent=pct3,
                    fourth_child_percent=pct4,
                    conditions=conditions,
                    stacks_with_bursary=stacks,
                    notes=notes,
                    source_url=source,
                )
            )
            count += 1
    session.commit()
    return count


def _seed_isi_inspections(session: Session) -> int:
    """Create ISIInspection records from researched data. Returns count inserted."""
    private_schools = session.query(School).filter_by(is_private=True).all()
    if not private_schools:
        return 0

    count = 0
    for school in private_schools:
        matched = [r for r in _ISI_INSPECTION_ROWS if _match_school(school.name, r[0])]
        if not matched:
            continue

        session.query(ISIInspection).filter_by(school_id=school.id).delete()

        for row in matched:
            (
                _,
                insp_date,
                overall,
                achievement,
                personal_dev,
                compliance,
                insp_type,
                report_url,
                findings,
                recommendations,
                is_current,
            ) = row
            session.add(
                ISIInspection(
                    school_id=school.id,
                    inspection_date=insp_date,
                    overall_rating=overall,
                    achievement_rating=achievement,
                    personal_development_rating=personal_dev,
                    compliance_met=compliance,
                    inspection_type=insp_type,
                    report_url=report_url,
                    key_findings=findings,
                    recommendations=recommendations,
                    is_current=is_current,
                )
            )
            count += 1
    session.commit()
    return count


def _seed_private_results(session: Session) -> int:
    """Create PrivateSchoolResults records from researched data. Returns count inserted."""
    private_schools = session.query(School).filter_by(is_private=True).all()
    if not private_schools:
        return 0

    count = 0
    for school in private_schools:
        matched = [r for r in _RESULTS_ROWS if _match_school(school.name, r[0])]
        if not matched:
            continue

        session.query(PrivateSchoolResults).filter_by(school_id=school.id).delete()

        for row in matched:
            _, result_type, year, metric_name, metric_value, source_url, notes = row
            session.add(
                PrivateSchoolResults(
                    school_id=school.id,
                    result_type=result_type,
                    year=year,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    source_url=source_url,
                    notes=notes,
                )
            )
            count += 1
    session.commit()
    return count


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


def _ensure_database(db_path: Path) -> Session:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return Session(engine)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.db.seed",
        description="Seed the school-finder database from government data sources.",
    )
    parser.add_argument("--council", required=True, help="Local authority name to filter by.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to the SQLite database file.")
    parser.add_argument("--force-download", action="store_true", default=False, help="Force re-download.")
    parser.add_argument(
        "--private-only",
        action="store_true",
        default=False,
        help="Only re-seed private schools (radius import + fee details). Skips state school import, Ofsted, and performance data.",
    )
    parser.add_argument(
        "--private-radius-km",
        type=float,
        default=30.0,
        help="Radius in km for private school import (default: 30).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the seed script.

    Uses government data services to populate the database with real data.
    No random or fake data is generated.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    args = parse_args(argv)
    council: str = args.council
    db_path: Path = args.db
    force_download: bool = args.force_download
    private_only: bool = args.private_only
    private_radius_km: float = args.private_radius_km

    print("School Finder - Database Seed (Government Data Only)")
    print(f"  Council filter : {council}")
    print(f"  Database       : {db_path}")
    if private_only:
        print(f"  Mode           : private schools only (radius {private_radius_km} km)")
    print()

    gias = GIASService()

    if not private_only:
        # ------------------------------------------------------------------
        # Step 1: GIAS - School register
        # ------------------------------------------------------------------
        print("[1/4] Fetching school register from GIAS ...")
        try:
            gias_stats = gias.refresh(
                council=council,
                force_download=force_download,
                db_path=str(db_path),
            )
            print(f"  Inserted: {gias_stats['inserted']}")
            print(f"  Updated:  {gias_stats['updated']}")
            print(f"  Total:    {gias_stats['total']}")
            print(f"  With coordinates: {gias_stats['with_coordinates']}")
        except Exception as exc:
            print(f"  ERROR: GIAS download failed: {exc}")
            print("  Cannot proceed without school data.")
            sys.exit(1)

    # ------------------------------------------------------------------
    # Private schools by radius (not limited to council)
    # ------------------------------------------------------------------
    step_label = "[1/2]" if private_only else "[1b/4]"
    print(f"\n{step_label} Importing private schools within {private_radius_km} km radius ...")
    try:
        # Compute centroid of schools already imported for the council
        session_tmp = _ensure_database(db_path)
        council_schools = session_tmp.query(School).filter_by(council=council).all()
        session_tmp.close()
        if council_schools:
            lats = [s.lat for s in council_schools if s.lat is not None]
            lngs = [s.lng for s in council_schools if s.lng is not None]
            if lats and lngs:
                center_lat = sum(lats) / len(lats)
                center_lng = sum(lngs) / len(lngs)
                pvt_radius_stats = gias.refresh_private_schools_by_radius(
                    center_lat=center_lat,
                    center_lng=center_lng,
                    radius_km=private_radius_km,
                    force_download=force_download,
                    db_path=str(db_path),
                )
                print(f"  Inserted: {pvt_radius_stats['inserted']}")
                print(f"  Updated:  {pvt_radius_stats['updated']}")
                print(f"  Total private schools (within {private_radius_km} km): {pvt_radius_stats['total']}")
            else:
                print("  SKIP: No geocoded schools to compute centroid.")
        else:
            print("  SKIP: No council schools found to compute centroid.")
    except Exception as exc:
        print(f"  WARNING: Private school radius import failed: {exc}")
        print("  Continuing without additional private schools.")

    if not private_only:
        # ------------------------------------------------------------------
        # Step 2: Ofsted - Inspection ratings
        # ------------------------------------------------------------------
        print("\n[2/4] Fetching Ofsted ratings ...")
        ofsted = OfstedService()
        try:
            ofsted_stats = ofsted.refresh(
                council=council,
                force_download=force_download,
                db_path=str(db_path),
            )
            print(f"  Updated:   {ofsted_stats['updated']}")
            print(f"  Skipped:   {ofsted_stats['skipped']}")
            print(f"  Not found: {ofsted_stats['not_found']}")
        except Exception as exc:
            print(f"  WARNING: Ofsted import failed: {exc}")
            print("  Continuing without Ofsted data.")

        # ------------------------------------------------------------------
        # Step 3: EES - Performance data (KS2 + KS4)
        # ------------------------------------------------------------------
        print("\n[3/4] Fetching performance data from EES API ...")
        ees = EESService()
        try:
            perf_stats = ees.refresh_performance(
                council=council,
                force_download=force_download,
                db_path=str(db_path),
            )
            for key, sub_stats in perf_stats.items():
                print(
                    f"  {key.upper()}: imported={sub_stats.get('imported', 0)}, skipped={sub_stats.get('skipped', 0)}"
                )
        except Exception as exc:
            print(f"  WARNING: Performance data import failed: {exc}")
            print("  Continuing without performance data.")

    # ------------------------------------------------------------------
    # Private school details (researched fee data)
    # ------------------------------------------------------------------
    step_label = "[2/2]" if private_only else "[4/4]"
    print(f"\n{step_label} Seeding private school details ...")
    session = _ensure_database(db_path)
    try:
        pvt_count = _seed_private_school_details(session)
        print(f"  Private school fee tiers: {pvt_count}")

        # Scholarships, bursaries, sibling discounts, ISI inspections, results
        sch_count = _seed_scholarships(session)
        print(f"  Scholarships: {sch_count}")
        bur_count = _seed_bursaries(session)
        print(f"  Bursaries: {bur_count}")
        sib_count = _seed_sibling_discounts(session)
        print(f"  Sibling discounts: {sib_count}")
        isi_count = _seed_isi_inspections(session)
        print(f"  ISI inspections: {isi_count}")
        res_count = _seed_private_results(session)
        print(f"  Private school results: {res_count}")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        council_schools = session.query(School).filter_by(council=council).all()
        all_private = session.query(School).filter_by(is_private=True).all()
        total_clubs = session.query(SchoolClub).count()

        print()
        print("=" * 60)
        print(f"  SUMMARY: {council}")
        print("=" * 60)

        primary_count = sum(1 for s in council_schools if s.age_range_to and s.age_range_to <= 13 and not s.is_private)
        secondary_count = sum(
            1
            for s in council_schools
            if s.age_range_from
            and s.age_range_from >= 11
            and s.age_range_to
            and s.age_range_to >= 16
            and not s.is_private
        )
        private_in_council = sum(1 for s in council_schools if s.is_private)

        print(f"  State schools       : {len(council_schools) - private_in_council}")
        print(f"  State primary       : {primary_count}")
        print(f"  State secondary     : {secondary_count}")
        print(f"  Private (in council): {private_in_council}")
        print(f"  Private (all nearby): {len(all_private)}")
        print(f"  Clubs in DB         : {total_clubs}")
        print()

        rating_counts = Counter(s.ofsted_rating for s in council_schools if s.ofsted_rating)
        print("  Ofsted ratings (council):")
        for rating in ["Outstanding", "Good", "Requires Improvement", "Inadequate"]:
            c = rating_counts.get(rating, 0)
            if c:
                print(f"    {rating:25s}: {c}")
        no_rating = sum(1 for s in council_schools if not s.ofsted_rating)
        if no_rating:
            print(f"    {'(no rating)':25s}: {no_rating}")

        print()
        print("  NOTE: Fields without real data are left empty.")
        print("  Run agents (clubs, term_times, ethos) to populate additional data.")
        print("  Run 'python -m src.services.gov_data refresh' to update government data.")
        print("=" * 60)
    finally:
        session.close()

    print()
    print("Done.")


if __name__ == "__main__":
    main()
