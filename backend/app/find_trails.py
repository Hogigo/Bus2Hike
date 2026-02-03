#!/usr/bin/env python3
"""
Finds possible hiking trails from a starting point based on distance constraints.
docker exec bus2hike-backend-1 python app/find_trails.py lat lon diameter max_distance max-paths
"""

import argparse
import json
import os
import sys

import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger


class TrailFinder:
    """
    Finds trails in the network based on user-defined spatial and distance criteria.
    """

    def __init__(self, db_url: str):
        """
        Initializes the TrailFinder.

        Args:
            db_url: The database connection URL.
        """
        self.db_url = db_url
        self.connection = None
        self.cursor = None

    def connect(self):
        """Establishes the database connection."""
        try:
            self.connection = psycopg2.connect(self.db_url)
            self.cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            logger.info("Connected to database successfully.")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def disconnect(self):
        """Closes the database connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Database connection closed.")

    def find_start_nodes(self, lat: float, lon: float, diameter: float) -> list[int]:
        """
        Finds trail_nodes within a given diameter from a starting point.

        Args:
            lat: Latitude of the starting point.
            lon: Longitude of the starting point.
            diameter: The search radius in kilometers.

        Returns:
            A list of node IDs.
        """
        logger.info(f"Finding start nodes within {diameter}km from ({lat}, {lon})...")
        query = """
            SELECT id
            FROM trail_nodes
            WHERE ST_DWithin(
                geometry::geography,
                ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography,
                %(diameter_m)s
            );
        """
        # Convert diameter from km to meters for ST_DWithin
        params = {"lat": lat, "lon": lon, "diameter_m": diameter * 1000}
        self.cursor.execute(query, params)
        nodes = self.cursor.fetchall()
        node_ids = [row["id"] for row in nodes]
        logger.info(f"Found {len(node_ids)} potential start nodes.")
        return node_ids

    def find_paths_from_node(
        self, start_node_id: int, max_distance: float, max_paths: int = None
    ) -> list[dict]:
        """
        Finds all simple paths from a start node up to a max distance.

        Args:
            start_node_id: The ID of the node to start the search from.
            max_distance: The maximum length of the paths in kilometers.
            max_paths: Maximum number of paths to return (None for unlimited).

        Returns:
            A list of path records, each containing edge IDs, node sequence, and total cost.
        """
        logger.info(
            f"Searching for paths from node {start_node_id} up to {max_distance}km..."
        )

        # This recursive CTE traverses the graph to find all paths.
        # Key fix: We now track both edges AND the direction they were traversed
        # by storing edge_id with a direction indicator, and we track the actual node sequence
        query = """
            WITH RECURSIVE trail_paths (
                path_edges,
                path_directions,
                node_sequence,
                last_node,
                total_cost,
                visited_edges
            ) AS (
                -- Base Case: Start at the given node
                SELECT
                    ARRAY[]::integer[],
                    ARRAY[]::boolean[],
                    ARRAY[id],
                    id,
                    0.0,
                    ARRAY[]::integer[]
                FROM trail_nodes WHERE id = %(start_node_id)s

                UNION ALL

                -- Recursive Step: Explore to next nodes via actual edges
                SELECT
                    tp.path_edges || te.id,
                    tp.path_directions || CASE 
                        WHEN te.source_node_id = tp.last_node THEN true  -- forward direction
                        ELSE false  -- reverse direction
                    END,
                    tp.node_sequence || CASE 
                        WHEN te.source_node_id = tp.last_node THEN te.target_node_id
                        ELSE te.source_node_id
                    END,
                    CASE 
                        WHEN te.source_node_id = tp.last_node THEN te.target_node_id
                        ELSE te.source_node_id
                    END,
                    tp.total_cost + te.length_km,
                    tp.visited_edges || te.id
                FROM trail_paths tp
                JOIN trail_edges te ON (
                    -- Edge connects to our current node
                    te.source_node_id = tp.last_node OR te.target_node_id = tp.last_node
                )
                WHERE 
                    -- Don't revisit edges (prevents cycles)
                    NOT (te.id = ANY(tp.visited_edges))
                    -- Don't exceed max distance
                    AND (tp.total_cost + te.length_km) <= %(max_distance)s
                    -- Don't revisit nodes (prevents cycles)
                    AND NOT (
                        CASE 
                            WHEN te.source_node_id = tp.last_node THEN te.target_node_id
                            ELSE te.source_node_id
                        END = ANY(tp.node_sequence)
                    )
            )
            -- Select all valid paths found (with at least one edge)
            SELECT 
                path_edges, 
                path_directions,
                node_sequence,
                total_cost
            FROM trail_paths
            WHERE array_length(path_edges, 1) > 0
            ORDER BY total_cost DESC
            %(limit_clause)s;
        """

        limit_clause = f"LIMIT {max_paths}" if max_paths else ""
        query = query.replace("%(limit_clause)s", limit_clause)

        params = {"start_node_id": start_node_id, "max_distance": max_distance}
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def build_geojson_from_paths(self, paths: list[dict]) -> dict:
        """
        Builds a GeoJSON FeatureCollection from a list of paths.

        Args:
            paths: A list of path records from the search query.

        Returns:
            A GeoJSON FeatureCollection dictionary.
        """
        if not paths:
            return {"type": "FeatureCollection", "features": []}

        logger.info(f"Building GeoJSON for {len(paths)} paths...")
        all_edge_ids = {edge_id for path in paths for edge_id in path["path_edges"]}

        # Fetch all required geometries
        query = """
            SELECT
                id,
                ST_AsGeoJSON(geometry) as geojson,
                length_km,
                difficulty,
                source_node_id,
                target_node_id
            FROM trail_edges WHERE id = ANY(%(edge_ids)s);
        """
        self.cursor.execute(query, {"edge_ids": list(all_edge_ids)})
        edge_data = {row["id"]: row for row in self.cursor.fetchall()}

        features = []
        for i, path in enumerate(paths):
            if not path["path_edges"]:
                continue

            coordinates = []

            # Build coordinates using edge directions
            for idx, (edge_id, forward_direction) in enumerate(
                zip(path["path_edges"], path["path_directions"])
            ):
                edge = edge_data.get(edge_id)
                if not edge:
                    logger.warning(f"Edge {edge_id} not found in database")
                    continue

                coords = json.loads(edge["geojson"])["coordinates"]

                # If we're going in reverse direction, flip the coordinates
                if not forward_direction:
                    coords = coords[::-1]

                if idx == 0:
                    # First edge: add all coordinates
                    coordinates.extend(coords)
                else:
                    # Subsequent edges: skip first coordinate (it should match the last one)
                    if coordinates and len(coords) > 0:
                        # Verify connection
                        last_point = coordinates[-1]
                        first_point = coords[0]

                        # Check if points match (with tolerance for floating point)
                        if abs(last_point[0] - first_point[0]) < 1e-7 and \
                           abs(last_point[1] - first_point[1]) < 1e-7:
                            coordinates.extend(coords[1:])
                        else:
                            logger.warning(
                                f"Path {i}, Edge {edge_id}: Coordinates don't connect properly. "
                                f"Last: {last_point}, First: {first_point}"
                            )
                            # Add anyway, but this indicates a data problem
                            coordinates.extend(coords)
                    else:
                        coordinates.extend(coords)

            if len(coordinates) < 2:
                logger.warning(f"Path {i} has fewer than 2 coordinates, skipping")
                continue

            feature = {
                "type": "Feature",
                "properties": {
                    "path_id": i,
                    "total_distance_km": float(round(path["total_cost"], 2)),
                    "edge_ids": path["path_edges"],
                    "node_sequence": path["node_sequence"],
                },
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }
            features.append(feature)

        return {"type": "FeatureCollection", "features": features}


def find_trails(latitude, longitude, diameter, max_distance, max_paths):
    """Main function to run the trail finder."""

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("Error: DATABASE_URL environment variable not set.")
        sys.exit(1)

    finder = TrailFinder(db_url)
    all_paths = []
    try:
        finder.connect()
        start_nodes = finder.find_start_nodes(latitude, longitude, diameter)

        if not start_nodes:
            logger.info("No trail entry points found within the specified diameter.")
            # Output empty GeoJSON
            print(json.dumps({"type": "FeatureCollection", "features": []}))
            return

        # Distribute max_paths across start nodes
        max_paths_per_node = max(1, max_paths // len(start_nodes))

        for node_id in start_nodes:
            paths = finder.find_paths_from_node(
                node_id, max_distance, max_paths_per_node
            )
            all_paths.extend(paths)

            # Stop if we've reached the limit
            if len(all_paths) >= max_paths:
                all_paths = all_paths[:max_paths]
                break

        logger.info(f"Found a total of {len(all_paths)} paths.")
        geojson_result = finder.build_geojson_from_paths(all_paths)

        # Print the final GeoJSON to standard output
        print(json.dumps(geojson_result, indent=2))

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)
    finally:
        if finder.connection:
            finder.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find hiking trails.")
    parser.add_argument("latitude", type=float, help="Latitude of the starting point.")
    parser.add_argument("longitude", type=float, help="Longitude of the starting point.")
    parser.add_argument(
        "diameter",
        type=float,
        help="Search radius in kilometers to find trail entry points.",
    )
    parser.add_argument(
        "max_distance", type=float, help="Maximum length of the trail in kilometers."
    )
    parser.add_argument(
        "max_paths",
        type=int,
        default=100,
        help="Maximum number of paths to return (default: 100).",
    )
    args = parser.parse_args()
    find_trails(**vars(args))