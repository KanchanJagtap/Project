"""
Schemas Package.
Exports all Pydantic v2 API response and request models.
"""

from .camera import CameraApproachInfo, CameraResponse
from .common import BoundingBoxSchema, ORMModel, PaginatedResponse, TimeRangeFilter
from .junction import JunctionApproachResponse, JunctionResponse
from .signal import SignalDecisionResponse
from .traffic import TrafficSnapshotResponse
from .vehicle import (
    PlateObservationResponse,
    VehicleHistoryResponse,
    VehicleResponse,
    VehicleTrackResponse,
)

__all__ = [
    "ORMModel",
    "PaginatedResponse",
    "BoundingBoxSchema",
    "TimeRangeFilter",
    "JunctionResponse",
    "JunctionApproachResponse",
    "CameraResponse",
    "CameraApproachInfo",
    "VehicleResponse",
    "VehicleTrackResponse",
    "PlateObservationResponse",
    "VehicleHistoryResponse",
    "TrafficSnapshotResponse",
    "SignalDecisionResponse",
]
