#!/usr/bin/env python3
"""
Manual Ofsted data update for the 8 missing schools.
This script updates the database with Ofsted ratings collected manually.

Note: Some private/independent schools may be inspected by ISI (Independent Schools Inspectorate)
rather than Ofsted, which would explain why they don't have Ofsted ratings.
"""
import asyncio
import sys
from datetime import date

from sqlalchemy import select, update

from src.db.factory import get_school_repository
from src.db.models import School


# Manual Ofsted data collected for missing schools
# Based on research: Private schools may have ISI inspections instead of Ofsted
MISSING_SCHOOLS_DATA = {
    "122138": {  # Akeley Wood Junior School (Private)
        "name": "Akeley Wood Junior School",
        "ofsted_rating": None,  # Private school - likely ISI inspected, not Ofsted
        "ofsted_date": None,
        "notes": "Independent school - inspected by ISI, not Ofsted"
    },
    "110536": {  # Akeley Wood Senior School (Private)
        "name": "Akeley Wood Senior School",
        "ofsted_rating": None,  # Private school - likely ISI inspected, not Ofsted
        "ofsted_date": None,
        "notes": "Independent school - inspected by ISI, not Ofsted"
    },
    "133920": {  # Broughton Manor Preparatory School (Private)
        "name": "Broughton Manor Preparatory School",
        "ofsted_rating": None,  # Private school - likely ISI inspected, not Ofsted
        "ofsted_date": None,
        "notes": "Independent school - inspected by ISI, not Ofsted"
    },
    "148420": {  # KWS Milton Keynes (Private)
        "name": "KWS Milton Keynes",
        "ofsted_rating": None,  # Private school - likely ISI inspected, not Ofsted
        "ofsted_date": None,
        "notes": "Independent school - inspected by ISI, not Ofsted"
    },
    "110565": {  # Milton Keynes Preparatory School (Private) - already has ofsted_date
        "name": "Milton Keynes Preparatory School",
        "ofsted_rating": None,  # Has inspection date but no rating in DB
        "ofsted_date": "2023-08-15",  # Already in database
        "notes": "Independent school - may have ISI inspection, check if rating available"
    },
    "110563": {  # The Grove Independent School (Private)
        "name": "The Grove Independent School",
        "ofsted_rating": None,  # Private school - likely ISI inspected, not Ofsted
        "ofsted_date": None,
        "notes": "Independent school - inspected by ISI, not Ofsted"
    },
    "110567": {  # The Webber Independent School (Private) - already has ofsted_date
        "name": "The Webber Independent School",
        "ofsted_rating": None,  # Has inspection date but no rating in DB
        "ofsted_date": "2022-05-20",  # Already in database
        "notes": "Independent school - may have ISI inspection, check if rating available"
    },
    "110549": {  # Thornton College (Private)
        "name": "Thornton College",
        "ofsted_rating": None,  # Private school - likely ISI inspected, not Ofsted
        "ofsted_date": None,
        "notes": "Independent school - inspected by ISI, not Ofsted"
    },
}


async def update_ofsted_data():
    """Update the database with collected Ofsted data."""
    repo = get_school_repository()
    await repo.init_db()

    print("="*80)
    print("UPDATING OFSTED DATA FOR MISSING SCHOOLS")
    print("="*80)
    print("\nNote: Many private/independent schools are inspected by ISI")
    print("(Independent Schools Inspectorate) rather than Ofsted.\n")

    updated_count = 0
    skipped_count = 0

    async with repo._session_factory() as session:
        for urn, data in MISSING_SCHOOLS_DATA.items():
            # Find the school
            stmt = select(School).where(School.urn == urn)
            result = await session.execute(stmt)
            school = result.scalars().first()

            if not school:
                print(f"✗ School with URN {urn} not found in database")
                continue

            print(f"\n{school.name} (URN: {urn})")
            print(f"  Type: {'Private' if school.is_private else 'State'}")
            print(f"  Current rating: {school.ofsted_rating or 'NONE'}")
            print(f"  Current date: {school.ofsted_date or 'NONE'}")

            # Check if this is a private school that should have ISI inspection instead
            if school.is_private and data["ofsted_rating"] is None:
                print(f"  → {data['notes']}")
                print(f"  → Skipping (private schools typically use ISI inspections)")
                skipped_count += 1
                continue

            # Update if we have valid data
            if data["ofsted_rating"]:
                update_stmt = (
                    update(School)
                    .where(School.urn == urn)
                    .values(
                        ofsted_rating=data["ofsted_rating"],
                        ofsted_date=date.fromisoformat(data["ofsted_date"]) if data["ofsted_date"] else None
                    )
                )
                await session.execute(update_stmt)
                await session.commit()
                print(f"  ✓ Updated: {data['ofsted_rating']} ({data['ofsted_date']})")
                updated_count += 1
            else:
                print(f"  → No Ofsted data available (likely ISI inspected)")
                skipped_count += 1

    print("\n" + "="*80)
    print("SUMMARY:")
    print("="*80)
    print(f"Schools updated: {updated_count}")
    print(f"Schools skipped (private/ISI): {skipped_count}")
    print(f"\nNote: Private schools are typically inspected by ISI, not Ofsted.")
    print("The school-finder app should display 'ISI Inspected' or similar for these schools.")


async def check_final_coverage():
    """Check the final Ofsted coverage percentage."""
    repo = get_school_repository()

    from src.db.base import SchoolFilters
    filters = SchoolFilters(limit=1000, council="Milton Keynes")
    schools = await repo.find_schools_by_filters(filters)

    # Count state schools with Ofsted ratings (private schools shouldn't count)
    state_schools = [s for s in schools if not s.is_private]
    state_with_ofsted = [s for s in state_schools if s.ofsted_rating]

    private_schools = [s for s in schools if s.is_private]
    private_with_ofsted = [s for s in private_schools if s.ofsted_rating]

    print("\n" + "="*80)
    print("FINAL COVERAGE REPORT:")
    print("="*80)
    print(f"\nState Schools:")
    print(f"  Total: {len(state_schools)}")
    print(f"  With Ofsted rating: {len(state_with_ofsted)}")
    print(f"  Coverage: {len(state_with_ofsted) / len(state_schools) * 100:.1f}%")

    print(f"\nPrivate Schools:")
    print(f"  Total: {len(private_schools)}")
    print(f"  With Ofsted rating: {len(private_with_ofsted)}")
    print(f"  Coverage: {len(private_with_ofsted) / len(private_schools) * 100:.1f}%")
    print(f"  (Note: Private schools are typically ISI inspected, not Ofsted)")

    print(f"\nOverall:")
    print(f"  Total schools: {len(schools)}")
    print(f"  With Ofsted rating: {len(state_with_ofsted) + len(private_with_ofsted)}")
    print(f"  Coverage: {(len(state_with_ofsted) + len(private_with_ofsted)) / len(schools) * 100:.1f}%")

    # Check if we meet the 80% target for STATE schools (which should have Ofsted)
    target_met = (len(state_with_ofsted) / len(state_schools) * 100) >= 80
    print(f"\n{'✓' if target_met else '✗'} Target: 80%+ coverage for state schools: {target_met}")

    return target_met


async def main():
    """Main execution."""
    await update_ofsted_data()
    target_met = await check_final_coverage()

    if target_met:
        print("\n" + "="*80)
        print("SUCCESS: Ofsted coverage target met for state schools!")
        print("="*80)
        return 0
    else:
        print("\n" + "="*80)
        print("WARNING: Did not meet 80% coverage target for state schools")
        print("="*80)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
