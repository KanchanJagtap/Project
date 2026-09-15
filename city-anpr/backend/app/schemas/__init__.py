"""
Schemas Package.
Exports all Pydantic v2 API response and request models.
"""

from .camera import CameraApproachInfo, CameraResponse
from .common import BoundingBoxSchema, ORMModel, PaginatedResponse, TimeRangeFilter
from .junction import JunctionApproachResponse, JunctionResponse
from .processing import (
    CamerasListResponse,
    LatestFrameSnapshot,
    ProcessingOverviewResponse,
    ProcessingStartRequest,
    ProcessingState,
    ProcessingStatusResponse,
    ProcessingStopRequest,
)
from .signal import SignalDecisionResponse
from .system import ComponentHealth, SystemHealthResponse
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
    "ProcessingState",
    "ProcessingStartRequest",
    "ProcessingStopRequest",
    "ProcessingStatusResponse",
    "LatestFrameSnapshot",
    "CamerasListResponse",
    "ProcessingOverviewResponse",
    "ComponentHealth",
    "SystemHealthResponse",
]
from .topology import TopologyEdgeResponse
__all__.append("TopologyEdgeResponse")
