"""Common domain records shared by vision, traffic, API, and UI layers.

The contracts deliberately use standard-library dataclasses.  They are easy to
construct in prototype scripts and can later be adapted to API or persistence
models without coupling the vision pipeline to a web framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple, Union


VehicleType = Literal["motorcycle", "car", "auto", "bus", "truck"]
VEHICLE_TYPES = frozenset({"motorcycle", "car", "auto", "bus", "truck"})
TrafficLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
TRAFFIC_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})

BoundingBox = Tuple[float, float, float, float]
Point = Tuple[float, float]
TrackId = Union[int, str]


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for contract defaults."""

    return datetime.now(timezone.utc)


def _validate_vehicle_type(vehicle_type: str) -> str:
    if vehicle_type not in VEHICLE_TYPES:
        allowed = ", ".join(sorted(VEHICLE_TYPES))
        raise ValueError(
            f"Unsupported vehicle_type {vehicle_type!r}; expected one of: {allowed}."
        )
    return vehicle_type


def _normalize_bbox(bbox: BoundingBox) -> BoundingBox:
    if len(bbox) != 4:
        raise ValueError("bbox must contain exactly four values: (x1, y1, x2, y2).")

    x1, y1, x2, y2 = (float(value) for value in bbox)
    if x2 < x1 or y2 < y1:
        raise ValueError("bbox must satisfy x2 >= x1 and y2 >= y1.")
    return x1, y1, x2, y2


def _validate_confidence(confidence: float, field_name: str = "confidence") -> float:
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0.")
    return confidence


def _validate_traffic_level(traffic_level: str) -> str:
    if traffic_level not in TRAFFIC_LEVELS:
        allowed = ", ".join(sorted(TRAFFIC_LEVELS))
        raise ValueError(
            f"Unsupported traffic_level {traffic_level!r}; expected one of: {allowed}."
        )
    return traffic_level


@dataclass
class Detection:
    """A single vehicle detection from one camera frame."""

    vehicle_type: VehicleType
    bbox: BoundingBox
    confidence: float
    timestamp: datetime = field(default_factory=utc_now)
    frame_number: Optional[int] = None
    camera_id: Optional[str] = None

    def __post_init__(self) -> None:
        self.vehicle_type = _validate_vehicle_type(self.vehicle_type)  # type: ignore[assignment]
        self.bbox = _normalize_bbox(self.bbox)
        self.confidence = _validate_confidence(self.confidence)



@dataclass
class AppearanceEmbedding:
    vector: List[float]
    model_name: str
    dimension: int
    quality_score: Optional[float] = None

    def __post_init__(self) -> None:
        if self.dimension <= 0:
            raise ValueError("dimension must be positive")
        if len(self.vector) != self.dimension:
            raise ValueError(f"vector length {len(self.vector)} must match dimension {self.dimension}")

@dataclass
class TrackedVehicle:
    """The current state and trajectory of a persistent vehicle track."""

    track_id: TrackId
    vehicle_type: VehicleType
    bbox: BoundingBox
    confidence: float
    first_seen: datetime = field(default_factory=utc_now)
    last_seen: Optional[datetime] = None
    trajectory: List[Point] = field(default_factory=list)
    first_seen_frame: Optional[int] = None
    last_seen_frame: Optional[int] = None
    camera_id: Optional[str] = None
    frames_tracked: int = 1
    best_confidence: Optional[float] = None
    center: Optional[Point] = None
    type_history: List[VehicleType] = field(default_factory=list)
    appearance_embedding: Optional[AppearanceEmbedding] = None

    def __post_init__(self) -> None:
        self.vehicle_type = _validate_vehicle_type(self.vehicle_type)  # type: ignore[assignment]
        self.bbox = _normalize_bbox(self.bbox)
        self.confidence = _validate_confidence(self.confidence)
        if self.last_seen is None:
            self.last_seen = self.first_seen
        elif self.last_seen < self.first_seen:
            raise ValueError("last_seen cannot be earlier than first_seen.")
        if self.first_seen_frame is not None and self.first_seen_frame < 0:
            raise ValueError("first_seen_frame cannot be negative.")
        if self.last_seen_frame is not None and self.last_seen_frame < 0:
            raise ValueError("last_seen_frame cannot be negative.")
        if (
            self.first_seen_frame is not None
            and self.last_seen_frame is not None
            and self.last_seen_frame < self.first_seen_frame
        ):
            raise ValueError("last_seen_frame cannot be earlier than first_seen_frame.")
        self.frames_tracked = int(self.frames_tracked)
        if self.frames_tracked < 1:
            raise ValueError("frames_tracked must be at least 1.")
        if self.best_confidence is None:
            self.best_confidence = self.confidence
        else:
            self.best_confidence = _validate_confidence(
                self.best_confidence, "best_confidence"
            )
            if self.best_confidence < self.confidence:
                raise ValueError("best_confidence cannot be less than confidence.")
        self.trajectory = [
            (float(point[0]), float(point[1])) for point in self.trajectory
        ]
        if self.center is not None:
            self.center = (float(self.center[0]), float(self.center[1]))
        self.type_history = [
            _validate_vehicle_type(vehicle_type) for vehicle_type in self.type_history
        ]


@dataclass
class PlateObservation:
    """A license-plate detection and its OCR result from one frame."""

    plate_text: str
    detection_confidence: float
    ocr_confidence: float
    bbox: BoundingBox
    timestamp: datetime = field(default_factory=utc_now)
    frame_number: Optional[int] = None
    track_id: Optional[TrackId] = None
    camera_id: Optional[str] = None
    raw_plate_text: Optional[str] = None
    ocr_variant: Optional[str] = None
    vehicle_bbox: Optional[BoundingBox] = None
    association_confidence: Optional[float] = None
    coordinate_space: str = "frame"

    def __post_init__(self) -> None:
        self.raw_plate_text = (
            self.plate_text if self.raw_plate_text is None else self.raw_plate_text
        )
        self.plate_text = self.plate_text.strip().upper()
        self.bbox = _normalize_bbox(self.bbox)
        self.detection_confidence = _validate_confidence(
            self.detection_confidence, "detection_confidence"
        )
        self.ocr_confidence = _validate_confidence(self.ocr_confidence, "ocr_confidence")
        if self.vehicle_bbox is not None:
            self.vehicle_bbox = _normalize_bbox(self.vehicle_bbox)
        if self.association_confidence is not None:
            self.association_confidence = _validate_confidence(
                self.association_confidence, "association_confidence"
            )
        if not self.coordinate_space.strip():
            raise ValueError("coordinate_space cannot be empty.")


@dataclass
class TrafficSnapshot:
    """Traffic metrics calculated for one camera at a point in time."""

    camera_id: str
    active_vehicle_count: int
    queue_length: int
    moving_vehicles: int
    slow_vehicles: int
    stationary_vehicles: int
    traffic_pressure: float
    traffic_level: TrafficLevel
    timestamp: datetime = field(default_factory=utc_now)
    frame_number: Optional[int] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        count_fields = (
            "active_vehicle_count",
            "queue_length",
            "moving_vehicles",
            "slow_vehicles",
            "stationary_vehicles",
        )
        for field_name in count_fields:
            value = int(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative.")
            setattr(self, field_name, value)

        self.traffic_pressure = float(self.traffic_pressure)
        if not 0.0 <= self.traffic_pressure <= 100.0:
            raise ValueError("traffic_pressure must be between 0.0 and 100.0.")
        self.traffic_level = _validate_traffic_level(self.traffic_level)  # type: ignore[assignment]


@dataclass
class Camera:
    """Camera identity and per-camera processing configuration."""

    camera_id: str
    source: str
    name: Optional[str] = None
    resolution: Optional[Tuple[int, int]] = None
    fps: Optional[float] = None
    queue_roi: Optional[Dict[str, Any]] = None
    lane_configuration: List[Dict[str, Any]] = field(default_factory=list)
    direction_configuration: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.camera_id.strip():
            raise ValueError("camera_id cannot be empty.")
        if not self.source.strip():
            raise ValueError("source cannot be empty.")
        if self.resolution is not None:
            width, height = self.resolution
            if width <= 0 or height <= 0:
                raise ValueError("resolution dimensions must be positive.")
        if self.fps is not None and self.fps <= 0:
            raise ValueError("fps must be positive when provided.")


@dataclass
class Event:
    """A generic camera event for ANPR, traffic, safety, or emergency flows."""

    event_id: str
    event_type: str
    timestamp: datetime = field(default_factory=utc_now)
    camera_id: Optional[str] = None
    frame_number: Optional[int] = None
    track_id: Optional[TrackId] = None
    severity: Optional[str] = None
    status: str = "open"
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id cannot be empty.")
        if not self.event_type.strip():
            raise ValueError("event_type cannot be empty.")
        if not self.status.strip():
            raise ValueError("status cannot be empty.")
