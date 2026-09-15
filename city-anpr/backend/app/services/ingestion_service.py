"""
AI -> Database Ingestion Service (Milestone 2B).

Translates and persists AI pipeline outputs (FrameResult, TrackedVehicle,
PlateObservation, TrafficSnapshot, SignalDecision) into the database
with proper canonical identity resolution, relationship linkage,
idempotency safeguards, and transactional boundaries.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.contracts.models import (
    PlateObservation,
    TrackedVehicle,
    TrafficSnapshot,
)
from ai.pipeline.single_camera_pipeline import FrameResult
from ai.traffic.signal_optimizer import SignalDecision

from backend.app.adapters.ingestion import (
    IngestionResult,
    plate_observation_to_model,
    signal_decision_to_model,
    tracked_vehicle_to_model,
    traffic_snapshot_to_model,
)
from backend.app.models.camera import CameraModel
from backend.app.models.junction import Junction, JunctionApproach
from backend.app.models.observation import PlateObservationModel
from backend.app.models.signal import SignalDecisionModel
from backend.app.models.tracking import VehicleTrack
from backend.app.models.traffic import TrafficSnapshotModel
from backend.app.models.vehicle import Vehicle

logger = logging.getLogger(__name__)


class IngestionService:
    """
    Ingestion service handling database persistence for AI pipeline outputs.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        auto_register_metadata: bool = True,
    ) -> None:
        """
        Parameters
        ----------
        session:
            Active SQLAlchemy AsyncSession.
        auto_register_metadata:
            If True, automatically registers missing Camera, Junction, and
            JunctionApproach records to guarantee referential integrity.
        """
        self.session = session
        self.auto_register_metadata = auto_register_metadata

    # =========================================================================
    # 1. Main Entrypoint: FrameResult Ingestion
    # =========================================================================

    async def ingest_frame_result(
        self,
        result: FrameResult,
        *,
        junction_id: Optional[str] = None,
    ) -> IngestionResult:
        """
        Ingest a full FrameResult inside a single atomic transaction.

        If any operation fails, the transaction rolls back cleanly without
        leaving partial data.
        """
        summary = IngestionResult(
            camera_id=result.camera_id,
            frame_number=result.frame_number,
        )

        try:
            # 1. Ensure camera exists for foreign key constraints
            if self.auto_register_metadata:
                await self._ensure_camera(result.camera_id)

            # 2. Ingest and update tracked vehicles
            track_mapping: Dict[int, VehicleTrack] = {}
            if result.tracked_vehicle_contracts:
                tracks = await self.ingest_tracked_vehicles(
                    result.tracked_vehicle_contracts,
                    camera_id=result.camera_id,
                )
                summary.tracks_updated = len(tracks)
                for t in tracks:
                    track_mapping[t.local_track_id] = t

            # 3. Ingest plate observations and link with tracks/vehicles
            if result.plate_observations:
                obs_models = await self.ingest_plate_observations(
                    result.plate_observations,
                    camera_id=result.camera_id,
                    track_mapping=track_mapping,
                )
                summary.plates_persisted = len(obs_models)

            # 4. Ingest traffic snapshot
            if result.snapshot:
                snapshot_model = await self.ingest_traffic_snapshot(
                    result.snapshot,
                    camera_id=result.camera_id,
                )
                summary.snapshot_persisted = snapshot_model is not None

            # 5. Ingest signal decisions
            if result.signal_decisions:
                junc_id = junction_id or f"junction-{result.camera_id}"
                dec_models = await self.ingest_signal_decisions(
                    result.signal_decisions,
                    junction_id=junc_id,
                    timestamp=result.timestamp,
                )
                summary.decisions_persisted = len(dec_models)

            # Flush changes to the session
            await self.session.flush()
            return summary

        except Exception as exc:
            logger.error(
                "Ingestion failed for camera=%s frame=%d: %s. Rolling back transaction.",
                result.camera_id,
                result.frame_number,
                exc,
                exc_info=True,
            )
            await self.session.rollback()
            raise

    # =========================================================================
    # 2. Vehicle Identity Resolution
    # =========================================================================

    async def resolve_or_create_vehicle(
        self,
        plate_text: Optional[str],
        vehicle_type: str = "car",
        timestamp: Optional[datetime] = None,
    ) -> Vehicle:
        """
        Resolve an existing canonical Vehicle record or create a new one.

        Rules:
        - If plate_text is non-empty and matches an existing canonical vehicle,
          return that vehicle and update its metadata.
        - If plate_text is non-empty but unknown, create a new canonical Vehicle.
        - If plate_text is None/empty, create a canonical Vehicle with
          canonical_plate_text=None (valid under partial unique index).
        """
        ts = timestamp or datetime.now(timezone.utc)
        normalized_plate = plate_text.strip().upper() if plate_text else None

        if normalized_plate:
            stmt = select(Vehicle).where(Vehicle.canonical_plate_text == normalized_plate)
            res = await self.session.execute(stmt)
            existing = res.scalars().first()

            if existing is not None:
                # Update last seen and detection counts
                existing.last_detected_at = max(existing.last_detected_at, ts)
                existing.total_detections_count += 1
                return existing

            # Create new vehicle with known plate
            new_vehicle = Vehicle(
                canonical_plate_text=normalized_plate,
                canonical_vehicle_type=vehicle_type,
                first_detected_at=ts,
                last_detected_at=ts,
                total_detections_count=1,
            )
            self.session.add(new_vehicle)
            await self.session.flush()
            return new_vehicle

        # Unidentified vehicle (no plate)
        anonymous_vehicle = Vehicle(
            canonical_plate_text=None,
            canonical_vehicle_type=vehicle_type,
            first_detected_at=ts,
            last_detected_at=ts,
            total_detections_count=1,
        )
        self.session.add(anonymous_vehicle)
        await self.session.flush()
        return anonymous_vehicle

    # =========================================================================
    # 3. Tracked Vehicles Ingestion (Idempotent Update/Create)
    # =========================================================================

    async def ingest_tracked_vehicles(
        self,
        tracks: Sequence[TrackedVehicle],
        *,
        camera_id: str,
    ) -> List[VehicleTrack]:
        """
        Persist or update continuous tracking sessions for vehicles.

        Idempotency rule:
        If a track with (camera_id, local_track_id) is currently active,
        update its bounding box, frames_tracked, trajectory, and last_seen_at
        rather than inserting duplicate rows.
        """
        persisted: List[VehicleTrack] = []

        for track in tracks:
            local_id = (
                int(track.track_id)
                if isinstance(track.track_id, int) or str(track.track_id).isdigit()
                else hash(track.track_id) % (10**6)
            )

            stmt = (
                select(VehicleTrack)
                .where(
                    VehicleTrack.camera_id == camera_id,
                    VehicleTrack.local_track_id == local_id,
                )
                .order_by(VehicleTrack.last_seen_at.desc())
            )
            res = await self.session.execute(stmt)
            existing = res.scalars().first()

            if existing is not None:
                # Update existing continuous tracking session
                existing.last_seen_at = track.last_seen or track.first_seen
                existing.last_seen_frame = (
                    track.last_seen_frame or track.first_seen_frame or existing.last_seen_frame
                )
                existing.frames_tracked = max(existing.frames_tracked, track.frames_tracked)
                existing.confidence = track.confidence
                existing.best_confidence = max(
                    existing.best_confidence or 0.0, track.confidence
                )
                existing.last_bbox = list(track.bbox)
                if track.center:
                    existing.center = list(track.center)
                existing.trajectory_summary = [list(pt) for pt in track.trajectory]
                existing.type_history = list(track.type_history)
                persisted.append(existing)
            else:
                # Insert new session
                new_track = tracked_vehicle_to_model(track, camera_id=camera_id)
                self.session.add(new_track)
                persisted.append(new_track)

        await self.session.flush()
        return persisted

    # =========================================================================
    # 4. Plate Observations Ingestion
    # =========================================================================

    async def ingest_plate_observations(
        self,
        observations: Sequence[PlateObservation],
        *,
        camera_id: str,
        track_mapping: Optional[Dict[int, VehicleTrack]] = None,
    ) -> List[PlateObservationModel]:
        """
        Persist plate observations and link them to tracks and vehicles.

        Idempotency rule:
        If an observation with the same camera_id, frame_number, and plate_text
        already exists, it is reused to avoid duplicate entries.
        """
        persisted: List[PlateObservationModel] = []
        track_map = track_mapping or {}

        for obs in observations:
            plate_text = obs.plate_text.strip().upper()
            if not plate_text:
                continue

            # Check for existing identical observation
            stmt = select(PlateObservationModel).where(
                PlateObservationModel.camera_id == camera_id,
                PlateObservationModel.frame_number == obs.frame_number,
                PlateObservationModel.plate_text == plate_text,
            )
            res = await self.session.execute(stmt)
            existing_obs = res.scalars().first()

            if existing_obs is not None:
                persisted.append(existing_obs)
                continue

            # Resolve or create canonical Vehicle
            canonical_vehicle = await self.resolve_or_create_vehicle(
                plate_text=plate_text,
                vehicle_type="car",
                timestamp=obs.timestamp,
            )

            # Determine associated track
            associated_track: Optional[VehicleTrack] = None
            if obs.track_id is not None:
                tid = int(obs.track_id) if str(obs.track_id).isdigit() else None
                if tid is not None and tid in track_map:
                    associated_track = track_map[tid]
                    # Link track to canonical vehicle if not already linked
                    if associated_track.vehicle_id is None:
                        associated_track.vehicle_id = canonical_vehicle.vehicle_id

            obs_model = plate_observation_to_model(
                obs,
                camera_id=camera_id,
                track_session_id=associated_track.track_session_id if associated_track else None,
                vehicle_id=canonical_vehicle.vehicle_id,
            )
            self.session.add(obs_model)
            persisted.append(obs_model)

        await self.session.flush()
        return persisted

    # =========================================================================
    # 5. Traffic Snapshot Ingestion
    # =========================================================================

    async def ingest_traffic_snapshot(
        self,
        snapshot: TrafficSnapshot,
        *,
        camera_id: Optional[str] = None,
    ) -> Optional[TrafficSnapshotModel]:
        """
        Persist traffic snapshot with idempotency check.
        """
        cam_id = camera_id or snapshot.camera_id

        # Idempotency check: check if snapshot already recorded for this frame/timestamp
        if snapshot.frame_number is not None:
            stmt = select(TrafficSnapshotModel).where(
                TrafficSnapshotModel.camera_id == cam_id,
                TrafficSnapshotModel.frame_number == snapshot.frame_number,
            )
        else:
            stmt = select(TrafficSnapshotModel).where(
                TrafficSnapshotModel.camera_id == cam_id,
                TrafficSnapshotModel.timestamp == snapshot.timestamp,
            )

        res = await self.session.execute(stmt)
        existing = res.scalars().first()

        if existing is not None:
            # Update metrics if re-ingested
            existing.active_vehicle_count = snapshot.active_vehicle_count
            existing.queue_length = snapshot.queue_length
            existing.moving_vehicles = snapshot.moving_vehicles
            existing.slow_vehicles = snapshot.slow_vehicles
            existing.stationary_vehicles = snapshot.stationary_vehicles
            existing.traffic_pressure = snapshot.traffic_pressure
            existing.traffic_level = snapshot.traffic_level
            existing.metrics = dict(snapshot.metrics)
            await self.session.flush()
            return existing

        model = traffic_snapshot_to_model(snapshot, camera_id=cam_id)
        self.session.add(model)
        await self.session.flush()
        return model

    # =========================================================================
    # 6. Signal Decisions Ingestion
    # =========================================================================

    async def ingest_signal_decisions(
        self,
        decisions: Sequence[SignalDecision],
        *,
        junction_id: str,
        timestamp: Optional[datetime] = None,
    ) -> List[SignalDecisionModel]:
        """
        Persist signal optimizer decisions per junction and approach.
        """
        persisted: List[SignalDecisionModel] = []
        ts = timestamp or datetime.now(timezone.utc)

        for dec in decisions:
            if self.auto_register_metadata:
                await self._ensure_junction_and_approach(junction_id, dec.approach_id)

            # Idempotency check: check if decision exists for junction, approach, timestamp
            stmt = select(SignalDecisionModel).where(
                SignalDecisionModel.junction_id == junction_id,
                SignalDecisionModel.approach_id == dec.approach_id,
                SignalDecisionModel.timestamp == ts,
            )
            res = await self.session.execute(stmt)
            existing = res.scalars().first()

            if existing is not None:
                existing.priority_score = dec.priority_score
                existing.green_time = dec.green_time
                existing.reason = dec.reason
                persisted.append(existing)
            else:
                model = signal_decision_to_model(
                    dec,
                    junction_id=junction_id,
                    timestamp=ts,
                )
                self.session.add(model)
                persisted.append(model)

        await self.session.flush()
        return persisted

    # =========================================================================
    # Internal Helpers: Metadata Referential Integrity
    # =========================================================================

    async def _ensure_camera(self, camera_id: str) -> CameraModel:
        stmt = select(CameraModel).where(CameraModel.camera_id == camera_id)
        res = await self.session.execute(stmt)
        cam = res.scalars().first()
        if cam is None:
            cam = CameraModel(
                camera_id=camera_id,
                source=f"auto://{camera_id}",
                name=f"Camera {camera_id}",
                enabled=True,
            )
            self.session.add(cam)
            await self.session.flush()
        return cam

    async def _ensure_junction_and_approach(
        self,
        junction_id: str,
        approach_id: str,
    ) -> None:
        # Ensure junction
        stmt_junc = select(Junction).where(Junction.junction_id == junction_id)
        res_junc = await self.session.execute(stmt_junc)
        junc = res_junc.scalars().first()
        if junc is None:
            junc = Junction(
                junction_id=junction_id,
                name=f"Junction {junction_id}",
            )
            self.session.add(junc)
            await self.session.flush()

        # Ensure approach
        stmt_app = select(JunctionApproach).where(JunctionApproach.approach_id == approach_id)
        res_app = await self.session.execute(stmt_app)
        app = res_app.scalars().first()
        if app is None:
            app = JunctionApproach(
                approach_id=approach_id,
                junction_id=junction_id,
                direction_name=f"Approach {approach_id}",
            )
            self.session.add(app)
            await self.session.flush()
