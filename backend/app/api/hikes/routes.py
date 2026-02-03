from typing import Optional, List
from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel

from  .crud import *
from .schemas import HikeGetDto

router = APIRouter(prefix="/hikes", tags=["hikes"])

class FilterParams(BaseModel):
    longitude: Optional[float] = Query(default=None, ge=-180, le=180)
    latitude: Optional[float] = Query(default=None, ge=-90, le=90)
    range_km: Optional[float] = Query(default=None, gt=0)

    def all_query_params_missing(self) -> bool:
        all_values = self.model_dump().values()
        return all(value is None for value in all_values)

    def all_query_params_present(self) -> bool:
        all_values = self.model_dump().values()
        return all(v is not None for v in all_values)


@router.get("")
def list_hikes(filter_params: FilterParams = Depends()) -> List[HikeGetDto]:
    if filter_params.all_query_params_present():
        return get_hikes_near_point(filter_params.longitude, filter_params.latitude, filter_params.range_km)
    raise HTTPException(
        status_code=400,
        detail="Provide either all query parameters (longitude, latitude, range_km) or none."
    )




