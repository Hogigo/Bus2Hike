from fastapi import APIRouter
from app.api.hikes.routes import router as hikes_router
from app.api.transport_stops.routes import router as transport_stops_router

api_router = APIRouter()
api_router.include_router(hikes_router)
api_router.include_router(transport_stops_router)
