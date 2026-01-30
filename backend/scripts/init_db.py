import psycopg2
import os
import time
import logging

DB_NAME = os.getenv("POSTGRES_DB", "mydatabase")
DB_USER = os.getenv("POSTGRES_USER", "user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")
DB_HOST = os.getenv("POSTGRES_HOST", "db")
WIPE_DB = os.getenv("WIPE_DB", "False").lower() == "true"

# hiking_trails table
create_hiking_trails_query = """
    CREATE TABLE IF NOT EXISTS hiking_trails (
        id SERIAL PRIMARY KEY,
        odh_id VARCHAR(255) UNIQUE NOT NULL,
        difficulty VARCHAR(50),
        length_km DECIMAL(10, 2),
        duration_minutes INTEGER,
        elevation_gain_m INTEGER,
        elevation_loss_m INTEGER,
        description TEXT,
        geometry GEOMETRY(LINESTRING, 4326),
        start_point GEOMETRY(POINT, 4326),
        end_point GEOMETRY(POINT, 4326),
        circular BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_hiking_trails_odh_id 
        ON hiking_trails(odh_id);

    CREATE INDEX IF NOT EXISTS idx_hiking_trails_difficulty 
        ON hiking_trails(difficulty);

    CREATE INDEX IF NOT EXISTS idx_hiking_trails_geometry 
        ON hiking_trails USING GIST(geometry);

    CREATE INDEX IF NOT EXISTS idx_hiking_trails_start_point 
        ON hiking_trails USING GIST(start_point);

    CREATE INDEX IF NOT EXISTS idx_hiking_trails_end_point 
        ON hiking_trails USING GIST(end_point);
"""


def get_connection():
    """Retries connection until the database is ready."""
    retries = 10
    while retries > 0:
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                host=DB_HOST
            )
            logging.log(logging.INFO, "Connected to database successfully")
            return conn
        except psycopg2.OperationalError:
            logging.log(logging.WARNING, f"Database not ready. Retrying... ({retries} attempts left)")
            time.sleep(3)
            retries -= 1
    raise Exception("Could not connect to the database.")

def init_db():
    conn = get_connection()

    conn.autocommit = True  # Necessary for schema changes like CREATE/DROP
    cur = conn.cursor()

    # 1. Handle Wiping
    if WIPE_DB:
        logging.log(logging.INFO,"Wiping database...")
        # A quick way to wipe: Drop and recreate the public schema
        cur.execute("DROP SCHEMA public CASCADE;")
        cur.execute("CREATE SCHEMA public;")
        cur.execute("GRANT ALL ON SCHEMA public TO public;")

    # Enable PostGIS extension if not already enabled (execute always after WIPE_DB)
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # 2. Create Table
    logging.log(logging.INFO, "Ensuring hiking trails tables exist...")
    cur.execute(create_hiking_trails_query)

    logging.log(logging.INFO,"Table 'hiking_trails' created successfully (or already exists)")

    cur.close()
    conn.close()

    logging.log(logging.INFO,"Database initialization complete.")


if __name__ == "__main__":
    init_db()