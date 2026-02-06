from __future__ import annotations

import datetime
from typing import Literal

from src.db.models import OfstedHistory

TrajectoryType = Literal["improving", "stable", "declining", "unknown"]


def calculate_trajectory(history: list[OfstedHistory]) -> dict:
    """Calculate Ofsted trajectory from inspection history.

    Args:
        history: List of OfstedHistory records ordered by date descending (newest first)

    Returns:
        Dict with trajectory, current_rating, previous_rating, inspection_age_years, is_stale
    """
    if not history:
        return {
            "trajectory": "unknown",
            "current_rating": None,
            "previous_rating": None,
            "inspection_age_years": None,
            "is_stale": False,
        }

    # Rating order (best to worst)
    rating_order = ["Outstanding", "Good", "Requires Improvement", "Inadequate"]

    current = history[0]
    current_rating = current.rating
    previous_rating = history[1].rating if len(history) > 1 else None

    # Calculate age of last inspection
    today = datetime.date.today()
    inspection_age_days = (today - current.inspection_date).days
    inspection_age_years = inspection_age_days / 365.25
    is_stale = inspection_age_years > 5.0

    # Determine trajectory
    trajectory: TrajectoryType = "unknown"
    if previous_rating and current_rating in rating_order and previous_rating in rating_order:
        current_idx = rating_order.index(current_rating)
        previous_idx = rating_order.index(previous_rating)

        if current_idx < previous_idx:
            trajectory = "improving"
        elif current_idx > previous_idx:
            trajectory = "declining"
        else:
            trajectory = "stable"
    elif not previous_rating:
        trajectory = "stable"  # Only one inspection, assume stable

    return {
        "trajectory": trajectory,
        "current_rating": current_rating,
        "previous_rating": previous_rating,
        "inspection_age_years": round(inspection_age_years, 1),
        "is_stale": is_stale,
    }
