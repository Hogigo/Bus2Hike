from fastapi import APIRouter
from app.api.hikes.routes import router as hikes_router

api_router = APIRouter()
api_router.include_router(hikes_router)
