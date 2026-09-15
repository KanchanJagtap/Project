"""
Pydantic v2 Schemas for SignalDecision.
Kept strictly separate from SQLAlchemy database models and AI contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import Field

from .common import ORMModel


class SignalDecisionResponse(ORMModel):
    """Schema for persisted adaptive signal timing decision."""
    decision_id: uuid.UUID = Field(..., description="Unique decision UUID")
    junction_id: str = Field(..., description="Junction ID where decision applies")
    approach_id: str = Field(..., description="Specific approach receiving the decision")
    timestamp: datetime = Field(..., description="Decision timestamp (UTC)")
    priority_score: float = Field(..., description="Calculated priority score")
    green_time: int = Field(..., description="Allocated green time in seconds")
    reason: str = Field(..., description="Algorithmic rationale for allocation")
    is_emergency_override: bool = Field(default=False, description="Flag indicating emergency vehicle override")
