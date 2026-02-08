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
    PrivateSchoolDetails,
    School,
    SchoolClub,
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

from datetime import time  # noqa: E402

_PRIVATE_DETAIL_ROWS: list[tuple[str, str, float, float, float, time, time, bool, str | None, str | None]] = [
    # Thornton College (Girls boarding/day, Catholic)
    (
        "Thornton",
        "Pre-prep (3-7)",
        3800.0,
        11400.0,
        4.5,
        time(8, 15),
        time(16, 0),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Thornton",
        "Prep (7-11)",
        4500.0,
        13500.0,
        4.5,
        time(8, 15),
        time(16, 15),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Thornton",
        "Senior (11-16)",
        5200.0,
        15600.0,
        4.2,
        time(8, 15),
        time(16, 30),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    (
        "Thornton",
        "Sixth Form (16-18)",
        5500.0,
        16500.0,
        4.2,
        time(8, 15),
        time(16, 30),
        True,
        "Bus routes from MK, Buckingham, and Towcester.",
        "Follows own term dates. Three terms with half-term breaks.",
    ),
    # Akeley Wood Senior
    (
        "Akeley Wood Senior",
        "Senior (11-16)",
        5800.0,
        17400.0,
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
        6100.0,
        18300.0,
        5.0,
        time(8, 30),
        time(16, 15),
        True,
        "Dedicated school bus service covering most of North Bucks.",
        "Follows own term dates. Three terms per year.",
    ),
    # Akeley Wood Junior
    (
        "Akeley Wood Junior",
        "Pre-prep (3-7)",
        3200.0,
        9600.0,
        4.8,
        time(8, 30),
        time(15, 30),
        True,
        "Shared bus service with Senior School.",
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Akeley Wood Junior",
        "Prep (7-11)",
        4200.0,
        12600.0,
        4.8,
        time(8, 30),
        time(15, 45),
        True,
        "Shared bus service with Senior School.",
        "Follows own term dates. Three terms per year.",
    ),
    # MK Prep School
    (
        "Milton Keynes Prep",
        "Reception (4-5)",
        3500.0,
        10500.0,
        3.5,
        time(8, 20),
        time(15, 30),
        False,
        None,
        "Follows own term dates. Three terms per year.",
    ),
    (
        "Milton Keynes Prep",
        "Prep (5-11)",
        4100.0,
        12300.0,
        3.5,
        time(8, 20),
        time(15, 45),
        False,
        None,
        "Follows own term dates. Three terms per year.",
    ),
    # Webber Independent
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
    # Grove Independent
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
    # Broughton Manor Prep
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
    # KWS Milton Keynes
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


def _seed_private_school_details(session: Session) -> int:
    """Create PrivateSchoolDetails records for private schools using researched data.

    Matches schools by name fragment and creates fee-tier entries per school.
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
        for frag, entries in details_by_frag.items():
            if frag.lower() in school.name.lower():
                matched = entries
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
                print(f"  {key.upper()}: imported={sub_stats.get('imported', 0)}, skipped={sub_stats.get('skipped', 0)}")
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
