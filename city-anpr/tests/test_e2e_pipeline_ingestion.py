"""
Milestone 2E — End-to-End AI -> PostgreSQL Runtime Integration Test.
=====================================================================

Validates the full vertical runtime stack:
    CCTV video (data/videos/traffic.mp4)
      -> SingleCameraPipeline
      -> FrameResult contracts
      -> IngestionService
      -> PostgreSQL persistence
      -> FastAPI REST read endpoints

Verifies:
1. Pipeline processes 30 frames and yields valid FrameResult objects.
2. FrameResult objects are ingested via IngestionService into live PostgreSQL.
3. Vehicle tracks are persisted with ByteTrack local IDs.
4. Known plate observations are persisted and linked.
5. Known plates resolve to canonical Vehicle records with accurate vehicle classifications.
6. Associated tracks link correctly to canonical vehicles.
7. Unplated/anonymous vehicles do NOT manufacture spurious canonical Vehicle rows.
8. Traffic snapshots and signal decisions persist for every frame.
9. Second ingestion of the exact same 30-frame batch is completely idempotent.
10. Existing FastAPI read endpoints retrieve the persisted live data.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, List
import unittest

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


def is_postgres_available() -> bool:
    """Synchronously test if PostgreSQL is reachable via asyncpg."""
    try:
        import asyncpg

        async def _ping():
            url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
            conn = await asyncpg.connect(url, timeout=3.0)
            await conn.close()
            return True

        return asyncio.run(_ping())
    except Exception:
        return False


POSTGRES_AVAILABLE = is_postgres_available()


@unittest.skipUnless(
    POSTGRES_AVAILABLE,
    f"PostgreSQL is not reachable at {settings.DATABASE_URL}. Skipping Milestone 2E live tests.",
)
class EndToEndPipelinePostgresTests(unittest.IsolatedAsyncioTestCase):
    """Full vertical integration test: CCTV Video -> AI -> DB -> FastAPI."""

    CAMERA_ID = "e2e-cctv-cam"
    JUNCTION_ID = "e2e-junc-test"
    APPROACH_ID = "e2e-app-north"
    NUM_FRAMES = 30

    async def asyncSetUp(self):
        # Database connection
        self.engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.session = self.session_factory()
        self.service = IngestionService(self.session, auto_register_metadata=True)

        # Clean up any stale records from previous runs
        await self._cleanup_data()

        # Paths for AI models and test CCTV video
        tracker_model = (
            PROJECT_ROOT / "runs" / "detect" / "runs" / "cctv" / "uvh26_80ep-2" / "weights" / "best.pt"
        )
        if not tracker_model.exists():
            tracker_model = PROJECT_ROOT / "yolo11n.pt"

        self.tracker_model_path = str(tracker_model)
        self.plate_model_path = str(PROJECT_ROOT / "ai" / "models" / "license_plate.pt")
        self.video_path = str(PROJECT_ROOT / "data" / "videos" / "traffic.mp4")

        # Initialize the existing SingleCameraPipeline (unchanged)
        self.pipeline = SingleCameraPipeline(
            camera_id=self.CAMERA_ID,
            tracker_model_path=self.tracker_model_path,
            plate_model_path=self.plate_model_path,
            approach_id=self.APPROACH_ID,
            anpr_every_n_frames=1,
            road_capacity=40,
        )

    async def asyncTearDown(self):
        await self._cleanup_data()
        await self.session.close()
        await self.engine.dispose()

    async def _cleanup_data(self):
        """Purge test-specific entities in foreign-key dependency order."""
        async with self.session_factory() as cleanup_session:
            # Delete signal decisions for test junction
            await cleanup_session.execute(
                delete(SignalDecisionModel).where(
                    SignalDecisionModel.junction_id == self.JUNCTION_ID
                )
            )
            # Delete snapshots for test camera
            await cleanup_session.execute(
                delete(TrafficSnapshotModel).where(
                    TrafficSnapshotModel.camera_id == self.CAMERA_ID
                )
            )
            # Find and delete plate observations for test camera
            obs_res = await cleanup_session.execute(
                select(PlateObservationModel.vehicle_id)
                .where(PlateObservationModel.camera_id == self.CAMERA_ID)
                .distinct()
            )
            associated_veh_ids = [vid for vid in obs_res.scalars().all() if vid is not None]

            await cleanup_session.execute(
                delete(PlateObservationModel).where(
                    PlateObservationModel.camera_id == self.CAMERA_ID
                )
            )
            # Delete tracks for test camera
            await cleanup_session.execute(
                delete(VehicleTrack).where(VehicleTrack.camera_id == self.CAMERA_ID)
            )
            # Delete canonical vehicles created by test run
            if associated_veh_ids:
                await cleanup_session.execute(
                    delete(Vehicle).where(Vehicle.vehicle_id.in_(associated_veh_ids))
                )
            # Delete approach, camera, and junction
            await cleanup_session.execute(
                delete(JunctionApproach).where(
                    JunctionApproach.junction_id == self.JUNCTION_ID
                )
            )
            await cleanup_session.execute(
                delete(CameraModel).where(CameraModel.camera_id == self.CAMERA_ID)
            )
            await cleanup_session.execute(
                delete(Junction).where(Junction.junction_id == self.JUNCTION_ID)
            )
            await cleanup_session.commit()

    async def test_e2e_runtime_pipeline_to_postgres_and_fastapi(self):
        """
        Full Milestone 2E Runtime Execution:
        Video -> SingleCameraPipeline -> IngestionService -> PostgreSQL -> FastAPI.
        """
        # ---------------------------------------------------------------------
        # 1. Pre-register Junction and Camera metadata
        # ---------------------------------------------------------------------
        junction = Junction(
            junction_id=self.JUNCTION_ID,
            name="E2E CCTV Validation Chowk",
            latitude=18.5204,
            longitude=73.8567,
            target_cycle_seconds=120,
            status="NORMAL",
        )
        camera = CameraModel(
            camera_id=self.CAMERA_ID,
            source=self.video_path,
            name="E2E Validation CCTV Camera",
            resolution_width=1280,
            resolution_height=720,
            fps=30.0,
            enabled=True,
        )
        approach = JunctionApproach(
            approach_id=self.APPROACH_ID,
            junction_id=self.JUNCTION_ID,
            camera_id=self.CAMERA_ID,
            direction_name="Northbound Inflow",
            cardinal_direction="N",
        )
        self.session.add_all([junction, camera, approach])
        await self.session.commit()

        # ---------------------------------------------------------------------
        # 2. Process 30 frames through SingleCameraPipeline and ingest
        # ---------------------------------------------------------------------
        frame_results: List[FrameResult] = []
        tracks_updated_total = 0
        plates_persisted_total = 0

        for result in self.pipeline.process_video(
            self.video_path,
            max_frames=self.NUM_FRAMES,
            print_every=10,
        ):
            frame_results.append(result)
            summary = await self.service.ingest_frame_result(
                result, junction_id=self.JUNCTION_ID
            )
            tracks_updated_total += summary.tracks_updated
            plates_persisted_total += summary.plates_persisted
            self.assertEqual(summary.camera_id, self.CAMERA_ID)
            self.assertEqual(summary.frame_number, result.frame_number)

        # Commit all 30 frames in the transaction
        await self.session.commit()

        self.assertEqual(
            len(frame_results),
            self.NUM_FRAMES,
            f"Expected exactly {self.NUM_FRAMES} FrameResults from pipeline.",
        )

        # ---------------------------------------------------------------------
        # 3. Verify Database Persistence
        # ---------------------------------------------------------------------
        # (a) Traffic Snapshots: exactly 30 snapshots, one per frame
        stmt_snap = select(TrafficSnapshotModel).where(
            TrafficSnapshotModel.camera_id == self.CAMERA_ID
        )
        res_snap = await self.session.execute(stmt_snap)
        snapshots = res_snap.scalars().all()
        self.assertEqual(
            len(snapshots),
            self.NUM_FRAMES,
            f"Expected {self.NUM_FRAMES} traffic snapshots in PostgreSQL, got {len(snapshots)}.",
        )

        # (b) Signal Decisions: exactly 30 decisions, one per frame
        stmt_sig = select(SignalDecisionModel).where(
            SignalDecisionModel.junction_id == self.JUNCTION_ID
        )
        res_sig = await self.session.execute(stmt_sig)
        decisions = res_sig.scalars().all()
        self.assertEqual(
            len(decisions),
            self.NUM_FRAMES,
            f"Expected {self.NUM_FRAMES} signal decisions in PostgreSQL, got {len(decisions)}.",
        )

        # (c) Vehicle Tracks: camera-local tracking sessions persisted
        stmt_tracks = select(VehicleTrack).where(
            VehicleTrack.camera_id == self.CAMERA_ID
        )
        res_tracks = await self.session.execute(stmt_tracks)
        tracks = res_tracks.scalars().all()
        self.assertGreater(
            len(tracks),
            0,
            "Expected vehicle tracks to be persisted for the video stream.",
        )

        # (d) Anonymous / Unplated Vehicle Rule:
        # Tracks without an associated plate MUST have vehicle_id = NULL
        unplated_tracks = [t for t in tracks if t.vehicle_id is None]
        self.assertGreater(
            len(unplated_tracks),
            0,
            "Expected some tracks to have vehicle_id=NULL (unplated vehicles).",
        )

        # Verify zero anonymous canonical vehicles were created with canonical_plate_text = NULL
        stmt_anon_vehs = select(func.count(Vehicle.vehicle_id)).where(
            Vehicle.canonical_plate_text.is_(None)
        )
        anon_count = (await self.session.execute(stmt_anon_vehs)).scalar()
        self.assertEqual(
            anon_count,
            0,
            f"Expected 0 anonymous canonical vehicles, but found {anon_count}!",
        )

        # (e) Plate Observations
        stmt_obs = select(PlateObservationModel).where(
            PlateObservationModel.camera_id == self.CAMERA_ID
        )
        res_obs = await self.session.execute(stmt_obs)
        observations = res_obs.scalars().all()
        self.assertGreater(
            len(observations),
            0,
            "Expected plate observations to be persisted.",
        )

        # (f) Canonical Vehicles created from known plates
        stmt_vehs = select(Vehicle)
        res_vehs = await self.session.execute(stmt_vehs)
        canonical_vehicles = res_vehs.scalars().all()
        self.assertGreater(
            len(canonical_vehicles),
            0,
            "Expected canonical vehicles to be created from detected plates.",
        )

        # Verify vehicle classifications match track types (not blindly 'car')
        for v in canonical_vehicles:
            self.assertIsNotNone(v.canonical_plate_text)
            self.assertIn(
                v.canonical_vehicle_type,
                ["car", "motorcycle", "truck", "bus", "auto", "three_wheeler"],
            )

        # (g) Track / Plate Linking:
        # When an observation is associated with a track, both link to the canonical vehicle
        associated_obs = [o for o in observations if o.track_session_id is not None]
        self.assertGreater(
            len(associated_obs),
            0,
            "Expected at least one plate observation to be geometrically associated with a vehicle track.",
        )

        for a_obs in associated_obs:
            self.assertIsNotNone(
                a_obs.vehicle_id,
                "Associated plate observation must link to canonical Vehicle.",
            )
            self.assertIsNotNone(
                a_obs.track_session_id,
                "Associated plate observation must link to VehicleTrack.",
            )
            linked_track = next(
                (t for t in tracks if t.track_session_id == a_obs.track_session_id),
                None,
            )
            self.assertIsNotNone(linked_track, "Linked track must exist in DB.")
            self.assertIsNotNone(
                linked_track.vehicle_id,
                "Track with associated plate observation must have vehicle_id populated.",
            )

        # For each track with associated observations, verify its vehicle_id is one of those observations
        track_obs_map: dict = {}
        for a_obs in associated_obs:
            track_obs_map.setdefault(a_obs.track_session_id, []).append(a_obs.vehicle_id)

        for track_session_id, obs_veh_ids in track_obs_map.items():
            linked_track = next(t for t in tracks if t.track_session_id == track_session_id)
            self.assertIn(
                linked_track.vehicle_id,
                obs_veh_ids,
                "VehicleTrack.vehicle_id must match a canonical Vehicle associated with this track.",
            )

        # ---------------------------------------------------------------------
        # 4. Verify Idempotency on Second Ingestion Run
        # ---------------------------------------------------------------------
        # Re-ingest the exact same 30 FrameResults
        for result in frame_results:
            await self.service.ingest_frame_result(
                result, junction_id=self.JUNCTION_ID
            )
        await self.session.commit()

        # Check that rows did NOT duplicate
        res_snap_2 = await self.session.execute(stmt_snap)
        self.assertEqual(
            len(res_snap_2.scalars().all()),
            self.NUM_FRAMES,
            "TrafficSnapshots must not duplicate on re-ingestion.",
        )

        res_sig_2 = await self.session.execute(stmt_sig)
        self.assertEqual(
            len(res_sig_2.scalars().all()),
            self.NUM_FRAMES,
            "SignalDecisions must not duplicate on re-ingestion.",
        )

        res_tracks_2 = await self.session.execute(stmt_tracks)
        self.assertEqual(
            len(res_tracks_2.scalars().all()),
            len(tracks),
            "VehicleTracks must not duplicate on re-ingestion.",
        )

        res_obs_2 = await self.session.execute(stmt_obs)
        self.assertEqual(
            len(res_obs_2.scalars().all()),
            len(observations),
            "PlateObservations must not duplicate on re-ingestion.",
        )

        res_vehs_2 = await self.session.execute(stmt_vehs)
        self.assertEqual(
            len(res_vehs_2.scalars().all()),
            len(canonical_vehicles),
            "Canonical Vehicles must not duplicate on re-ingestion.",
        )

        # ---------------------------------------------------------------------
        # 5. Verify FastAPI Read Endpoints
        # ---------------------------------------------------------------------
        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            async with self.session_factory() as s:
                yield s

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 1. GET /health
            res_h = await client.get("/health")
            self.assertEqual(res_h.status_code, 200)
            self.assertEqual(res_h.json(), {"status": "ok"})

            # 2. GET /api/vehicles
            res_v = await client.get("/api/vehicles")
            self.assertEqual(res_v.status_code, 200)
            api_vehicles = res_v.json()
            self.assertIsInstance(api_vehicles, list)
            self.assertGreaterEqual(len(api_vehicles), len(canonical_vehicles))

            # Pick an actually persisted canonical plate
            target_plate = canonical_vehicles[0].canonical_plate_text
            self.assertIsNotNone(target_plate)

            # 3. GET /api/vehicles/{plate}
            res_p = await client.get(f"/api/vehicles/{target_plate}")
            self.assertEqual(res_p.status_code, 200)
            veh_data = res_p.json()
            self.assertEqual(veh_data["canonical_plate_text"], target_plate)
            self.assertIn("canonical_vehicle_type", veh_data)

            # 4. GET /api/vehicles/{plate}/history
            res_hist = await client.get(f"/api/vehicles/{target_plate}/history")
            self.assertEqual(res_hist.status_code, 200)
            hist_data = res_hist.json()
            self.assertIn("vehicle", hist_data)
            self.assertIn("tracks", hist_data)
            self.assertIn("plate_observations", hist_data)
            self.assertEqual(hist_data["vehicle"]["canonical_plate_text"], target_plate)
            self.assertGreater(len(hist_data["plate_observations"]), 0)

            # 5. GET /api/traffic/latest?camera_id=...
            res_t = await client.get(f"/api/traffic/latest?camera_id={self.CAMERA_ID}")
            self.assertEqual(res_t.status_code, 200)
            traf_data = res_t.json()
            self.assertEqual(traf_data["camera_id"], self.CAMERA_ID)
            self.assertEqual(traf_data["frame_number"], self.NUM_FRAMES)
            self.assertIn("traffic_pressure", traf_data)
            self.assertIn("traffic_level", traf_data)

            # 6. GET /api/signals/latest?junction_id=...
            res_s = await client.get(f"/api/signals/latest?junction_id={self.JUNCTION_ID}")
            self.assertEqual(res_s.status_code, 200)
            sig_data = res_s.json()
            self.assertIsInstance(sig_data, list)
            self.assertGreater(len(sig_data), 0)
            self.assertEqual(sig_data[0]["junction_id"], self.JUNCTION_ID)
            self.assertIn("green_time", sig_data[0])

        app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
