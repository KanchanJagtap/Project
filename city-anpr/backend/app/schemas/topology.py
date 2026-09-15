"""
Pydantic v2 Schemas for TopologyEdge.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import Field

from .common import ORMModel


class TopologyEdgeResponse(ORMModel):
    """Schema for a topology edge response."""
    topology_edge_id: uuid.UUID = Field(..., description="Unique topology edge UUID")
    source_junction_id: str = Field(..., description="Source junction ID")
    target_junction_id: str = Field(..., description="Target junction ID")
    distance_meters: float = Field(..., description="Distance between junctions in meters")
    min_travel_time_sec: float = Field(..., description="Minimum allowed travel time in seconds")
    max_travel_time_sec: float = Field(..., description="Maximum allowed travel time in seconds")
    is_active: bool = Field(..., description="Whether this transition is currently active")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")
