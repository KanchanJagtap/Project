"""
Pydantic v2 Schemas for Video Processing Orchestration Service (Milestone 2F).
Kept strictly separated from SQLAlchemy database models and AI domain contracts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ProcessingState(str, Enum):
    """Lifecycle states of the background processing service."""
    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProcessingStartRequest(BaseModel):
    """Request payload to initiate a background video processing run."""
    source: str = Field(..., description="Path to CCTV video file or stream source")
    camera_id: str = Field(default="cctv-cam-01", description="Identifier of the camera")
    max_frames: Optional[int] = Field(default=None, ge=1, description="Stop processing after N frames (None = entire video)")
    junction_id: Optional[str] = Field(default=None, description="Optional junction ID for signal decision linkage")
    anpr_every_n_frames: int = Field(default=5, ge=1, description="Run ANPR every N frames")


class ProcessingStatusResponse(BaseModel):
    """Status payload reporting the current state and progress of the processing service."""
    state: ProcessingState = Field(..., description="Current lifecycle state of the processing service")
    source: Optional[str] = Field(default=None, description="Video source being processed")
    camera_id: Optional[str] = Field(default=None, description="Active camera ID")
    junction_id: Optional[str] = Field(default=None, description="Associated junction ID")
    processed_frames: int = Field(default=0, ge=0, description="Number of video frames processed so far")
    max_frames: Optional[int] = Field(default=None, description="Maximum frames limit for the job, if configured")
    started_at: Optional[datetime] = Field(default=None, description="Timestamp when processing job started")
    finished_at: Optional[datetime] = Field(default=None, description="Timestamp when processing job reached a terminal state")
    error: Optional[str] = Field(default=None, description="Error message if the processing job failed")
