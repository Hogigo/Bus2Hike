from psycopg2.extras import RealDictCursor

from app.db import engine
from .schemas import TransportStopGetDto


def get_all_transport_stops():
    LIST_TRANSPORT_STOPS_SQL = """
        SELECT
            id,
            name,
            created_at,
            ST_AsGeoJSON(geometry)::json AS geometry
        FROM transport_stops
        ORDER BY id
    """
    with engine.connect() as connection:
        raw_conn = connection.connection
        try:
            with raw_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(LIST_TRANSPORT_STOPS_SQL)
                rows = cursor.fetchall()
            dtos = [TransportStopGetDto.from_row(r) for r in rows]
            return dtos
        except Exception as e:
            raw_conn.rollback()
            raise RuntimeError("Failed to fetch from database: " + str(e))

