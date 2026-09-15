"""
Pydantic v2 Schemas for Junction and JunctionApproach.
Kept strictly separate from SQLAlchemy database models and AI contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import Field

from .common import ORMModel


class JunctionApproachResponse(ORMModel):
    """Schema for a single junction approach."""
    approach_id: str = Field(..., description="Unique approach identifier")
    junction_id: str = Field(..., description="Foreign key to parent junction")
    camera_id: Optional[str] = Field(None, description="Monitored camera ID if assigned")
    direction_name: str = Field(..., description="Human-readable direction (e.g., Northbound)")
    cardinal_direction: Optional[str] = Field(None, description="Cardinal direction (N, S, E, W, etc.)")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")


class JunctionResponse(ORMModel):
    """Schema for a junction with its constituent approaches."""
    junction_id: str = Field(..., description="Unique junction identifier")
    name: str = Field(..., description="Descriptive junction name")
    latitude: Optional[float] = Field(None, description="GPS latitude coordinate")
    longitude: Optional[float] = Field(None, description="GPS longitude coordinate")
    target_cycle_seconds: int = Field(default=120, description="Target total signal cycle time in seconds")
    min_green_seconds: int = Field(default=20, description="Minimum green time limit per phase")
    max_green_seconds: int = Field(default=60, description="Maximum green time limit per phase")
    status: str = Field(default="NORMAL", description="Junction status (e.g., NORMAL, CONGESTED, EMERGENCY)")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")
    approaches: List[JunctionApproachResponse] = Field(
        default_factory=list, description="List of directional approaches for this junction"
    )
