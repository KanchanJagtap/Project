"""
SQLAlchemy 2.0 Model: Vehicle (Canonical Physical Identity).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, UUID_TYPE, utc_now

if TYPE_CHECKING:
    from .observation import PlateObservationModel
    from .tracking import VehicleTrack


class Vehicle(Base):
    """
    Canonical physical vehicle identity in the city.
    One vehicle can be observed across multiple cameras and track sessions.
    canonical_plate_text is nullable (e.g. unread or missing plates).
    Partial unique index ensures only non-null plates are unique.
    """
    __tablename__ = "vehicles"

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    canonical_plate_text: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )
    canonical_vehicle_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    total_detections_count: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    is_stolen: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_wanted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )

    __table_args__ = (
        # Partial unique index: only non-null canonical plates are enforced unique
        Index(
            "uq_vehicles_canonical_plate",
            "canonical_plate_text",
            unique=True,
            postgresql_where=text("canonical_plate_text IS NOT NULL"),
            sqlite_where=text("canonical_plate_text IS NOT NULL"),
        ),
        Index("idx_vehicles_last_detected", "last_detected_at"),
    )

    # Relationships
    tracks: Mapped[List[VehicleTrack]] = relationship(
        "VehicleTrack", back_populates="vehicle"
    )
    plate_observations: Mapped[List[PlateObservationModel]] = relationship(
        "PlateObservationModel", back_populates="vehicle"
    )
