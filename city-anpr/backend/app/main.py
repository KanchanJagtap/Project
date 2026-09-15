"""
FastAPI Application Entry Point.
City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking and Urban Traffic Analytics.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.api import api_router
from backend.app.core.config import settings

app = FastAPI(
    title="City-Wide ANPR & Traffic Analytics Engine",
    description=(
        "Production REST API for real-time CCTV ANPR vehicle tracking, "
        "queue detection, traffic pressure analytics, and adaptive signal timing."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Cross-Origin Resource Sharing (CORS) Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    summary="Root Health Check",
    tags=["Health"],
)
async def health_check() -> dict:
    """Return health status of the backend application."""
    return {"status": "ok"}


# Mount the API router under /api
app.include_router(api_router, prefix="/api")
