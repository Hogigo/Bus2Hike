#!/usr/bin/env python3
"""
Script to import hiking trails from OpenDataHub into PostgreSQL database.
Extracts trail information including names, coordinates, distance, and elevation.
"""

import requests
import json
import sys
from typing import Dict, List, Optional, Tuple
from geopy.distance import geodesic
import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv
from pydantic import TypeAdapter, ValidationError

# Load environment variables
load_dotenv()


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


class TrailProcessor:
    """Process trail data including distance and elevation calculations"""

    @staticmethod
    def calculate_distance(coordinates: List[Tuple[float, float]]) -> float:
        """
        Calculate total distance of trail path using geodesic distance

        Args:
            coordinates: List of [longitude, latitude] pairs

        Returns:
            Total distance in kilometers
        """
        coordinates_data_schema = TypeAdapter(List[Tuple[float, float]])
        try:
            valid_data = coordinates_data_schema.validate_python(coordinates)
        except ValidationError as e:
            print(f"calculate distance validation failed: {e}")
            return 0.0
        if len(coordinates) < 2:
            return 0.0

        total_distance = 0.0

        for i in range(len(coordinates) - 1):
            # coordinates are [lon, lat], geodesic expects (lat, lon)
            point1 = (coordinates[i][1], coordinates[i][0])
            point2 = (coordinates[i + 1][1], coordinates[i + 1][0])

            # Calculate distance in meters and add to total
            distance = geodesic(point1, point2).meters
            total_distance += distance

        # Return in kilometers
        return total_distance / 1000.0

    @staticmethod
    def calculate_elevation_stats(
        coordinates: List[List[float]],
    ) -> Tuple[float, float, float, float]:
        """
        PROBLEM: We don't have elevation data!
        Calculate elevation statistics from coordinates

        Args:
            coordinates: List of [longitude, latitude, elevation] tuples

        Returns:
            Tuple of (min_elevation, max_elevation, total_gain, total_loss) in meters
        """
        if not coordinates or len(coordinates[0]) < 3:
            return 0.0, 0.0, 0.0, 0.0

        elevations = [coord[2] for coord in coordinates if len(coord) >= 3]

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
    def extract_names(route_data: Dict) -> Dict[str, Optional[str]]:
        """
        Extract trail names in different languages

        Args:
            route_data: Route data from API

        Returns:
            Dict with keys: name, name_de, name_it, name_en
        """
        # Try to get Detail object with localized names
        detail = route_data.get("Detail", {})

        names = {
            "name": detail.get("Title", route_data.get("Shortname", "Unknown Trail")),
            "name_de": detail.get("de", {}).get("Title"),
            "name_it": detail.get("it", {}).get("Title"),
            "name_en": detail.get("en", {}).get("Title"),
        }

        # Fallback to Shortname if no Detail title
        if names["name"] == "Unknown Trail" and "Shortname" in route_data:
            names["name"] = route_data["Shortname"]

        return names

    @staticmethod
    def extract_metadata(route_data: Dict) -> Dict:
        """
        Extract additional trail metadata

        Args:
            route_data: Route data from API

        Returns:
            Dict with difficulty, duration, description, etc.
        """
        detail = route_data.get("Detail", {})

        # Try to extract difficulty
        difficulty_map = {
            "1": "easy",
            "2": "intermediate",
            "3": "difficult",
            "easy": "easy",
            "intermediate": "intermediate",
            "difficult": "difficult",
        }

        difficulty_raw = route_data.get("Difficulty")
        difficulty = (
            difficulty_map.get(str(difficulty_raw), None) if difficulty_raw else None
        )

        # Extract descriptions
        description = None
        if detail:
            # Try different language descriptions
            for lang in ["en", "de", "it"]:
                if lang in detail and "BaseText" in detail[lang]:
                    description = detail[lang]["BaseText"]
                    break

        # Check if trail is circular
        is_circular = route_data.get("IsCircular", False)

        return {
            "difficulty": difficulty,
            "description": description,
            "circular": is_circular,
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
    processor = TrailProcessor()
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

            # Extract metadata
            metadata = processor.extract_metadata(route)

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
                "coordinates": coordinates,
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


def test():
    """
    Test execution function
    No database involved
    """

    print("=" * 60)
    print("OpenDataHub Hiking Trails Test Import Script")
    print("=" * 60)

    # Initialize components
    client = OpenDataHubClient()
    processor = TrailProcessor()

    try:
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
            # min_elev, max_elev, elev_gain, elev_loss = (
            #     processor.calculate_elevation_stats(coordinates)
            # )
            # print(f"  Elevation: {min_elev:.0f}m - {max_elev:.0f}m")
            # print(f"  Gain: {elev_gain:.0f}m, Loss: {elev_loss:.0f}m")

            # Extract metadata
            metadata = processor.extract_metadata(route)

            # Estimate duration if not provided (using simple heuristic)
            # Naismith's rule: 5 km/h + 1 hour per 600m gain
            # duration_hours = (distance_km / 5.0) + (elev_gain / 600.0)
            # duration_minutes = int(duration_hours * 60)

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
    test()
