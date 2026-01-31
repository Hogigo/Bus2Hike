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

    with engine.connect().connection.cursor() as cursor:
        cursor.execute(LIST_TRANSPORT_STOPS_SQL)
        rows = cursor.fetchall()
        formatted_data = [add_column_names_to_row(cursor, r) for r in rows]
        dtos = [TransportStopGetDto.from_row(d) for d in formatted_data]
        return dtos


def add_column_names_to_row(cursor: object, row: tuple) -> dict:
    cols = [desc.name for desc in cursor.description]
    return dict(zip(cols, row))
