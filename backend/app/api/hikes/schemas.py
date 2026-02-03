from fastapi import Query
from pydantic import BaseModel

class TrailFilterParams(BaseModel):
    latitude: float = Query(..., ge=-90, le=90)
    longitude: float = Query(..., ge=-180, le=180)

    diameter: float = Query(
        default=10.0,
        gt=0,
        description="Search diameter in kilometers"
    )

    max_distance: float = Query(
        default=10.0,
        gt=0,
        description="Maximum trail length in kilometers"
    )

    max_paths: int = Query(
        default=5,
        gt=0,
        le=100,
        description="Maximum number of trails to return"
    )