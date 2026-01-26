#!/usr/bin/env python3
"""
Script to import hiking trails from OpenDataHub into PostgreSQL database.
Extracts trail information including names, coordinates, distance, and elevation.
"""
import logging

import requests
import json
import sys
from typing import Dict, List, Optional, Tuple, Annotated
from enum import Enum
from geopy.distance import geodesic
import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv
from pydantic import TypeAdapter, Field, ValidationError
from pathlib import Path

# Load environment variables
load_dotenv()

# Coordinate can have also altitude value
Coordinate = Annotated[List[float], Field(min_length=2)]
CoordinateListValidator = TypeAdapter(List[Coordinate])

class OpenDataHubClient:
    """Client for fetching hiking trails from OpenDataHub API"""

    def __init__(self, base_url: str = "https://tourism.opendatahub.com/v1/"):
        self.base_url = base_url.rstrip("/")

    def get_geoshapes(
        self, page_size: int = 100, route_type: str = "hikingtrails"
    ) -> Dict:
        """
        Fetch hiking trail GeoShapes from OpenDataHub

        Args:
            page_size: Number of items per page
            route_type: Type of routes to fetch (default: hikingtrails)

        Returns:
            Dict containing API response with trail data
        """
        endpoint = f"{self.base_url}/GeoShape"
        params = {
            "removenullvalues": "true",
            "pagesize": str(page_size),
            "type": route_type,
        }

        print(f"Fetching trails from: {endpoint}")
        print(f"Parameters: {params}")

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from OpenDataHub: {e}")
            raise


class ElevationService:
    """Service for fetching elevation data from coordinates"""

    def __init__(self, base_url: str = "https://api.open-elevation.com/api/v1"):
        self.base_url = base_url
        self.elevation_cache = {}  # Simple in-memory cache
        self._is_latitude_first = True

    def set_latitude_first(self):
        logging.log(logging.INFO, "Setting latitude first for coordinates in ElevationService instance")
        self._is_latitude_first = True

    def set_longitude_first(self):
        logging.log(logging.INFO, "Setting longitude first for coordinates in ElevationService instance")
        self._is_latitude_first = False

    def get_elevation_for_coordinates(self, coordinates: List[List[float]]) -> List[float]:
        """
        Get elevation data for a list of coordinates
        
        Args:
            coordinates: List of [latitude, longitude] pairs
            
        Returns:
            List of elevation values in meters
        """
        try:
            # This ensures it's a list of lists, and each inner list has at least 2 items
            validated_coords = CoordinateListValidator.validate_python(coordinates)
        except ValidationError as e:
            print(f"Invalid input data: {e}")
            # raise ValueError("Input must be a List of [latitude, longitude] pairs.")
            return []

        if not validated_coords:
            return []

        # Check cache first
        cache_key = tuple(tuple(coord) for coord in validated_coords)
        if cache_key in self.elevation_cache:
            return self.elevation_cache[cache_key]
        
        try:
            # Prepare data for Open-Elevation API
            # The API expects {"locations": [{"latitude": lat, "longitude": lon}, ...]}
            if self._is_latitude_first:
                locations = [
                    {"latitude": coord[0], "longitude": coord[1]}
                    for coord in validated_coords
                ]
            else:
                locations = [
                    {"latitude": coord[1], "longitude": coord[0]}
                    for coord in validated_coords
                ]
            
            payload = {"locations": locations}
            
            print(f"Fetching elevation data for {len(validated_coords)} points...")
            response = requests.post(
                f"{self.base_url}/lookup", 
                json=payload, 
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            elevations = []
            
            for location_result in result.get("results", []):
                elevation = location_result.get("elevation", 0.0)
                elevations.append(elevation)
            
            # Cache the result
            self.elevation_cache[cache_key] = elevations
            
            return elevations
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching elevation data: {e}")
            # Return zeros as fallback
            return [0.0] * len(coordinates)



class TrailDifficulty(Enum):
    EASY = "Easy"
    MODERATE = "Moderate"
    HARD = "Hard"
    VERY_HARD = "Very Hard"
    EXTREME = "Extreme"

class TrailProcessor:
    """
    Process trail data including distance and elevation calculations
    Latitude as first coordinate is expected, use set_longitude_first to invert this
    """

    def __init__(self, elevation_service: Optional[ElevationService] = None):
        self._elevation_service = elevation_service or ElevationService()
        self._is_latitude_first = True

    def set_latitude_first(self):
        logging.log(logging.INFO, "Setting latitude first for coordinates in TrailProcessor instance")
        self._is_latitude_first = True
        self._elevation_service.set_latitude_first()

    def set_longitude_first(self):
        logging.log(logging.INFO, "Setting longitude first for coordinates in TrailProcessor instance")
        self._is_latitude_first = False
        self._elevation_service.set_longitude_first()

    def validate_coordinates_format(self, coordinates: List[List[float]]) -> bool:
        """
        Checks if the coordinates data format is valid, otherwise returns False
        """
        try:
            # This ensures it's a list of lists, and each inner list has at least 2 items
            validated_coords = CoordinateListValidator.validate_python(coordinates)
        except ValidationError as e:
            print(f"calculate distance validation failed: {e}")
            return False
        return True

    def calculate_distance(self, coordinates: List[List[float]]) -> float:
        """
        Calculate total distance of trail path using geodesic distance

        Args:
            coordinates: List of [latitude, longitude] pairs, supports also other data if index > 1

        Returns:
            Total distance in kilometers
        """
        try:
            # This ensures it's a list of lists, and each inner list has at least 2 items
            validated_coords = CoordinateListValidator.validate_python(coordinates)
        except ValidationError as e:
            print(f"calculate distance validation failed: {e}")
            return 0.0


        if len(validated_coords) < 2:
            return 0.0

        total_distance = 0.0

        for i in range(len(validated_coords) - 1):
            coord1 = validated_coords[i][:2]
            coord2 = validated_coords[i+1][:2]
            # Calculate distance in meters and add to total (geodsic expects (lat, lon))
            if not self._is_latitude_first:
                distance = geodesic(coord1, coord2).meters
            else:
                # (lon, lat) case
                distance = geodesic(coord1[::-1], coord2[::-1]).meters
            total_distance += distance

        # Return in kilometers
        return total_distance / 1000.0

    def calculate_elevation_stats(
        self, coordinates: List[List[float]]
    ) -> Tuple[float, float, float, float]:
        """
        Calculate elevation statistics from coordinates by fetching elevation data

        Args:
            coordinates: List of [latitude, longitude] pairs
            coordinates: List of [latitude, longitude, altitude]

        Returns:
            Tuple of (min_elevation, max_elevation, total_gain, total_loss) in meters
        """
        if not coordinates or len(coordinates) < 2:
            return 0.0, 0.0, 0.0, 0.0

        # check if elevation already given in input
        if len(coordinates[0]) > 2:
           elevations = [coordinate[2] for coordinate in coordinates]
        # Get elevation data for all coordinates
        else:
            elevations = self._elevation_service.get_elevation_for_coordinates(coordinates)

        if not elevations:
            return 0.0, 0.0, 0.0, 0.0

        min_elev = min(elevations)
        max_elev = max(elevations)

        # Calculate cumulative gain and loss
        total_gain = 0.0
        total_loss = 0.0

        for i in range(len(elevations) - 1):
            diff = elevations[i + 1] - elevations[i]
            if diff > 0:
                total_gain += diff
            else:
                total_loss += abs(diff)

        return min_elev, max_elev, total_gain, total_loss

    @staticmethod
    def extract_id(route_data: Dict) -> Optional[str]:
        """
        Extract trail ID
        Args:
            route_data: Route data from API

        Returns:
            Id as string
        """
        id_ = route_data.get("Id", None)
        if id_:
            id_ = id_.rsplit('.',1)[-1]
        return id_

    def is_circular(
            self, coordinates: List[List[float]]
    ) -> bool:
        """
        Returns true if a trail is circular
        """
        try:
            # This ensures it's a list of lists, and each inner list has at least 2 items
            validated_coords = CoordinateListValidator.validate_python(coordinates)
        except ValidationError as e:
            print(f"is_circuler validation failed: {e}")
            return False

        if len(validated_coords) < 2:
            return False

        first_coord= validated_coords[0][:2]
        last_coord = validated_coords[-1][:2]
        # Calculate distance in meters and add to total (geodsic expects (lat, lon))
        if not self._is_latitude_first:
            distance = geodesic(first_coord, last_coord).meters
        else:
            # (lon, lat) case
            distance = geodesic(first_coord[::-1], last_coord[::-1]).meters

        if distance < 100:
            return True
        return False

    def create_coordinates_with_elevation(
        self, coordinates: List[List[float]]
    ) -> List[List[float]]:
        """
        Create 3D coordinates by adding elevation data to 2D coordinates

        Args:
            coordinates: List of [latitude, longitude] pairs
            
        Returns:
            List of [latitude, longitude, elevation] tuples
            if longitude is the first argument, the function will return [longitude, latitude, elevation] tuples
        """
        if not coordinates:
            return []
            
        elevations = self._elevation_service.get_elevation_for_coordinates(coordinates)
        
        # Combine coordinates with elevation data
        coords_3d = []
        for i, coord in enumerate(coordinates):
            if i < len(elevations):
                coords_3d.append([coord[0], coord[1], elevations[i]])
            else:
                # Fallback if elevation data is missing
                coords_3d.append([coord[0], coord[1], 0.0])
        
        return coords_3d


    @staticmethod
    def estimate_trail_difficulty(
            distance_km: float,
            elevation_gain_m: float,
            max_elevation_m: float,
            duration_hours: float,
            is_circular: bool
    ) -> Dict[str, any]:
        """
        Estimate hiking trail difficulty based on multiple factors.

        Args:
            distance_km: Total trail distance in kilometers
            elevation_gain_m: Total elevation gain in meters
            max_elevation_m: Maximum elevation point
            duration_hours: Estimated duration in hours
            is_circular: Whether the trail is circular/loop

        Returns:
            Dictionary with difficulty rating, score, and breakdown
        """
        score = 0
        breakdown = {}

        # 1. Distance factor (0-30 points)
        if distance_km < 5:
            distance_points = distance_km * 2
        elif distance_km < 15:
            distance_points = 10 + (distance_km - 5) * 1.5
        elif distance_km < 30:
            distance_points = 25 + (distance_km - 15) * 0.3
        else:
            distance_points = 30

        score += distance_points
        breakdown['distance'] = round(distance_points, 1)

        # 2. Elevation gain factor (0-35 points)
        if elevation_gain_m < 200:
            gain_points = elevation_gain_m * 0.05
        elif elevation_gain_m < 800:
            gain_points = 10 + (elevation_gain_m - 200) * 0.025
        elif elevation_gain_m < 1500:
            gain_points = 25 + (elevation_gain_m - 800) * 0.014
        else:
            gain_points = 35

        score += gain_points
        breakdown['elevation_gain'] = round(gain_points, 1)

        # 3. Steepness factor (0-20 points)
        # Calculate average steepness (gain per km)
        if distance_km > 0:
            avg_steepness = elevation_gain_m / distance_km
            if avg_steepness < 50:
                steepness_points = avg_steepness * 0.1
            elif avg_steepness < 150:
                steepness_points = 5 + (avg_steepness - 50) * 0.1
            else:
                steepness_points = min(20, 15 + (avg_steepness - 150) * 0.05)
        else:
            steepness_points = 0

        score += steepness_points
        breakdown['steepness'] = round(steepness_points, 1)

        # 4. Maximum elevation factor (0-10 points)
        # High altitude can make trails more challenging
        if max_elevation_m < 1000:
            altitude_points = 0
        elif max_elevation_m < 2000:
            altitude_points = (max_elevation_m - 1000) * 0.003
        elif max_elevation_m < 3000:
            altitude_points = 3 + (max_elevation_m - 2000) * 0.005
        else:
            altitude_points = min(10, 8 + (max_elevation_m - 3000) * 0.002)

        score += altitude_points
        breakdown['altitude'] = round(altitude_points, 1)

        # 5. Duration factor (0-5 points)
        # Very long trails add fatigue factor
        if duration_hours > 8:
            duration_points = min(5, (duration_hours - 8) * 0.5)
        else:
            duration_points = 0

        score += duration_points
        breakdown['duration'] = round(duration_points, 1)

        # 6. Circular trail bonus/penalty (±2 points)
        # Circular trails are slightly easier (no need to return same way)
        if is_circular:
            circular_points = -2
        else:
            circular_points = 2

        score += circular_points
        breakdown['trail_type'] = circular_points

        # Determine difficulty level based on total score (0-100)
        if score < 20:
            difficulty = TrailDifficulty.EASY
        elif score < 40:
            difficulty = TrailDifficulty.MODERATE
        elif score < 60:
            difficulty = TrailDifficulty.HARD
        elif score < 80:
            difficulty = TrailDifficulty.VERY_HARD
        else:
            difficulty = TrailDifficulty.EXTREME

        return {
            'difficulty': difficulty.value,
            'score': round(score, 1),
            'max_score': 100,
            'breakdown': breakdown,
        }

class DatabaseImporter:
    """Handle database operations for importing trails"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.connection = None

    def connect(self):
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(self.db_url)
            print("Connected to database successfully")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("Database connection closed")

    def clear_trails(self):
        """Clear existing trails from database"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM hiking_trails")
            self.connection.commit()
            print("Cleared existing trails from database")
        except Exception as e:
            print(f"Error clearing trails: {e}")
            self.connection.rollback()
            raise

    def insert_trail(self, trail_data: Dict):
        """
        Insert a single trail into database

        Args:
            trail_data: Dictionary containing trail information
        """
        try:
            cursor = self.connection.cursor()

            # Convert coordinates list to LineString WKT
            coords_wkt = self._coordinates_to_linestring(trail_data["coordinates"])

            # Get start and end points
            start_point = trail_data["coordinates"][0]
            end_point = trail_data["coordinates"][-1]

            query = """
                INSERT INTO hiking_trails (
                    odh_id, name, name_de, name_it, name_en,
                    difficulty, length_km, duration_minutes,
                    elevation_gain_m, elevation_loss_m, description,
                    geometry, start_point, end_point, circular
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    ST_GeomFromText(%s, 4326),
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    %s
                )
            """

            values = (
                trail_data["odh_id"],
                trail_data["name"],
                trail_data["name_de"],
                trail_data["name_it"],
                trail_data["name_en"],
                trail_data["difficulty"],
                trail_data["length_km"],
                trail_data["duration_minutes"],
                trail_data["elevation_gain_m"],
                trail_data["elevation_loss_m"],
                trail_data["description"],
                coords_wkt,
                start_point[0],
                start_point[1],  # start point lon, lat
                end_point[0],
                end_point[1],  # end point lon, lat
                trail_data["circular"],
            )

            cursor.execute(query, values)
            self.connection.commit()

        except Exception as e:
            print(f"Error inserting trail {trail_data.get('name', 'unknown')}: {e}")
            self.connection.rollback()
            raise

    @staticmethod
    def _coordinates_to_linestring(coordinates: List[List[float]]) -> str:
        """
        Convert coordinates list to WKT LineString format

        Args:
            coordinates: List of [lon, lat] or [lon, lat, elev] coordinates

        Returns:
            WKT LineString string
        """
        # Format: LINESTRING(lon1 lat1, lon2 lat2, ...)
        coord_pairs = [f"{coord[0]} {coord[1]}" for coord in coordinates]
        return f"LINESTRING({', '.join(coord_pairs)})"


def main():
    """Main execution function"""

    print("=" * 60)
    print("OpenDataHub Hiking Trails Import Script")
    print("=" * 60)

    # Database connection string
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://hikingapp:hikingpass@localhost:5432/hiking_planner",
    )

    # Initialize components
    client = OpenDataHubClient()
    elevation_service = ElevationService()
    processor = TrailProcessor(elevation_service)
    db_importer = DatabaseImporter(db_url)

    try:
        # Connect to database
        db_importer.connect()

        # Optional: clear existing trails
        clear_existing = input("Clear existing trails from database? (y/N): ").lower()
        if clear_existing == "y":
            db_importer.clear_trails()

        # Fetch trails from OpenDataHub
        print("\nFetching trails from OpenDataHub...")
        response = client.get_geoshapes(page_size=100)

        routes = response.get("Items", [])
        print(f"Found {len(routes)} trails")

        # Process each trail
        processed_count = 0
        skipped_count = 0

        for idx, route in enumerate(routes, 1):
            print(f"\n[{idx}/{len(routes)}] Processing trail...")

            # Check SRID (coordinate system)
            srid = route.get("Srid", "")
            if srid != "EPSG:4326":
                print(f"  ⚠ Skipping - unsupported SRID: {srid}")
                skipped_count += 1
                continue

            # Extract basic info
            odh_id = route.get("Id", "")
            if not odh_id:
                print(f"  ⚠ Skipping - no ID found")
                skipped_count += 1
                continue

            print(f"  Trail ID: {odh_id}")

            # Extract names
            names = processor.extract_names(route)
            print(f"  Name: {names['name']}")

            # Extract coordinates
            geometry = route.get("Geometry", {})
            coordinates = geometry.get("coordinates", [])

            if len(coordinates) < 2:
                print(f"  ⚠ Skipping - insufficient coordinates")
                skipped_count += 1
                continue

            # Calculate distance
            distance_km = processor.calculate_distance(coordinates)
            print(f"  Distance: {distance_km:.2f} km")

            # Calculate elevation stats
            min_elev, max_elev, elev_gain, elev_loss = (
                processor.calculate_elevation_stats(coordinates)
            )
            print(f"  Elevation: {min_elev:.0f}m - {max_elev:.0f}m")
            print(f"  Gain: {elev_gain:.0f}m, Loss: {elev_loss:.0f}m")
            
            # Create 3D coordinates with elevation data
            coordinates_3d = processor.create_coordinates_with_elevation(coordinates)

            # Estimate duration if not provided (using simple heuristic)
            # Naismith's rule: 5 km/h + 1 hour per 600m gain
            duration_hours = (distance_km / 5.0) + (elev_gain / 600.0)
            duration_minutes = int(duration_hours * 60)

            # Prepare trail data for database
            trail_data = {
                "odh_id": odh_id,
                "name": names["name"],
                "name_de": names["name_de"],
                "name_it": names["name_it"],
                "name_en": names["name_en"],
                "difficulty": metadata["difficulty"],
                "length_km": round(distance_km, 2),
                "duration_minutes": duration_minutes,
                "elevation_gain_m": int(elev_gain),
                "elevation_loss_m": int(elev_loss),
                "description": metadata["description"],
                "coordinates": coordinates_3d,  # Use 3D coordinates with elevation
                "circular": metadata["circular"],
            }

            # Insert into database
            try:
                db_importer.insert_trail(trail_data)
                print(f"  ✓ Successfully imported")
                processed_count += 1
            except Exception as e:
                print(f"  ✗ Failed to import: {e}")
                skipped_count += 1

        # Summary
        print("\n" + "=" * 60)
        print("Import Summary")
        print("=" * 60)
        print(f"Total trails found: {len(routes)}")
        print(f"Successfully imported: {processed_count}")
        print(f"Skipped: {skipped_count}")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error during import: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        # Close database connection
        db_importer.close()

    print("\n✓ Import completed successfully!")


def dump_to_file(path: Path):
    """
    Test execution function
    No database involved
    """

    print("=" * 60)
    print("OpenDataHub Hiking Trails Test Import Script")
    print("=" * 60)

    # Initialize components
    client = OpenDataHubClient()
    elevation_service = ElevationService()
    processor = TrailProcessor(elevation_service)

    try:
        # Fetch trails from OpenDataHub
        print("\nFetching trails from OpenDataHub...")
        response = client.get_geoshapes(page_size=100)
        print(f"\nWriting to {str(path)}")
        # path.write_text(json.dumps(response, indent=2))

        routes = response.get("Items", [])
        print(f"Found {len(routes)} trails")


        # Process each trail
        processed_count = 0
        skipped_count = 0

        for idx, route in enumerate(routes, 1):
            print(f"\n[{idx}/{len(routes)}] Processing trail...")

            # Check SRID (coordinate system)
            srid = route.get("Srid", "")
            if srid != "EPSG:4326":
                print(f"  ⚠ Skipping - unsupported SRID: {srid}")
                skipped_count += 1
                continue

            # No names to extract in JSON
            # names = processor.extract_names(route)
            # print(f"  Name: {names['name']}")

            id_ = processor.extract_id(route)
            if not id_:
                print(f"  ⚠ Skipping - no ID found")
                skipped_count += 1
                continue

            print(f"  Trail ID: {id_}")

            # Extract coordinates
            geometry = route.get("Geometry", {})
            coordinates = geometry.get("coordinates", [])

            if len(coordinates) < 2:
                print(f"  ⚠ Skipping - insufficient coordinates")
                skipped_count += 1
                continue

            if not processor.validate_coordinates_format(coordinates):
                print(f"  ⚠ Skipping - coordinates format not valid")
                skipped_count += 1
                continue

            # Coordinates in JSON are expressed in [longitude, latitude], we need to specify this to the processor
            processor.set_longitude_first()

            coordinates_3d = processor.create_coordinates_with_elevation(coordinates)

            # Calculate distance
            distance_km = processor.calculate_distance(coordinates_3d)
            print(f"  Distance: {distance_km:.2f} km")

            # Calculate elevation stats
            min_elev, max_elev, elev_gain, elev_loss = (
                processor.calculate_elevation_stats(coordinates_3d)
            )
            print(f"  Elevation Min: {min_elev:.0f}m Max: {max_elev:.0f}m")
            print(f"  Gain: {elev_gain:.0f}m, Loss: {elev_loss:.0f}m")

            # Estimate duration if not provided (using simple heuristic)
            # Naismith's rule: 5 km/h + 1 hour per 600m gain
            duration_hours = (distance_km / 5.0) + (elev_gain / 600.0)
            duration_minutes = int(duration_hours * 60)
            print(f"Extimate duration: {duration_hours}h")

            is_circular = processor.is_circular(coordinates_3d)
            print(f"Is circular: {"yes" if is_circular else "no"}")

            difficulty_data = processor.estimate_trail_difficulty(distance_km, elev_gain, max_elev, duration_hours, is_circular)

            print(f"difficulty: {difficulty_data.get("difficulty")} ")
            print(f"score: {difficulty_data.get("score")}/{difficulty_data.get("max_score")}")
            # Prepare trail data for database
            #             trail_data = {
            #                 "odh_id": odh_id,
            #                 "name": names["name"],
            #                 "name_de": names["name_de"],
            #                 "name_it": names["name_it"],
            #                 "name_en": names["name_en"],
            #                 "difficulty": metadata["difficulty"],
            #                 "length_km": round(distance_km, 2),
            #                 "duration_minutes": duration_minutes,
            #                 "elevation_gain_m": int(elev_gain),
            #                 "elevation_loss_m": int(elev_loss),
            #                 "description": metadata["description"],
            #                 "coordinates": coordinates,
            #                 "circular": metadata["circular"],
            #             }

        # Summary
        print("\n" + "=" * 60)
        print("Import Summary")
        print("=" * 60)
        print(f"Total trails found: {len(routes)}")
        print(f"Successfully imported: {processed_count}")
        print(f"Skipped: {skipped_count}")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error during import: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("\n✓ Import completed successfully!")


if __name__ == "__main__":
    # main()
    output_file=Path("/app/scripts/output/trails.json")
    output_file.parent.mkdir(exist_ok=True, parents=True)
    dump_to_file(output_file)
