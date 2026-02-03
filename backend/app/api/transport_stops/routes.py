from typing import List

from fastapi import APIRouter, Depends
from .crud import get_transport_stop_by_filter_params
from .schemas import TransportStopGetDto, FilterParams

router = APIRouter(prefix="/transport-stops", tags=["transport-stops"])


@router.get("")
def list_transport_stops(filter_params: FilterParams = Depends()) -> List[TransportStopGetDto]:
    return get_transport_stop_by_filter_params(filter_params)
