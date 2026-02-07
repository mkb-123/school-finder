#!/usr/bin/env python3
"""
Ralph Wiggum Ofsted Data Collection Loop
Iteration 1: Extract all school URNs and begin Ofsted data lookup
"""
import asyncio
import json
import sys
from pathlib import Path

from src.db.factory import get_school_repository


async def main():
    """Extract all schools with URNs from the database."""
    repo = get_school_repository()

    # Initialize database
    await repo.init_db()

    # Get all schools (no filters, get everything)
    from src.db.base import SchoolFilters
    filters = SchoolFilters(limit=1000, council="Milton Keynes")  # Get all MK schools
    schools = await repo.find_schools_by_filters(filters)

    print(f"Found {len(schools)} schools in Milton Keynes")
    print("\n" + "="*80)
    print("SCHOOLS WITH URN (ready for Ofsted lookup):")
    print("="*80)

    schools_with_urn = []
    schools_without_urn = []
    schools_with_ofsted = []

    for school in schools:
        if school.urn:
            schools_with_urn.append({
                "id": school.id,
                "name": school.name,
                "urn": school.urn,
                "type": school.type,
                "ofsted_rating": school.ofsted_rating,
                "ofsted_date": str(school.ofsted_date) if school.ofsted_date else None,
                "postcode": school.postcode,
                "is_private": school.is_private
            })
            if school.ofsted_rating:
                schools_with_ofsted.append(school)
            print(f"✓ {school.name} (URN: {school.urn}) - Current Rating: {school.ofsted_rating or 'MISSING'}")
        else:
            schools_without_urn.append({
                "id": school.id,
                "name": school.name,
                "type": school.type,
                "is_private": school.is_private
            })
            print(f"✗ {school.name} - NO URN (type: {school.type})")

    print("\n" + "="*80)
    print("SUMMARY:")
    print("="*80)
    print(f"Total schools: {len(schools)}")
    print(f"Schools with URN: {len(schools_with_urn)}")
    print(f"Schools without URN: {len(schools_without_urn)}")
    print(f"Schools with existing Ofsted rating: {len(schools_with_ofsted)}")
    print(f"Schools needing Ofsted data: {len(schools_with_urn) - len(schools_with_ofsted)}")

    # Save to JSON for tracking
    output_file = Path("/tmp/ralph_ofsted_schools.json")
    output_data = {
        "total_schools": len(schools),
        "schools_with_urn": schools_with_urn,
        "schools_without_urn": schools_without_urn,
        "needs_ofsted_count": len(schools_with_urn) - len(schools_with_ofsted),
        "coverage_pct": round(len(schools_with_ofsted) / len(schools_with_urn) * 100, 2) if schools_with_urn else 0
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✓ Data saved to {output_file}")
    print(f"\nCurrent Ofsted coverage: {output_data['coverage_pct']}%")
    print(f"Target: 80%+ coverage")

    return output_data


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0)
