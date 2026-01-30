from psycopg2.extras import RealDictCursor

from .schemas import HikeGetDto
from app.db import engine
def get_all_hikes():
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
                            ST_AsGeoJSON(geometry)::json      AS geometry, ST_AsGeoJSON(start_point)::json   AS start_point, ST_AsGeoJSON(end_point) ::json     AS end_point
                     FROM hiking_trails
                     ORDER BY id \
                     """
    with engine.connect().connection.cursor() as cursor:
        cursor.execute(LIST_HIKES_SQL)
        rows = cursor.fetchall()
        formated_data = [add_column_names_to_row(cursor, r) for r in rows]
        dtos = [HikeGetDto.from_row(d) for d in formated_data]
        return dtos




def add_column_names_to_row(cursor: object, row: tuple[str]) -> dict:
    cols = [desc.name for desc in cursor.description]
    data = dict(zip(cols, row))
    return data