"""
Optimized Trail Network Builder
Uses PostGIS spatial queries for better performance on large datasets.
"""

import psycopg2
import os
from psycopg2.extras import execute_values
from loguru import logger


class OptimizedTrailNetworkBuilder:
    """
    Builds a routable network using PostGIS spatial operations.
    More efficient for large datasets than pure Python approach.
    """

    def __init__(self, db_url: str, snap_tolerance: float = 0.00001):
        """
        Initialize the network builder.

        Args:
            db_config: Database connection configuration
            snap_tolerance: Distance threshold for snapping nearby points (in degrees)
        """
        self.db_url = db_url
        self.snap_tolerance = snap_tolerance
        self.connection = None
        self.cursor = None

    def connect(self):
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(self.db_url)
            self.cursor = self.connection.cursor()
            logger.info("Connected to database successfully")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise


    def disconnect(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Database connection closed")

    def create_network_tables(self):
        """Create the network topology tables."""
        logger.info("Creating network tables...")

        self.cursor.execute("""
            DROP TABLE IF EXISTS trail_edges CASCADE;
            DROP TABLE IF EXISTS trail_nodes CASCADE;
        """)

        # activate pgrouting extension
        self.cursor.execute("""
        CREATE EXTENSION IF NOT EXISTS pgrouting;
        """)

        # Create nodes table
        self.cursor.execute("""
            CREATE TABLE trail_nodes (
                id SERIAL PRIMARY KEY,
                geometry GEOMETRY(POINTZ, 4326) NOT NULL,
                node_type VARCHAR(20),
                elevation_m DECIMAL(10, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX idx_trail_nodes_geom ON trail_nodes USING GIST(geometry);
        """)

        # Create edges table
        self.cursor.execute("""
            CREATE TABLE trail_edges (
                id SERIAL PRIMARY KEY,
                source_node_id INTEGER REFERENCES trail_nodes(id),
                target_node_id INTEGER REFERENCES trail_nodes(id),
                original_trail_id INTEGER REFERENCES hiking_trails(id),
                geometry GEOMETRY(LINESTRINGZ, 4326) NOT NULL,
                length_km DECIMAL(10, 2),
                difficulty VARCHAR(50),
                elevation_gain_m INTEGER,
                elevation_loss_m INTEGER,
                bidirectional BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX idx_trail_edges_geom ON trail_edges USING GIST(geometry);
            CREATE INDEX idx_trail_edges_source ON trail_edges(source_node_id);
            CREATE INDEX idx_trail_edges_target ON trail_edges(target_node_id);
        """)

        self.connection.commit()
        logger.info("Network tables created successfully")

    def extract_and_insert_nodes(self):
        """
        Extract all potential nodes using PostGIS and insert them.
        This includes endpoints and intersections.
        """
        logger.info("Extracting nodes using PostGIS...")

        # Step 1: Create temporary table with all potential node points
        self.cursor.execute("""
            CREATE TEMP TABLE temp_raw_nodes AS
            WITH endpoints AS (
                -- Get all start and end points
                SELECT 
                    ST_StartPoint(geometry) as geom,
                    'endpoint' as node_type,
                    ST_Z(ST_StartPoint(geometry)) as elevation_m
                FROM hiking_trails
                WHERE geometry IS NOT NULL

                UNION ALL

                SELECT 
                    ST_EndPoint(geometry) as geom,
                    'endpoint' as node_type,
                    ST_Z(ST_EndPoint(geometry)) as elevation_m
                FROM hiking_trails
                WHERE geometry IS NOT NULL
            ),
            intersections AS (
                -- Find intersection points between trails
                SELECT DISTINCT
                    (ST_DumpPoints(ST_Intersection(a.geometry, b.geometry))).geom as geom,
                    'intersection' as node_type,
                    ST_Z((ST_DumpPoints(ST_Intersection(a.geometry, b.geometry))).geom) as elevation_m
                FROM hiking_trails a
                JOIN hiking_trails b ON a.id < b.id
                WHERE ST_Intersects(a.geometry, b.geometry)
                    AND ST_GeometryType(ST_Intersection(a.geometry, b.geometry)) IN ('ST_Point', 'ST_MultiPoint')
            )
            SELECT geom, node_type, elevation_m
            FROM endpoints
            UNION
            SELECT geom, node_type, elevation_m
            FROM intersections;
        """)

        self.cursor.execute("SELECT COUNT(*) FROM temp_raw_nodes")
        raw_count = self.cursor.fetchone()[0]
        logger.info(f"Found {raw_count} raw node points")

        # Step 2: Cluster nearby points and insert unique nodes
        logger.info(f"Clustering points within {self.snap_tolerance} tolerance...")

        self.cursor.execute(f"""
            INSERT INTO trail_nodes (geometry, node_type, elevation_m)
            SELECT 
                ST_SetSRID(ST_MakePoint(
                    AVG(ST_X(geom)),
                    AVG(ST_Y(geom)),
                    AVG(elevation_m)
                ), 4326) as geometry,
                MIN(node_type) as node_type,  -- Prefer 'intersection' over 'endpoint'
                AVG(elevation_m) as elevation_m
            FROM (
                SELECT 
                    geom,
                    node_type,
                    elevation_m,
                    ST_ClusterDBSCAN(geom, eps := {self.snap_tolerance}, minpoints := 1) 
                        OVER () AS cluster_id
                FROM temp_raw_nodes
            ) clustered
            GROUP BY cluster_id;
        """)

        self.cursor.execute("SELECT COUNT(*) FROM trail_nodes")
        node_count = self.cursor.fetchone()[0]

        self.connection.commit()
        logger.info(f"Inserted {node_count} unique nodes after clustering")

        # Clean up
        self.cursor.execute("DROP TABLE temp_raw_nodes")

    def create_edges_from_trails(self):
        """
        Split trails at nodes and create edges.
        Uses PostGIS ST_Split for efficient geometry operations.
        """
        logger.info("Creating edges by splitting trails at nodes...")

        # Create temporary table for split segments
        self.cursor.execute("""
            CREATE TEMP TABLE temp_trail_segments AS
            WITH trail_splits AS (
                SELECT 
                    t.id as trail_id,
                    t.difficulty,
                    t.elevation_gain_m as total_gain,
                    t.elevation_loss_m as total_loss,
                    -- Split each trail at all nearby nodes
                    (ST_Dump(
                        COALESCE(
                            ST_Split(
                                ST_Snap(
                                    t.geometry,
                                    (SELECT ST_Collect(n.geometry) 
                                     FROM trail_nodes n 
                                     WHERE ST_DWithin(t.geometry, n.geometry, %s)),
                                    %s
                                ),
                                (SELECT ST_Collect(n.geometry) 
                                 FROM trail_nodes n 
                                 WHERE ST_DWithin(t.geometry, n.geometry, %s))
                            ),
                            t.geometry  -- If split fails, use original
                        )
                    )).geom as segment_geom
                FROM hiking_trails t
                WHERE t.geometry IS NOT NULL
            )
            SELECT 
                trail_id,
                difficulty,
                segment_geom,
                ST_Length(segment_geom::geography) / 1000.0 as length_km,
                -- Calculate elevation change
                GREATEST(0, 
                    ST_Z(ST_EndPoint(segment_geom)) - ST_Z(ST_StartPoint(segment_geom))
                ) as elevation_gain_m,
                GREATEST(0, 
                    ST_Z(ST_StartPoint(segment_geom)) - ST_Z(ST_EndPoint(segment_geom))
                ) as elevation_loss_m
            FROM trail_splits
            WHERE ST_GeometryType(segment_geom) = 'ST_LineString'
                AND ST_NPoints(segment_geom) >= 2;
        """, (self.snap_tolerance, self.snap_tolerance, self.snap_tolerance))

        self.cursor.execute("SELECT COUNT(*) FROM temp_trail_segments")
        segment_count = self.cursor.fetchone()[0]
        logger.info(f"Created {segment_count} trail segments")

        # Insert edges with source and target node references
        logger.info("Linking segments to nodes and creating edges...")

        self.cursor.execute(f"""
            WITH potential_edges AS (
                SELECT
                    source_node.id as source_node_id,
                    target_node.id as target_node_id,
                    s.trail_id,
                    s.segment_geom,
                    s.length_km,
                    s.difficulty,
                    s.elevation_gain_m::INTEGER as elevation_gain_m,
                    s.elevation_loss_m::INTEGER as elevation_loss_m,
                    TRUE as bidirectional
                FROM temp_trail_segments s
                CROSS JOIN LATERAL (SELECT id FROM trail_nodes ORDER BY geometry <-> ST_StartPoint(s.segment_geom) LIMIT 1) source_node
                CROSS JOIN LATERAL (SELECT id FROM trail_nodes ORDER BY geometry <-> ST_EndPoint(s.segment_geom) LIMIT 1) target_node
                WHERE source_node.id != target_node.id
                    AND ST_Distance((SELECT geometry FROM trail_nodes WHERE id = source_node.id), ST_StartPoint(s.segment_geom)) < {self.snap_tolerance * 10}
                    AND ST_Distance((SELECT geometry FROM trail_nodes WHERE id = target_node.id), ST_EndPoint(s.segment_geom)) < {self.snap_tolerance * 10}
            ),
            deduplicated_edges AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER(PARTITION BY source_node_id, target_node_id ORDER BY length_km DESC) as rn
                FROM potential_edges
            )
            INSERT INTO trail_edges
            (source_node_id, target_node_id, original_trail_id, geometry,
             length_km, difficulty, elevation_gain_m, elevation_loss_m, bidirectional)
            SELECT
                source_node_id,
                target_node_id,
                trail_id,
                segment_geom,
                length_km,
                difficulty,
                elevation_gain_m,
                elevation_loss_m,
                bidirectional
            FROM deduplicated_edges
            WHERE rn = 1;
        """)

        self.cursor.execute("SELECT COUNT(*) FROM trail_edges")
        edge_count = self.cursor.fetchone()[0]

        self.connection.commit()
        logger.info(f"Inserted {edge_count} edges")

        # Clean up
        self.cursor.execute("DROP TABLE temp_trail_segments")

    def create_indexes_and_constraints(self):
        """Create additional indexes for routing performance."""
        logger.info("Creating additional indexes...")

        # Add reverse lookup index for bidirectional routing
        self.cursor.execute("""
            CREATE INDEX idx_trail_edges_target_source 
            ON trail_edges(target_node_id, source_node_id);
        """)

        # Add index on length for distance-based queries
        self.cursor.execute("""
            CREATE INDEX idx_trail_edges_length ON trail_edges(length_km);
        """)

        self.connection.commit()
        logger.info("Indexes created")

    def analyze_network(self):
        """Generate network statistics."""
        logger.info("Analyzing network...")

        # Node statistics
        self.cursor.execute("""
            SELECT 
                node_type,
                COUNT(*) as count
            FROM trail_nodes
            GROUP BY node_type;
        """)
        node_stats = self.cursor.fetchall()

        # Edge statistics
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total_edges,
                SUM(length_km) as total_length_km,
                AVG(length_km) as avg_length_km,
                MIN(length_km) as min_length_km,
                MAX(length_km) as max_length_km
            FROM trail_edges;
        """)
        edge_stats = self.cursor.fetchone()

        # Connectivity check
        self.cursor.execute("""
            SELECT COUNT(*) as isolated_nodes
            FROM trail_nodes n
            WHERE NOT EXISTS (
                SELECT 1 FROM trail_edges e 
                WHERE e.source_node_id = n.id OR e.target_node_id = n.id
            );
        """)
        isolated = self.cursor.fetchone()[0]

        logger.info(f"""
        ╔══════════════════════════════════════════════════════════╗
        ║              Network Analysis Results                    ║
        ╠══════════════════════════════════════════════════════════╣
        ║ Node Statistics:                                         ║
        """)
        for node_type, count in node_stats:
            logger.info(f"║   {node_type:20s}: {count:>30} ║")

        logger.info(f"""║                                                          ║
        ║ Edge Statistics:                                         ║
        ║   Total edges:               {edge_stats[0]:>26} ║
        ║   Total length:              {edge_stats[1]:>20.2f} km ║
        ║   Average edge length:       {edge_stats[2]:>20.2f} km ║
        ║   Min edge length:           {edge_stats[3]:>20.2f} km ║
        ║   Max edge length:           {edge_stats[4]:>20.2f} km ║
        ║                                                          ║
        ║ Connectivity:                                            ║
        ║   Isolated nodes:            {isolated:>26} ║
        ╚══════════════════════════════════════════════════════════╝
        """)

    def build_network(self):
        """Main method to build the complete network."""
        try:
            self.connect()

            self.cursor.execute("SELECT COUNT(*) FROM hiking_trails")
            trail_count = self.cursor.fetchone()[0]
            logger.info(f"Found {trail_count} trails in hiking_trails table.")

            logger.info("Starting network build process...")

            # Step 1: Create tables
            self.create_network_tables()

            # Step 2: Extract and insert nodes
            self.extract_and_insert_nodes()

            # Step 3: Create edges
            self.create_edges_from_trails()

            # Step 4: Create indexes
            self.create_indexes_and_constraints()

            # Step 5: Analyze results
            self.analyze_network()

            logger.info("Network building complete!")

        except Exception as e:
            logger.error(f"Error building network: {e}")
            if self.connection:
                self.connection.rollback()
            raise
        finally:
            self.disconnect()


def main():
    """Example usage"""

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("No DATABASE_URL env variable found")
        raise Exception
    snap_tolerance = 0.0001  # ~11 meter
    builder = OptimizedTrailNetworkBuilder(db_url, snap_tolerance=snap_tolerance)
    builder.build_network()


if __name__ == '__main__':
    main()