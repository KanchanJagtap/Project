"""
SQLAlchemy 2.0 Model: SignalDecisionModel.
Maps cleanly to ai.traffic.signal_optimizer.SignalDecision.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, UUID_TYPE, utc_now

if TYPE_CHECKING:
    from .junction import Junction, JunctionApproach


class SignalDecisionModel(Base):
    """
    Historical record of signal optimization decisions per junction and approach.
    Directly reflects the SignalDecision contract.
    """
    __tablename__ = "signal_decisions"

    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    junction_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("junctions.junction_id", ondelete="CASCADE"), nullable=False
    )
    approach_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("junction_approaches.approach_id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    green_time: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    is_emergency_override: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    __table_args__ = (
        Index("idx_signals_junction_time", "junction_id", "timestamp"),
        Index("idx_signals_approach_time", "approach_id", "timestamp"),
    )

    # Relationships
    junction: Mapped[Junction] = relationship("Junction", back_populates="signal_decisions")
    approach: Mapped[JunctionApproach] = relationship("JunctionApproach", back_populates="signal_decisions")
