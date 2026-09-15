"""
Single-Camera End-to-End AI Orchestrator
=========================================
Milestone 1 — City-Wide AI Engine

Connects the existing AI modules in order:

    CCTV video / frame source
      → VehicleTracker  (YOLO UVH26 + ByteTrack)
      → ANPRPipeline    (YOLO plate detector + PaddleOCR)
      → associate_plates_to_vehicles()   (geometric, same-frame)
      → TrafficPressureEngine  (queue + pressure + arrival rate)
      → ApproachState adapter
      → SignalOptimizer
      → TrafficSnapshot  (contract output)

Design rules enforced here
---------------------------
* No existing AI module is modified.
* All data model conversions go through the existing contract adapters
  (tracked_vehicle_from_dict, association.associate_plates_to_vehicles).
* The orchestrator is stateless across calls *except* for the mutable
  engine state that each component already carries (ByteTrack ID
  registry, EMA smoothing, arrival events).  All that state lives
  inside the existing module instances.
* Public interface is intentionally minimal so a FastAPI layer can wrap
  it later without changes to this file.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

import cv2

from ai.anpr.anpr_pipeline import ANPRPipeline
from ai.contracts.adapters import tracked_vehicle_from_dict
from ai.contracts.association import associate_plates_to_vehicles
from ai.contracts.models import (
    PlateObservation,
    TrafficSnapshot,
    TrackedVehicle,
)
from ai.tracking.vehicle_tracker import VehicleTracker
from ai.traffic.signal_optimizer import ApproachState, SignalDecision, SignalOptimizer
from ai.traffic.traffic_pressure import TrafficPressureEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public result dataclass
# ---------------------------------------------------------------------------


@dataclass
class FrameResult:
    """
    Everything the orchestrator produces for one processed frame.

    This is the payload that a FastAPI endpoint will later serialise.
    All values come directly from existing module outputs or existing
    contract dataclasses — no invented fields.
    """

    # ---- identity ----------------------------------------------------------
    frame_number: int
    camera_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ---- vehicle tracking --------------------------------------------------
    active_vehicles: List[Dict[str, Any]] = field(default_factory=list)
    """
    Raw active-vehicle dicts built from ByteTrack output.
    Schema: {id, type, confidence, bbox, center, trajectory,
             first_seen, last_seen, frames_tracked, best_confidence,
             type_history}
    """

    tracked_vehicle_contracts: List[TrackedVehicle] = field(default_factory=list)
    """Converted TrackedVehicle contracts for the current frame's active vehicles."""

    # ---- ANPR --------------------------------------------------------------
    plate_observations: List[PlateObservation] = field(default_factory=list)
    """
    PlateObservation contracts produced from the ANPR pipeline output.
    track_id is populated for plates that were geometrically associated.
    """

    # ---- traffic analytics -------------------------------------------------
    snapshot: Optional[TrafficSnapshot] = None
    """The TrafficSnapshot contract emitted for this frame."""

    # ---- signal optimizer --------------------------------------------------
    signal_decisions: List[SignalDecision] = field(default_factory=list)
    """
    Recommended green-time allocation from the SignalOptimizer.
    Contains exactly one SignalDecision for a single-camera setup.
    """

    # ---- diagnostics -------------------------------------------------------
    processing_time_ms: float = 0.0
    anpr_skipped: bool = False
    """True when ANPR was skipped for this frame (see anpr_every_n_frames)."""


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class SingleCameraPipeline:
    """
    Single-camera end-to-end AI pipeline.

    Parameters
    ----------
    camera_id:
        Logical camera identifier — propagated to all contract objects.
    tracker_model_path:
        Path to the UVH26 YOLO weights used by VehicleTracker.
    plate_model_path:
        Path to the license-plate YOLO weights used by ANPRPipeline.
    approach_id:
        Identifier for this camera's intersection approach, passed to
        SignalOptimizer.  Defaults to ``camera_id``.
    anpr_every_n_frames:
        Run the ANPR pipeline only every N frames to reduce CPU/GPU load.
        Frame 1 always runs ANPR.  Default: 1 (every frame).
    road_capacity:
        Maximum expected vehicles for the TrafficPressureEngine.
    """

    def __init__(
        self,
        camera_id: str,
        tracker_model_path: str,
        plate_model_path: str = "ai/models/license_plate.pt",
        approach_id: Optional[str] = None,
        anpr_every_n_frames: int = 1,
        road_capacity: int = 40,
    ) -> None:
        self.camera_id = camera_id
        self.approach_id = approach_id or camera_id
        self.anpr_every_n_frames = max(1, anpr_every_n_frames)

        # ------------------------------------------------------------------
        # Instantiate the existing AI modules (unchanged)
        # ------------------------------------------------------------------
        print(f"[Pipeline:{camera_id}] Loading VehicleTracker …")
        self._tracker = VehicleTracker(model_path=tracker_model_path)

        print(f"[Pipeline:{camera_id}] Loading ANPRPipeline …")
        self._anpr = ANPRPipeline(plate_model_path=plate_model_path)

        print(f"[Pipeline:{camera_id}] Loading TrafficPressureEngine …")
        self._pressure_engine = TrafficPressureEngine(road_capacity=road_capacity)

        print(f"[Pipeline:{camera_id}] Loading SignalOptimizer …")
        self._signal_optimizer = SignalOptimizer()

        # ------------------------------------------------------------------
        # Persistent vehicle history — owned by the orchestrator and passed
        # by reference into TrafficPressureEngine.calculate_pressure() exactly
        # as the existing test scripts do.
        # ------------------------------------------------------------------
        self._vehicle_history: Dict[int, Dict[str, Any]] = {}

        # Starvation tracking for SignalOptimizer
        self._starvation_time: float = 0.0
        self._last_green_frame: int = 0

        print(f"[Pipeline:{camera_id}] Ready.")

    # ------------------------------------------------------------------
    # Video processing entry point
    # ------------------------------------------------------------------

    def process_video(
        self,
        video_path: str,
        max_frames: Optional[int] = None,
        print_every: int = 30,
    ) -> Generator[FrameResult, None, None]:
        """
        Yield one :class:`FrameResult` per processed frame.

        Parameters
        ----------
        video_path:
            Path to the CCTV video file.
        max_frames:
            Stop after this many frames (``None`` = entire video).
        print_every:
            Print a progress line every N frames (0 = silent).

        Yields
        ------
        FrameResult
            One result per video frame, in order.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(
                f"SingleCameraPipeline: cannot open video: {video_path}"
            )

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        # VehicleTracker.track_video() streams YOLO+ByteTrack results;
        # it opens the video internally via Ultralytics.
        tracking_stream = self._tracker.track_video(video_path)

        frame_number = 0

        for yolo_result in tracking_stream:
            frame_number += 1
            if max_frames is not None and frame_number > max_frames:
                break

            t0 = time.perf_counter()

            # Ultralytics attaches the original frame to the result.
            frame = yolo_result.orig_img  # numpy ndarray, BGR

            # ----------------------------------------------------------
            # 1. Extract active vehicles from ByteTrack output
            # ----------------------------------------------------------
            active_vehicles = self._extract_active_vehicles(
                yolo_result, frame_number
            )

            # ----------------------------------------------------------
            # 2. ANPR — detect plates in the full frame
            # ----------------------------------------------------------
            run_anpr = (frame_number == 1) or (
                frame_number % self.anpr_every_n_frames == 0
            )

            raw_plates: List[Dict[str, Any]] = []
            if run_anpr and frame is not None:
                raw_plates = self._anpr.detect_and_read(frame)

            # ----------------------------------------------------------
            # 3. TrafficPressureEngine — queue + pressure
            #    calculate_pressure() is the sole owner/caller of
            #    update_vehicle_history().
            # ----------------------------------------------------------
            pressure_result = self._pressure_engine.calculate_pressure(
                active_vehicles=active_vehicles,
                vehicle_history=self._vehicle_history,
                current_frame=frame_number,
                fps=fps,
                frame_width=frame_width,
                frame_height=frame_height,
            )

            # ----------------------------------------------------------
            # 4. Convert tracking history → TrackedVehicle contracts
            #    Built from the authoritative vehicle history updated
            #    by calculate_pressure().
            # ----------------------------------------------------------
            tracked_contracts = self._build_tracked_contracts(frame_number)

            # ----------------------------------------------------------
            # 5. Build PlateObservation objects and associate to tracks
            # ----------------------------------------------------------
            plate_obs_raw = self._build_plate_observations(
                raw_plates, frame_number
            )
            associated_plates = associate_plates_to_vehicles(
                vehicles=tracked_contracts,
                plates=plate_obs_raw,
            )

            # ----------------------------------------------------------
            # 6. Build TrafficSnapshot contract
            # ----------------------------------------------------------
            snapshot = self._build_snapshot(pressure_result, frame_number)

            # ----------------------------------------------------------
            # 7. Build ApproachState and run SignalOptimizer
            # ----------------------------------------------------------
            approach = self._build_approach_state(pressure_result, frame_number, fps)
            signal_decisions = self._signal_optimizer.optimize([approach])

            # Update starvation tracking based on decision
            if signal_decisions:
                decision = signal_decisions[0]
                if decision.approach_id == self.approach_id and decision.green_time > 0:
                    self._last_green_frame = frame_number

            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            result = FrameResult(
                frame_number=frame_number,
                camera_id=self.camera_id,
                active_vehicles=list(active_vehicles),
                tracked_vehicle_contracts=tracked_contracts,
                plate_observations=associated_plates,
                snapshot=snapshot,
                signal_decisions=signal_decisions,
                processing_time_ms=round(elapsed_ms, 1),
                anpr_skipped=not run_anpr,
            )

            if print_every > 0 and frame_number % print_every == 0:
                self._print_progress(result, pressure_result)

            yield result

    # ------------------------------------------------------------------
    # Single-frame entry point (for FastAPI integration)
    # ------------------------------------------------------------------

    def process_frame(
        self,
        frame,  # numpy ndarray BGR
        frame_number: int,
        fps: float = 30.0,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
    ) -> FrameResult:
        """
        Process a single pre-decoded frame in detection-only mode.

        Because ByteTrack requires a continuous temporal stream, isolated
        single frames cannot maintain persistent tracking IDs or trajectory
        history. This method performs vehicle and license plate detection
        without updating persistent tracking history or calculating
        history-dependent traffic analytics (queue, pressure, signal optimization).

        Returns
        -------
        FrameResult
            Contains active vehicle detections and plate observations without
            synthetic track IDs or trajectory-dependent snapshots.
        """
        t0 = time.perf_counter()

        # Run YOLO detection without persistent ByteTrack tracking.
        raw_yolo = self._tracker.model(frame, verbose=False)

        active_vehicles: List[Dict[str, Any]] = []
        for result in raw_yolo:
            if result.boxes is None:
                continue
            for idx in range(len(result.boxes)):
                class_id = int(result.boxes.cls[idx])
                if class_id not in self._tracker.VEHICLE_CLASSES:
                    continue
                vehicle_type = self._tracker.VEHICLE_CLASSES[class_id]
                confidence = float(result.boxes.conf[idx])
                x1, y1, x2, y2 = map(int, result.boxes.xyxy[idx].tolist())
                active_vehicles.append(
                    {
                        "id": None,
                        "type": vehicle_type,
                        "confidence": confidence,
                        "bbox": [x1, y1, x2, y2],
                    }
                )

        raw_plates = self._anpr.detect_and_read(frame)
        plate_obs_raw = self._build_plate_observations(raw_plates, frame_number)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return FrameResult(
            frame_number=frame_number,
            camera_id=self.camera_id,
            active_vehicles=active_vehicles,
            tracked_vehicle_contracts=[],
            plate_observations=plate_obs_raw,
            snapshot=None,
            signal_decisions=[],
            processing_time_ms=round(elapsed_ms, 1),
            anpr_skipped=False,
        )

    # ------------------------------------------------------------------
    # Internal helpers — no AI logic, pure conversion/wiring
    # ------------------------------------------------------------------

    def _extract_active_vehicles(
        self,
        yolo_result,
        frame_number: int,
    ) -> List[Dict[str, Any]]:
        """
        Convert one YOLO+ByteTrack result into the dict list expected by
        TrafficPressureEngine.calculate_pressure().

        Returns only current-frame vehicle data. Trajectory accumulation
        is owned solely by TrafficPressureEngine.update_vehicle_history().
        """
        vehicles: List[Dict[str, Any]] = []

        if yolo_result.boxes is None:
            return vehicles

        boxes = yolo_result.boxes

        for idx in range(len(boxes)):
            class_id = int(boxes.cls[idx])
            if class_id not in self._tracker.VEHICLE_CLASSES:
                continue

            # ByteTrack may not have assigned an ID yet on the very first
            # frame — boxes.id is None until tracking initialises.
            if boxes.id is None:
                continue

            track_id = int(boxes.id[idx])
            vehicle_type = self._tracker.VEHICLE_CLASSES[class_id]
            confidence = float(boxes.conf[idx])
            x1, y1, x2, y2 = map(int, boxes.xyxy[idx].tolist())

            vehicles.append(
                {
                    "id": track_id,
                    "type": vehicle_type,
                    "confidence": confidence,
                    "bbox": [x1, y1, x2, y2],
                }
            )

        return vehicles

    def _build_tracked_contracts(
        self,
        frame_number: int,
    ) -> List[TrackedVehicle]:
        """
        Convert all vehicles currently in history into TrackedVehicle
        contracts using the existing adapter (strict=True).

        Only vehicles last seen in the *current* frame are included so
        that the plate-association step sees only the active frame's tracks.
        """
        contracts: List[TrackedVehicle] = []
        for record in self._vehicle_history.values():
            if record.get("last_seen") != frame_number:
                continue
            try:
                contract = tracked_vehicle_from_dict(
                    record,
                    camera_id=self.camera_id,
                )
                contracts.append(contract)
            except Exception as exc:
                logger.warning(
                    "Failed to adapt tracking record for track_id=%s at frame %d: %s",
                    record.get("id"),
                    frame_number,
                    exc,
                )
        return contracts

    def _build_plate_observations(
        self,
        raw_plates: List[Dict[str, Any]],
        frame_number: int,
    ) -> List[PlateObservation]:
        """
        Convert ANPRPipeline.detect_and_read() output dicts into
        PlateObservation contracts.

        ANPRPipeline output schema:
            {"text": str, "detection_confidence": float,
             "ocr_confidence": float, "bbox": [x1, y1, x2, y2]}

        Plates with empty or unread OCR text are skipped so artificial
        sentinel text is not injected into the contract stream.
        """
        observations: List[PlateObservation] = []
        for plate in raw_plates:
            text = str(plate.get("text", "")).strip()
            if not text:
                continue

            det_conf = float(plate.get("detection_confidence", 0.0))
            ocr_conf = float(plate.get("ocr_confidence", 0.0))
            bbox = plate.get("bbox", [0, 0, 1, 1])

            # Ensure det_conf is at least 0.01 to pass validation.
            det_conf = max(det_conf, 0.01)
            ocr_conf = max(ocr_conf, 0.0)

            # Guard: skip completely degenerate bboxes (x2<=x1 or y2<=y1).
            x1, y1, x2, y2 = bbox
            if x2 <= x1 or y2 <= y1:
                continue

            try:
                obs = PlateObservation(
                    plate_text=text,
                    detection_confidence=det_conf,
                    ocr_confidence=ocr_conf,
                    bbox=(float(x1), float(y1), float(x2), float(y2)),
                    frame_number=frame_number,
                    camera_id=self.camera_id,
                    raw_plate_text=text,
                    coordinate_space="frame",
                )
                observations.append(obs)
            except Exception as exc:
                logger.warning(
                    "Failed to construct PlateObservation at frame %d: %s",
                    frame_number,
                    exc,
                )

        return observations

    def _build_snapshot(
        self,
        pressure_result: Dict[str, Any],
        frame_number: int,
    ) -> TrafficSnapshot:
        """
        Construct the TrafficSnapshot contract from the pressure engine
        output dict.

        Exact keys used (all present in the engine's return dict):
            pressure, traffic_level, active_vehicle_count,
            queue_length, moving_vehicles, slow_vehicles,
            stationary_vehicles
        """
        return TrafficSnapshot(
            camera_id=self.camera_id,
            active_vehicle_count=int(pressure_result["active_vehicle_count"]),
            queue_length=int(pressure_result["queue_length"]),
            moving_vehicles=int(pressure_result.get("moving_vehicles", 0)),
            slow_vehicles=int(pressure_result.get("slow_vehicles", 0)),
            stationary_vehicles=int(pressure_result.get("stationary_vehicles", 0)),
            traffic_pressure=float(pressure_result["pressure"]),
            traffic_level=pressure_result["traffic_level"],
            frame_number=frame_number,
            metrics={
                "raw_pressure": pressure_result.get("raw_pressure"),
                "vehicle_load": pressure_result.get("vehicle_load"),
                "road_occupancy": pressure_result.get("road_occupancy"),
                "queue_score": pressure_result.get("queue_score"),
                "arrival_rate": pressure_result.get("arrival_rate"),
                "arrival_status": pressure_result.get("arrival_status"),
                "unique_vehicle_count": pressure_result.get("unique_vehicle_count"),
                "component_weights": pressure_result.get("component_weights"),
            },
        )

    def _build_approach_state(
        self,
        pressure_result: Dict[str, Any],
        frame_number: int,
        fps: float,
    ) -> ApproachState:
        """
        Convert the pressure engine output into an ApproachState for the
        SignalOptimizer.  This is the thin adapter the architecture
        inspection identified as missing.

        ApproachState fields (from signal_optimizer.py):
            approach_id, traffic_pressure, queue_length,
            average_waiting_time, arrival_rate, starvation_time,
            emergency_priority
        """
        # Update starvation: frames since this approach last held green.
        if fps > 0:
            seconds_since_green = (frame_number - self._last_green_frame) / fps
        else:
            seconds_since_green = 0.0
        self._starvation_time = seconds_since_green

        return ApproachState(
            approach_id=self.approach_id,
            traffic_pressure=float(pressure_result["pressure"]),
            queue_length=int(pressure_result["queue_length"]),
            average_waiting_time=float(
                pressure_result.get("average_waiting_time", 0.0)
            ),
            arrival_rate=float(pressure_result.get("arrival_rate", 0.0)),
            starvation_time=self._starvation_time,
            emergency_priority=False,  # placeholder — no emergency feed yet
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @staticmethod
    def _print_progress(
        result: FrameResult,
        pressure_result: Dict[str, Any],
    ) -> None:
        associated_count = sum(
            1 for p in result.plate_observations if p.track_id is not None
        )
        read_count = sum(
            1
            for p in result.plate_observations
            if p.plate_text and p.plate_text != "UNKNOWN"
        )
        decision = (
            result.signal_decisions[0] if result.signal_decisions else None
        )
        print(
            f"Frame {result.frame_number:5d} | "
            f"Vehicles: {len(result.active_vehicles):3d} | "
            f"Plates detected: {len(result.plate_observations):2d} | "
            f"Plates read: {read_count:2d} | "
            f"Associated: {associated_count:2d} | "
            f"Pressure: {result.snapshot.traffic_pressure:5.1f} "
            f"({result.snapshot.traffic_level}) | "
            f"Queue: {result.snapshot.queue_length:2d} | "
            f"Green: {decision.green_time if decision else '?':>3}s | "
            f"{result.processing_time_ms:.0f}ms"
        )
