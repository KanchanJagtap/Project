"""
Milestone 1 Integration Test — Single-Camera End-to-End Pipeline
=================================================================

Demonstrates:
    1. Frames processed
    2. Tracked vehicles detected
    3. Plates detected
    4. Plates associated with vehicle track IDs
    5. Queue statistics
    6. Traffic pressure
    7. Signal optimization result
    8. TrafficSnapshot successfully produced

Run from the project root:

    python ai/pipeline/test_single_camera_integration.py

Requires:
    data/videos/traffic.mp4
    ai/models/license_plate.pt
    A YOLO model reachable via MODEL_PATH below
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Make the project root importable regardless of where the script is run.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VIDEO_PATH = PROJECT_ROOT / "data" / "videos" / "traffic.mp4"

# Use the smaller yolo11n.pt as a fallback when the full UVH26 trained
# model is absent.  The integration test is about pipeline wiring, not
# classifier accuracy.
UVH26_MODEL = (
    PROJECT_ROOT / "runs" / "detect" / "runs" / "cctv" / "uvh26_80ep-2" / "weights" / "best.pt"
)
FALLBACK_MODEL = PROJECT_ROOT / "yolo11n.pt"

PLATE_MODEL = PROJECT_ROOT / "ai" / "models" / "license_plate.pt"

CAMERA_ID = "traffic-demo"
APPROACH_ID = "traffic-demo-approach"

# Process this many frames for a quick smoke-test.
# Set to None to run the entire video.
MAX_FRAMES = 90

# Print a summary line every N frames.
PRINT_EVERY = 30

# Run ANPR on every frame for the integration test.
ANPR_EVERY_N_FRAMES = 1

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print()
    print("=" * 70)
    print("  MILESTONE 1 — SINGLE-CAMERA END-TO-END INTEGRATION TEST")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Pre-flight checks
    # ------------------------------------------------------------------
    if not VIDEO_PATH.is_file():
        print(f"\nERROR: test video not found: {VIDEO_PATH}")
        sys.exit(1)

    tracker_model = UVH26_MODEL if UVH26_MODEL.is_file() else FALLBACK_MODEL
    if not tracker_model.is_file():
        print(f"\nERROR: no YOLO model found (tried {UVH26_MODEL} and {FALLBACK_MODEL})")
        sys.exit(1)

    if not PLATE_MODEL.is_file():
        print(f"\nERROR: license plate model not found: {PLATE_MODEL}")
        sys.exit(1)

    print(f"\n  Video           : {VIDEO_PATH}")
    print(f"  Tracker model   : {tracker_model.name}")
    print(f"  Plate model     : {PLATE_MODEL.name}")
    print(f"  Camera ID       : {CAMERA_ID}")
    print(f"  Approach ID     : {APPROACH_ID}")
    print(
        f"  Frames to process: {'ALL' if MAX_FRAMES is None else MAX_FRAMES}"
    )

    # ------------------------------------------------------------------
    # Delayed import — models load here
    # ------------------------------------------------------------------
    from ai.pipeline import SingleCameraPipeline

    print()
    pipeline = SingleCameraPipeline(
        camera_id=CAMERA_ID,
        tracker_model_path=str(tracker_model),
        plate_model_path=str(PLATE_MODEL),
        approach_id=APPROACH_ID,
        anpr_every_n_frames=ANPR_EVERY_N_FRAMES,
    )

    # ------------------------------------------------------------------
    # Accumulators
    # ------------------------------------------------------------------
    total_frames = 0
    total_vehicles_seen: set[int] = set()
    total_plates_detected = 0
    total_plates_read = 0
    total_plates_associated = 0
    max_queue = 0
    max_pressure = 0.0
    last_snapshot = None
    last_decision = None
    last_result = None
    wall_start = time.perf_counter()

    print()
    print(
        f"{'Frame':>6}  {'Vehicles':>8}  {'Plates':>6}  {'Read':>5}  "
        f"{'Assoc':>6}  {'Pressure':>9}  {'Level':>8}  {'Queue':>5}  {'Green':>5}  {'ms':>6}"
    )
    print("-" * 84)

    # ------------------------------------------------------------------
    # Run the pipeline
    # ------------------------------------------------------------------
    for result in pipeline.process_video(
        str(VIDEO_PATH),
        max_frames=MAX_FRAMES,
        print_every=0,  # we handle our own printing below
    ):
        total_frames = result.frame_number

        for v in result.active_vehicles:
            total_vehicles_seen.add(v["id"])

        plates_this_frame = len(result.plate_observations)
        read_this_frame = sum(
            1
            for p in result.plate_observations
            if p.plate_text and p.plate_text != "UNKNOWN"
        )
        assoc_this_frame = sum(
            1 for p in result.plate_observations if p.track_id is not None
        )

        total_plates_detected += plates_this_frame
        total_plates_read += read_this_frame
        total_plates_associated += assoc_this_frame

        if result.snapshot:
            last_snapshot = result.snapshot
            max_queue = max(max_queue, result.snapshot.queue_length)
            max_pressure = max(max_pressure, result.snapshot.traffic_pressure)

        if result.signal_decisions:
            last_decision = result.signal_decisions[0]

        last_result = result

        # Print per-frame summary every PRINT_EVERY frames or on last frame.
        if result.frame_number % PRINT_EVERY == 0 or (
            MAX_FRAMES is not None and result.frame_number >= MAX_FRAMES
        ):
            snap = result.snapshot
            dec = result.signal_decisions[0] if result.signal_decisions else None
            print(
                f"{result.frame_number:6d}  "
                f"{len(result.active_vehicles):8d}  "
                f"{plates_this_frame:6d}  "
                f"{read_this_frame:5d}  "
                f"{assoc_this_frame:6d}  "
                f"{snap.traffic_pressure if snap else 0.0:9.2f}  "
                f"{snap.traffic_level if snap else 'N/A':>8}  "
                f"{snap.queue_length if snap else 0:5d}  "
                f"{dec.green_time if dec else '?':>5}  "
                f"{result.processing_time_ms:6.0f}"
            )

    wall_elapsed = time.perf_counter() - wall_start

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)
    print(f"  Frames processed          : {total_frames}")
    print(f"  Unique vehicle track IDs  : {len(total_vehicles_seen)}")
    print(f"  Total plates detected     : {total_plates_detected}")
    print(f"  Total plates read (OCR)   : {total_plates_read}")
    print(f"  Total plates associated   : {total_plates_associated}")
    print(f"  Max queue length          : {max_queue}")
    print(f"  Max traffic pressure      : {max_pressure:.2f}")
    print(f"  Wall-clock time           : {wall_elapsed:.1f}s")
    print()

    # ------------------------------------------------------------------
    # TrafficSnapshot assertion
    # ------------------------------------------------------------------
    print("  TrafficSnapshot check ...")
    assert last_snapshot is not None, "No TrafficSnapshot was produced!"
    print(f"    camera_id             : {last_snapshot.camera_id}")
    print(f"    active_vehicle_count  : {last_snapshot.active_vehicle_count}")
    print(f"    queue_length          : {last_snapshot.queue_length}")
    print(f"    moving_vehicles       : {last_snapshot.moving_vehicles}")
    print(f"    slow_vehicles         : {last_snapshot.slow_vehicles}")
    print(f"    stationary_vehicles   : {last_snapshot.stationary_vehicles}")
    print(f"    traffic_pressure      : {last_snapshot.traffic_pressure:.2f}")
    print(f"    traffic_level         : {last_snapshot.traffic_level}")
    print(f"    frame_number          : {last_snapshot.frame_number}")
    print(f"    timestamp             : {last_snapshot.timestamp.isoformat()}")
    print()

    # ------------------------------------------------------------------
    # SignalDecision assertion
    # ------------------------------------------------------------------
    print("  SignalDecision check ...")
    assert last_decision is not None, "No SignalDecision was produced!"
    print(f"    approach_id           : {last_decision.approach_id}")
    print(f"    priority_score        : {last_decision.priority_score:.2f}")
    print(f"    green_time            : {last_decision.green_time}s")
    print(f"    reason                : {last_decision.reason}")
    print()

    # ------------------------------------------------------------------
    # Plate association check (informational — may be 0 on short clips)
    # ------------------------------------------------------------------
    if last_result and last_result.plate_observations:
        print("  Plate associations in last result frame:")
        for obs in last_result.plate_observations[:5]:
            print(
                f"    plate={obs.plate_text!r}  "
                f"track_id={obs.track_id}  "
                f"det_conf={obs.detection_confidence:.2f}  "
                f"ocr_conf={obs.ocr_confidence:.2f}"
            )
    else:
        print("  (No plates in last printed frame — normal for short clips.)")

    print()
    print("=" * 70)
    print("  ALL CHECKS PASSED ✓")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
