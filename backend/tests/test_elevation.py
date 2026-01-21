#!/usr/bin/env python3
"""
Test module for elevation service functionality
"""

import pytest
import sys
from scripts.import_trails import ElevationService


class TestElevationService:
    """Test class for ElevationService"""

    @pytest.fixture
    def elevation_service(self):
        """Fixture to create ElevationService instance"""
        return ElevationService()

    @pytest.fixture
    def test_coordinates(self):
        """Fixture providing test coordinates"""
        # Mount Everest base camp area - should have high elevations
        return [
            [86.9250, 27.9881],  # Mount Everest base camp
            [86.9255, 27.9885],  # Nearby point
            [86.9260, 27.9890],  # Another nearby point
        ]

    def test_elevation_service_initialization(self, elevation_service):
        """Test that ElevationService can be initialized"""
        assert elevation_service is not None
        assert elevation_service.base_url == "https://api.open-elevation.com/api/v1"
        assert hasattr(elevation_service, "elevation_cache")

    def test_elevation_data_fetching(self, elevation_service, test_coordinates):
        """Test that elevation data can be fetched for coordinates"""
        # Test with valid coordinates
        elevations = elevation_service.get_elevation_for_coordinates(test_coordinates)

        # Verify we got elevation data
        assert elevations is not None
        assert len(elevations) == len(test_coordinates)

        # Verify elevations are reasonable (should be positive for Everest area)
        for elevation in elevations:
            assert isinstance(elevation, (int, float))
            # Everest base camp should be above 4000m
            assert elevation > 4000, f"Expected elevation > 4000m, got {elevation}"

    def test_elevation_cache(self, elevation_service, test_coordinates):
        """Test that elevation caching works"""
        # First call
        elevations1 = elevation_service.get_elevation_for_coordinates(test_coordinates)

        # Second call should use cache
        elevations2 = elevation_service.get_elevation_for_coordinates(test_coordinates)

        # Results should be identical
        assert elevations1 == elevations2

        # Cache should not be empty
        assert len(elevation_service.elevation_cache) > 0

    def test_empty_coordinates(self, elevation_service):
        """Test handling of empty coordinates list"""
        elevations = elevation_service.get_elevation_for_coordinates([])
        assert elevations == []

    def test_single_coordinate(self, elevation_service):
        """Test handling of single coordinate"""
        single_coord = [[86.9250, 27.9881]]
        elevations = elevation_service.get_elevation_for_coordinates(single_coord)

        assert len(elevations) == 1
        assert isinstance(elevations[0], (int, float))


def main():
    """Main function for direct execution"""

    # Create and test elevation service
    elevation_service = ElevationService()
    test_coords = [
        [86.9250, 27.9881],  # Mount Everest base camp
        [86.9255, 27.9885],  # Nearby point
        [86.9260, 27.9890],  # Another nearby point
    ]

    print("Testing elevation service with sample coordinates...")
    print(f"Coordinates: {test_coords}")

    try:
        elevations = elevation_service.get_elevation_for_coordinates(test_coords)
        print(f"Elevations: {elevations}")
        print("✓ Elevation service working!")

        # Verify elevations are reasonable
        for i, elevation in enumerate(elevations):
            if elevation > 4000:
                print(
                    f"  Point {i + 1}: {elevation:.1f}m (reasonable for Everest area)"
                )
            else:
                print(f"  ⚠ Point {i + 1}: {elevation:.1f}m (lower than expected)")

        return True
    except Exception as e:
        print(f"✗ Error testing elevation service: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

