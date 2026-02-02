#!/usr/bin/env python3
"""
Finds possible hiking trails from a starting point based on distance constraints.
docker exec bus2hike-backend-1 python app/find_trails.py lat lon diameter max_distance
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
        self, start_node_id: int, max_distance: float
    ) -> list[dict]:
        """
        Finds all simple paths from a start node up to a max distance.

        Args:
            start_node_id: The ID of the node to start the search from.
            max_distance: The maximum length of the paths in kilometers.

        Returns:
            A list of path records, each containing edge IDs and total cost.
        """
        logger.info(
            f"Searching for paths from node {start_node_id} up to {max_distance}km..."
        )

        # This recursive CTE traverses the graph to find all paths.
        # It handles the bi-directional nature of edges by using a UNION ALL
        # to create a directed graph representation where each edge has a reverse.
        query = """
            WITH RECURSIVE trail_paths (path_edges, last_node, total_cost, visited_nodes) AS (
                -- Base Case: Start at the given node
                SELECT
                    ARRAY[]::integer[],
                    id,
                    0.0,
                    ARRAY[id]
                FROM trail_nodes WHERE id = %(start_node_id)s

                UNION ALL

                -- Recursive Step: Explore to next nodes
                SELECT
                    tp.path_edges || g.id,
                    g.target,
                    tp.total_cost + g.cost,
                    tp.visited_nodes || g.target
                FROM trail_paths tp,
                (
                    -- Create a directed graph view with forward and backward edges
                    SELECT id, source_node_id as source, target_node_id as target, length_km as cost FROM trail_edges
                    UNION ALL
                    SELECT id, target_node_id as source, source_node_id as target, length_km as cost FROM trail_edges
                ) g
                WHERE tp.last_node = g.source
                  AND NOT (g.target = ANY(tp.visited_nodes)) -- Avoid cycles
                  AND (tp.total_cost + g.cost) <= %(max_distance)s
            )
            -- Select all valid paths found
            SELECT path_edges, total_cost
            FROM trail_paths
            WHERE total_cost > 0;
        """
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

        # Fetch all required geometries in a single query
        query = """
            SELECT
                id,
                ST_AsGeoJSON(geometry) as geojson,
                length_km,
                difficulty
            FROM trail_edges WHERE id = ANY(%(edge_ids)s);
        """
        self.cursor.execute(query, {"edge_ids": list(all_edge_ids)})
        edge_geoms = {row["id"]: row for row in self.cursor.fetchall()}

        features = []
        for i, path in enumerate(paths):
            coordinates = []
            # This logic for stitching coordinates is simplified and assumes segments connect perfectly.
            # A more robust solution might use ST_LineMerge on a collection of geometries.
            for edge_id in path["path_edges"]:
                edge = edge_geoms.get(edge_id)
                if edge:
                    # The coordinates from ST_AsGeoJSON are what we need
                    coords = json.loads(edge["geojson"])["coordinates"]
                    if not coordinates or coordinates[-1] != coords[0]:
                        coordinates.extend(coords)
                    else:
                        coordinates.extend(coords[1:])

            if not coordinates:
                continue

            feature = {
                "type": "Feature",
                "properties": {
                    "path_id": i,
                    "total_distance_km": float(round(path["total_cost"], 2)),
                    "edge_ids": path["path_edges"],
                },
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }
            features.append(feature)

        return {"type": "FeatureCollection", "features": features}


def main():
    """Main function to run the trail finder."""
    parser = argparse.ArgumentParser(description="Find hiking trails.")
    parser.add_argument("lat", type=float, help="Latitude of the starting point.")
    parser.add_argument("lon", type=float, help="Longitude of the starting point.")
    parser.add_argument(
        "diameter",
        type=float,
        help="Search radius in kilometers to find trail entry points.",
    )
    parser.add_argument(
        "max_distance", type=float, help="Maximum length of the trail in kilometers."
    )
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("Error: DATABASE_URL environment variable not set.")
        sys.exit(1)

    finder = TrailFinder(db_url)
    all_paths = []
    try:
        finder.connect()
        start_nodes = finder.find_start_nodes(args.lat, args.lon, args.diameter)

        if not start_nodes:
            logger.info("No trail entry points found within the specified diameter.")
            # Output empty GeoJSON
            print(json.dumps({"type": "FeatureCollection", "features": []}))
            return

        for node_id in start_nodes:
            paths = finder.find_paths_from_node(node_id, args.max_distance)
            all_paths.extend(paths)

        logger.info(f"Found a total of {len(all_paths)} possible paths.")
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
    main()
