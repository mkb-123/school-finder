"""Tests for the Haversine distance function in src.services.catchment."""

from __future__ import annotations

from src.services.catchment import haversine_distance

# ---------------------------------------------------------------------------
# Known reference distances
# ---------------------------------------------------------------------------


class TestHaversineKnownDistances:
    """Verify the haversine formula against well-known reference pairs."""

    def test_london_to_milton_keynes(self):
        """London (51.5074, -0.1278) to Milton Keynes (52.0406, -0.7594) is approx 72 km."""
        distance = haversine_distance(51.5074, -0.1278, 52.0406, -0.7594)
        assert 70 <= distance <= 74, f"Expected ~72 km, got {distance:.2f} km"

    def test_same_point_returns_zero(self):
        """Distance from a point to itself must be exactly 0."""
        assert haversine_distance(52.0406, -0.7594, 52.0406, -0.7594) == 0.0

    def test_antipodal_points(self):
        """North Pole to South Pole is half the Earth's circumference (~20 015 km)."""
        distance = haversine_distance(90.0, 0.0, -90.0, 0.0)
        assert 20_000 <= distance <= 20_050, f"Expected ~20015 km, got {distance:.2f} km"

    def test_equator_quarter_circumference(self):
        """Two points on the equator separated by 90 degrees of longitude (~10 008 km)."""
        distance = haversine_distance(0.0, 0.0, 0.0, 90.0)
        assert 10_000 <= distance <= 10_020, f"Expected ~10008 km, got {distance:.2f} km"


# ---------------------------------------------------------------------------
# Milton Keynes postcode pairs
# ---------------------------------------------------------------------------


class TestHaversineMKPostcodes:
    """Verify approximate distances between Milton Keynes postcode locations."""

    def test_central_mk_to_bletchley(self):
        """MK9 (Central MK, 52.0406, -0.7594) to MK3 (Bletchley, 52.0010, -0.7320) is ~5 km."""
        distance = haversine_distance(52.0406, -0.7594, 52.0010, -0.7320)
        assert 3.0 <= distance <= 6.0, f"Expected ~5 km, got {distance:.2f} km"

    def test_central_mk_to_newport_pagnell(self):
        """MK9 (Central MK) to MK16 (Newport Pagnell, 52.0870, -0.7230) is ~6 km."""
        distance = haversine_distance(52.0406, -0.7594, 52.0870, -0.7230)
        assert 4.0 <= distance <= 8.0, f"Expected ~6 km, got {distance:.2f} km"

    def test_bletchley_to_newport_pagnell(self):
        """MK3 (Bletchley) to MK16 (Newport Pagnell) is ~10 km."""
        distance = haversine_distance(52.0010, -0.7320, 52.0870, -0.7230)
        assert 8.0 <= distance <= 12.0, f"Expected ~10 km, got {distance:.2f} km"

    def test_wolverton_to_woburn_sands(self):
        """MK12 (Wolverton, 52.0640, -0.8090) to MK17 (Woburn Sands, 52.0020, -0.6530) is ~12 km."""
        distance = haversine_distance(52.0640, -0.8090, 52.0020, -0.6530)
        assert 10.0 <= distance <= 14.0, f"Expected ~12 km, got {distance:.2f} km"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestHaversineEdgeCases:
    """Edge cases and symmetry properties of the haversine formula."""

    def test_symmetry(self):
        """haversine(A, B) == haversine(B, A)."""
        d1 = haversine_distance(51.5074, -0.1278, 52.0406, -0.7594)
        d2 = haversine_distance(52.0406, -0.7594, 51.5074, -0.1278)
        assert d1 == d2

    def test_crossing_prime_meridian(self):
        """Distance across the Prime Meridian (London to Paris) is ~340 km."""
        distance = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)
        assert 330 <= distance <= 350, f"Expected ~340 km, got {distance:.2f} km"

    def test_very_short_distance(self):
        """Two points just metres apart should produce a very small positive distance."""
        # ~100m apart (roughly 0.001 degrees of latitude at MK)
        distance = haversine_distance(52.0406, -0.7594, 52.0416, -0.7594)
        assert 0.05 <= distance <= 0.2, f"Expected ~0.11 km, got {distance:.4f} km"
