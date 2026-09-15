"""
SQLAlchemy 2.0 Model: Junction and JunctionApproach.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, utc_now

if TYPE_CHECKING:
    from .camera import CameraModel
    from .signal import SignalDecisionModel
    from .topology import TopologyEdge


class Junction(Base):
    """
    Physical intersection/junction where multiple approaches converge.
    """
    __tablename__ = "junctions"

    junction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_cycle_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    min_green_seconds: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_green_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="NORMAL", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    approaches: Mapped[List[JunctionApproach]] = relationship(
        "JunctionApproach",
        back_populates="junction",
        cascade="all, delete-orphan",
        order_by="JunctionApproach.approach_id",
    )
    signal_decisions: Mapped[List[SignalDecisionModel]] = relationship(
        "SignalDecisionModel",
        back_populates="junction",
        cascade="all, delete-orphan",
    )
    outgoing_edges: Mapped[List[TopologyEdge]] = relationship(
        "TopologyEdge",
        foreign_keys="[TopologyEdge.source_junction_id]",
        back_populates="source_junction",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[List[TopologyEdge]] = relationship(
        "TopologyEdge",
        foreign_keys="[TopologyEdge.target_junction_id]",
        back_populates="target_junction",
        cascade="all, delete-orphan",
    )


class JunctionApproach(Base):
    """
    Specific directional approach belonging to a junction, monitored by a camera.
    """
    __tablename__ = "junction_approaches"

    approach_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    junction_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("junctions.junction_id", ondelete="CASCADE"), nullable=False
    )
    camera_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("cameras.camera_id", ondelete="SET NULL"), unique=True, nullable=True
    )
    direction_name: Mapped[str] = mapped_column(String(64), nullable=False)
    cardinal_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    junction: Mapped[Junction] = relationship("Junction", back_populates="approaches")
    camera: Mapped[Optional[CameraModel]] = relationship(
        "CameraModel", back_populates="approach"
    )
    signal_decisions: Mapped[List[SignalDecisionModel]] = relationship(
        "SignalDecisionModel", back_populates="approach"
    )
