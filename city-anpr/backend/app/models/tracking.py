"""
SQLAlchemy 2.0 Model: VehicleTrack (Local Camera Tracking Session).
Maps to ai.contracts.models.TrackedVehicle.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import ARRAY_FLOAT_TYPE, ARRAY_STR_TYPE, Base, JSON_TYPE, UUID_TYPE, utc_now

if TYPE_CHECKING:
    from .camera import CameraModel
    from .observation import PlateObservationModel
    from .vehicle import Vehicle


class VehicleTrack(Base):
    """
    Continuous tracking session of a vehicle within a single camera's field of view.
    Corresponds directly to ByteTrack track sessions.
    """
    __tablename__ = "vehicle_tracks"

    track_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID_TYPE, ForeignKey("vehicles.vehicle_id", ondelete="SET NULL"), nullable=True
    )
    camera_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False
    )
    local_track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    best_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    first_seen_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    frames_tracked: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_bbox: Mapped[List[float]] = mapped_column(JSON_TYPE, nullable=False)
    center: Mapped[Optional[List[float]]] = mapped_column(JSON_TYPE, nullable=True)
    trajectory_summary: Mapped[List[Any]] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    type_history: Mapped[List[str]] = mapped_column(
        ARRAY_STR_TYPE, default=list, nullable=False
    )
    appearance_embedding: Mapped[Optional[List[float]]] = mapped_column(
        ARRAY_FLOAT_TYPE, nullable=True
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    embedding_dimension: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    embedding_quality: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    __table_args__ = (
        Index("idx_tracks_camera_time", "camera_id", "last_seen_at"),
        Index("idx_tracks_vehicle_id", "vehicle_id"),
        Index("idx_tracks_local_active", "camera_id", "local_track_id", "last_seen_frame"),
    )

    # Relationships
    vehicle: Mapped[Optional[Vehicle]] = relationship("Vehicle", back_populates="tracks")
    camera: Mapped[CameraModel] = relationship("CameraModel", back_populates="tracks")
    plate_observations: Mapped[List[PlateObservationModel]] = relationship(
        "PlateObservationModel", back_populates="track"
    )

    # Helper properties for API response enrichment
    @property
    def camera_name(self) -> Optional[str]:
        return self.camera.name if self.camera else None

    @property
    def junction_id(self) -> Optional[str]:
        if self.camera and self.camera.approach:
            return self.camera.approach.junction_id
        return None

    @property
    def junction_name(self) -> Optional[str]:
        if self.camera and self.camera.approach and self.camera.approach.junction:
            return self.camera.approach.junction.name
        return None
