"""
Pydantic v2 Schemas for Camera.
Kept strictly separate from SQLAlchemy database models and AI contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field

from .common import ORMModel


class CameraApproachInfo(ORMModel):
    """Brief summary of the junction approach monitored by a camera."""
    approach_id: str = Field(..., description="Approach ID")
    junction_id: str = Field(..., description="Parent junction ID")
    direction_name: str = Field(..., description="Direction name (e.g. Northbound Entry)")
    cardinal_direction: Optional[str] = Field(None, description="Cardinal direction")


class CameraResponse(ORMModel):
    """Schema for camera registration and calibration metadata."""
    camera_id: str = Field(..., description="Unique camera identifier")
    source: str = Field(..., description="Video stream source URI or path")
    name: Optional[str] = Field(None, description="Human-readable camera name")
    resolution_width: Optional[int] = Field(None, description="Video width in pixels")
    resolution_height: Optional[int] = Field(None, description="Video height in pixels")
    fps: Optional[float] = Field(None, description="Stream frames per second")
    queue_roi: Optional[Dict[str, Any]] = Field(None, description="Queue region of interest polygon")
    lane_configuration: List[Dict[str, Any]] = Field(
        default_factory=list, description="Configured traffic lanes"
    )
    direction_configuration: List[Dict[str, Any]] = Field(
        default_factory=list, description="Configured entry/exit directions"
    )
    enabled: bool = Field(default=True, description="Whether camera stream is active")
    created_at: datetime = Field(..., description="Registration timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")
    approach: Optional[CameraApproachInfo] = Field(
        None, description="Associated junction approach if assigned"
    )
