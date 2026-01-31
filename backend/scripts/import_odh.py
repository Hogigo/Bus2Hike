#!/usr/bin/env python3
"""
Script to import hiking trails from OpenDataHub into PostgreSQL database.
Extracts trail information including names, coordinates, distance, and elevation.
"""
import logging

import requests
import json
import sys
from typing import Dict, List, Optional, Tuple, Annotated, Iterator
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

class TrailDifficulty(Enum):
    EASY = "Easy"
    MODERATE = "Moderate"
    HARD = "Hard"
    VERY_HARD = "Very Hard"
    EXTREME = "Extreme"


class OpenDataHubClient:
    """Client for fetching hiking trails from OpenDataHub API"""

    def __init__(self, base_url: str = "https://tourism.opendatahub.com/v1/"):
        self.base_url = base_url.rstrip("/")


    def get_geoshapes(
        self, page_size: int = 100, route_type: str = "hikingtrails"
    ) -> Iterator[Dict]:
        """
        Fetch hiking trail GeoShapes from OpenDataHub across all pages
        Args:
            page_size: Number of items per page
            route_type: Type of routes to fetch (default: hikingtrails)
        Yields:
            Dict containing API response with trail data for each page
        """
        endpoint = f"{self.base_url}/GeoShape"
        params = {
            "removenullvalues": "true",
            "pagesize": str(page_size),
            "type": route_type,
        }

        current_page = 1
        total_pages = None

        print(f"Fetching trails from: {endpoint}")
        print(f"Parameters: {params}")

        while True:
            try:
                # Add page number to params
                params["pagenumber"] = str(current_page)

                response = requests.get(endpoint, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Get total pages from first response
                if total_pages is None:
                    total_pages = data.get("TotalPages", 1)
                    print(f"Total pages to fetch: {total_pages}")

                print(f"Fetching page {current_page}/{total_pages}")

                # Yield current page data
                yield data

                # Check if there are more pages
                next_page = data.get("NextPage")
                if next_page is None or current_page >= total_pages:
                    print("All pages fetched successfully")
                    break

                current_page += 1

            except requests.exceptions.RequestException as e:
                print(f"Error fetching data from OpenDataHub (page {current_page}): {e}")
                raise


    def get_transport_stops(self, page_size: int = 100) -> Iterator[Dict]:
        """
        Fetch public transportation stops from OpenDataHub

        Args:
            page_size: Number of items per page
        Yields:
            Dict containing API response with stop data (GTFS)
        """
        # For stops, we use the Activity endpoint
        endpoint = f"{self.base_url}/ODHActivityPoi"

        params = {
            "pagesize": str(page_size),
            "language": "en",
            "source": "gtfsapi",
            "tagfilter": "72861940-e6b6-435a-9bb9-7a20058bd6d0"
        }

        current_page = 1
        total_pages = None

        print(f"Fetching transport stops from: {endpoint}")

        while True:
            try:
                params["pagenumber"] = str(current_page)
                response = requests.get(endpoint, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                if total_pages is None:
                    total_pages = data.get("TotalPages", 1)
                    print(f"Total pages for stops: {total_pages}")

                print(f"Fetching stops page {current_page}/{total_pages}")
                yield data

                if current_page >= total_pages:
                    break

                current_page += 1

            except requests.exceptions.RequestException as e:
                print(f"Error fetching stops (page {current_page}): {e}")
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

        if distance < 50:
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
    """Handle database operations"""

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

    def insert_transport_stop(self, transport_data: Dict):
        """
        Insert a single transport stop into database
        """
        try:
            cursor = self.connection.cursor()

            # 1. Prepare the Point WKT (Longitude First for PostGIS)
            # PostGIS ST_GeomFromText expects 'POINT(Longitude Latitude)'
            lon = transport_data.get("longitude")
            lat = transport_data.get("latitude")
            name = transport_data.get("name")

            if lon is None or lat is None:
                print(f"Skipping stop {name}: Missing coordinates.")
                return

            point_wkt = f"POINT({lon} {lat})"

            # 2. Execute the Insert
            # We use a simple query since your table doesn't have a UNIQUE constraint
            # on 'name', but if you want to avoid duplicates, consider adding
            # a UNIQUE(name) or UNIQUE(geometry) to your table schema.
            query = """
                INSERT INTO transport_stops (
                    name, 
                    geometry
                ) VALUES (
                    %s, 
                    ST_GeomFromText(%s, 4326)
                )
            """

            cursor.execute(query, (name, point_wkt))
            self.connection.commit()

        except Exception as e:
            print(f"Error inserting transport stop {transport_data.get('name')}: {e}")
            self.connection.rollback()
            raise

    def insert_trail(self, trail_data: Dict, latitude_first: bool=True):
        """
        Insert a single trail into database

        Args:
        trail_data {
            "trail_id": str,
            "difficulty": str(TrailDifficulty),
            "length_km": float,
            "duration_minutes": int,
            "elevation_gain_m": int,
            "elevation_loss_m": int,
            "elevation_max_m": int,
            "elevation_min_m": int,
            "description": str,
            "coordinates": coordinates_3d, (lat, lon, alt)
            "start_point": coordinate_3d, (lat, lon, alt)
            "end_point": coordinate_3d, (lat, lon, alt)
            "circular": bool,
        }
        """
        try:
            cursor = self.connection.cursor()

            # Convert coordinates list to LineStringZ WKT
            # Returns: 'LINESTRING Z (X Y Z, ...)'
            coords_wkt = self._coordinates_to_linestring(trail_data["coordinates"], latitude_first)

            # Returns: 'POINT Z (X Y Z)'
            start_wkt = self._point_to_wkt(trail_data["coordinates"][0], latitude_first)
            end_wkt = self._point_to_wkt(trail_data["coordinates"][-1], latitude_first)

            query = """
                INSERT INTO hiking_trails (
                    odh_id, difficulty, length_km, duration_minutes,
                    elevation_gain_m, elevation_loss_m, elevation_max_m, elevation_min_m,
                    description,
                    geometry, start_point, end_point, 
                    circular
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s,
                    ST_GeomFromText(%s, 4326),
                    ST_GeomFromText(%s, 4326),
                    ST_GeomFromText(%s, 4326),
                    %s
                )
            """
            values = (
                trail_data["trail_id"],
                trail_data["difficulty"],
                trail_data["length_km"],
                trail_data["duration_minutes"],
                trail_data["elevation_gain_m"],
                trail_data["elevation_loss_m"],
                trail_data["elevation_max_m"],
                trail_data["elevation_min_m"],
                trail_data["description"],
                coords_wkt,
                start_wkt,
                end_wkt,
                trail_data["circular"],
            )

            cursor.execute(query, values)
            self.connection.commit()

        except Exception as e:
            print(f"Error inserting trail {trail_data.get('name', 'unknown')}: {e}")
            self.connection.rollback()
            raise

    @staticmethod
    def _point_to_wkt(coord: List[float], latitude_first: bool = True) -> str:
        """Helper to convert a single point to WKT POINT Z"""
        if latitude_first:
            lat, lon = coord[0], coord[1]
        else:
            lon, lat = coord[0], coord[1]

        elev = coord[2] if len(coord) > 2 else 0
        return f"POINT Z ({lon} {lat} {elev})"

    @staticmethod
    def _coordinates_to_linestring(coordinates: List[List[float]], latitude_first: bool = True) -> str:
        """
        Convert coordinates list to WKT LineStringZ format (X Y Z).

        Args:
            coordinates: List of [lat, lon, elev] or [lon, lat, elev]
            latitude_first: True if input is [lat, lon, ...], False if [lon, lat, ...]

        Returns:
            WKT LineString string in 'X Y Z' format
        """
        formatted_coords = []

        for coord in coordinates:
            # Extract Lon (X), Lat (Y), and Elev (Z)
            if latitude_first:
                lat, lon = coord[0], coord[1]
            else:
                lon, lat = coord[0], coord[1]

            elev = coord[2] if len(coord) > 2 else 0

            # PostGIS WKT expects: LONGITUDE LATITUDE ELEVATION
            formatted_coords.append(f"{lon} {lat} {elev}")

        return f"LINESTRING Z ({', '.join(formatted_coords)})"


def dump_to_file(path: Path, page_size: int=10):
    """
    Dumps trails data into the specified file path
    """
    print("=" * 60)
    print(f"Dumping OpenDataHub Hiking Trails into {path}")
    print("=" * 60)

    # Initialize components
    client = OpenDataHubClient()

    try:
        # Fetch trails from OpenDataHub
        print("\nFetching trails from OpenDataHub...")
        pages_iter = client.get_geoshapes(page_size)

        print(f"\nWriting to {str(path)}")
        path.write_text(json.dumps(next(pages_iter,""), indent=2))

    except Exception as e:
        print(f"\n✗ Error during file dump: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

def import_trails(limit=None):
    """
    Takes the trails data from OpenDataHub and stores them in the database
    """
    print("=" * 60)
    print("OpenDataHub Hiking Trails Import Script")
    print("=" * 60)

    db_url = os.getenv("DATABASE_URL")

    # Initialize components
    client = OpenDataHubClient()
    elevation_service = ElevationService()
    processor = TrailProcessor(elevation_service)
    db_importer = DatabaseImporter(db_url)


    try:
        # Connect to database
        db_importer.connect()

        # Fetch trails from OpenDataHub
        print("\nFetching trails from OpenDataHub...")

        # Process each trail
        found_count = 0
        processed_count = 0
        skipped_count = 0

        for page in client.get_geoshapes(page_size=100):
            print(f"Processing page {page.get("CurrentPage")} out of {page.get("TotalPages")}")
            routes = page.get("Items", [])
            print(f"Found {len(routes)} trails")

            for idx, route in enumerate(routes, 1):
                if processed_count_exceeds_limit(processed_count, limit):
                    return
                print(f"\n[{idx}/{len(routes)}] Processing trail...")
                found_count += 1
                # Check SRID (coordinate system)
                srid = route.get("Srid", "")
                if srid != "EPSG:4326":
                    print(f"  ⚠ Skipping - unsupported SRID: {srid}")
                    skipped_count += 1
                    continue

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

                # Add altitude to each pair of coordinates
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
                trail_data = {
                    "trail_id": id_,
                    "difficulty": difficulty_data.get("difficulty"),
                    "length_km": round(distance_km, 2),
                    "duration_minutes": duration_minutes,
                    "elevation_gain_m": int(elev_gain),
                    "elevation_loss_m": int(elev_loss),
                    "elevation_max_m": int(max_elev),
                    "elevation_min_m": int(min_elev),
                    "description": "",
                    "coordinates": coordinates_3d,
                    "circular": is_circular,
                }
                # Insert into database
                try:
                    db_importer.insert_trail(trail_data, latitude_first=False)
                    print(f"  ✓ Successfully imported")
                    processed_count += 1
                except Exception as e:
                    print(f"  ✗ Failed to import: {e}")
                    skipped_count += 1
        # Summary
        print("\n" + "=" * 60)
        print("Import Summary")
        print("=" * 60)
        print(f"Total trails found: {found_count}")
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

def processed_count_exceeds_limit(processed_count: int, limit: int | None) -> bool:
    if limit is None:
        return False
    elif processed_count >= limit:
        return True
    return False

def import_public_transportation_stops(limit=None):
    """
    Takes the public transportation stops from data from OpenDataHub and stores them in the database
    """
    print("=" * 60)
    print("OpenDataHub Public Transport Stops Import Script")
    print("=" * 60)

    def _get_name(_pt_stop):
        """
        Extracts the name of a public transportation stop.
        In the ODH ActivityPoi format for GTFS, the name is typically in 'Shortname'.
        """
        # 1. Primary location for names in this format
        _name = _pt_stop.get("Shortname")
        if _name:
            return _name

        # 2. Fallback to nested Detail titles (standard for other ODH types)
        detail = _pt_stop.get("Detail", {})
        # Priority: Italian (local region), then English, then German
        for lang in ["it", "en", "de"]:
            title = detail.get(lang, {}).get("Title")
            if title:
                return title

        return ""

    def _get_gps_info(_pt_stop):
        gps_point = _pt_stop.get("GpsInfo", "")
        if not gps_point:
            return "", ""
        return gps_point[0].get("Latitude", ""), gps_point[0].get("Longitude", "")

    db_url = os.getenv("DATABASE_URL")

    # Initialize components
    client = OpenDataHubClient()
    db_importer = DatabaseImporter(db_url)



    try:
        # Connect to database
        db_importer.connect()

        print("\nFetching transportation stops from OpenDataHub...")

        # Process each stop
        found_count = 0
        processed_count = 0
        skipped_count = 0

        for page in client.get_transport_stops(page_size=100):
            print(f"Processing page {page.get("CurrentPage")} out of {page.get("TotalPages")}")
            stops = page.get("Items", [])

            for idx, pt_stop in enumerate(stops , 1):
                if processed_count_exceeds_limit(processed_count, limit):
                    return
                print(f"\n[{idx}/{len(stops)}] Processing stop...")

                found_count += 1

                name = _get_name(pt_stop)
                lat, lon = _get_gps_info(pt_stop)

                print(f"lon: {lon}, lat:{lat}")
                if not lat or not lon:
                    print(f"  ⚠ Skipping - no Gps Info found")
                    skipped_count += 1
                    continue

                print(f"stop name: {name}")
                print(f"lon: {lon}, lat:{lat}")

                # Prepare trail data for database
                transport_data = {
                    "name": name,
                    "latitude": lat,
                    "longitude": lon
                }
                # Insert into database
                try:
                    db_importer.insert_transport_stop(transport_data)
                    print(f"  ✓ Successfully imported")
                    processed_count += 1
                except Exception as e:
                    print(f"  ✗ Failed to import: {e}")
                    skipped_count += 1
        # Summary
        print("\n" + "=" * 60)
        print("Import Summary")
        print("=" * 60)
        print(f"Total stops found: {found_count}")
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

def retreive_and_validate_user_input():
    transport_stops_limit = None
    trails_limit = None
    if len(sys.argv) > 1:
        transport_stops_limit = int(sys.argv[1])
        trails_limit = int(sys.argv[2])
    return transport_stops_limit, trails_limit



if __name__ == "__main__":
    transport_stops_limit, trails_limit = retreive_and_validate_user_input()

    import_public_transportation_stops(transport_stops_limit)
    import_trails(trails_limit)
