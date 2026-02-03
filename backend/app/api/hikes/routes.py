from typing import Optional, List
from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel
from app.find_trails import find_trails
import json

from .schemas import TrailFilterParams

router = APIRouter(prefix="/hikes", tags=["hikes"])



@router.get("")
def list_hikes(filter_params: TrailFilterParams = Depends()):
    trails = find_trails(filter_params.latitude,
                         filter_params.longitude,
                         filter_params.diameter,
                         filter_params.max_distance,
                         filter_params.max_paths)
    return json.loads(trails)




