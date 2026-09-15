"""
Unit Tests for AI -> Database Ingestion Service (Milestone 2B).

Uses an in-memory async SQLite engine (via aiosqlite) to verify:
1. TrackedVehicle -> VehicleTrack conversion and persistence
2. PlateObservation -> PlateObservationModel persistence
3. Known plate resolves to existing canonical Vehicle
4. Repeated known plate does not create duplicate canonical Vehicles
5. Unassociated plate observation remains valid and persists
6. TrafficSnapshot persists cleanly
7. SignalDecision persists cleanly
8. Transaction rollback works when a batch fails
9. Repeated ingestion does not blindly duplicate records where contract provides idempotency
10. Full FrameResult ingestion end-to-end
"""

import unittest
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ai.contracts.models import (
    PlateObservation,
    TrackedVehicle,
    TrafficSnapshot,
)
from ai.pipeline.single_camera_pipeline import FrameResult
from ai.traffic.signal_optimizer import SignalDecision

from backend.app.db.base import Base
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


class IngestionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create an isolated async in-memory SQLite engine for each test
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.session = self.session_factory()
        self.service = IngestionService(self.session, auto_register_metadata=True)

    async def asyncTearDown(self):
        await self.session.close()
        await self.engine.dispose()

    # -------------------------------------------------------------------------
    # Test 1: TrackedVehicle -> VehicleTrack
    # -------------------------------------------------------------------------
    async def test_01_tracked_vehicle_to_vehicle_track(self):
        """1. TrackedVehicle contract converts to VehicleTrack and persists."""
        track = TrackedVehicle(
            track_id=101,
            vehicle_type="car",
            bbox=(100.0, 150.0, 250.0, 300.0),
            confidence=0.92,
            camera_id="cam-01",
            first_seen_frame=1,
            last_seen_frame=15,
            frames_tracked=15,
            trajectory=[(175.0, 225.0)],
            type_history=["car"],
        )

        persisted = await self.service.ingest_tracked_vehicles([track], camera_id="cam-01")
        await self.session.commit()

        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0].local_track_id, 101)
        self.assertEqual(persisted[0].camera_id, "cam-01")
        self.assertEqual(persisted[0].frames_tracked, 15)
        self.assertEqual(persisted[0].last_bbox, [100.0, 150.0, 250.0, 300.0])

        stmt = select(VehicleTrack).where(VehicleTrack.local_track_id == 101)
        res = await self.session.execute(stmt)
        queried = res.scalars().first()
        self.assertIsNotNone(queried)
        self.assertEqual(queried.vehicle_type, "car")

    # -------------------------------------------------------------------------
    # Test 2: PlateObservation -> PlateObservationModel
    # -------------------------------------------------------------------------
    async def test_02_plate_observation_to_model(self):
        """2. PlateObservation converts to PlateObservationModel and persists."""
        now = datetime.now(timezone.utc)
        obs = PlateObservation(
            plate_text="MH12AB1234",
            raw_plate_text="mh 12 ab 1234",
            detection_confidence=0.91,
            ocr_confidence=0.88,
            bbox=(50.0, 60.0, 150.0, 90.0),
            frame_number=10,
            camera_id="cam-01",
            timestamp=now,
        )

        persisted = await self.service.ingest_plate_observations([obs], camera_id="cam-01")
        await self.session.commit()

        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0].plate_text, "MH12AB1234")
        self.assertEqual(persisted[0].frame_number, 10)
        self.assertAlmostEqual(persisted[0].ocr_confidence, 0.88)

        stmt = select(PlateObservationModel).where(PlateObservationModel.plate_text == "MH12AB1234")
        res = await self.session.execute(stmt)
        queried = res.scalars().first()
        self.assertIsNotNone(queried)
        self.assertEqual(queried.camera_id, "cam-01")

    # -------------------------------------------------------------------------
    # Test 3 & 4: Known plate resolves to existing canonical Vehicle without duplicates
    # -------------------------------------------------------------------------
    async def test_03_and_04_canonical_vehicle_resolution_and_deduplication(self):
        """3 & 4. Known plate resolves to canonical Vehicle, repeated observations do not duplicate."""
        now1 = datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone.utc)
        now2 = datetime(2026, 9, 15, 10, 5, 0, tzinfo=timezone.utc)

        # First observation of plate MH14DE9999
        v1 = await self.service.resolve_or_create_vehicle("MH14DE9999", "car", now1)
        await self.session.commit()
        self.assertIsNotNone(v1.vehicle_id)
        self.assertEqual(v1.canonical_plate_text, "MH14DE9999")
        self.assertEqual(v1.total_detections_count, 1)

        # Second observation of same plate (e.g. at another camera or later frame)
        v2 = await self.service.resolve_or_create_vehicle("MH14DE9999", "car", now2)
        await self.session.commit()

        # Must resolve to the exact same vehicle ID without duplicate row
        self.assertEqual(v1.vehicle_id, v2.vehicle_id)
        self.assertEqual(v2.total_detections_count, 2)
        self.assertEqual(v2.last_detected_at, now2)

        # Confirm total rows in vehicles table is exactly 1
        stmt = select(Vehicle).where(Vehicle.canonical_plate_text == "MH14DE9999")
        res = await self.session.execute(stmt)
        all_vehicles = res.scalars().all()
        self.assertEqual(len(all_vehicles), 1)

    # -------------------------------------------------------------------------
    # Test 5: Unassociated plate observation remains valid
    # -------------------------------------------------------------------------
    async def test_05_unassociated_plate_observation_persists(self):
        """5. PlateObservation without an associated track persists with track_session_id=None."""
        obs = PlateObservation(
            plate_text="DL01XY9000",
            detection_confidence=0.85,
            ocr_confidence=0.82,
            bbox=(20.0, 30.0, 100.0, 70.0),
            frame_number=25,
            camera_id="cam-02",
            track_id=None,  # No track associated
        )

        persisted = await self.service.ingest_plate_observations([obs], camera_id="cam-02")
        await self.session.commit()

        self.assertEqual(len(persisted), 1)
        self.assertIsNone(persisted[0].track_session_id)
        self.assertIsNotNone(persisted[0].vehicle_id)  # Canonical vehicle resolved
        self.assertEqual(persisted[0].plate_text, "DL01XY9000")

    # -------------------------------------------------------------------------
    # Test 6: TrafficSnapshot persists
    # -------------------------------------------------------------------------
    async def test_06_traffic_snapshot_persists(self):
        """6. TrafficSnapshot contract persists cleanly with metrics and levels."""
        now = datetime.now(timezone.utc)
        snap = TrafficSnapshot(
            camera_id="cam-01",
            active_vehicle_count=8,
            queue_length=2,
            moving_vehicles=3,
            slow_vehicles=2,
            stationary_vehicles=3,
            traffic_pressure=28.4,
            traffic_level="MEDIUM",
            timestamp=now,
            frame_number=60,
            metrics={"arrival_rate": 12.5, "occupancy": 14.0},
        )

        persisted = await self.service.ingest_traffic_snapshot(snap)
        await self.session.commit()

        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.traffic_pressure, 28.4)
        self.assertEqual(persisted.traffic_level, "MEDIUM")
        self.assertEqual(persisted.metrics["arrival_rate"], 12.5)

        stmt = select(TrafficSnapshotModel).where(TrafficSnapshotModel.camera_id == "cam-01")
        res = await self.session.execute(stmt)
        queried = res.scalars().first()
        self.assertIsNotNone(queried)
        self.assertEqual(queried.queue_length, 2)

    # -------------------------------------------------------------------------
    # Test 7: SignalDecision persists
    # -------------------------------------------------------------------------
    async def test_07_signal_decision_persists(self):
        """7. SignalDecision contract persists and correctly links junction/approach."""
        now = datetime.now(timezone.utc)
        dec = SignalDecision(
            approach_id="app-east",
            priority_score=42.5,
            green_time=50,
            reason="High queue volume detected on Eastbound approach",
        )

        persisted = await self.service.ingest_signal_decisions(
            [dec],
            junction_id="junc-main",
            timestamp=now,
        )
        await self.session.commit()

        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0].green_time, 50)
        self.assertEqual(persisted[0].junction_id, "junc-main")
        self.assertEqual(persisted[0].approach_id, "app-east")

    # -------------------------------------------------------------------------
    # Test 8: Transaction rollback works when a batch fails
    # -------------------------------------------------------------------------
    async def test_08_transaction_rollback_on_failure(self):
        """8. If an ingestion operation fails midway, changes are completely rolled back."""
        import unittest.mock

        # Pre-seed camera
        cam = CameraModel(camera_id="cam-rollback", source="file:///test.mp4")
        self.session.add(cam)
        await self.session.commit()

        # Build a valid track and observation
        valid_track = TrackedVehicle(
            track_id=505,
            vehicle_type="truck",
            bbox=(0.0, 0.0, 10.0, 10.0),
            confidence=0.8,
            camera_id="cam-rollback",
        )
        valid_obs = PlateObservation(
            plate_text="FAIL9999",
            detection_confidence=0.9,
            ocr_confidence=0.9,
            bbox=(0.0, 0.0, 1.0, 1.0),
            camera_id="cam-rollback",
        )

        frame_result = FrameResult(
            frame_number=1,
            camera_id="cam-rollback",
            tracked_vehicle_contracts=[valid_track],
            plate_observations=[valid_obs],
        )

        # Simulate a database failure during plate observation ingestion
        with unittest.mock.patch.object(
            self.service,
            "ingest_plate_observations",
            side_effect=RuntimeError("Simulated database write error"),
        ):
            with self.assertRaises(RuntimeError):
                await self.service.ingest_frame_result(frame_result)

        # Verify that track 505 was rolled back and is NOT committed in the database
        stmt = select(VehicleTrack).where(VehicleTrack.local_track_id == 505)
        res = await self.session.execute(stmt)
        self.assertIsNone(res.scalars().first())

    # -------------------------------------------------------------------------
    # Test 9: Repeated ingestion does not duplicate records
    # -------------------------------------------------------------------------
    async def test_09_idempotency_avoids_blind_duplication(self):
        """9. Ingesting the same frame multiple times updates rather than duplicating rows."""
        now = datetime.now(timezone.utc)
        track = TrackedVehicle(
            track_id=77,
            vehicle_type="car",
            bbox=(10.0, 10.0, 50.0, 50.0),
            confidence=0.9,
            camera_id="cam-idemp",
            first_seen_frame=1,
            last_seen_frame=1,
            frames_tracked=1,
        )
        obs = PlateObservation(
            plate_text="KA01AB1111",
            detection_confidence=0.88,
            ocr_confidence=0.92,
            bbox=(15.0, 15.0, 45.0, 30.0),
            frame_number=1,
            camera_id="cam-idemp",
            track_id=77,
            timestamp=now,
        )
        snap = TrafficSnapshot(
            camera_id="cam-idemp",
            active_vehicle_count=1,
            queue_length=0,
            moving_vehicles=1,
            slow_vehicles=0,
            stationary_vehicles=0,
            traffic_pressure=15.0,
            traffic_level="LOW",
            timestamp=now,
            frame_number=1,
        )
        dec = SignalDecision(
            approach_id="app-idemp",
            priority_score=10.0,
            green_time=25,
            reason="Low demand",
        )

        frame_result = FrameResult(
            frame_number=1,
            camera_id="cam-idemp",
            timestamp=now,
            tracked_vehicle_contracts=[track],
            plate_observations=[obs],
            snapshot=snap,
            signal_decisions=[dec],
        )

        # First ingestion
        res1 = await self.service.ingest_frame_result(frame_result, junction_id="junc-idemp")
        await self.session.commit()
        self.assertEqual(res1.tracks_updated, 1)
        self.assertEqual(res1.plates_persisted, 1)
        self.assertTrue(res1.snapshot_persisted)

        # Re-ingest the exact same frame result
        res2 = await self.service.ingest_frame_result(frame_result, junction_id="junc-idemp")
        await self.session.commit()

        # Total counts in database must NOT be doubled
        stmt_tracks = select(VehicleTrack).where(VehicleTrack.camera_id == "cam-idemp")
        res_t = await self.session.execute(stmt_tracks)
        self.assertEqual(len(res_t.scalars().all()), 1)

        stmt_plates = select(PlateObservationModel).where(PlateObservationModel.camera_id == "cam-idemp")
        res_p = await self.session.execute(stmt_plates)
        self.assertEqual(len(res_p.scalars().all()), 1)

        stmt_snaps = select(TrafficSnapshotModel).where(TrafficSnapshotModel.camera_id == "cam-idemp")
        res_s = await self.session.execute(stmt_snaps)
        self.assertEqual(len(res_s.scalars().all()), 1)

        stmt_vehs = select(Vehicle).where(Vehicle.canonical_plate_text == "KA01AB1111")
        res_v = await self.session.execute(stmt_vehs)
        self.assertEqual(len(res_v.scalars().all()), 1)

    # -------------------------------------------------------------------------
    # Test 10: Full FrameResult End-to-End Ingestion
    # -------------------------------------------------------------------------
    async def test_10_full_frame_result_e2e_linkage(self):
        """10. Verify full FrameResult links track to canonical vehicle and plate."""
        now = datetime.now(timezone.utc)
        track = TrackedVehicle(
            track_id=8,
            vehicle_type="car",
            bbox=(100.0, 200.0, 300.0, 400.0),
            confidence=0.94,
            camera_id="cam-demo",
            first_seen_frame=30,
            last_seen_frame=30,
            frames_tracked=1,
            trajectory=[(200.0, 300.0)],
            type_history=["car"],
        )
        obs = PlateObservation(
            plate_text="TS09AB9999",
            detection_confidence=0.91,
            ocr_confidence=0.95,
            bbox=(150.0, 250.0, 250.0, 280.0),
            frame_number=30,
            camera_id="cam-demo",
            track_id=8,  # Associated with track 8
            timestamp=now,
        )
        snap = TrafficSnapshot(
            camera_id="cam-demo",
            active_vehicle_count=1,
            queue_length=1,
            moving_vehicles=0,
            slow_vehicles=0,
            stationary_vehicles=1,
            traffic_pressure=25.0,
            traffic_level="MEDIUM",
            timestamp=now,
            frame_number=30,
        )
        dec = SignalDecision(
            approach_id="app-demo",
            priority_score=15.0,
            green_time=60,
            reason="Standard cycle",
        )

        frame = FrameResult(
            frame_number=30,
            camera_id="cam-demo",
            timestamp=now,
            tracked_vehicle_contracts=[track],
            plate_observations=[obs],
            snapshot=snap,
            signal_decisions=[dec],
        )

        summary = await self.service.ingest_frame_result(frame, junction_id="junc-demo")
        await self.session.commit()

        self.assertEqual(summary.tracks_updated, 1)
        self.assertEqual(summary.plates_persisted, 1)
        self.assertTrue(summary.snapshot_persisted)
        self.assertEqual(summary.decisions_persisted, 1)

        # Verify track got linked to the canonical vehicle
        stmt_t = select(VehicleTrack).where(VehicleTrack.local_track_id == 8)
        res_t = await self.session.execute(stmt_t)
        persisted_track = res_t.scalars().first()
        self.assertIsNotNone(persisted_track)
        self.assertIsNotNone(persisted_track.vehicle_id)

        # Verify plate got linked to the same canonical vehicle and track session
        stmt_o = select(PlateObservationModel).where(PlateObservationModel.plate_text == "TS09AB9999")
        res_o = await self.session.execute(stmt_o)
        persisted_obs = res_o.scalars().first()
        self.assertIsNotNone(persisted_obs)
        self.assertEqual(persisted_obs.vehicle_id, persisted_track.vehicle_id)
        self.assertEqual(persisted_obs.track_session_id, persisted_track.track_session_id)


if __name__ == "__main__":
    unittest.main()
