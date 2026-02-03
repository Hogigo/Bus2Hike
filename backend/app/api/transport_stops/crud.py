from typing import List

from psycopg2.extras import RealDictCursor

from app.db import engine
from .schemas import TransportStopGetDto, FilterParams


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
    dtos = execute_query_and_return_list_of_dtos(LIST_TRANSPORT_STOPS_SQL)
    return dtos

def get_transport_stop_by_filter_params(filter_params: FilterParams) -> List[TransportStopGetDto]:
    params = (
        filter_params.longitude,
        filter_params.latitude,
        filter_params.range_km,
    )
    dtos = execute_query_and_return_list_of_dtos(LIST_ALL_TRANSPORT_STOPS_NEAR_POINT, params)
    print(len(dtos))
    return dtos


def execute_query_and_return_list_of_dtos(query: str, params: tuple = None):
    with engine.connect() as connection:
        raw_conn = connection.connection
        try:
            with raw_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

            dtos = [TransportStopGetDto.from_row(dict(r)) for r in rows]
            return dtos
        except Exception as e:
            raw_conn.rollback()
            raise RuntimeError("Failed to fetch from database: " + str(e))


LIST_ALL_TRANSPORT_STOPS_NEAR_POINT="""
SELECT
    id,
    name,
    created_at,
    ST_AsGeoJSON(geometry)::json AS geometry
FROM transport_stops
WHERE ST_DWithin(
    geometry::geography,
    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
    %s * 1000
)
ORDER BY id;

"""