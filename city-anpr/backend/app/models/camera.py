"""
SQLAlchemy 2.0 Model: Camera.
Maps cleanly to ai.contracts.models.Camera.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, JSON_TYPE, utc_now

if TYPE_CHECKING:
    from .junction import JunctionApproach
    from .observation import PlateObservationModel
    from .tracking import VehicleTrack
    from .traffic import TrafficSnapshotModel


class CameraModel(Base):
    """
    Physical CCTV camera stream registration and vision calibration.
    """
    __tablename__ = "cameras"

    camera_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    resolution_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    queue_roi: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    lane_configuration: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    direction_configuration: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    approach: Mapped[Optional[JunctionApproach]] = relationship(
        "JunctionApproach", back_populates="camera", uselist=False
    )
    tracks: Mapped[List[VehicleTrack]] = relationship(
        "VehicleTrack", back_populates="camera", cascade="all, delete-orphan"
    )
    plate_observations: Mapped[List[PlateObservationModel]] = relationship(
        "PlateObservationModel", back_populates="camera", cascade="all, delete-orphan"
    )
    snapshots: Mapped[List[TrafficSnapshotModel]] = relationship(
        "TrafficSnapshotModel", back_populates="camera", cascade="all, delete-orphan"
    )
