"""Run the existing YOLO + ByteTrack tracker and validate contract conversion.

This intentionally reproduces the vehicle-history records built by
``ai/tracking/test_vehicle_intelligence.py`` without changing that prototype.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from ai.contracts.adapters import tracked_vehicle_from_dict
from ai.contracts.models import TrackedVehicle
from ai.tracking.vehicle_tracker import VehicleTracker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIDEO_PATH = PROJECT_ROOT / "data/videos/traffic.mp4"
MODEL_PATH = PROJECT_ROOT / "yolo11n.pt"


def build_vehicle_history() -> Tuple[int, Dict[int, Dict[str, Any]]]:
    """Build the same history records as the current VehicleIntelligence script."""

    tracker = VehicleTracker(model_path=str(MODEL_PATH))
    results = tracker.track_video(str(VIDEO_PATH))
    vehicle_history: Dict[int, Dict[str, Any]] = {}
    frame_number = 0

    for result in results:
        frame_number += 1

        if result.boxes is None:
            continue

        boxes = result.boxes

        for index in range(len(boxes)):
            class_id = int(boxes.cls[index])
            if class_id not in tracker.VEHICLE_CLASSES:
                continue
            if boxes.id is None:
                continue

            track_id = int(boxes.id[index])
            vehicle_type = tracker.VEHICLE_CLASSES[class_id]
            confidence = float(boxes.conf[index])
            x1, y1, x2, y2 = map(int, boxes.xyxy[index].tolist())
            center = [int((x1 + x2) / 2), int((y1 + y2) / 2)]

            if track_id not in vehicle_history:
                vehicle_history[track_id] = {
                    "id": track_id,
                    "type": vehicle_type,
                    "first_seen": frame_number,
                    "last_seen": frame_number,
                    "frames_tracked": 1,
                    "best_confidence": confidence,
                    "bbox": [x1, y1, x2, y2],
                    "center": center,
                    "trajectory": [center],
                }
                continue

            vehicle = vehicle_history[track_id]
            vehicle["last_seen"] = frame_number
            vehicle["frames_tracked"] += 1
            vehicle["best_confidence"] = max(vehicle["best_confidence"], confidence)
            vehicle["bbox"] = [x1, y1, x2, y2]
            vehicle["center"] = center
            vehicle["trajectory"].append(center)

    return frame_number, vehicle_history


def verify_contract(record: Dict[str, Any], contract: TrackedVehicle) -> None:
    """Confirm every available current history field survived adaptation."""

    assert contract.track_id == record["id"]
    assert contract.vehicle_type == record["type"]
    assert contract.first_seen_frame == record["first_seen"]
    assert contract.last_seen_frame == record["last_seen"]
    assert contract.frames_tracked == record["frames_tracked"]
    assert contract.best_confidence == record["best_confidence"]
    assert contract.bbox == tuple(float(value) for value in record["bbox"])
    assert contract.center == tuple(float(value) for value in record["center"])
    assert contract.trajectory == [
        tuple(float(value) for value in point) for point in record["trajectory"]
    ]
    if "type_history" in record:
        assert contract.type_history == record["type_history"]


def run_integration() -> Tuple[int, int, int, List[str], TrackedVehicle]:
    """Track the supplied video, convert every history record, and verify it."""

    if not VIDEO_PATH.is_file():
        raise FileNotFoundError(f"Tracking video was not found: {VIDEO_PATH}")
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"YOLO model was not found: {MODEL_PATH}")

    frames_processed, vehicle_history = build_vehicle_history()
    converted: List[TrackedVehicle] = []
    rejected: List[str] = []

    for track_id, record in sorted(vehicle_history.items()):
        try:
            contract = tracked_vehicle_from_dict(record, camera_id="traffic-demo")
            verify_contract(record, contract)
            converted.append(contract)
        except (KeyError, TypeError, ValueError, AssertionError) as error:
            rejected.append(f"track_id={track_id}: {error}")

    print(f"Frames processed: {frames_processed}")
    print(f"Tracked records processed: {len(vehicle_history)}")
    print(f"Successfully converted: {len(converted)}")
    print(f"Rejected records: {len(rejected)}")
    for message in rejected:
        print(f"  REJECTED {message}")

    if not converted:
        raise AssertionError("The tracker produced no convertible vehicle records.")

    representative = converted[0]
    print("Representative contract output:")
    print(
        {
            "track_id": representative.track_id,
            "vehicle_type": representative.vehicle_type,
            "first_seen_frame": representative.first_seen_frame,
            "last_seen_frame": representative.last_seen_frame,
            "frames_tracked": representative.frames_tracked,
            "best_confidence": representative.best_confidence,
            "bbox": representative.bbox,
            "center": representative.center,
            "trajectory_points": len(representative.trajectory),
            "type_history": representative.type_history,
        }
    )

    if rejected:
        raise AssertionError("One or more tracking records could not be adapted.")

    return (
        len(vehicle_history),
        len(converted),
        len(rejected),
        rejected,
        representative,
    )


if __name__ == "__main__":
    run_integration()
