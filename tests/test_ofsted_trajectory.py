"""Tests for Ofsted trajectory calculation service."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from src.services.ofsted_trajectory import calculate_trajectory


def create_mock_inspection(
    school_id: int,
    inspection_date: datetime.date,
    rating: str,
    is_current: bool = False,
) -> MagicMock:
    """Create a mock OfstedHistory object."""
    mock = MagicMock()
    mock.school_id = school_id
    mock.inspection_date = inspection_date
    mock.rating = rating
    mock.is_current = is_current
    mock.report_url = f"https://reports.ofsted.gov.uk/provider/21/{school_id}"
    mock.strengths_quote = "Test strengths"
    mock.improvements_quote = "Test improvements"
    return mock


class TestOfstedTrajectory:
    """Test trajectory calculation for various scenarios."""

    def test_no_history_returns_unknown(self):
        """Empty history should return unknown trajectory."""
        result = calculate_trajectory([])

        assert result["trajectory"] == "unknown"
        assert result["current_rating"] is None
        assert result["previous_rating"] is None
        assert result["inspection_age_years"] is None
        assert result["is_stale"] is False

    def test_single_inspection_returns_stable(self):
        """Single inspection should be treated as stable."""
        today = datetime.date.today()
        history = [
            create_mock_inspection(1, today, "Good", is_current=True),
        ]

        result = calculate_trajectory(history)

        assert result["trajectory"] == "stable"
        assert result["current_rating"] == "Good"
        assert result["previous_rating"] is None
        assert result["inspection_age_years"] == 0.0
        assert result["is_stale"] is False

    def test_improving_trajectory(self):
        """School improving from Requires Improvement to Good."""
        today = datetime.date.today()
        four_years_ago = today - datetime.timedelta(days=4 * 365)

        history = [
            create_mock_inspection(1, today, "Good", is_current=True),
            create_mock_inspection(1, four_years_ago, "Requires Improvement"),
        ]

        result = calculate_trajectory(history)

        assert result["trajectory"] == "improving"
        assert result["current_rating"] == "Good"
        assert result["previous_rating"] == "Requires Improvement"
        assert result["inspection_age_years"] == 0.0
        assert result["is_stale"] is False

    def test_declining_trajectory(self):
        """School declining from Outstanding to Good."""
        today = datetime.date.today()
        three_years_ago = today - datetime.timedelta(days=3 * 365)

        history = [
            create_mock_inspection(1, today, "Good", is_current=True),
            create_mock_inspection(1, three_years_ago, "Outstanding"),
        ]

        result = calculate_trajectory(history)

        assert result["trajectory"] == "declining"
        assert result["current_rating"] == "Good"
        assert result["previous_rating"] == "Outstanding"
        assert result["inspection_age_years"] == 0.0
        assert result["is_stale"] is False

    def test_stable_trajectory(self):
        """School maintaining Good rating."""
        today = datetime.date.today()
        four_years_ago = today - datetime.timedelta(days=4 * 365)

        history = [
            create_mock_inspection(1, today, "Good", is_current=True),
            create_mock_inspection(1, four_years_ago, "Good"),
        ]

        result = calculate_trajectory(history)

        assert result["trajectory"] == "stable"
        assert result["current_rating"] == "Good"
        assert result["previous_rating"] == "Good"
        assert result["inspection_age_years"] == 0.0
        assert result["is_stale"] is False

    def test_stale_inspection_flagged(self):
        """Inspections over 5 years old should be flagged as stale."""
        today = datetime.date.today()
        six_years_ago = today - datetime.timedelta(days=6 * 365)

        history = [
            create_mock_inspection(1, six_years_ago, "Outstanding", is_current=True),
        ]

        result = calculate_trajectory(history)

        assert result["trajectory"] == "stable"
        assert result["current_rating"] == "Outstanding"
        assert result["inspection_age_years"] == pytest.approx(6.0, abs=0.1)
        assert result["is_stale"] is True

    def test_not_stale_at_five_years(self):
        """Exactly 5 years should not be flagged as stale."""
        today = datetime.date.today()
        five_years_ago = today - datetime.timedelta(days=5 * 365)

        history = [
            create_mock_inspection(1, five_years_ago, "Good", is_current=True),
        ]

        result = calculate_trajectory(history)

        assert result["inspection_age_years"] == pytest.approx(5.0, abs=0.1)
        assert result["is_stale"] is False

    def test_multiple_inspections_only_uses_two_most_recent(self):
        """Trajectory should only compare current vs previous (not older)."""
        today = datetime.date.today()
        three_years_ago = today - datetime.timedelta(days=3 * 365)
        six_years_ago = today - datetime.timedelta(days=6 * 365)
        nine_years_ago = today - datetime.timedelta(days=9 * 365)

        history = [
            create_mock_inspection(1, today, "Good", is_current=True),
            create_mock_inspection(1, three_years_ago, "Requires Improvement"),
            create_mock_inspection(1, six_years_ago, "Good"),
            create_mock_inspection(1, nine_years_ago, "Outstanding"),
        ]

        result = calculate_trajectory(history)

        # Should show improving (Requires Improvement → Good)
        # Not declining (Outstanding → Good over full history)
        assert result["trajectory"] == "improving"
        assert result["current_rating"] == "Good"
        assert result["previous_rating"] == "Requires Improvement"

    def test_outstanding_to_inadequate_is_declining(self):
        """Dramatic decline should be detected."""
        today = datetime.date.today()
        four_years_ago = today - datetime.timedelta(days=4 * 365)

        history = [
            create_mock_inspection(1, today, "Inadequate", is_current=True),
            create_mock_inspection(1, four_years_ago, "Outstanding"),
        ]

        result = calculate_trajectory(history)

        assert result["trajectory"] == "declining"
        assert result["current_rating"] == "Inadequate"
        assert result["previous_rating"] == "Outstanding"

    def test_inadequate_to_outstanding_is_improving(self):
        """Dramatic improvement should be detected."""
        today = datetime.date.today()
        four_years_ago = today - datetime.timedelta(days=4 * 365)

        history = [
            create_mock_inspection(1, today, "Outstanding", is_current=True),
            create_mock_inspection(1, four_years_ago, "Inadequate"),
        ]

        result = calculate_trajectory(history)

        assert result["trajectory"] == "improving"
        assert result["current_rating"] == "Outstanding"
        assert result["previous_rating"] == "Inadequate"

    def test_inspection_age_calculation_accuracy(self):
        """Test precise age calculation in years."""
        today = datetime.date.today()
        eighteen_months_ago = today - datetime.timedelta(days=int(1.5 * 365))

        history = [
            create_mock_inspection(1, eighteen_months_ago, "Good", is_current=True),
        ]

        result = calculate_trajectory(history)

        # Should be approximately 1.5 years
        assert result["inspection_age_years"] == pytest.approx(1.5, abs=0.1)
        assert result["is_stale"] is False

    def test_edge_case_current_inspection_today(self):
        """Current inspection should show 0.0 years age."""
        today = datetime.date.today()

        history = [
            create_mock_inspection(1, today, "Outstanding", is_current=True),
        ]

        result = calculate_trajectory(history)

        assert result["inspection_age_years"] == 0.0
        assert result["is_stale"] is False

    def test_invalid_rating_returns_unknown(self):
        """Unknown ratings should result in unknown trajectory."""
        today = datetime.date.today()
        four_years_ago = today - datetime.timedelta(days=4 * 365)

        history = [
            create_mock_inspection(1, today, "Unknown Rating", is_current=True),
            create_mock_inspection(1, four_years_ago, "Good"),
        ]

        result = calculate_trajectory(history)

        # Can't determine trajectory with invalid rating
        assert result["trajectory"] == "unknown"
        assert result["current_rating"] == "Unknown Rating"
        assert result["previous_rating"] == "Good"

    def test_case_sensitive_rating_comparison(self):
        """Ratings must match exact casing."""
        today = datetime.date.today()
        four_years_ago = today - datetime.timedelta(days=4 * 365)

        history = [
            create_mock_inspection(1, today, "good", is_current=True),  # lowercase
            create_mock_inspection(1, four_years_ago, "Good"),
        ]

        result = calculate_trajectory(history)

        # lowercase "good" not in rating_order, so trajectory is unknown
        assert result["trajectory"] == "unknown"

    def test_all_ratings_in_order(self):
        """Test each adjacent rating pair."""
        today = datetime.date.today()
        past = today - datetime.timedelta(days=3 * 365)

        # Outstanding → Good (declining)
        result1 = calculate_trajectory(
            [
                create_mock_inspection(1, today, "Good"),
                create_mock_inspection(1, past, "Outstanding"),
            ]
        )
        assert result1["trajectory"] == "declining"

        # Good → Requires Improvement (declining)
        result2 = calculate_trajectory(
            [
                create_mock_inspection(1, today, "Requires Improvement"),
                create_mock_inspection(1, past, "Good"),
            ]
        )
        assert result2["trajectory"] == "declining"

        # Requires Improvement → Inadequate (declining)
        result3 = calculate_trajectory(
            [
                create_mock_inspection(1, today, "Inadequate"),
                create_mock_inspection(1, past, "Requires Improvement"),
            ]
        )
        assert result3["trajectory"] == "declining"
