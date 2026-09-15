"""
Pydantic v2 Schemas for Video Processing Orchestration Service (Milestones 2F/2G).
Kept strictly separated from SQLAlchemy database models and AI domain contracts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ProcessingState(str, Enum):
    """Lifecycle states of a camera processing worker."""

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
    camera_id: str = Field(
        default="cctv-cam-01", description="Identifier of the camera"
    )
    max_frames: Optional[int] = Field(
        default=None,
        ge=1,
        description="Stop processing after N frames (None = entire video)",
    )
    junction_id: Optional[str] = Field(
        default=None,
        description="Optional junction ID for signal decision linkage",
    )
    anpr_every_n_frames: int = Field(
        default=5, ge=1, description="Run ANPR every N frames"
    )


class ProcessingStopRequest(BaseModel):
    """Optional request payload to halt video processing for a specific camera."""

    camera_id: Optional[str] = Field(
        default=None,
        description="Identifier of camera to stop. If omitted and only one camera is active, stops that camera.",
    )


class LatestFrameSnapshot(BaseModel):
    """Immutable snapshot of the most recently processed FrameResult.

    Every field comes directly from FrameResult or its nested contract
    objects.  No values are invented or estimated.

    Source mapping:
    - frame_number          <- FrameResult.frame_number
    - timestamp             <- FrameResult.timestamp
    - processing_time_ms    <- FrameResult.processing_time_ms
    - active_vehicle_count  <- len(FrameResult.tracked_vehicle_contracts)
    - plate_observations_count <- len(FrameResult.plate_observations)
    - plate_texts           <- [p.plate_text for p in FrameResult.plate_observations]
    - traffic_pressure      <- FrameResult.snapshot.traffic_pressure  (if snapshot)
    - traffic_level         <- FrameResult.snapshot.traffic_level     (if snapshot)
    - signal_green_time     <- FrameResult.signal_decisions[0].green_time (if any)
    - signal_reason         <- FrameResult.signal_decisions[0].reason     (if any)
    """

    frame_number: int = Field(
        ..., description="Frame number of the most recently processed frame"
    )
    timestamp: datetime = Field(
        ..., description="Timestamp of the most recently processed frame"
    )
    processing_time_ms: float = Field(
        ..., description="Processing time for this frame in milliseconds"
    )
    active_vehicle_count: int = Field(
        default=0, description="Number of tracked vehicles in this frame"
    )
    plate_observations_count: int = Field(
        default=0, description="Number of plate observations in this frame"
    )
    plate_texts: List[str] = Field(
        default_factory=list, description="Plate texts observed in this frame"
    )
    traffic_pressure: Optional[float] = Field(
        default=None,
        description="Traffic pressure from TrafficSnapshot, if available",
    )
    traffic_level: Optional[str] = Field(
        default=None,
        description="Traffic level from TrafficSnapshot, if available",
    )
    signal_green_time: Optional[int] = Field(
        default=None,
        description="Recommended green time from first SignalDecision, if available",
    )
    signal_reason: Optional[str] = Field(
        default=None, description="Signal decision reason, if available"
    )

    model_config = {"frozen": True}


class ProcessingStatusResponse(BaseModel):
    """Status payload reporting the current state and progress of a camera
    processing worker.

    Fields from 2F are preserved for backward compatibility.
    Fields added in 2G (elapsed_seconds, fps, latest_frame) are optional
    and absent from the 2F default IDLE response.
    """

    state: ProcessingState = Field(
        ..., description="Current lifecycle state of the processing worker"
    )
    source: Optional[str] = Field(
        default=None, description="Video source being processed"
    )
    camera_id: Optional[str] = Field(
        default=None, description="Active camera ID"
    )
    junction_id: Optional[str] = Field(
        default=None, description="Associated junction ID"
    )
    processed_frames: int = Field(
        default=0, ge=0, description="Number of video frames processed so far"
    )
    max_frames: Optional[int] = Field(
        default=None,
        description="Maximum frames limit for the job, if configured",
    )
    started_at: Optional[datetime] = Field(
        default=None, description="Timestamp when processing job started"
    )
    finished_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when processing job reached a terminal state",
    )
    error: Optional[str] = Field(
        default=None, description="Error message if the processing job failed"
    )
    # 2G runtime fields -------------------------------------------------------
    elapsed_seconds: Optional[float] = Field(
        default=None,
        description="Elapsed processing time in seconds, computed from started_at",
    )
    fps: Optional[float] = Field(
        default=None,
        description=(
            "Effective processing frames per second "
            "(processed_frames / elapsed_seconds)"
        ),
    )
    latest_frame: Optional[LatestFrameSnapshot] = Field(
        default=None,
        description="Snapshot of the most recently processed frame",
    )


class CamerasListResponse(BaseModel):
    """Response listing all registered camera processing workers."""

    cameras: List[ProcessingStatusResponse] = Field(
        default_factory=list,
        description="List of all camera processing statuses",
    )
    active_count: int = Field(
        default=0,
        description=(
            "Number of cameras currently in an active state "
            "(STARTING, RUNNING, STOPPING)"
        ),
    )
