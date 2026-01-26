import psycopg2
import os
from typing import Optional

# TODO WORK HERE, CHECK GEMINI RESPONSE

def create_trails_database_schema(db_url: str) -> None:
    """
    Initialize database schema for hiking trails application.
    Creates PostGIS extension, tables, and indexes.

    Args:
        db_url: PostgreSQL connection string
    """
    connection = None

    try:
        connection = psycopg2.connect(db_url)
        cursor = connection.cursor()

        print("Connected to database successfully")

        # Enable PostGIS extension if not already enabled
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        print("PostGIS extension enabled")

        # Create hiking_trails table
        create_table_query = """
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

        cursor.execute(create_table_query)
        connection.commit()

        print("Table 'hiking_trails' created successfully (or already exists)")
        print("All indexes created successfully")

        cursor.close()

    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error initializing database: {e}")
        raise

    finally:
        if connection:
            connection.close()
            print("Database connection closed")


def clear_all_trails(db_url: str) -> None:
    """
    Clear all existing trails from the database.

    Args:
        db_url: PostgreSQL connection string
    """
    connection = None

    try:
        connection = psycopg2.connect(db_url)
        cursor = connection.cursor()

        cursor.execute("DELETE FROM hiking_trails")
        deleted_count = cursor.rowcount
        connection.commit()

        print(f"Cleared {deleted_count} trails from database")

        cursor.close()

    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error clearing trails: {e}")
        raise

    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    # Get database URL from environment
    DATABASE_URL = os.getenv("DATABASE_URL")
    WIPE_DB = os.getenv("WIPEDB", "False").lower() == "true"

    if not DATABASE_URL :
        print("Error: DATABASE_URL not set in environment")
        exit(1)

    print("Initializing database schema...")
    create_trails_database_schema(DATABASE_URL)
    print("\nDatabase initialization complete!")