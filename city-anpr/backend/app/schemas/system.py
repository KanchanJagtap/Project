"""
Pydantic v2 Schemas for System Health & Readiness Inspection (Milestone 2H).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    """Health status of an individual system component."""

    status: str = Field(..., description="Component status: 'ok', 'degraded', or 'error'")
    message: Optional[str] = Field(default=None, description="Diagnostic detail or error message")


class SystemHealthResponse(BaseModel):
    """System-wide health and readiness report for dashboard consumption."""

    status: str = Field(..., description="Overall system health: 'healthy' or 'unhealthy'")
    database: ComponentHealth = Field(..., description="PostgreSQL database connectivity status")
    models: ComponentHealth = Field(..., description="AI model weights filesystem accessibility")
    active_workers: int = Field(default=0, ge=0, description="Number of currently running camera workers")
    timestamp: datetime = Field(..., description="Timestamp of the health check evaluation")
