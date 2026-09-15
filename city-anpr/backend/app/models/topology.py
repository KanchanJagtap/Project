"""
SQLAlchemy 2.0 Model: TopologyEdge.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, UUID_TYPE, utc_now

if TYPE_CHECKING:
    from .junction import Junction


class TopologyEdge(Base):
    """
    Physical road-network transition constraint between two junctions.
    """
    __tablename__ = "topology_edges"

    topology_edge_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    source_junction_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("junctions.junction_id", ondelete="CASCADE"), nullable=False
    )
    target_junction_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("junctions.junction_id", ondelete="CASCADE"), nullable=False
    )
    distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    min_travel_time_sec: Mapped[float] = mapped_column(Float, nullable=False)
    max_travel_time_sec: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint("source_junction_id != target_junction_id", name="ck_topology_no_self_loop"),
        CheckConstraint("distance_meters > 0", name="ck_topology_dist_positive"),
        CheckConstraint("min_travel_time_sec > 0", name="ck_topology_min_time_positive"),
        CheckConstraint("max_travel_time_sec >= min_travel_time_sec", name="ck_topology_max_time_valid"),
        Index("idx_topology_source_target_active", "source_junction_id", "target_junction_id", "is_active"),
    )

    # Relationships
    source_junction: Mapped[Junction] = relationship(
        "Junction", foreign_keys=[source_junction_id], back_populates="outgoing_edges"
    )
    target_junction: Mapped[Junction] = relationship(
        "Junction", foreign_keys=[target_junction_id], back_populates="incoming_edges"
    )
