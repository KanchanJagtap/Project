"""
SQLAlchemy 2.0 Model: TrafficSnapshotModel.
Maps cleanly to ai.contracts.models.TrafficSnapshot.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, JSON_TYPE, UUID_TYPE, utc_now

if TYPE_CHECKING:
    from .camera import CameraModel


class TrafficSnapshotModel(Base):
    """
    Traffic metrics calculated for one camera at a point in time.
    Directly reflects the TrafficSnapshot contract.
    """
    __tablename__ = "traffic_snapshots"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    frame_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active_vehicle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    queue_length: Mapped[int] = mapped_column(Integer, nullable=False)
    moving_vehicles: Mapped[int] = mapped_column(Integer, nullable=False)
    slow_vehicles: Mapped[int] = mapped_column(Integer, nullable=False)
    stationary_vehicles: Mapped[int] = mapped_column(Integer, nullable=False)
    traffic_pressure: Mapped[float] = mapped_column(Float, nullable=False)
    traffic_level: Mapped[str] = mapped_column(String(16), nullable=False)
    metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON_TYPE, default=dict, nullable=False
    )

    __table_args__ = (
        Index("idx_snapshots_camera_time", "camera_id", "timestamp"),
        Index("idx_snapshots_level", "traffic_level"),
    )

    # Relationships
    camera: Mapped[CameraModel] = relationship("CameraModel", back_populates="snapshots")
