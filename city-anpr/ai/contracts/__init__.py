"""Shared, dependency-free domain contracts for the City ANPR prototype."""

from .models import (
    BoundingBox,
    Camera,
    Detection,
    Event,
    PlateObservation,
    Point,
    TrackId,
    TrafficSnapshot,
    TrafficLevel,
    TrackedVehicle,
    TRAFFIC_LEVELS,
    VEHICLE_TYPES,
    VehicleType,
)

__all__ = [
    "BoundingBox",
    "Camera",
    "Detection",
    "Event",
    "PlateObservation",
    "Point",
    "TrackId",
    "TrafficSnapshot",
    "TrafficLevel",
    "TrackedVehicle",
    "TRAFFIC_LEVELS",
    "VEHICLE_TYPES",
    "VehicleType",
]
