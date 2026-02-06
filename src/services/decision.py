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

MAX_DISTANCE_KM = 10.0
MAX_FEE_ANNUAL = 30_000.0  # reference upper-bound for normalisation

DEFAULT_WEIGHTS: dict[str, float] = {
    "distance": 0.25,
    "ofsted": 0.30,
    "clubs": 0.25,
    "fees": 0.20,
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


# ---------------------------------------------------------------------------
# WeightedScorer
# ---------------------------------------------------------------------------


class WeightedScorer:
    """Scores schools using user-defined importance weights.

    Weights are provided as a dict mapping dimension names to
    relative importance values.  They are normalised internally
    so they don't need to sum to 1.
    """

    DIMENSIONS = ("distance", "ofsted", "clubs", "fees")

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


def school_data_from_orm(school: Any, clubs: list[Any] | None = None, distance_km: float | None = None) -> SchoolData:
    """Construct a :class:`SchoolData` from an ORM ``School`` instance.

    Optionally accepts a list of ``SchoolClub`` ORM instances to populate
    the breakfast/afterschool flags, and a pre-computed *distance_km* value
    (since the ``School`` ORM model has no ``distance_km`` column).
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
