"""Generate realistic holiday club seed data for schools."""

from __future__ import annotations

import random
from datetime import time

from sqlalchemy.orm import Session

from src.db.models import HolidayClub, School

# Holiday club provider names (mix of school-run and external)
_HOLIDAY_CLUB_PROVIDERS = [
    ("School Holiday Club", True),
    ("Kids Zone Holiday Camp", False),
    ("Active Adventures", False),
    ("Creative Kids Club", False),
    ("Camp Explore", False),
    ("School Activity Hub", True),
    ("Play & Learn Holiday Club", False),
    ("Adventures Unlimited", False),
    ("Fun Factory", False),
    ("Extended Schools Holiday Care", True),
]

# Holiday descriptions
_HOLIDAY_CLUB_DESCRIPTIONS = [
    "Fun-filled days with sports, arts, crafts, and games during school holidays",
    "Active holiday camp with outdoor activities, team games, and creative workshops",
    "Multi-activity holiday club offering sports, arts, STEM activities, and trips",
    "Holiday childcare with structured activities and free play for all ages",
    "Themed weeks during holidays including science, sports, arts, and outdoor adventure",
    "Holiday provision with breakfast, lunch, and varied activities throughout the day",
]


def generate_holiday_clubs(schools: list[School], seed: int = 42) -> list[HolidayClub]:
    """Generate realistic holiday club data for a subset of schools.

    Args:
        schools: List of School objects to generate holiday clubs for
        seed: Random seed for reproducibility

    Returns:
        List of HolidayClub objects
    """
    rng = random.Random(seed)
    holiday_clubs: list[HolidayClub] = []

    for school in schools:
        if school.id is None:
            continue

        # Not all schools have holiday clubs - roughly 60% have at least one
        if rng.random() > 0.60:
            continue

        # Determine if school has holiday provision
        num_providers = rng.choices([0, 1, 1, 1, 2], weights=[40, 35, 15, 7, 3])[0]

        if num_providers == 0:
            continue

        selected_providers = rng.sample(_HOLIDAY_CLUB_PROVIDERS, min(num_providers, len(_HOLIDAY_CLUB_PROVIDERS)))

        for provider_name, is_school_run in selected_providers:
            # Determine age range
            if school.age_range_from is not None and school.age_range_to is not None:
                age_from = max(4, school.age_range_from)
                age_to = min(11, school.age_range_to)  # Holiday clubs typically cap at 11

                # Some providers only serve part of the school age range
                if rng.random() < 0.3:
                    if age_to - age_from > 4:
                        if rng.random() < 0.5:
                            age_to = age_from + rng.randint(3, 5)
                        else:
                            age_from = age_to - rng.randint(3, 5)
            else:
                age_from = 4
                age_to = 11

            # Operating hours
            start_hour = rng.choice([7, 8, 8, 8, 9])
            start_min = rng.choice([0, 30]) if start_hour in (7, 8) else 0
            end_hour = rng.choice([17, 18, 18])
            end_min = rng.choice([0, 30])

            # Costs
            hours_per_day = (end_hour + end_min / 60) - (start_hour + start_min / 60)
            # Typical cost is £5-8 per hour
            cost_per_day = round(hours_per_day * rng.uniform(5.0, 8.0), 2)

            # Weekly discount (typically 10-20% off 5 days)
            cost_per_week = round(cost_per_day * 5 * rng.uniform(0.80, 0.90), 2)

            # Available weeks - most clubs run during main school holidays
            available_weeks_options = [
                "Easter, Summer, October half-term",
                "Summer, October half-term, February half-term",
                "Summer only",
                "All school holidays",
                "Easter, Summer, October half-term, February half-term",
            ]
            available_weeks = rng.choice(available_weeks_options)

            # Booking URL (more likely for external providers)
            booking_url = None
            if not is_school_run or rng.random() < 0.3:
                provider_slug = provider_name.lower().replace(" ", "-").replace("&", "and")
                booking_url = f"https://www.{provider_slug}.co.uk/booking"

            holiday_clubs.append(
                HolidayClub(
                    school_id=school.id,
                    provider_name=provider_name,
                    is_school_run=is_school_run,
                    description=rng.choice(_HOLIDAY_CLUB_DESCRIPTIONS),
                    age_from=age_from,
                    age_to=age_to,
                    start_time=time(start_hour, start_min),
                    end_time=time(end_hour, end_min),
                    cost_per_day=cost_per_day,
                    cost_per_week=cost_per_week,
                    available_weeks=available_weeks,
                    booking_url=booking_url,
                )
            )

    return holiday_clubs


def upsert_holiday_clubs(session: Session, holiday_clubs: list[HolidayClub]) -> int:
    """Insert holiday club records, skipping duplicates by (school_id, provider_name).

    Args:
        session: SQLAlchemy session
        holiday_clubs: List of HolidayClub objects to insert

    Returns:
        Number of records inserted
    """
    inserted = 0
    for club in holiday_clubs:
        existing = (
            session.query(HolidayClub).filter_by(school_id=club.school_id, provider_name=club.provider_name).first()
        )
        if existing is None:
            session.add(club)
            inserted += 1
    session.commit()
    return inserted
