"""Decision support service for the school comparison and ranking page.

Provides weighted scoring of schools against user-defined priorities,
auto-generated pros/cons summaries, and "what if" scenario re-ranking
to help parents make informed decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OFSTED_SCORES: dict[str, float] = {
    "Outstanding": 100.0,
    "Good": 75.0,
    "Requires Improvement": 25.0,
    "Inadequate": 0.0,
}

OFSTED_ORDER: list[str] = ["Outstanding", "Good", "Requires Improvement", "Inadequate"]

# Ofsted trajectory scores
OFSTED_TRAJECTORY_SCORES: dict[str, float] = {
    "improving": 100.0,  # e.g., Requires Improvement -> Good
    "stable": 75.0,  # Same rating maintained
    "declining": 25.0,  # e.g., Outstanding -> Good
    "new": 50.0,  # No previous rating
}

MAX_DISTANCE_KM = 10.0
MAX_FEE_ANNUAL = 30_000.0  # reference upper-bound for normalisation
MAX_CLASS_SIZE = 35.0  # reference upper-bound for class size
MAX_PARKING_CHAOS = 5.0  # parking ratings are on a 1-5 scale
MAX_UNIFORM_COST = 500.0  # reference upper-bound for uniform cost in GBP
MAX_HOMEWORK_HOURS = 3.0  # reference upper-bound for daily homework hours

DEFAULT_WEIGHTS: dict[str, float] = {
    "distance": 0.25,
    "ofsted": 0.30,
    "clubs": 0.25,
    "fees": 0.20,
    "ofsted_trajectory": 0.0,
    "attendance": 0.0,
    "class_size": 0.0,
    "parking": 0.0,
    "holiday_club": 0.0,
    "uniform": 0.0,
    "diversity": 0.0,
    "sibling_priority": 0.0,
    "school_run_ease": 0.0,
    "homework": 0.0,
}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class SchoolData:
    """Flat representation of a school used by the scoring engine.

    This is constructed from an ORM model or API response dict so
    that the scorer doesn't depend on SQLAlchemy directly.
    """

    id: int
    name: str
    ofsted_rating: str | None = None
    distance_km: float | None = None
    is_private: bool = False
    has_breakfast_club: bool = False
    has_afterschool_club: bool = False
    annual_fee: float | None = None
    age_range_from: int | None = None
    age_range_to: int | None = None
    gender_policy: str | None = None
    faith: str | None = None
    school_type: str | None = None
    postcode: str | None = None

    # New extended metrics
    ofsted_trajectory: str | None = None  # "improving" / "stable" / "declining" / "new"
    attendance_rate: float | None = None  # percentage, 0-100
    avg_class_size: float | None = None  # average class size
    parking_chaos_score: float | None = None  # average chaos rating, 1-5 (lower is better)
    has_holiday_club: bool = False  # whether school has holiday club provision
    uniform_cost: float | None = None  # total uniform cost estimate
    diversity_score: float | None = None  # composite diversity metric, 0-100
    sibling_priority_strength: float | None = None  # probability of sibling admission, 0-100
    school_run_ease_score: float | None = None  # composite of distance + journey time + safety, 0-100
    homework_hours_per_day: float | None = None  # estimated daily homework hours


@dataclass
class ScoredSchool:
    """A school together with its composite score and component breakdown."""

    school: SchoolData
    composite_score: float
    component_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class WhatIfScenario:
    """User-defined constraint overrides for "what if" re-ranking."""

    max_distance_km: float | None = None
    min_rating: str | None = None
    include_faith: bool | None = None
    max_annual_fee: float | None = None


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _normalise_distance(distance_km: float | None) -> float:
    """Normalise distance to a 0-100 score (closer = higher).

    A distance of 0 km yields 100, a distance >= MAX_DISTANCE_KM yields 0.
    """
    if distance_km is None:
        return 50.0  # neutral if unknown
    clamped = max(0.0, min(distance_km, MAX_DISTANCE_KM))
    return 100.0 * (1.0 - clamped / MAX_DISTANCE_KM)


def _normalise_ofsted(rating: str | None) -> float:
    """Map an Ofsted rating string to a 0-100 score."""
    if rating is None:
        return 50.0  # neutral if unrated
    return OFSTED_SCORES.get(rating, 50.0)


def _normalise_clubs(has_breakfast: bool, has_afterschool: bool) -> float:
    """Score club availability: 50 points for each type, cumulative."""
    score = 0.0
    if has_breakfast:
        score += 50.0
    if has_afterschool:
        score += 50.0
    return score


def _normalise_fees(annual_fee: float | None, is_private: bool) -> float:
    """Normalise fees to 0-100 (cheaper = higher).

    State schools (not private) get a perfect 100 (free).
    Private schools are scored inversely against MAX_FEE_ANNUAL.
    """
    if not is_private:
        return 100.0
    if annual_fee is None:
        return 50.0  # neutral if unknown
    clamped = max(0.0, min(annual_fee, MAX_FEE_ANNUAL))
    return 100.0 * (1.0 - clamped / MAX_FEE_ANNUAL)


def _normalise_ofsted_trajectory(trajectory: str | None) -> float:
    """Map an Ofsted trajectory indicator to a 0-100 score."""
    if trajectory is None:
        return 50.0  # neutral if unknown
    return OFSTED_TRAJECTORY_SCORES.get(trajectory, 50.0)


def _normalise_attendance(attendance_rate: float | None) -> float:
    """Normalise attendance rate to 0-100 (higher attendance = higher score).

    Attendance is already a percentage (0-100), so just pass through.
    """
    if attendance_rate is None:
        return 50.0  # neutral if unknown
    return max(0.0, min(attendance_rate, 100.0))


def _normalise_class_size(avg_class_size: float | None) -> float:
    """Normalise class size to 0-100 (smaller = higher).

    Smaller classes are generally preferred for individual attention.
    """
    if avg_class_size is None:
        return 50.0  # neutral if unknown
    clamped = max(0.0, min(avg_class_size, MAX_CLASS_SIZE))
    return 100.0 * (1.0 - clamped / MAX_CLASS_SIZE)


def _normalise_parking(parking_chaos_score: float | None) -> float:
    """Normalise parking chaos rating to 0-100 (lower chaos = higher score).

    Parking ratings are 1-5 where 5 is most chaotic, so invert.
    """
    if parking_chaos_score is None:
        return 50.0  # neutral if unknown
    clamped = max(1.0, min(parking_chaos_score, MAX_PARKING_CHAOS))
    return 100.0 * (1.0 - (clamped - 1.0) / (MAX_PARKING_CHAOS - 1.0))


def _normalise_holiday_club(has_holiday_club: bool) -> float:
    """Score holiday club availability: 100 if available, 0 if not."""
    return 100.0 if has_holiday_club else 0.0


def _normalise_uniform(uniform_cost: float | None) -> float:
    """Normalise uniform cost to 0-100 (cheaper = higher)."""
    if uniform_cost is None:
        return 50.0  # neutral if unknown
    clamped = max(0.0, min(uniform_cost, MAX_UNIFORM_COST))
    return 100.0 * (1.0 - clamped / MAX_UNIFORM_COST)


def _normalise_diversity(diversity_score: float | None) -> float:
    """Normalise diversity score to 0-100.

    Diversity is already a 0-100 composite metric, so just pass through.
    """
    if diversity_score is None:
        return 50.0  # neutral if unknown
    return max(0.0, min(diversity_score, 100.0))


def _normalise_sibling_priority(sibling_priority_strength: float | None) -> float:
    """Normalise sibling priority strength to 0-100.

    This is a probability percentage, so just pass through.
    """
    if sibling_priority_strength is None:
        return 50.0  # neutral if unknown
    return max(0.0, min(sibling_priority_strength, 100.0))


def _normalise_school_run_ease(school_run_ease_score: float | None) -> float:
    """Normalise school run ease score to 0-100.

    This is a composite metric already on 0-100 scale.
    """
    if school_run_ease_score is None:
        return 50.0  # neutral if unknown
    return max(0.0, min(school_run_ease_score, 100.0))


def _normalise_homework(homework_hours_per_day: float | None) -> float:
    """Normalise homework intensity to 0-100.

    Lower homework hours = higher score (assuming parents prefer less homework).
    This slider allows parents to toggle preference direction.
    """
    if homework_hours_per_day is None:
        return 50.0  # neutral if unknown
    clamped = max(0.0, min(homework_hours_per_day, MAX_HOMEWORK_HOURS))
    return 100.0 * (1.0 - clamped / MAX_HOMEWORK_HOURS)


# ---------------------------------------------------------------------------
# WeightedScorer
# ---------------------------------------------------------------------------


class WeightedScorer:
    """Scores schools using user-defined importance weights.

    Weights are provided as a dict mapping dimension names to
    relative importance values.  They are normalised internally
    so they don't need to sum to 1.
    """

    DIMENSIONS = (
        "distance",
        "ofsted",
        "clubs",
        "fees",
        "ofsted_trajectory",
        "attendance",
        "class_size",
        "parking",
        "holiday_club",
        "uniform",
        "diversity",
        "sibling_priority",
        "school_run_ease",
        "homework",
    )

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        raw = weights if weights else dict(DEFAULT_WEIGHTS)
        # Only keep known dimensions
        filtered = {k: max(v, 0.0) for k, v in raw.items() if k in self.DIMENSIONS}
        total = sum(filtered.values())
        if total == 0:
            # Avoid division by zero: fall back to equal weights
            self._weights = {k: 1.0 / len(self.DIMENSIONS) for k in self.DIMENSIONS}
        else:
            self._weights = {k: v / total for k, v in filtered.items()}
        # Fill in missing dimensions with 0
        for dim in self.DIMENSIONS:
            self._weights.setdefault(dim, 0.0)

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def _component_scores(self, school: SchoolData) -> dict[str, float]:
        return {
            "distance": _normalise_distance(school.distance_km),
            "ofsted": _normalise_ofsted(school.ofsted_rating),
            "clubs": _normalise_clubs(school.has_breakfast_club, school.has_afterschool_club),
            "fees": _normalise_fees(school.annual_fee, school.is_private),
            "ofsted_trajectory": _normalise_ofsted_trajectory(school.ofsted_trajectory),
            "attendance": _normalise_attendance(school.attendance_rate),
            "class_size": _normalise_class_size(school.avg_class_size),
            "parking": _normalise_parking(school.parking_chaos_score),
            "holiday_club": _normalise_holiday_club(school.has_holiday_club),
            "uniform": _normalise_uniform(school.uniform_cost),
            "diversity": _normalise_diversity(school.diversity_score),
            "sibling_priority": _normalise_sibling_priority(school.sibling_priority_strength),
            "school_run_ease": _normalise_school_run_ease(school.school_run_ease_score),
            "homework": _normalise_homework(school.homework_hours_per_day),
        }

    def score_school(self, school: SchoolData) -> ScoredSchool:
        """Compute the weighted composite score for a single school."""
        components = self._component_scores(school)
        composite = sum(self._weights[k] * components[k] for k in self.DIMENSIONS)
        return ScoredSchool(
            school=school,
            composite_score=round(composite, 1),
            component_scores={k: round(v, 1) for k, v in components.items()},
        )

    def rank_schools(self, schools: list[SchoolData]) -> list[ScoredSchool]:
        """Score and rank a list of schools (highest score first)."""
        scored = [self.score_school(s) for s in schools]
        scored.sort(key=lambda s: s.composite_score, reverse=True)
        return scored


# ---------------------------------------------------------------------------
# Pros / Cons generation
# ---------------------------------------------------------------------------


def generate_pros_cons(school: SchoolData) -> tuple[list[str], list[str]]:
    """Auto-generate a list of pros and cons for a school.

    Examines the school's attributes and produces human-readable bullet
    points highlighting strengths and weaknesses.

    Returns
    -------
    tuple[list[str], list[str]]
        A ``(pros, cons)`` pair.
    """
    pros: list[str] = []
    cons: list[str] = []

    # --- Ofsted ---
    rating = school.ofsted_rating
    if rating == "Outstanding":
        pros.append("Outstanding Ofsted rating")
    elif rating == "Good":
        pros.append("Good Ofsted rating")
    elif rating == "Requires Improvement":
        cons.append("Requires Improvement Ofsted rating")
    elif rating == "Inadequate":
        cons.append("Inadequate Ofsted rating")

    # --- Distance ---
    if school.distance_km is not None:
        if school.distance_km <= 1.0:
            pros.append(f"Walking distance ({school.distance_km:.1f} km)")
        elif school.distance_km <= 3.0:
            pros.append(f"Nearby ({school.distance_km:.1f} km)")
        elif school.distance_km <= 5.0:
            cons.append(f"Moderate distance ({school.distance_km:.1f} km)")
        else:
            cons.append(f"Over {school.distance_km:.1f} km away")

    # --- Clubs ---
    if school.has_breakfast_club:
        pros.append("Breakfast club available")
    else:
        cons.append("No breakfast club")

    if school.has_afterschool_club:
        pros.append("After-school club available")
    else:
        cons.append("No after-school club")

    # --- Fees (private only) ---
    if school.is_private:
        if school.annual_fee is not None:
            if school.annual_fee <= 10_000:
                pros.append(f"Competitive fees ({_fmt_gbp(school.annual_fee)}/year)")
            elif school.annual_fee >= 20_000:
                cons.append(f"High fees ({_fmt_gbp(school.annual_fee)}/year)")
            else:
                pros.append(f"Fees: {_fmt_gbp(school.annual_fee)}/year")
        else:
            cons.append("Fee information not available")
    else:
        pros.append("State-funded (no tuition fees)")

    # --- Faith ---
    if school.faith:
        # Neutral observation, listed as a pro for clarity
        pros.append(f"Faith school ({school.faith})")

    # --- Ofsted Trajectory ---
    if school.ofsted_trajectory == "improving":
        pros.append("Improving Ofsted rating trajectory")
    elif school.ofsted_trajectory == "declining":
        cons.append("Declining Ofsted rating trajectory")

    # --- Attendance ---
    if school.attendance_rate is not None:
        if school.attendance_rate >= 96.0:
            pros.append(f"Excellent attendance rate ({school.attendance_rate:.1f}%)")
        elif school.attendance_rate < 93.0:
            cons.append(f"Below-average attendance ({school.attendance_rate:.1f}%)")

    # --- Class Size ---
    if school.avg_class_size is not None:
        if school.avg_class_size <= 25.0:
            pros.append(f"Small class sizes (avg {school.avg_class_size:.1f} pupils)")
        elif school.avg_class_size >= 32.0:
            cons.append(f"Large class sizes (avg {school.avg_class_size:.1f} pupils)")

    # --- Parking ---
    if school.parking_chaos_score is not None:
        if school.parking_chaos_score <= 2.0:
            pros.append("Easy drop-off and parking")
        elif school.parking_chaos_score >= 4.0:
            cons.append("Difficult drop-off and parking")

    # --- Holiday Club ---
    if school.has_holiday_club:
        pros.append("Holiday club available on-site")
    else:
        cons.append("No holiday club provision")

    # --- Uniform ---
    if school.uniform_cost is not None:
        if school.uniform_cost <= 150.0:
            pros.append(f"Affordable uniform (approx {_fmt_gbp(school.uniform_cost)})")
        elif school.uniform_cost >= 350.0:
            cons.append(f"Expensive uniform (approx {_fmt_gbp(school.uniform_cost)})")

    # --- Diversity ---
    if school.diversity_score is not None:
        if school.diversity_score >= 70.0:
            pros.append("Highly diverse school community")
        elif school.diversity_score <= 30.0:
            cons.append("Limited demographic diversity")

    # --- Sibling Priority ---
    if school.sibling_priority_strength is not None:
        if school.sibling_priority_strength >= 80.0:
            pros.append("Strong sibling admission priority")
        elif school.sibling_priority_strength <= 40.0:
            cons.append("Weak sibling admission priority")

    # --- School Run Ease ---
    if school.school_run_ease_score is not None:
        if school.school_run_ease_score >= 80.0:
            pros.append("Very easy school run")
        elif school.school_run_ease_score <= 40.0:
            cons.append("Challenging school run")

    # --- Homework ---
    if school.homework_hours_per_day is not None:
        if school.homework_hours_per_day <= 0.5:
            pros.append("Light homework load")
        elif school.homework_hours_per_day >= 2.0:
            cons.append("Heavy homework load")

    return (pros, cons)


def _fmt_gbp(amount: float) -> str:
    """Format a number as GBP currency string."""
    return f"\u00a3{amount:,.0f}"


# ---------------------------------------------------------------------------
# "What if" scenario re-ranking
# ---------------------------------------------------------------------------


def apply_what_if(
    schools: list[SchoolData],
    scenario: WhatIfScenario,
) -> list[SchoolData]:
    """Filter a school list according to "what if" constraint overrides.

    Returns the subset of *schools* that pass the scenario constraints.
    The caller can then re-rank the filtered list with :class:`WeightedScorer`.
    """
    result: list[SchoolData] = []
    for s in schools:
        # Distance constraint
        if scenario.max_distance_km is not None:
            if s.distance_km is not None and s.distance_km > scenario.max_distance_km:
                continue

        # Minimum Ofsted rating
        if scenario.min_rating is not None:
            if s.ofsted_rating is None:
                continue
            try:
                threshold_idx = OFSTED_ORDER.index(scenario.min_rating)
            except ValueError:
                pass  # unknown rating value, skip check
            else:
                try:
                    school_idx = OFSTED_ORDER.index(s.ofsted_rating)
                except ValueError:
                    continue
                if school_idx > threshold_idx:
                    continue

        # Faith filter
        if scenario.include_faith is False:
            if s.faith:
                continue

        # Max fee
        if scenario.max_annual_fee is not None:
            if s.is_private and s.annual_fee is not None and s.annual_fee > scenario.max_annual_fee:
                continue

        result.append(s)

    return result


# ---------------------------------------------------------------------------
# Convenience: build SchoolData from ORM model or dict
# ---------------------------------------------------------------------------


def school_data_from_orm(
    school: Any,
    clubs: list[Any] | None = None,
    distance_km: float | None = None,
    holiday_clubs: list[Any] | None = None,
    performance: list[Any] | None = None,
    class_sizes: list[Any] | None = None,
    parking_ratings: list[Any] | None = None,
    uniform: list[Any] | None = None,
) -> SchoolData:
    """Construct a :class:`SchoolData` from an ORM ``School`` instance.

    Optionally accepts related data for extended metrics:
    - clubs: list of SchoolClub instances
    - distance_km: pre-computed distance
    - holiday_clubs: list of HolidayClub instances
    - performance: list of SchoolPerformance instances
    - class_sizes: list of SchoolClassSize instances
    - parking_ratings: list of ParkingRating instances
    - uniform: list of SchoolUniform instances
    """
    has_breakfast = False
    has_afterschool = False
    if clubs:
        for c in clubs:
            ct = getattr(c, "club_type", "")
            if ct == "breakfast":
                has_breakfast = True
            elif ct == "after_school":
                has_afterschool = True

    # Try to get annual fee from private_details relationship
    annual_fee: float | None = None
    private_details = getattr(school, "private_details", None)
    if private_details:
        for pd in private_details:
            fee = getattr(pd, "annual_fee", None)
            if fee is not None:
                annual_fee = fee
                break

    # Holiday club availability
    has_holiday_club = bool(holiday_clubs) if holiday_clubs is not None else False

    # Attendance rate from performance data
    attendance_rate: float | None = None
    if performance:
        for perf in performance:
            if getattr(perf, "metric_type", "") == "attendance_rate":
                try:
                    attendance_rate = float(getattr(perf, "metric_value", ""))
                except (ValueError, TypeError):
                    pass
                break

    # Average class size from most recent year
    avg_class_size: float | None = None
    if class_sizes:
        # Get most recent year's average
        class_size_values = [
            getattr(cs, "avg_class_size", None) for cs in class_sizes if getattr(cs, "avg_class_size", None) is not None
        ]
        if class_size_values:
            avg_class_size = sum(class_size_values) / len(class_size_values)

    # Parking chaos score - average of all ratings
    parking_chaos_score: float | None = None
    if parking_ratings:
        chaos_scores = []
        for pr in parking_ratings:
            dropoff = getattr(pr, "dropoff_chaos", None)
            pickup = getattr(pr, "pickup_chaos", None)
            parking = getattr(pr, "parking_availability", None)
            road = getattr(pr, "road_congestion", None)
            restrictions = getattr(pr, "restrictions_hazards", None)
            scores = [s for s in [dropoff, pickup, parking, road, restrictions] if s is not None]
            if scores:
                chaos_scores.append(sum(scores) / len(scores))
        if chaos_scores:
            parking_chaos_score = sum(chaos_scores) / len(chaos_scores)

    # Uniform cost
    uniform_cost: float | None = None
    if uniform:
        for u in uniform:
            cost = getattr(u, "total_cost_estimate", None)
            if cost is not None:
                uniform_cost = cost
                break

    # Ofsted trajectory - placeholder (would need historical Ofsted data to compute)
    ofsted_trajectory: str | None = None  # Could be computed from performance history if available

    # Diversity score - placeholder (would need demographic data)
    diversity_score: float | None = None

    # Sibling priority strength - placeholder (would need admissions criteria data)
    sibling_priority_strength: float | None = None

    # School run ease score - placeholder (composite metric, could use distance + journey data)
    school_run_ease_score: float | None = None

    # Homework hours per day - placeholder (would need school policy data)
    homework_hours_per_day: float | None = None

    return SchoolData(
        id=school.id,
        name=school.name,
        ofsted_rating=getattr(school, "ofsted_rating", None),
        distance_km=distance_km,
        is_private=getattr(school, "is_private", False),
        has_breakfast_club=has_breakfast,
        has_afterschool_club=has_afterschool,
        annual_fee=annual_fee,
        age_range_from=getattr(school, "age_range_from", None),
        age_range_to=getattr(school, "age_range_to", None),
        gender_policy=getattr(school, "gender_policy", None),
        faith=getattr(school, "faith", None),
        school_type=getattr(school, "type", None),
        postcode=getattr(school, "postcode", None),
        ofsted_trajectory=ofsted_trajectory,
        attendance_rate=attendance_rate,
        avg_class_size=avg_class_size,
        parking_chaos_score=parking_chaos_score,
        has_holiday_club=has_holiday_club,
        uniform_cost=uniform_cost,
        diversity_score=diversity_score,
        sibling_priority_strength=sibling_priority_strength,
        school_run_ease_score=school_run_ease_score,
        homework_hours_per_day=homework_hours_per_day,
    )


def school_data_from_dict(d: dict[str, Any]) -> SchoolData:
    """Construct a :class:`SchoolData` from an API response dict."""
    clubs = d.get("clubs", [])
    has_breakfast = any(c.get("club_type") == "breakfast" for c in clubs)
    has_afterschool = any(c.get("club_type") == "after_school" for c in clubs)

    annual_fee: float | None = None
    private_details = d.get("private_details", [])
    if private_details:
        for pd in private_details:
            fee = pd.get("annual_fee")
            if fee is not None:
                annual_fee = fee
                break

    # Extended metrics from dict
    has_holiday_club = bool(d.get("holiday_clubs", []))

    attendance_rate: float | None = None
    performance = d.get("performance", [])
    if performance:
        for perf in performance:
            if perf.get("metric_type") == "attendance_rate":
                try:
                    attendance_rate = float(perf.get("metric_value", ""))
                except (ValueError, TypeError):
                    pass
                break

    class_sizes = d.get("class_sizes", [])
    avg_class_size: float | None = None
    if class_sizes:
        class_size_values = [cs.get("avg_class_size") for cs in class_sizes if cs.get("avg_class_size") is not None]
        if class_size_values:
            avg_class_size = sum(class_size_values) / len(class_size_values)

    parking_ratings = d.get("parking_ratings", [])
    parking_chaos_score: float | None = None
    if parking_ratings:
        chaos_scores = []
        for pr in parking_ratings:
            scores = [
                pr.get(k)
                for k in [
                    "dropoff_chaos",
                    "pickup_chaos",
                    "parking_availability",
                    "road_congestion",
                    "restrictions_hazards",
                ]
                if pr.get(k) is not None
            ]
            if scores:
                chaos_scores.append(sum(scores) / len(scores))
        if chaos_scores:
            parking_chaos_score = sum(chaos_scores) / len(chaos_scores)

    uniform = d.get("uniform", [])
    uniform_cost: float | None = None
    if uniform:
        for u in uniform:
            cost = u.get("total_cost_estimate")
            if cost is not None:
                uniform_cost = cost
                break

    return SchoolData(
        id=d["id"],
        name=d["name"],
        ofsted_rating=d.get("ofsted_rating"),
        distance_km=d.get("distance_km"),
        is_private=d.get("is_private", False),
        has_breakfast_club=has_breakfast,
        has_afterschool_club=has_afterschool,
        annual_fee=annual_fee,
        age_range_from=d.get("age_range_from"),
        age_range_to=d.get("age_range_to"),
        gender_policy=d.get("gender_policy"),
        faith=d.get("faith"),
        school_type=d.get("type"),
        postcode=d.get("postcode"),
        ofsted_trajectory=d.get("ofsted_trajectory"),
        attendance_rate=attendance_rate,
        avg_class_size=avg_class_size,
        parking_chaos_score=parking_chaos_score,
        has_holiday_club=has_holiday_club,
        uniform_cost=uniform_cost,
        diversity_score=d.get("diversity_score"),
        sibling_priority_strength=d.get("sibling_priority_strength"),
        school_run_ease_score=d.get("school_run_ease_score"),
        homework_hours_per_day=d.get("homework_hours_per_day"),
    )


# ---------------------------------------------------------------------------
# Legacy API (kept for backwards compatibility with existing callers)
# ---------------------------------------------------------------------------


def calculate_weighted_score(school: Any, weights: dict[str, float]) -> float:
    """Calculate a personalised composite score for a school.

    This is a simplified wrapper around :class:`WeightedScorer` for
    callers that just need a single float score.
    """
    if isinstance(school, SchoolData):
        sd = school
    else:
        sd = school_data_from_orm(school)
    scorer = WeightedScorer(weights)
    return scorer.score_school(sd).composite_score
