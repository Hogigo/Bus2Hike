from fastapi import APIRouter
from .crud import get_all_transport_stops
from .schemas import TransportStopGetDto

router = APIRouter(prefix="/transport-stops", tags=["transport-stops"])


@router.get("", response_model=list[TransportStopGetDto])
def list_transport_stops():
    return get_all_transport_stops()
