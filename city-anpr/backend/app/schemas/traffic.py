"""
Pydantic v2 Schemas for TrafficSnapshot.
Kept strictly separate from SQLAlchemy database models and AI contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import Field

from .common import ORMModel


class TrafficSnapshotResponse(ORMModel):
    """Schema for persisted traffic density and queue metrics."""
    snapshot_id: uuid.UUID = Field(..., description="Unique snapshot UUID")
    camera_id: str = Field(..., description="Camera ID where metrics were computed")
    timestamp: datetime = Field(..., description="Snapshot timestamp (UTC)")
    frame_number: Optional[int] = Field(None, description="Video frame number")
    active_vehicle_count: int = Field(..., description="Total active vehicles in scene")
    queue_length: int = Field(..., description="Vehicles detected waiting in queue")
    moving_vehicles: int = Field(..., description="Vehicles actively moving")
    slow_vehicles: int = Field(..., description="Vehicles moving slowly")
    stationary_vehicles: int = Field(..., description="Stationary vehicles")
    traffic_pressure: float = Field(..., description="Calculated traffic pressure score (0.0 to 1.0+)")
    traffic_level: str = Field(..., description="Categorical traffic level (LOW, MEDIUM, HIGH, CRITICAL)")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Detailed component metrics")
