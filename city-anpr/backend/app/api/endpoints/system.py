"""
System Health & Readiness Endpoints (Milestone 2H).
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.schemas.system import ComponentHealth, SystemHealthResponse
from backend.app.services.processing_service import (
    DEFAULT_PLATE_PATH,
    DEFAULT_TRACKER_PATH,
    ProcessingService,
    get_processing_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=SystemHealthResponse,
    summary="System Health & Readiness Inspection",
    description="Inspect overall system health including PostgreSQL connectivity, model weights file accessibility, and active camera worker count.",
)
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    service: ProcessingService = Depends(get_processing_service),
) -> SystemHealthResponse:
    """Evaluate deep system readiness and component health without loading heavy AI models."""
    now = datetime.now(timezone.utc)

    # 1. Database check: execute lightweight SELECT 1
    db_health: ComponentHealth
    try:
        await db.execute(text("SELECT 1"))
        db_health = ComponentHealth(status="ok", message="Database connection active")
    except Exception as exc:
        logger.error("System health check: database connection failed: %s", exc)
        db_health = ComponentHealth(status="error", message=f"Database unreachable: {exc}")

    # 2. Model weights check: verify files exist and are readable on disk
    models_health: ComponentHealth
    missing_models = []
    tracker_path = Path(DEFAULT_TRACKER_PATH)
    if not (tracker_path.exists() and os.access(tracker_path, os.R_OK)):
        missing_models.append(f"Tracker ({tracker_path.name})")

    plate_path = Path(DEFAULT_PLATE_PATH)
    if not (plate_path.exists() and os.access(plate_path, os.R_OK)):
        missing_models.append(f"Plate ({plate_path.name})")

    if missing_models:
        models_health = ComponentHealth(
            status="error",
            message=f"Missing or unreadable model weights: {', '.join(missing_models)}",
        )
    else:
        models_health = ComponentHealth(
            status="ok",
            message="All model weights verified on disk",
        )

    # 3. Active camera workers count
    cameras_info = service.get_all_cameras()
    active_workers = cameras_info.active_count

    # Overall health determination
    is_healthy = db_health.status == "ok" and models_health.status == "ok"
    overall_status = "healthy" if is_healthy else "unhealthy"

    return SystemHealthResponse(
        status=overall_status,
        database=db_health,
        models=models_health,
        active_workers=active_workers,
        timestamp=now,
    )
