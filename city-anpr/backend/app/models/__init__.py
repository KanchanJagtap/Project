"""
SQLAlchemy Models Package.
Exports all 8 foundational database entities.
"""

from .camera import CameraModel
from .junction import Junction, JunctionApproach
from .observation import PlateObservationModel
from .signal import SignalDecisionModel
from .tracking import VehicleTrack
from .traffic import TrafficSnapshotModel
from .topology import TopologyEdge
from .vehicle import Vehicle

__all__ = [
    "Junction",
    "JunctionApproach",
    "CameraModel",
    "Vehicle",
    "VehicleTrack",
    "PlateObservationModel",
    "TrafficSnapshotModel",
    "SignalDecisionModel",
    "TopologyEdge",
]
