from psycopg2.extras import RealDictCursor

from .schemas import HikeGetDto
from app.db import engine
def get_all_hikes():
    dtos = execute_query_and_return_list_of_dtos(LIST_HIKES_SQL)
    return dtos




def get_hikes_near_point(longitude: float, latitude: float, range_km: float):
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError("longitude must be between -180 and 180")
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError("latitude must be between -90 and 90")
    if range_km <= 0:
        raise ValueError("range_km must be > 0")

    params = (longitude, latitude, range_km, range_km)

    dtos = execute_query_and_return_list_of_dtos(LIST_HIKES_NEAR_POINT_SQL, params)
    return dtos


def execute_query_and_return_list_of_dtos(query: str, params: tuple = None):
    with engine.connect() as connection:
        raw_conn = connection.connection
        try:
            with raw_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

            dtos = [HikeGetDto.from_row(dict(r)) for r in rows]
            return dtos
        except Exception as e:
            raw_conn.rollback()
            raise RuntimeError("Failed to fetch from database: " + str(e))


LIST_HIKES_NEAR_POINT_SQL = """
                                SELECT ht.id, \
                                       ht.odh_id, \
                                       ht.difficulty, \
                                       ht.length_km, \
                                       ht.duration_minutes, \
                                       ht.elevation_gain_m, \
                                       ht.elevation_loss_m, \
                                       ht.description, \
                                       ht.circular, \
                                       ht.created_at, \
                                       ht.updated_at, \
                                       ST_AsGeoJSON(ht.geometry)::json    AS geometry, \
                                       ST_AsGeoJSON(ht.start_point)::json AS start_point, \
                                       ST_AsGeoJSON(ht.end_point)::json   AS end_point, \
                                       LEAST( \
                                               ST_Distance(ht.start_point::geography, q.pt), \
                                               ST_Distance(ht.end_point::geography, q.pt) \
                                       )                                  AS start_point_distance_from_selected_point
                                FROM hiking_trails ht
                                         CROSS JOIN (SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography AS pt) q
                                WHERE ST_DWithin(ht.start_point::geography, q.pt, %s * 1000)
                                   OR ST_DWithin(ht.end_point::geography, q.pt, %s * 1000)
                                ORDER BY start_point_distance_from_selected_point; \
                                """

LIST_HIKES_SQL = """
                 SELECT id, \
                        odh_id, \
                        difficulty, \
                        length_km, \
                        duration_minutes, \
                        elevation_gain_m, \
                        elevation_loss_m, \
                        description, \
                        circular, \
                        created_at, \
                        updated_at, \
                        ST_AsGeoJSON(geometry)::json    AS geometry, \
                        ST_AsGeoJSON(start_point)::json AS start_point, \
                        ST_AsGeoJSON(end_point) ::json  AS end_point
                 FROM hiking_trails
                 ORDER BY id \
                 """