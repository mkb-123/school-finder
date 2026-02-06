"""Decision support service for the school comparison and ranking page.

Provides weighted scoring of schools against user-defined priorities, and
auto-generated pros/cons summaries to help parents make informed decisions.

.. note::
    This module contains **stub implementations**.  The scoring weights and
    pros/cons logic should be fleshed out once the full data model is populated
    and real user-testing feedback is available.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Weighted scoring
# ---------------------------------------------------------------------------


def calculate_weighted_score(school: Any, weights: dict[str, float]) -> float:
    """Calculate a personalised composite score for a school.

    The score is a weighted sum of normalised school attributes.  Users set
    the *weights* dictionary to reflect what matters most to them (e.g.
    ``{"ofsted_rating": 0.4, "distance_km": 0.3, "has_breakfast_club": 0.2,
    "fees": 0.1}``).

    Parameters
    ----------
    school:
        A school object (ORM model instance or dict-like) with attributes
        corresponding to the keys in *weights*.
    weights:
        A mapping of attribute name to importance weight (0.0 -- 1.0).
        Weights do **not** need to sum to 1; they will be normalised
        internally.

    Returns
    -------
    float
        A composite score (higher is better).  The exact scale depends on
        the normalisation strategy used for each attribute.

    .. todo::
        * Implement attribute normalisation (min-max or z-score) based on the
          full result set so scores are comparable across searches.
        * Handle inverse metrics (e.g. lower distance is better, but higher
          Ofsted numeric rating is *worse* -- Outstanding = 1).
        * Support categorical attributes (e.g. faith, school type) via
          user-specified preference ordering.
    """
    # TODO: Implement real weighted scoring logic.
    # Placeholder: return 0.0 for every school until the scoring model is built.
    _ = school
    _ = weights
    return 0.0


# ---------------------------------------------------------------------------
# Pros / Cons generation
# ---------------------------------------------------------------------------


def generate_pros_cons(school: Any) -> tuple[list[str], list[str]]:
    """Auto-generate a list of pros and cons for a school.

    Examines the school's attributes and produces human-readable bullet
    points highlighting strengths and weaknesses (e.g.
    ``"Outstanding Ofsted rating"``, ``"No breakfast club available"``).

    Parameters
    ----------
    school:
        A school object (ORM model instance or dict-like).

    Returns
    -------
    tuple[list[str], list[str]]
        A ``(pros, cons)`` pair, each being a list of short description
        strings.

    .. todo::
        * Implement heuristic rules for common pros/cons:
          - Ofsted rating thresholds
          - Distance from home (close = pro, far = con)
          - Club availability
          - Fees (for private schools)
          - Recent inspection trend (improving vs declining)
        * Consider letting users customise which attributes generate
          pros/cons entries.
    """
    # TODO: Implement real pros/cons generation logic based on school attributes.
    _ = school
    pros: list[str] = []
    cons: list[str] = []
    return (pros, cons)
