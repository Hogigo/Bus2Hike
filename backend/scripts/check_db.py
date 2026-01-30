import os
import sys
import psycopg2
from loguru import logger

# Ensure your .env or environment has:
# DATABASE_URL=postgresql://user:password@localhost:5432/mydatabase
DB_URL = os.getenv("DATABASE_URL", None)

def check_database():
    """Connects to the DB and prints hiking trails."""
    conn = None
    try:
        if not DB_URL:
            logger.error("DATABASE_URL environment variable is not set.")
            return False

        # 1. Attempt Connection
        conn = psycopg2.connect(DB_URL)

        with conn.cursor() as cur:
            # 2. Check if PostGIS is active
            cur.execute("SELECT postgis_version();")
            version = cur.fetchone()[0]
            logger.success(f"Connected! PostGIS version: {version}")

            # 3. Execute your specific query
            logger.info("Fetching hiking trails...")
            cur.execute("SELECT * FROM hiking_trails LIMIT 10;")

            # 4. Fetch all rows from the result set
            rows = cur.fetchall()

            if not rows:
                logger.warning("Table 'hiking_trails' is empty or does not exist.")
            else:
                print("\n--- HIKING TRAILS (Top 10) ---")
                for row in rows:
                    print(row)
                print("------------------------------\n")

        return True

    except psycopg2.errors.UndefinedTable:
        logger.error("The table 'hiking_trails' does not exist yet.")
        return False
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        return False

    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if check_database():
        sys.exit(0)
    else:
        sys.exit(1)