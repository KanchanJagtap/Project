"""Measure same-frame geometric plate-to-track association on the CCTV video."""

from __future__ import annotations

import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import cv2

from ai.anpr.anpr_pipeline import ANPRPipeline
from ai.contracts.adapters import tracked_vehicle_from_dict
from ai.contracts.association import associate_plates_to_vehicles
from ai.contracts.models import PlateObservation, TrackedVehicle
from ai.tracking.vehicle_tracker import VehicleTracker


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VIDEO_PATH = PROJECT_ROOT / "data/videos/traffic.mp4"

# Use the trained 80-epoch vehicle detector.
MODEL_PATH = (
    PROJECT_ROOT
    / "runs/detect/runs/cctv/uvh26_80ep-2/weights/best.pt"
)

CAMERA_ID = "traffic-demo"

MINIMUM_COVERAGE = 0.90

VEHICLE_BBOX_EXPANSION = 2.0

LOW_OCR_CONFIDENCE = 0.50


def _bbox_area(
    bbox: Tuple[float, float, float, float],
) -> float:
    """Calculate bounding-box area."""

    x1, y1, x2, y2 = bbox

    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _candidate_count(
    plate: PlateObservation,
    vehicles: Sequence[TrackedVehicle],
) -> int:
    """Count containment candidates using the association geometry rules."""

    if _bbox_area(plate.bbox) <= 0.0:
        return 0

    px1, py1, px2, py2 = plate.bbox

    center_x = (px1 + px2) / 2.0
    center_y = (py1 + py2) / 2.0

    count = 0

    for vehicle in vehicles:

        if plate.frame_number != vehicle.last_seen_frame:
            continue

        if (
            plate.camera_id is not None
            and vehicle.camera_id is not None
            and plate.camera_id != vehicle.camera_id
        ):
            continue

        if _bbox_area(vehicle.bbox) <= 0.0:
            continue

        x1, y1, x2, y2 = vehicle.bbox

        x1 -= VEHICLE_BBOX_EXPANSION
        y1 -= VEHICLE_BBOX_EXPANSION
        x2 += VEHICLE_BBOX_EXPANSION
        y2 += VEHICLE_BBOX_EXPANSION

        if (
            x1 <= center_x <= x2
            and y1 <= center_y <= y2
        ):
            count += 1

    return count


def _summary(
    values: List[float],
) -> Dict[str, float]:
    """Return summary statistics."""

    if not values:
        return {
            "count": 0,
            "min": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "max": 0.0,
        }

    return {
        "count": len(values),
        "min": min(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def _coverage_buckets(
    values: List[float],
) -> Dict[str, int]:
    """Group association coverage into useful ranges."""

    return {
        "0.90-0.95": sum(
            0.90 <= value < 0.95
            for value in values
        ),
        "0.95-0.99": sum(
            0.95 <= value < 0.99
            for value in values
        ),
        "0.99-1.00": sum(
            0.99 <= value <= 1.00
            for value in values
        ),
    }


def _update_history(
    history: Dict[int, Dict[str, Any]],
    tracker: VehicleTracker,
    track_result: Any,
    frame_number: int,
) -> List[Dict[str, Any]]:
    """Reproduce the current VehicleIntelligence per-track history shape."""

    active_records: List[Dict[str, Any]] = []

    if (
        track_result.boxes is None
        or track_result.boxes.id is None
    ):
        return active_records

    boxes = track_result.boxes

    for index in range(len(boxes)):

        class_id = int(boxes.cls[index])

        if class_id not in tracker.VEHICLE_CLASSES:
            continue

        track_id = int(boxes.id[index])

        vehicle_type = tracker.VEHICLE_CLASSES[class_id]

        confidence = float(boxes.conf[index])

        x1, y1, x2, y2 = map(
            int,
            boxes.xyxy[index].tolist(),
        )

        center = [
            int((x1 + x2) / 2),
            int((y1 + y2) / 2),
        ]

        if track_id not in history:

            history[track_id] = {
                "id": track_id,
                "type": vehicle_type,
                "first_seen": frame_number,
                "last_seen": frame_number,
                "frames_tracked": 1,
                "best_confidence": confidence,
                "bbox": [
                    x1,
                    y1,
                    x2,
                    y2,
                ],
                "center": center,
                "trajectory": [center],
            }

        else:

            record = history[track_id]

            record["last_seen"] = frame_number

            record["frames_tracked"] += 1

            record["best_confidence"] = max(
                record["best_confidence"],
                confidence,
            )

            record["bbox"] = [
                x1,
                y1,
                x2,
                y2,
            ]

            record["center"] = center

            record["trajectory"].append(center)

        active_records.append(
            dict(history[track_id])
        )

    return active_records


def run_measurement() -> Dict[str, Any]:
    """Run full-frame ANPR and tracking over the same raw video frames."""

    if not VIDEO_PATH.is_file():
        raise FileNotFoundError(
            f"Required traffic video is unavailable: {VIDEO_PATH}"
        )

    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Required trained vehicle model is unavailable: {MODEL_PATH}"
        )

    raw_frames = cv2.VideoCapture(
        str(VIDEO_PATH)
    )

    if not raw_frames.isOpened():
        raise RuntimeError(
            f"Could not open video: {VIDEO_PATH}"
        )

    print("=" * 70)
    print("REAL ANPR + TRACKING ASSOCIATION TEST")
    print("=" * 70)

    print(
        f"Video: {VIDEO_PATH}"
    )

    print(
        f"Vehicle model: {MODEL_PATH}"
    )

    print(
        f"Minimum association coverage: "
        f"{MINIMUM_COVERAGE:.2f}"
    )

    print()

    tracker = VehicleTracker(
        model_path=str(MODEL_PATH)
    )

    anpr = ANPRPipeline()

    track_results = tracker.track_video(
        str(VIDEO_PATH)
    )

    history: Dict[int, Dict[str, Any]] = {}

    started_at = time.perf_counter()

    frames_processed = 0

    frames_with_plates = 0

    total_plates = 0

    associated_plates = 0

    unassociated_plates = 0

    no_containing_vehicle = 0

    multiple_candidates = 0

    empty_ocr_text = 0

    low_ocr_confidence = 0

    coverage_scores: List[float] = []

    ocr_confidences: List[float] = []

    detection_confidences: List[float] = []

    associations_by_vehicle_type: Counter = Counter()

    try:

        for frame_number, track_result in enumerate(
            track_results,
            start=1,
        ):

            ok, frame = raw_frames.read()

            if not ok:
                raise RuntimeError(
                    "Raw frame reader ended before "
                    "the tracking result stream."
                )

            frames_processed = frame_number

            active_records = _update_history(
                history,
                tracker,
                track_result,
                frame_number,
            )

            tracked_vehicles = [
                tracked_vehicle_from_dict(
                    record,
                    camera_id=CAMERA_ID,
                )
                for record in active_records
            ]

            anpr_results = anpr.detect_and_read(
                frame
            )

            plate_observations = [
                PlateObservation(
                    plate_text=result["text"],
                    detection_confidence=result[
                        "detection_confidence"
                    ],
                    ocr_confidence=result[
                        "ocr_confidence"
                    ],
                    bbox=result["bbox"],
                    frame_number=frame_number,
                    camera_id=CAMERA_ID,
                    coordinate_space="frame",
                )
                for result in anpr_results
            ]

            if plate_observations:
                frames_with_plates += 1

            total_plates += len(
                plate_observations
            )

            ocr_confidences.extend(
                plate.ocr_confidence
                for plate in plate_observations
            )

            detection_confidences.extend(
                plate.detection_confidence
                for plate in plate_observations
            )

            for plate in plate_observations:

                candidates = _candidate_count(
                    plate,
                    tracked_vehicles,
                )

                if candidates == 0:

                    no_containing_vehicle += 1

                    print(
                        f"Frame {frame_number}: "
                        "plate has no containing vehicle"
                    )

                elif candidates > 1:

                    multiple_candidates += 1

                    print(
                        f"Frame {frame_number}: "
                        f"plate has {candidates} "
                        "containing vehicles"
                    )

                if not plate.plate_text:

                    empty_ocr_text += 1

                    print(
                        f"Frame {frame_number}: "
                        "plate OCR text is empty"
                    )

                if (
                    plate.ocr_confidence
                    < LOW_OCR_CONFIDENCE
                ):

                    low_ocr_confidence += 1

                    print(
                        f"Frame {frame_number}: "
                        "low OCR confidence "
                        f"({plate.ocr_confidence:.3f})"
                    )

            associated_observations = (
                associate_plates_to_vehicles(
                    tracked_vehicles,
                    plate_observations,
                    minimum_coverage=MINIMUM_COVERAGE,
                    vehicle_bbox_expansion=(
                        VEHICLE_BBOX_EXPANSION
                    ),
                )
            )

            vehicles_by_id = {
                vehicle.track_id: vehicle
                for vehicle in tracked_vehicles
            }

            for observation in associated_observations:

                if observation.track_id is None:

                    unassociated_plates += 1

                    continue

                associated_plates += 1

                coverage_scores.append(
                    observation.association_confidence
                    or 0.0
                )

                vehicle = vehicles_by_id[
                    observation.track_id
                ]

                associations_by_vehicle_type[
                    vehicle.vehicle_type
                ] += 1

                print(
                    "GEOMETRIC ASSOCIATION "
                    f"frame={frame_number} "
                    f"track_id={observation.track_id} "
                    f"vehicle_type={vehicle.vehicle_type} "
                    f"plate_text={observation.plate_text!r} "
                    f"plate_bbox={observation.bbox} "
                    f"vehicle_bbox={observation.vehicle_bbox} "
                    f"coverage="
                    f"{observation.association_confidence:.3f} "
                    f"ocr_confidence="
                    f"{observation.ocr_confidence:.3f}"
                )

    finally:

        raw_frames.release()

    elapsed_seconds = (
        time.perf_counter()
        - started_at
    )

    processing_fps = (
        frames_processed / elapsed_seconds
        if elapsed_seconds
        else 0.0
    )

    association_rate = (
        associated_plates / total_plates
        if total_plates
        else 0.0
    )

    result = {
        "frames_processed": frames_processed,
        "frames_with_plates": frames_with_plates,
        "total_plate_observations": total_plates,
        "associated_plate_observations": associated_plates,
        "unassociated_plate_observations": (
            unassociated_plates
        ),
        "association_rate": association_rate,
        "coverage_scores": _summary(
            coverage_scores
        ),
        "coverage_buckets": _coverage_buckets(
            coverage_scores
        ),
        "associations_by_vehicle_type": dict(
            associations_by_vehicle_type
        ),
        "ocr_confidence": _summary(
            ocr_confidences
        ),
        "plate_detection_confidence": _summary(
            detection_confidences
        ),
        "no_containing_vehicle": (
            no_containing_vehicle
        ),
        "multiple_candidates": (
            multiple_candidates
        ),
        "empty_ocr_text": empty_ocr_text,
        "low_ocr_confidence": (
            low_ocr_confidence
        ),
        "elapsed_seconds": elapsed_seconds,
        "processing_fps": processing_fps,
    }

    print()
    print(
        "=" * 70
    )
    print(
        "ANPR-TO-TRACKING GEOMETRIC ASSOCIATION SUMMARY"
    )
    print(
        "=" * 70
    )

    for name, value in result.items():
        print(
            f"  {name}: {value}"
        )

    return result


if __name__ == "__main__":
    run_measurement()