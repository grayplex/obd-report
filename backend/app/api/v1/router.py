from fastapi import APIRouter

from app.api.v1 import upload, trips, telemetry

api_router = APIRouter()

api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(trips.router, prefix="/trips", tags=["trips"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
