"""
SQLAlchemy 2.0 Model: PlateObservationModel (Individual ANPR Read).
Maps to ai.contracts.models.PlateObservation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, JSON_TYPE, UUID_TYPE, utc_now

if TYPE_CHECKING:
    from .camera import CameraModel
    from .tracking import VehicleTrack
    from .vehicle import Vehicle


class PlateObservationModel(Base):
    """
    Individual license-plate detection and OCR observation from one camera frame.
    May be associated with a local vehicle_track, or unassociated.
    """
    __tablename__ = "plate_observations"

    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    plate_text: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_plate_text: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    camera_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False
    )
    track_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID_TYPE, ForeignKey("vehicle_tracks.track_session_id", ondelete="SET NULL"), nullable=True
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID_TYPE, ForeignKey("vehicles.vehicle_id", ondelete="SET NULL"), nullable=True
    )
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    detection_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    association_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox: Mapped[List[float]] = mapped_column(JSON_TYPE, nullable=False)
    vehicle_bbox: Mapped[Optional[List[float]]] = mapped_column(JSON_TYPE, nullable=True)
    crop_image_uri: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ocr_variant: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    coordinate_space: Mapped[str] = mapped_column(String(32), default="frame", nullable=False)

    __table_args__ = (
        Index("idx_plate_obs_plate_text", "plate_text"),
        Index("idx_plate_obs_camera_time", "camera_id", "timestamp"),
        Index("idx_plate_obs_track_session", "track_session_id"),
        Index("idx_plate_obs_vehicle_id", "vehicle_id"),
    )

    # Relationships
    camera: Mapped[CameraModel] = relationship("CameraModel", back_populates="plate_observations")
    track: Mapped[Optional[VehicleTrack]] = relationship(
        "VehicleTrack", back_populates="plate_observations"
    )
    vehicle: Mapped[Optional[Vehicle]] = relationship(
        "Vehicle", back_populates="plate_observations"
    )
