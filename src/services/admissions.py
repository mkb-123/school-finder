"""Admissions likelihood estimation service.

Uses historical admissions data (last distance offered, applications received,
waiting-list movement) to estimate how likely a child is to receive a place at
a given school based on their distance from it.

.. note::
    This module contains a **stub implementation**.  The estimation logic
    should be expanded once real historical admissions data is available in the
    ``admissions_history`` table.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Likelihood labels
# ---------------------------------------------------------------------------

VERY_LIKELY = "Very likely"
LIKELY = "Likely"
UNLIKELY = "Unlikely"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def estimate_likelihood(
    school_id: int,
    distance_km: float,
    admissions_history: list[Any] | None = None,
) -> str:
    """Estimate the likelihood of a child being offered a place at a school.

    The estimation is based on the child's distance from the school compared
    against historical last-distance-offered data.

    Parameters
    ----------
    school_id:
        The database ID of the target school.
    distance_km:
        The straight-line (or road) distance in kilometres from the child's
        home to the school.
    admissions_history:
        A list of historical admissions records for the school (e.g. ORM
        model instances or dicts).  Each record should contain at least
        ``last_distance_offered_km``.  If ``None`` or empty, the function
        falls back to a conservative default.

    Returns
    -------
    str
        One of ``"Very likely"``, ``"Likely"``, or ``"Unlikely"``.

    .. todo::
        * Implement real estimation logic:
          - Compare *distance_km* against the median and minimum
            ``last_distance_offered_km`` across available years.
          - Factor in trend direction (is the catchment shrinking?).
          - Consider ``applications_received`` vs ``places_offered`` ratio.
          - Weight more recent years more heavily.
        * Return a richer result object (probability band, confidence
          level, supporting data points) instead of a plain string.
    """
    # TODO: Implement real admissions likelihood estimation.
    # Placeholder: return a conservative default until historical data is
    # available and the estimation model is built.
    _ = school_id
    _ = distance_km
    _ = admissions_history
    return LIKELY
