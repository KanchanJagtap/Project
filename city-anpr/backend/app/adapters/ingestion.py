"""
Ingestion Adapters Module.

Bridges AI contracts (FrameResult, TrackedVehicle, PlateObservation,
TrafficSnapshot, SignalDecision) to ORM model representations.
Keeps AI contracts completely decoupled from SQLAlchemy and web frameworks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from ai.contracts.models import (
    Camera,
    PlateObservation,
    TrackedVehicle,
    TrafficSnapshot,
)
from ai.pipeline.single_camera_pipeline import FrameResult
from ai.traffic.signal_optimizer import SignalDecision

from backend.app.models.camera import CameraModel
from backend.app.models.observation import PlateObservationModel
from backend.app.models.signal import SignalDecisionModel
from backend.app.models.tracking import VehicleTrack
from backend.app.models.traffic import TrafficSnapshotModel


@dataclass
class IngestionBatch:
    """
    Normalized batch container extracted from a FrameResult or independent feeds.
    """
    camera_id: str
    frame_number: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tracks: List[TrackedVehicle] = field(default_factory=list)
    plate_observations: List[PlateObservation] = field(default_factory=list)
    snapshot: Optional[TrafficSnapshot] = None
    signal_decisions: List[SignalDecision] = field(default_factory=list)
    junction_id: Optional[str] = None


@dataclass
class IngestionResult:
    """
    Summary of entities created or updated during an ingestion operation.
    """
    camera_id: str
    frame_number: int
    tracks_updated: int = 0
    plates_persisted: int = 0
    snapshot_persisted: bool = False
    decisions_persisted: int = 0
    vehicles_resolved: int = 0
    errors: List[str] = field(default_factory=list)


def frame_result_to_batch(
    result: FrameResult,
    *,
    junction_id: Optional[str] = None,
) -> IngestionBatch:
    """
    Convert a FrameResult from SingleCameraPipeline into an IngestionBatch.
    """
    return IngestionBatch(
        camera_id=result.camera_id,
        frame_number=result.frame_number,
        timestamp=result.timestamp,
        tracks=list(result.tracked_vehicle_contracts),
        plate_observations=list(result.plate_observations),
        snapshot=result.snapshot,
        signal_decisions=list(result.signal_decisions),
        junction_id=junction_id,
    )


def camera_contract_to_model(camera: Camera) -> CameraModel:
    """Convert an AI Camera contract to an ORM CameraModel."""
    res_w = camera.resolution[0] if camera.resolution else None
    res_h = camera.resolution[1] if camera.resolution else None
    return CameraModel(
        camera_id=camera.camera_id,
        source=camera.source,
        name=camera.name,
        resolution_width=res_w,
        resolution_height=res_h,
        fps=camera.fps,
        queue_roi=camera.queue_roi,
        lane_configuration=camera.lane_configuration,
        direction_configuration=camera.direction_configuration,
        enabled=camera.enabled,
    )


def tracked_vehicle_to_model(
    track: TrackedVehicle,
    *,
    camera_id: Optional[str] = None,
    vehicle_id: Optional[uuid.UUID] = None,
) -> VehicleTrack:
    """Convert an AI TrackedVehicle contract to a new ORM VehicleTrack."""
    cam_id = camera_id or track.camera_id or "unknown"
    local_id = (
        int(track.track_id)
        if isinstance(track.track_id, int) or str(track.track_id).isdigit()
        else hash(track.track_id) % (10**6)
    )
    return VehicleTrack(
        vehicle_id=vehicle_id,
        camera_id=cam_id,
        local_track_id=local_id,
        vehicle_type=track.vehicle_type,
        confidence=track.confidence,
        best_confidence=track.best_confidence or track.confidence,
        first_seen_at=track.first_seen,
        last_seen_at=track.last_seen or track.first_seen,
        first_seen_frame=track.first_seen_frame or 0,
        last_seen_frame=track.last_seen_frame or track.first_seen_frame or 0,
        frames_tracked=track.frames_tracked,
        last_bbox=list(track.bbox),
        center=list(track.center) if track.center else None,
        trajectory_summary=[list(pt) for pt in track.trajectory],
        type_history=list(track.type_history),
    )


def plate_observation_to_model(
    obs: PlateObservation,
    *,
    camera_id: Optional[str] = None,
    track_session_id: Optional[uuid.UUID] = None,
    vehicle_id: Optional[uuid.UUID] = None,
) -> PlateObservationModel:
    """Convert an AI PlateObservation contract to an ORM PlateObservationModel."""
    return PlateObservationModel(
        plate_text=obs.plate_text,
        raw_plate_text=obs.raw_plate_text,
        camera_id=camera_id or obs.camera_id or "unknown",
        track_session_id=track_session_id,
        vehicle_id=vehicle_id,
        frame_number=obs.frame_number or 0,
        timestamp=obs.timestamp,
        detection_confidence=obs.detection_confidence,
        ocr_confidence=obs.ocr_confidence,
        association_confidence=obs.association_confidence,
        bbox=list(obs.bbox),
        vehicle_bbox=list(obs.vehicle_bbox) if obs.vehicle_bbox else None,
        ocr_variant=obs.ocr_variant,
        coordinate_space=obs.coordinate_space,
    )


def traffic_snapshot_to_model(
    snapshot: TrafficSnapshot,
    *,
    camera_id: Optional[str] = None,
) -> TrafficSnapshotModel:
    """Convert an AI TrafficSnapshot contract to an ORM TrafficSnapshotModel."""
    return TrafficSnapshotModel(
        camera_id=camera_id or snapshot.camera_id,
        timestamp=snapshot.timestamp,
        frame_number=snapshot.frame_number,
        active_vehicle_count=snapshot.active_vehicle_count,
        queue_length=snapshot.queue_length,
        moving_vehicles=snapshot.moving_vehicles,
        slow_vehicles=snapshot.slow_vehicles,
        stationary_vehicles=snapshot.stationary_vehicles,
        traffic_pressure=snapshot.traffic_pressure,
        traffic_level=snapshot.traffic_level,
        metrics=dict(snapshot.metrics),
    )


def signal_decision_to_model(
    decision: SignalDecision,
    *,
    junction_id: str,
    approach_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> SignalDecisionModel:
    """Convert an AI SignalDecision contract to an ORM SignalDecisionModel."""
    return SignalDecisionModel(
        junction_id=junction_id,
        approach_id=approach_id or decision.approach_id,
        timestamp=timestamp or datetime.now(timezone.utc),
        priority_score=decision.priority_score,
        green_time=decision.green_time,
        reason=decision.reason,
    )
