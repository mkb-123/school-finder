"""Tests for extended decision support weighting sliders."""

from __future__ import annotations

from src.services.decision import (
    SchoolData,
    WeightedScorer,
    _normalise_attendance,
    _normalise_class_size,
    _normalise_diversity,
    _normalise_holiday_club,
    _normalise_homework,
    _normalise_ofsted_trajectory,
    _normalise_parking,
    _normalise_school_run_ease,
    _normalise_sibling_priority,
    _normalise_uniform,
)


class TestExtendedNormalisationFunctions:
    """Test the new normalisation functions for extended metrics."""

    def test_normalise_ofsted_trajectory(self):
        """Test Ofsted trajectory normalisation."""
        assert _normalise_ofsted_trajectory("improving") == 100.0
        assert _normalise_ofsted_trajectory("stable") == 75.0
        assert _normalise_ofsted_trajectory("declining") == 25.0
        assert _normalise_ofsted_trajectory("new") == 50.0
        assert _normalise_ofsted_trajectory(None) == 50.0
        assert _normalise_ofsted_trajectory("unknown") == 50.0

    def test_normalise_attendance(self):
        """Test attendance rate normalisation."""
        assert _normalise_attendance(100.0) == 100.0
        assert _normalise_attendance(95.0) == 95.0
        assert _normalise_attendance(0.0) == 0.0
        assert _normalise_attendance(None) == 50.0
        # Clamping
        assert _normalise_attendance(150.0) == 100.0
        assert _normalise_attendance(-10.0) == 0.0

    def test_normalise_class_size(self):
        """Test class size normalisation (smaller is better)."""
        assert _normalise_class_size(0.0) == 100.0  # Smallest possible
        assert _normalise_class_size(35.0) == 0.0  # MAX_CLASS_SIZE
        assert _normalise_class_size(17.5) == 50.0  # Midpoint
        assert _normalise_class_size(None) == 50.0
        # Clamping
        assert _normalise_class_size(50.0) == 0.0  # Above max

    def test_normalise_parking(self):
        """Test parking chaos normalisation (lower chaos is better)."""
        assert _normalise_parking(1.0) == 100.0  # Best (least chaos)
        assert _normalise_parking(5.0) == 0.0  # Worst (most chaos)
        assert _normalise_parking(3.0) == 50.0  # Midpoint
        assert _normalise_parking(None) == 50.0

    def test_normalise_holiday_club(self):
        """Test holiday club availability normalisation."""
        assert _normalise_holiday_club(True) == 100.0
        assert _normalise_holiday_club(False) == 0.0

    def test_normalise_uniform(self):
        """Test uniform cost normalisation (cheaper is better)."""
        assert _normalise_uniform(0.0) == 100.0  # Free
        assert _normalise_uniform(500.0) == 0.0  # MAX_UNIFORM_COST
        assert _normalise_uniform(250.0) == 50.0  # Midpoint
        assert _normalise_uniform(None) == 50.0
        # Clamping
        assert _normalise_uniform(1000.0) == 0.0

    def test_normalise_diversity(self):
        """Test diversity score normalisation."""
        assert _normalise_diversity(100.0) == 100.0
        assert _normalise_diversity(50.0) == 50.0
        assert _normalise_diversity(0.0) == 0.0
        assert _normalise_diversity(None) == 50.0
        # Clamping
        assert _normalise_diversity(150.0) == 100.0
        assert _normalise_diversity(-10.0) == 0.0

    def test_normalise_sibling_priority(self):
        """Test sibling priority strength normalisation."""
        assert _normalise_sibling_priority(100.0) == 100.0
        assert _normalise_sibling_priority(50.0) == 50.0
        assert _normalise_sibling_priority(0.0) == 0.0
        assert _normalise_sibling_priority(None) == 50.0

    def test_normalise_school_run_ease(self):
        """Test school run ease score normalisation."""
        assert _normalise_school_run_ease(100.0) == 100.0
        assert _normalise_school_run_ease(50.0) == 50.0
        assert _normalise_school_run_ease(0.0) == 0.0
        assert _normalise_school_run_ease(None) == 50.0

    def test_normalise_homework(self):
        """Test homework hours normalisation (less is better)."""
        assert _normalise_homework(0.0) == 100.0  # No homework
        assert _normalise_homework(3.0) == 0.0  # MAX_HOMEWORK_HOURS
        assert _normalise_homework(1.5) == 50.0  # Midpoint
        assert _normalise_homework(None) == 50.0


class TestExtendedWeightedScorer:
    """Test the WeightedScorer with extended dimensions."""

    def test_scorer_includes_all_dimensions(self):
        """Test that scorer handles all 14 dimensions."""
        weights = {
            "distance": 1.0,
            "ofsted": 1.0,
            "clubs": 1.0,
            "fees": 1.0,
            "ofsted_trajectory": 1.0,
            "attendance": 1.0,
            "class_size": 1.0,
            "parking": 1.0,
            "holiday_club": 1.0,
            "uniform": 1.0,
            "diversity": 1.0,
            "sibling_priority": 1.0,
            "school_run_ease": 1.0,
            "homework": 1.0,
        }
        scorer = WeightedScorer(weights)
        assert len(scorer.weights) == 14
        # All weights should be equal after normalisation
        assert all(abs(v - 1.0 / 14) < 0.001 for v in scorer.weights.values())

    def test_scorer_with_extended_school_data(self):
        """Test scoring with extended school data."""
        school = SchoolData(
            id=1,
            name="Test School",
            ofsted_rating="Good",
            distance_km=2.0,
            is_private=False,
            has_breakfast_club=True,
            has_afterschool_club=True,
            ofsted_trajectory="improving",
            attendance_rate=96.0,
            avg_class_size=25.0,
            parking_chaos_score=2.0,
            has_holiday_club=True,
            uniform_cost=200.0,
            diversity_score=70.0,
            sibling_priority_strength=80.0,
            school_run_ease_score=75.0,
            homework_hours_per_day=1.0,
        )

        scorer = WeightedScorer()
        scored = scorer.score_school(school)

        assert scored.school == school
        assert scored.composite_score > 0
        assert "distance" in scored.component_scores
        assert "ofsted_trajectory" in scored.component_scores
        assert "attendance" in scored.component_scores
        assert "parking" in scored.component_scores

    def test_scorer_prioritises_high_weight_dimensions(self):
        """Test that higher weights influence composite score more."""
        school = SchoolData(
            id=1,
            name="Test School",
            ofsted_rating="Good",
            distance_km=5.0,  # Mid-range distance
            attendance_rate=98.0,  # Excellent attendance
            avg_class_size=20.0,  # Small classes
        )

        # Weight attendance heavily
        weights_attendance = {
            "distance": 0.0,
            "ofsted": 0.0,
            "clubs": 0.0,
            "fees": 0.0,
            "attendance": 1.0,
            "class_size": 0.0,
        }

        # Weight class size heavily
        weights_class_size = {
            "distance": 0.0,
            "ofsted": 0.0,
            "clubs": 0.0,
            "fees": 0.0,
            "attendance": 0.0,
            "class_size": 1.0,
        }

        scorer_attendance = WeightedScorer(weights_attendance)
        scorer_class_size = WeightedScorer(weights_class_size)

        score_attendance = scorer_attendance.score_school(school)
        score_class_size = scorer_class_size.score_school(school)

        # Both should score highly, but with different emphasis
        assert score_attendance.composite_score > 90.0  # Excellent attendance drives score
        assert score_class_size.composite_score > 40.0  # Good class size drives score

    def test_unknown_dimensions_ignored(self):
        """Test that unknown dimension keys are ignored."""
        weights = {
            "distance": 1.0,
            "unknown_dimension": 100.0,  # Should be ignored
            "another_fake": 50.0,  # Should be ignored
        }
        scorer = WeightedScorer(weights)
        # Only 14 known dimensions should be present
        assert len(scorer.weights) == 14
        # Distance should get all the weight (normalised)
        assert scorer.weights["distance"] > 0.9


class TestExtendedSchoolRanking:
    """Test school ranking with extended dimensions."""

    def test_rank_schools_by_parking(self):
        """Test ranking schools by parking ease."""
        school_a = SchoolData(
            id=1,
            name="School A",
            parking_chaos_score=1.5,  # Easy parking
        )
        school_b = SchoolData(
            id=2,
            name="School B",
            parking_chaos_score=4.5,  # Chaotic parking
        )

        weights = {
            "distance": 0.0,
            "ofsted": 0.0,
            "clubs": 0.0,
            "fees": 0.0,
            "parking": 1.0,
        }

        scorer = WeightedScorer(weights)
        ranked = scorer.rank_schools([school_a, school_b])

        assert len(ranked) == 2
        assert ranked[0].school.id == 1  # School A ranks higher (easier parking)
        assert ranked[1].school.id == 2  # School B ranks lower

    def test_rank_schools_by_uniform_cost(self):
        """Test ranking schools by uniform affordability."""
        school_a = SchoolData(
            id=1,
            name="School A",
            uniform_cost=400.0,  # Expensive uniform
        )
        school_b = SchoolData(
            id=2,
            name="School B",
            uniform_cost=100.0,  # Affordable uniform
        )

        weights = {
            "distance": 0.0,
            "ofsted": 0.0,
            "clubs": 0.0,
            "fees": 0.0,
            "uniform": 1.0,
        }

        scorer = WeightedScorer(weights)
        ranked = scorer.rank_schools([school_a, school_b])

        assert len(ranked) == 2
        assert ranked[0].school.id == 2  # School B ranks higher (cheaper uniform)
        assert ranked[1].school.id == 1  # School A ranks lower
