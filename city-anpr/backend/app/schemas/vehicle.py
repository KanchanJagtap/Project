"""
Pydantic v2 Schemas for Vehicle, VehicleTrack, PlateObservation, and VehicleHistory.
Kept strictly separate from SQLAlchemy database models and AI contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional
from pydantic import Field

from .common import ORMModel


class VehicleResponse(ORMModel):
    """Schema for a canonical physical vehicle."""
    vehicle_id: uuid.UUID = Field(..., description="Unique canonical vehicle UUID")
    canonical_plate_text: Optional[str] = Field(None, description="Normalized canonical license plate text")
    canonical_vehicle_type: str = Field(..., description="Canonical vehicle classification (car, bus, truck, etc.)")
    first_detected_at: datetime = Field(..., description="First time observed in the city (UTC)")
    last_detected_at: datetime = Field(..., description="Most recent observation timestamp (UTC)")
    total_detections_count: int = Field(..., description="Total detection events across the city")
    is_stolen: bool = Field(default=False, description="Flag indicating vehicle is reported stolen")
    is_wanted: bool = Field(default=False, description="Flag indicating vehicle of law-enforcement interest")
    notes: Optional[str] = Field(None, description="Administrative or alert notes")


class VehicleTrackResponse(ORMModel):
    """Schema for a vehicle tracking session on a single camera."""
    track_session_id: uuid.UUID = Field(..., description="Unique track session UUID")
    vehicle_id: Optional[uuid.UUID] = Field(None, description="Associated canonical vehicle UUID")
    camera_id: str = Field(..., description="Camera ID where track occurred")
    local_track_id: int = Field(..., description="Tracker internal ID (ByteTrack)")
    vehicle_type: str = Field(..., description="Vehicle type identified in track")
    confidence: float = Field(..., description="Current/latest detection confidence")
    best_confidence: Optional[float] = Field(None, description="Highest confidence observed in session")
    first_seen_at: datetime = Field(..., description="First timestamp observed (UTC)")
    last_seen_at: datetime = Field(..., description="Last timestamp observed (UTC)")
    first_seen_frame: int = Field(..., description="First frame number")
    last_seen_frame: int = Field(..., description="Last frame number")
    frames_tracked: int = Field(..., description="Total count of frames tracked")
    last_bbox: List[float] = Field(..., description="Bounding box [x1, y1, x2, y2]")
    center: Optional[List[float]] = Field(None, description="Center coordinate [cx, cy]")
    trajectory_summary: List[Any] = Field(default_factory=list, description="Trajectory coordinate history")
    type_history: List[str] = Field(default_factory=list, description="Classification predictions history")


class PlateObservationResponse(ORMModel):
    """Schema for an individual license plate observation/read."""
    observation_id: uuid.UUID = Field(..., description="Unique observation UUID")
    plate_text: str = Field(..., description="OCR read plate text")
    raw_plate_text: Optional[str] = Field(None, description="Raw unnormalized OCR output")
    camera_id: str = Field(..., description="Camera ID where plate was read")
    track_session_id: Optional[uuid.UUID] = Field(None, description="Associated track session UUID")
    vehicle_id: Optional[uuid.UUID] = Field(None, description="Associated canonical vehicle UUID")
    frame_number: int = Field(..., description="Frame number of detection")
    timestamp: datetime = Field(..., description="Observation timestamp (UTC)")
    detection_confidence: float = Field(..., description="Plate detector confidence")
    ocr_confidence: float = Field(..., description="OCR text recognition confidence")
    association_confidence: Optional[float] = Field(None, description="Plate-to-vehicle association confidence")
    bbox: List[float] = Field(..., description="Plate bounding box [x1, y1, x2, y2]")
    vehicle_bbox: Optional[List[float]] = Field(None, description="Associated vehicle bounding box")
    crop_image_uri: Optional[str] = Field(None, description="URI or path to saved plate crop image")
    ocr_variant: Optional[str] = Field(None, description="OCR preprocessing/engine variant used")
    coordinate_space: str = Field(default="frame", description="Coordinate space (frame or vehicle_crop)")


class VehicleHistoryResponse(ORMModel):
    """Schema for complete vehicle history across cameras."""
    vehicle: VehicleResponse = Field(..., description="Canonical vehicle record")
    tracks: List[VehicleTrackResponse] = Field(default_factory=list, description="Camera tracking sessions")
    plate_observations: List[PlateObservationResponse] = Field(
        default_factory=list, description="License plate detection and OCR reads"
    )
