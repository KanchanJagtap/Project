"""
Main API Router.
Mounts all domain endpoint routers under /api.
"""

from fastapi import APIRouter

from backend.app.api.endpoints import (
    cameras,
    junctions,
    processing,
    signals,
    traffic,
    vehicles,
)

api_router = APIRouter()

api_router.include_router(junctions.router, prefix="/junctions", tags=["Junctions"])
api_router.include_router(cameras.router, prefix="/cameras", tags=["Cameras"])
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["Vehicles"])
api_router.include_router(traffic.router, prefix="/traffic", tags=["Traffic"])
api_router.include_router(signals.router, prefix="/signals", tags=["Signals"])
api_router.include_router(processing.router, prefix="/processing", tags=["Processing"])



@api_router.get(
    "/health",
    summary="API Health Check",
    tags=["Health"],
)
async def api_health() -> dict:
    """Sub-router health check."""
    return {"status": "ok"}
