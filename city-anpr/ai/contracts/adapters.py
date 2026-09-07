"""Adapters from the existing prototype dictionaries to shared contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional, Set

from .models import Detection, TrackId, TrackedVehicle, VehicleType


class UnsupportedVehicleTypeError(ValueError):
    """Raised when a source record uses a non-canonical vehicle label."""


class UnmappedTrackingMetadataError(ValueError):
    """Raised when strict conversion would discard an unknown track field."""


_TRACKING_FIELDS: Set[str] = {
    "id",
    "track_id",
    "type",
    "class",
    "vehicle_type",
    "confidence",
    "best_confidence",
    "bbox",
    "center",
    "trajectory",
    "first_seen",
    "last_seen",
    "first_seen_frame",
    "last_seen_frame",
    "frames_tracked",
    "type_history",
    "camera_id",
}


def _canonical_vehicle_type(value: Any) -> VehicleType:
    """Validate a source label before constructing a canonical contract."""

    if value not in {"motorcycle", "car", "auto", "bus", "truck"}:
        raise UnsupportedVehicleTypeError(
            f"Unsupported vehicle type {value!r}; canonical types are "
            "motorcycle, car, auto, bus, and truck."
        )
    return value  # type: ignore[return-value]


def _required(record: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in record:
        raise KeyError(f"Source record is missing required field {field_name!r}.")
    return record[field_name]


def _frame_number(value: Any, field_name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer frame number when provided.")
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return value


def detection_from_dict(
    record: Mapping[str, Any],
    *,
    camera_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    frame_number: Optional[int] = None,
) -> Detection:
    """Convert the existing ``{class, confidence, bbox}`` detection shape."""

    vehicle_type = _canonical_vehicle_type(_required(record, "class"))
    kwargs = {
        "vehicle_type": vehicle_type,
        "bbox": _required(record, "bbox"),
        "confidence": _required(record, "confidence"),
        "camera_id": camera_id,
        "frame_number": frame_number,
    }
    if timestamp is not None:
        kwargs["timestamp"] = timestamp
    return Detection(**kwargs)


def tracked_vehicle_from_dict(
    record: Mapping[str, Any],
    *,
    camera_id: Optional[str] = None,
    first_seen_at: Optional[datetime] = None,
    last_seen_at: Optional[datetime] = None,
    strict: bool = True,
) -> TrackedVehicle:
    """Convert existing tracking/vehicle-history dictionaries.

    Existing ``first_seen`` and ``last_seen`` values are frame numbers, not
    datetimes.  They are therefore mapped only to ``*_seen_frame`` fields.
    In strict mode, an unknown key is rejected so metadata cannot be silently
    discarded while the shared contract is still evolving.
    """

    unknown_fields = set(record) - _TRACKING_FIELDS
    if strict and unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise UnmappedTrackingMetadataError(
            f"Tracking record contains unmapped fields: {fields}."
        )

    track_id: TrackId = (
        record["track_id"] if "track_id" in record else _required(record, "id")
    )
    vehicle_type = _canonical_vehicle_type(
        record.get("vehicle_type", record.get("type", record.get("class")))
    )
    confidence = record.get("confidence", record.get("best_confidence"))
    if confidence is None:
        raise KeyError("Source tracking record needs confidence or best_confidence.")

    first_seen_frame = _frame_number(
        record.get("first_seen_frame", record.get("first_seen")), "first_seen"
    )
    last_seen_frame = _frame_number(
        record.get("last_seen_frame", record.get("last_seen")), "last_seen"
    )

    kwargs = {
        "track_id": track_id,
        "vehicle_type": vehicle_type,
        "bbox": _required(record, "bbox"),
        "confidence": confidence,
        "trajectory": record.get("trajectory", []),
        "first_seen_frame": first_seen_frame,
        "last_seen_frame": last_seen_frame,
        "frames_tracked": record.get("frames_tracked", 1),
        "best_confidence": record.get("best_confidence"),
        "center": record.get("center"),
        "type_history": record.get("type_history", []),
        "camera_id": camera_id if camera_id is not None else record.get("camera_id"),
    }
    if first_seen_at is not None:
        kwargs["first_seen"] = first_seen_at
    if last_seen_at is not None:
        kwargs["last_seen"] = last_seen_at
    return TrackedVehicle(**kwargs)
