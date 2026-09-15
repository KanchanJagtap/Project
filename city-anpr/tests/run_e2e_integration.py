"""
Milestone 2E Standalone Runtime Integration Runner.
===================================================

Runs a deterministic end-to-end integration pass:
  1. Loads SingleCameraPipeline with existing CCTV models.
  2. Processes 30 frames from data/videos/traffic.mp4.
  3. Ingests each FrameResult into live PostgreSQL via IngestionService.
  4. Verifies database record counts and track-plate linking.
  5. Verifies idempotency by re-ingesting the batch.
  6. Verifies FastAPI read endpoints against PostgreSQL.
  7. Cleans up test records and outputs the final metrics summary.

Usage:
    .venv/bin/python tests/run_e2e_integration.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import AsyncGenerator, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ai.pipeline.single_camera_pipeline import FrameResult, SingleCameraPipeline
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models import (
    CameraModel,
    Junction,
    JunctionApproach,
    PlateObservationModel,
    SignalDecisionModel,
    TrafficSnapshotModel,
    Vehicle,
    VehicleTrack,
)
from backend.app.services.ingestion_service import IngestionService

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CAMERA_ID = "e2e-cctv-cam"
JUNCTION_ID = "e2e-junc-test"
APPROACH_ID = "e2e-app-north"
NUM_FRAMES = 30


async def cleanup(session_factory) -> None:
    """Purge test-specific entities."""
    async with session_factory() as s:
        await s.execute(
            delete(SignalDecisionModel).where(SignalDecisionModel.junction_id == JUNCTION_ID)
        )
        await s.execute(
            delete(TrafficSnapshotModel).where(TrafficSnapshotModel.camera_id == CAMERA_ID)
        )
        obs_res = await s.execute(
            select(PlateObservationModel.vehicle_id)
            .where(PlateObservationModel.camera_id == CAMERA_ID)
            .distinct()
        )
        associated_veh_ids = [vid for vid in obs_res.scalars().all() if vid is not None]

        await s.execute(
            delete(PlateObservationModel).where(PlateObservationModel.camera_id == CAMERA_ID)
        )
        await s.execute(
            delete(VehicleTrack).where(VehicleTrack.camera_id == CAMERA_ID)
        )
        if associated_veh_ids:
            await s.execute(delete(Vehicle).where(Vehicle.vehicle_id.in_(associated_veh_ids)))

        await s.execute(
            delete(JunctionApproach).where(JunctionApproach.junction_id == JUNCTION_ID)
        )
        await s.execute(delete(CameraModel).where(CameraModel.camera_id == CAMERA_ID))
        await s.execute(delete(Junction).where(Junction.junction_id == JUNCTION_ID))
        await s.commit()


async def run_integration() -> Dict[str, any]:
    print("=" * 60)
    print("Milestone 2E — End-to-End AI -> PostgreSQL Runtime Integration")
    print("=" * 60)

    # 1. Database engine & session
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Initial cleanup
    await cleanup(session_factory)

    # 2. Configure SingleCameraPipeline
    tracker_model = (
        PROJECT_ROOT / "runs" / "detect" / "runs" / "cctv" / "uvh26_80ep-2" / "weights" / "best.pt"
    )
    if not tracker_model.exists():
        tracker_model = PROJECT_ROOT / "yolo11n.pt"

    plate_model = PROJECT_ROOT / "ai" / "models" / "license_plate.pt"
    video_path = PROJECT_ROOT / "data" / "videos" / "traffic.mp4"

    print(f"Video: {video_path}")
    print(f"Tracker Model: {tracker_model}")
    print(f"Plate Model: {plate_model}")
    print(f"Database: {settings.DATABASE_URL.split('@')[-1]}")
    print(f"Processing {NUM_FRAMES} frames...")

    pipeline = SingleCameraPipeline(
        camera_id=CAMERA_ID,
        tracker_model_path=str(tracker_model),
        plate_model_path=str(plate_model),
        approach_id=APPROACH_ID,
        anpr_every_n_frames=1,
    )

    # Pre-register junction & approach
    async with session_factory() as s:
        junction = Junction(
            junction_id=JUNCTION_ID,
            name="E2E CCTV Validation Chowk",
            target_cycle_seconds=120,
            status="NORMAL",
        )
        camera = CameraModel(
            camera_id=CAMERA_ID,
            source=str(video_path),
            name="E2E Validation CCTV Camera",
            enabled=True,
        )
        approach = JunctionApproach(
            approach_id=APPROACH_ID,
            junction_id=JUNCTION_ID,
            camera_id=CAMERA_ID,
            direction_name="Northbound Inflow",
            cardinal_direction="N",
        )
        s.add_all([junction, camera, approach])
        await s.commit()

    # 3. Process video & ingest
    frame_results: List[FrameResult] = []
    async with session_factory() as s:
        service = IngestionService(s, auto_register_metadata=True)
        for result in pipeline.process_video(str(video_path), max_frames=NUM_FRAMES, print_every=10):
            frame_results.append(result)
            await service.ingest_frame_result(result, junction_id=JUNCTION_ID)
        await s.commit()

    print(f"\nCompleted {len(frame_results)} frames through pipeline & ingestion.")

    # 4. Verify PostgreSQL persistence
    async with session_factory() as s:
        tracks = (
            await s.execute(select(VehicleTrack).where(VehicleTrack.camera_id == CAMERA_ID))
        ).scalars().all()
        obs = (
            await s.execute(select(PlateObservationModel).where(PlateObservationModel.camera_id == CAMERA_ID))
        ).scalars().all()
        vehs = (await s.execute(select(Vehicle))).scalars().all()
        snaps = (
            await s.execute(select(TrafficSnapshotModel).where(TrafficSnapshotModel.camera_id == CAMERA_ID))
        ).scalars().all()
        sigs = (
            await s.execute(select(SignalDecisionModel).where(SignalDecisionModel.junction_id == JUNCTION_ID))
        ).scalars().all()
        anon_vehs = (
            await s.execute(select(func.count(Vehicle.vehicle_id)).where(Vehicle.canonical_plate_text.is_(None)))
        ).scalar()

    assoc_obs = [o for o in obs if o.track_session_id is not None]
    unplated_tracks = [t for t in tracks if t.vehicle_id is None]

    print("\n--- Persistence Verification ---")
    print(f"Vehicle tracks persisted:          {len(tracks)}")
    print(f"Unplated tracks (vehicle_id=None):  {len(unplated_tracks)}")
    print(f"Anonymous canonical vehicles:      {anon_vehs} (must be 0)")
    print(f"Canonical vehicles resolved:       {len(vehs)}")
    print(f"Plate observations persisted:      {len(obs)}")
    print(f"Associated plate observations:     {len(assoc_obs)}")
    print(f"Traffic snapshots persisted:       {len(snaps)}")
    print(f"Signal decisions persisted:        {len(sigs)}")

    # 5. Verify Idempotency on 2nd Ingestion
    print("\n--- Verifying Idempotency on Second Ingestion ---")
    async with session_factory() as s:
        service = IngestionService(s, auto_register_metadata=True)
        for result in frame_results:
            await service.ingest_frame_result(result, junction_id=JUNCTION_ID)
        await s.commit()

    async with session_factory() as s:
        tracks_2 = (
            await s.execute(select(VehicleTrack).where(VehicleTrack.camera_id == CAMERA_ID))
        ).scalars().all()
        obs_2 = (
            await s.execute(select(PlateObservationModel).where(PlateObservationModel.camera_id == CAMERA_ID))
        ).scalars().all()
        vehs_2 = (await s.execute(select(Vehicle))).scalars().all()
        snaps_2 = (
            await s.execute(select(TrafficSnapshotModel).where(TrafficSnapshotModel.camera_id == CAMERA_ID))
        ).scalars().all()
        sigs_2 = (
            await s.execute(select(SignalDecisionModel).where(SignalDecisionModel.junction_id == JUNCTION_ID))
        ).scalars().all()

    print(f"Tracks after re-ingestion:         {len(tracks_2)} (diff: {len(tracks_2) - len(tracks)})")
    print(f"Observations after re-ingestion:   {len(obs_2)} (diff: {len(obs_2) - len(obs)})")
    print(f"Vehicles after re-ingestion:       {len(vehs_2)} (diff: {len(vehs_2) - len(vehs)})")
    print(f"Snapshots after re-ingestion:      {len(snaps_2)} (diff: {len(snaps_2) - len(snaps)})")
    print(f"Decisions after re-ingestion:      {len(sigs_2)} (diff: {len(sigs_2) - len(sigs)})")

    # 6. Verify FastAPI Read APIs
    print("\n--- Verifying FastAPI Read Endpoints ---")
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # GET /health
        res_h = await client.get("/health")
        print(f"GET /health:                       {res_h.status_code} {res_h.json()}")

        # GET /api/vehicles
        res_v = await client.get("/api/vehicles")
        print(f"GET /api/vehicles:                 {res_v.status_code} ({len(res_v.json())} vehicles)")

        target_plate = vehs[0].canonical_plate_text
        # GET /api/vehicles/{plate}
        res_p = await client.get(f"/api/vehicles/{target_plate}")
        print(f"GET /api/vehicles/{target_plate}:       {res_p.status_code} (type: {res_p.json().get('canonical_vehicle_type')})")

        # GET /api/vehicles/{plate}/history
        res_hist = await client.get(f"/api/vehicles/{target_plate}/history")
        hist = res_hist.json()
        print(f"GET /api/vehicles/{target_plate}/history: {res_hist.status_code} (tracks: {len(hist.get('tracks', []))}, obs: {len(hist.get('plate_observations', []))})")

        # GET /api/traffic/latest
        res_t = await client.get(f"/api/traffic/latest?camera_id={CAMERA_ID}")
        print(f"GET /api/traffic/latest:           {res_t.status_code} (frame: {res_t.json().get('frame_number')}, level: {res_t.json().get('traffic_level')})")

        # GET /api/signals/latest
        res_s = await client.get(f"/api/signals/latest?junction_id={JUNCTION_ID}")
        print(f"GET /api/signals/latest:           {res_s.status_code} (green: {res_s.json()[0].get('green_time')}s)")

    app.dependency_overrides.clear()

    # Final cleanup
    await cleanup(session_factory)
    await engine.dispose()
    print("\nTest data cleaned up successfully. Runtime integration complete.")

    return {
        "frames_processed": len(frame_results),
        "tracks_persisted": len(tracks),
        "unplated_tracks": len(unplated_tracks),
        "anon_vehicles": anon_vehs,
        "canonical_vehicles": len(vehs),
        "plate_observations": len(obs),
        "associated_observations": len(assoc_obs),
        "traffic_snapshots": len(snaps),
        "signal_decisions": len(sigs),
    }


if __name__ == "__main__":
    asyncio.run(run_integration())
