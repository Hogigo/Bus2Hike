from psycopg2.extras import RealDictCursor
from app.find_trails import TrailFinder
from .schemas import HikeGetDto
from app.db import engine


def get_hikes_near_point(longitude: float, latitude: float, range_km: float):
    return []

