from fastapi import APIRouter, Depends
from app.find_trails import find_trails
import json

from .schemas import TrailFilterParams
from app.generate_ai_description import generate_description
router = APIRouter(prefix="/hikes", tags=["hikes"])



@router.get("")
def list_hikes(filter_params: TrailFilterParams = Depends()):
    trails = find_trails(filter_params.latitude,
                         filter_params.longitude,
                         filter_params.diameter,
                         filter_params.max_distance,
                         filter_params.max_paths)
    generate_description(trails)
    return json.loads(trails)




