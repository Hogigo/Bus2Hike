#!/usr/bin/env python3
"""
Finds possible hiking trails from a starting point based on distance constraints.
docker exec bus2hike-backend-1 python app/find_trails.py lat lon diameter max_distance max-paths
"""

import argparse
import json
import math
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

    def find_paths_from_node_optimized(
            self, start_node_id: int, max_distance: float, max_paths: int = 100
    ) -> list[dict]:
        """Using pgRouting's built-in path finding, with improved target selection."""

        # 1. Get geometry of start node
        self.cursor.execute("SELECT ST_X(geometry) as lon, ST_Y(geometry) as lat FROM trail_nodes WHERE id = %s", (start_node_id,))
        start_node_geom = self.cursor.fetchone()
        if not start_node_geom:
            return []

        # 2. Find candidate target nodes within a radius
        query = """
            SELECT id, ST_X(geometry) as lon, ST_Y(geometry) as lat
            FROM trail_nodes
            WHERE id != %(start_node_id)s AND ST_DWithin(
                geometry::geography,
                (SELECT geometry FROM trail_nodes WHERE id = %(start_node_id)s)::geography,
                %(radius_m)s
            )
        """
        self.cursor.execute(query, {
            "start_node_id": start_node_id,
            "radius_m": max_distance * 1000
        })
        candidate_nodes = self.cursor.fetchall()

        if not candidate_nodes:
            return []

        # 3. Select diverse targets using angular binning
        def calculate_bearing(lat1, lon1, lat2, lon2):
            dLon = lon2 - lon1
            y = math.sin(dLon) * math.cos(lat2)
            x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon)
            bearing = math.atan2(y, x)
            return (math.degrees(bearing) + 360) % 360

        num_bins = max(8, max_paths)
        bins = [[] for _ in range(num_bins)]

        start_lat_rad = math.radians(start_node_geom['lat'])
        start_lon_rad = math.radians(start_node_geom['lon'])

        for node in candidate_nodes:
            end_lat_rad = math.radians(node['lat'])
            end_lon_rad = math.radians(node['lon'])
            bearing = calculate_bearing(start_lat_rad, start_lon_rad, end_lat_rad, end_lon_rad)
            bin_index = int(bearing / (360 / num_bins))
            bins[bin_index].append(node)

        selected_targets = []
        for bin_nodes in bins:
            if bin_nodes:
                # Pick node 'farthest' from start_node_geom in this bin
                farthest_node = max(bin_nodes, key=lambda n: ((n['lat'] - start_node_geom['lat']) ** 2 + (n['lon'] - start_node_geom['lon']) ** 2))
                selected_targets.append(farthest_node)

        all_paths = []
        for target in selected_targets:
            target_id = target['id']
            # Use pgRouting's dijkstra
            query = """
            SELECT * FROM pgr_dijkstra(
                'SELECT id, source_node_id as source, target_node_id as target,
                        length_km as cost, length_km as reverse_cost FROM trail_edges',
                %(start)s,
                %(end)s,
                directed := false
            );
            """
            self.cursor.execute(query, {"start": start_node_id, "end": target_id})
            path = self.cursor.fetchall()

            if path:
                formatted_path = self._format_path(path)
                if formatted_path:
                    all_paths.append(formatted_path)
            
            if len(all_paths) >= max_paths:
                break

        return all_paths

    def _format_path(self, pgr_path: list[dict]) -> dict:
        """Helper to convert pgr_dijkstra result to our path format."""
        if not pgr_path:
            return {}

        node_sequence = [p['node'] for p in pgr_path]
        path_edges = [p['edge'] for p in pgr_path if p['edge'] != -1]

        if not path_edges:
            return {
                "path_edges": [],
                "path_directions": [],
                "node_sequence": node_sequence,
                "total_cost": 0,
            }

        total_cost = pgr_path[-1]['agg_cost']

        # Fetch edge details to determine direction
        query = "SELECT id, source_node_id FROM trail_edges WHERE id = ANY(%(edge_ids)s);"
        self.cursor.execute(query, {"edge_ids": path_edges})
        edge_sources = {row['id']: row['source_node_id'] for row in self.cursor.fetchall()}

        path_directions = []
        for i in range(len(node_sequence) - 1):
            edge_id = path_edges[i]
            # The direction is forward if the source of the edge is the current node in the sequence
            if edge_id in edge_sources and edge_sources[edge_id] == node_sequence[i]:
                path_directions.append(True)
            else:
                path_directions.append(False)

        return {
            "path_edges": path_edges,
            "path_directions": path_directions,
            "node_sequence": node_sequence,
            "total_cost": total_cost,
        }

    def _truncate_path_geometry(self, path: dict, max_dist: float) -> (list, float):
        """Truncates a path's geometry to a max distance using PostGIS."""
        if not path['path_edges']:
            return [], 0.0

        total_length = path['total_cost']

        # Use a SQL query to build and truncate the line
        query = """
            WITH path_edges AS (
                SELECT * FROM unnest(%(edge_ids)s, %(directions)s) WITH ORDINALITY as t(edge_id, fwd, ord)
            ),
            ordered_geoms AS (
                SELECT
                    t.ord,
                    CASE
                        WHEN t.fwd THEN e.geometry
                        ELSE ST_Reverse(e.geometry)
                    END as geom
                FROM path_edges t
                JOIN trail_edges e ON t.edge_id = e.id
                ORDER BY t.ord
            ),
            full_path AS (
                SELECT ST_LineMerge(ST_Collect(geom)) as geometry
                FROM ordered_geoms
            )
            SELECT
                ST_AsGeoJSON(
                    CASE
                        WHEN %(total_length)s > %(max_dist)s THEN
                            ST_LineSubstring(geometry, 0, %(max_dist)s / %(total_length)s)
                        ELSE
                            geometry
                    END
                ) as truncated_geojson,
                CASE
                    WHEN %(total_length)s > %(max_dist)s THEN %(max_dist)s
                    ELSE %(total_length)s
                END as final_length
            FROM full_path;
        """
        params = {
            "edge_ids": path['path_edges'],
            "directions": path['path_directions'],
            "total_length": total_length,
            "max_dist": max_dist
        }
        self.cursor.execute(query, params)
        result = self.cursor.fetchone()

        if not result or not result['truncated_geojson']:
            return [], 0.0

        geom = json.loads(result['truncated_geojson'])
        final_length = result['final_length']

        return geom['coordinates'], final_length

    def build_geojson_from_paths(self, paths: list[dict], max_distance_cut: float = None) -> dict:
        """
        Builds a GeoJSON FeatureCollection from a list of paths.
        Args:
            paths: A list of path records from the search query.
            max_distance_cut: If specified, paths longer than this will be truncated.
        Returns:
            A GeoJSON FeatureCollection dictionary.
        """
        if not paths:
            return {"type": "FeatureCollection", "features": []}

        logger.info(f"Building GeoJSON for {len(paths)} paths...")

        features = []
        for i, path in enumerate(paths):
            if not path["path_edges"]:
                continue

            total_path_distance = path["total_cost"]
            needs_truncation = max_distance_cut is not None and total_path_distance > max_distance_cut

            if needs_truncation:
                final_coords, final_dist = self._truncate_path_geometry(path, max_distance_cut)
            else:
                # This path doesn't need truncation, but we still need its geometry.
                # To avoid having two separate logic paths, we can call truncate with a very large number,
                # but it's cleaner to have a non-truncating path builder.
                # For now, let's accept the N+1 queries for simplicity, even for non-truncated paths.
                # The _truncate_path_geometry will just return the full geometry if not over max_dist.
                final_coords, final_dist = self._truncate_path_geometry(path, total_path_distance + 1)


            if len(final_coords) < 2:
                logger.warning(f"Path {i} has fewer than 2 coordinates after processing, skipping")
                continue

            feature = {
                "type": "Feature",
                "properties": {
                    "path_id": i,
                    "total_distance_km": float(round(final_dist, 2)),
                    "edge_ids": path["path_edges"],
                    "node_sequence": path["node_sequence"],
                },
                "geometry": {"type": "LineString", "coordinates": final_coords},
            }
            features.append(feature)

        return {"type": "FeatureCollection", "features": features}


def find_trails(latitude, longitude, diameter, max_distance, max_paths) -> str:
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
            return json.dumps({"type": "FeatureCollection", "features": []})

        # Distribute max_paths across start nodes
        max_paths_per_node = max(1, max_paths // len(start_nodes))

        for node_id in start_nodes:
            paths = finder.find_paths_from_node_optimized(
                node_id, max_distance, max_paths_per_node
            )
            all_paths.extend(paths)

            # Stop if we've reached the limit
            if len(all_paths) >= max_paths:
                all_paths = all_paths[:max_paths]
                break

        logger.info(f"Found a total of {len(all_paths)} paths.")
        geojson_result = finder.build_geojson_from_paths(all_paths, max_distance)

        # Print the final GeoJSON to standard output
        return json.dumps(geojson_result, indent=2)

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
    print(find_trails(**vars(args)))