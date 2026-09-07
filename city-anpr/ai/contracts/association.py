"""Same-frame geometric association between plates and tracked vehicles."""

from __future__ import annotations

from dataclasses import replace
from typing import List, Sequence, Tuple

from .models import BoundingBox, PlateObservation, TrackedVehicle


def _area(bbox: BoundingBox) -> float:
    """Return bounding-box area, treating degenerate boxes as zero-area."""

    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _expanded_bbox(bbox: BoundingBox, expansion: float) -> BoundingBox:
    x1, y1, x2, y2 = bbox
    return x1 - expansion, y1 - expansion, x2 + expansion, y2 + expansion


def _contains_point(bbox: BoundingBox, point: Tuple[float, float]) -> bool:
    x1, y1, x2, y2 = bbox
    x, y = point
    return x1 <= x <= x2 and y1 <= y <= y2


def _plate_center(bbox: BoundingBox) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def _plate_coverage(vehicle_bbox: BoundingBox, plate_bbox: BoundingBox) -> float:
    """Return the fraction of plate area covered by a vehicle bounding box."""

    plate_area = _area(plate_bbox)
    if plate_area <= 0.0:
        return 0.0

    vx1, vy1, vx2, vy2 = vehicle_bbox
    px1, py1, px2, py2 = plate_bbox
    intersection_width = max(0.0, min(vx2, px2) - max(vx1, px1))
    intersection_height = max(0.0, min(vy2, py2) - max(vy1, py1))
    return (intersection_width * intersection_height) / plate_area


def _same_frame(plate: PlateObservation, vehicle: TrackedVehicle) -> bool:
    """Require matching frame numbers when either record supplies one."""

    if plate.frame_number is None and vehicle.last_seen_frame is None:
        return True
    if plate.frame_number is None or vehicle.last_seen_frame is None:
        return False
    return plate.frame_number == vehicle.last_seen_frame


def _same_camera(plate: PlateObservation, vehicle: TrackedVehicle) -> bool:
    """Reject only explicit camera-ID conflicts."""

    return (
        plate.camera_id is None
        or vehicle.camera_id is None
        or plate.camera_id == vehicle.camera_id
    )


def associate_plates_to_vehicles(
    vehicles: Sequence[TrackedVehicle],
    plates: Sequence[PlateObservation],
    *,
    minimum_coverage: float = 0.90,
    vehicle_bbox_expansion: float = 2.0,
) -> List[PlateObservation]:
    """Return new plate observations with reliable same-frame associations.

    A plate is eligible only when its center lies in an expanded vehicle bbox.
    Candidates are ranked by plate coverage (intersection / plate area), rather
    than normal IoU, because a correct plate occupies only a small part of its
    vehicle bbox.  No nearest-vehicle fallback is used.
    """

    if not 0.0 <= minimum_coverage <= 1.0:
        raise ValueError("minimum_coverage must be between 0.0 and 1.0.")
    if vehicle_bbox_expansion < 0.0:
        raise ValueError("vehicle_bbox_expansion cannot be negative.")

    associated: List[PlateObservation] = []

    for plate in plates:
        # Return a new object even when no association is possible.
        if plate.track_id is not None or plate.coordinate_space != "frame":
            associated.append(replace(plate))
            continue

        if _area(plate.bbox) <= 0.0:
            associated.append(replace(plate))
            continue

        center = _plate_center(plate.bbox)
        best_vehicle = None
        best_coverage = 0.0

        for vehicle in vehicles:
            if not _same_frame(plate, vehicle) or not _same_camera(plate, vehicle):
                continue
            if _area(vehicle.bbox) <= 0.0:
                continue

            expanded_vehicle_bbox = _expanded_bbox(
                vehicle.bbox, vehicle_bbox_expansion
            )
            if not _contains_point(expanded_vehicle_bbox, center):
                continue

            coverage = _plate_coverage(expanded_vehicle_bbox, plate.bbox)
            if coverage > best_coverage:
                best_vehicle = vehicle
                best_coverage = coverage

        if best_vehicle is None or best_coverage < minimum_coverage:
            associated.append(replace(plate))
            continue

        associated.append(
            replace(
                plate,
                track_id=best_vehicle.track_id,
                vehicle_bbox=best_vehicle.bbox,
                association_confidence=best_coverage,
            )
        )

    return associated
