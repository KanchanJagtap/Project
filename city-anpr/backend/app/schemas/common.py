"""
Common Pydantic v2 Schemas for API Layer.
Kept strictly separated from SQLAlchemy database models and AI domain contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, List, Optional, Tuple, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base Pydantic schema configured for SQLAlchemy ORM compatibility."""
    model_config = ConfigDict(from_attributes=True)


BoundingBoxSchema = Tuple[float, float, float, float]


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic pagination wrapper for list endpoints."""
    items: List[T]
    total: int = Field(ge=0, description="Total count of matching records")
    page: int = Field(ge=1, default=1, description="Current page number")
    size: int = Field(ge=1, le=100, default=20, description="Page size limit")


class TimeRangeFilter(BaseModel):
    """Common time range query parameters."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
