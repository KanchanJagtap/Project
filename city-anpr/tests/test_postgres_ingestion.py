"""
Real PostgreSQL Integration Test for Database & Ingestion Foundation (Milestone 2C).

Tests the IngestionService directly against a live PostgreSQL instance.
Requires PostgreSQL to be running and configured via settings.DATABASE_URL.
If PostgreSQL is unreachable, tests are skipped with a clear explanatory message.
"""

import asyncio
import os
import unittest
from datetime import datetime, timezone

from sqlalchemy import delete, select, text
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

from backend.app.core.config import settings
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


def is_postgres_available() -> bool:
    """Synchronously test if PostgreSQL is reachable via asyncpg."""
    try:
        import asyncpg

        async def _ping():
            # Parse asyncpg DSN
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
    f"PostgreSQL is not reachable at {settings.DATABASE_URL}. Skipping live PostgreSQL tests.",
)
class RealPostgresIngestionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Connect to the live PostgreSQL database
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

        # Clean up test rows before each test to maintain clean state
        await self._cleanup_test_data()

    async def asyncTearDown(self):
        await self._cleanup_test_data()
        await self.session.close()
        await self.engine.dispose()

    async def _cleanup_test_data(self):
        """Purge records created by the test suite."""
        async with self.session_factory() as cleanup_session:
            # Delete in foreign key dependency order
            await cleanup_session.execute(delete(SignalDecisionModel))
            await cleanup_session.execute(delete(TrafficSnapshotModel))
            await cleanup_session.execute(delete(PlateObservationModel))
            await cleanup_session.execute(delete(VehicleTrack))
            await cleanup_session.execute(delete(Vehicle))
            await cleanup_session.execute(delete(JunctionApproach))
            await cleanup_session.execute(delete(CameraModel))
            await cleanup_session.execute(delete(Junction))
            await cleanup_session.commit()

    # -------------------------------------------------------------------------
    # Test 1 & 2: Junction and Camera Exist
    # -------------------------------------------------------------------------
    async def test_01_and_02_junction_and_camera_exist(self):
        """1 & 2. Verify Junction and Camera records are created and retrieved in PostgreSQL."""
        junction = Junction(
            junction_id="pg-junc-01",
            name="Pune Station Chowk",
            latitude=18.5289,
            longitude=73.8744,
            target_cycle_seconds=120,
            status="NORMAL",
        )
        camera = CameraModel(
            camera_id="pg-cam-01",
            source="rtsp://10.0.0.1:554/live",
            name="Station North Approach Camera",
            enabled=True,
        )
        approach = JunctionApproach(
            approach_id="pg-app-01-n",
            junction_id="pg-junc-01",
            camera_id="pg-cam-01",
            direction_name="Northbound Entry",
            cardinal_direction="N",
        )
        self.session.add_all([junction, camera, approach])
        await self.session.commit()

        # Query back via PostgreSQL
        stmt_j = select(Junction).where(Junction.junction_id == "pg-junc-01")
        res_j = await self.session.execute(stmt_j)
        db_junction = res_j.scalars().first()
        self.assertIsNotNone(db_junction)
        self.assertEqual(db_junction.name, "Pune Station Chowk")

        stmt_c = select(CameraModel).where(CameraModel.camera_id == "pg-cam-01")
        res_c = await self.session.execute(stmt_c)
        db_cam = res_c.scalars().first()
        self.assertIsNotNone(db_cam)
        self.assertEqual(db_cam.source, "rtsp://10.0.0.1:554/live")

    # -------------------------------------------------------------------------
    # Test 3: Tracked vehicle creates/updates VehicleTrack in PostgreSQL
    # -------------------------------------------------------------------------
    async def test_03_tracked_vehicle_creates_and_updates_track(self):
        """3. Tracked vehicle creates a VehicleTrack and subsequent frames update it."""
        track_frame1 = TrackedVehicle(
            track_id=42,
            vehicle_type="car",
            bbox=(100.0, 100.0, 200.0, 200.0),
            confidence=0.91,
            camera_id="pg-cam-track",
            first_seen_frame=1,
            last_seen_frame=1,
            frames_tracked=1,
            trajectory=[(150.0, 150.0)],
            type_history=["car"],
        )

        persisted1 = await self.service.ingest_tracked_vehicles(
            [track_frame1], camera_id="pg-cam-track"
        )
        await self.session.commit()
        self.assertEqual(len(persisted1), 1)
        self.assertEqual(persisted1[0].frames_tracked, 1)

        # Simulate frame 10: vehicle moves and frames_tracked increments
        track_frame10 = TrackedVehicle(
            track_id=42,
            vehicle_type="car",
            bbox=(120.0, 120.0, 220.0, 220.0),
            confidence=0.95,
            camera_id="pg-cam-track",
            first_seen_frame=1,
            last_seen_frame=10,
            frames_tracked=10,
            trajectory=[(150.0, 150.0), (170.0, 170.0)],
            type_history=["car"],
        )
        persisted10 = await self.service.ingest_tracked_vehicles(
            [track_frame10], camera_id="pg-cam-track"
        )
        await self.session.commit()

        # Must update the continuous session, not create a second row
        self.assertEqual(persisted10[0].track_session_id, persisted1[0].track_session_id)
        self.assertEqual(persisted10[0].frames_tracked, 10)

        stmt = select(VehicleTrack).where(VehicleTrack.camera_id == "pg-cam-track")
        res = await self.session.execute(stmt)
        all_tracks = res.scalars().all()
        self.assertEqual(len(all_tracks), 1)
        self.assertEqual(all_tracks[0].best_confidence, 0.95)

    # -------------------------------------------------------------------------
    # Test 4 & 5: Known plate resolves/reuses canonical Vehicle
    # -------------------------------------------------------------------------
    async def test_04_and_05_known_plate_canonical_vehicle_reuse(self):
        """4 & 5. Known plate creates canonical Vehicle, repeated observation reuses it."""
        t1 = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 15, 12, 10, 0, tzinfo=timezone.utc)

        v1 = await self.service.resolve_or_create_vehicle("MH12PQ1234", "car", t1)
        await self.session.commit()
        self.assertIsNotNone(v1.vehicle_id)
        self.assertEqual(v1.canonical_plate_text, "MH12PQ1234")
        self.assertEqual(v1.total_detections_count, 1)

        # Repeated observation of same plate
        v2 = await self.service.resolve_or_create_vehicle("MH12PQ1234", "car", t2)
        await self.session.commit()

        self.assertEqual(v1.vehicle_id, v2.vehicle_id)
        self.assertEqual(v2.total_detections_count, 2)
        self.assertEqual(v2.last_detected_at, t2)

        # Verify exactly one row in PostgreSQL
        stmt = select(Vehicle).where(Vehicle.canonical_plate_text == "MH12PQ1234")
        res = await self.session.execute(stmt)
        self.assertEqual(len(res.scalars().all()), 1)

    # -------------------------------------------------------------------------
    # Test 6: PlateObservation correctly linked to VehicleTrack
    # -------------------------------------------------------------------------
    async def test_06_plate_observation_linked_to_vehicle_track(self):
        """6. Associated PlateObservation links to VehicleTrack and sets Vehicle on track."""
        now = datetime.now(timezone.utc)
        track = TrackedVehicle(
            track_id=88,
            vehicle_type="bus",
            bbox=(50.0, 50.0, 300.0, 300.0),
            confidence=0.92,
            camera_id="pg-cam-assoc",
        )
        obs = PlateObservation(
            plate_text="MH12BUS1",
            detection_confidence=0.88,
            ocr_confidence=0.90,
            bbox=(80.0, 200.0, 180.0, 240.0),
            frame_number=20,
            camera_id="pg-cam-assoc",
            track_id=88,
            timestamp=now,
        )

        frame = FrameResult(
            frame_number=20,
            camera_id="pg-cam-assoc",
            timestamp=now,
            tracked_vehicle_contracts=[track],
            plate_observations=[obs],
        )

        await self.service.ingest_frame_result(frame)
        await self.session.commit()

        # Query track and plate observation from PostgreSQL
        stmt_t = select(VehicleTrack).where(VehicleTrack.camera_id == "pg-cam-assoc")
        res_t = await self.session.execute(stmt_t)
        db_track = res_t.scalars().first()
        self.assertIsNotNone(db_track)
        self.assertIsNotNone(db_track.vehicle_id)

        stmt_p = select(PlateObservationModel).where(PlateObservationModel.camera_id == "pg-cam-assoc")
        res_p = await self.session.execute(stmt_p)
        db_plate = res_p.scalars().first()
        self.assertIsNotNone(db_plate)
        self.assertEqual(db_plate.track_session_id, db_track.track_session_id)
        self.assertEqual(db_plate.vehicle_id, db_track.vehicle_id)

    # -------------------------------------------------------------------------
    # Test 7: Unassociated PlateObservation without VehicleTrack
    # -------------------------------------------------------------------------
    async def test_07_unassociated_plate_observation(self):
        """7. PlateObservation without track_id persists with track_session_id=NULL."""
        now = datetime.now(timezone.utc)
        obs = PlateObservation(
            plate_text="MH14SOLO",
            detection_confidence=0.89,
            ocr_confidence=0.93,
            bbox=(10.0, 20.0, 100.0, 50.0),
            frame_number=5,
            camera_id="pg-cam-unassoc",
            track_id=None,
            timestamp=now,
        )

        frame = FrameResult(
            frame_number=5,
            camera_id="pg-cam-unassoc",
            timestamp=now,
            plate_observations=[obs],
        )

        await self.service.ingest_frame_result(frame)
        await self.session.commit()

        stmt = select(PlateObservationModel).where(PlateObservationModel.plate_text == "MH14SOLO")
        res = await self.session.execute(stmt)
        db_plate = res.scalars().first()
        self.assertIsNotNone(db_plate)
        self.assertIsNone(db_plate.track_session_id)
        self.assertIsNotNone(db_plate.vehicle_id)

    # -------------------------------------------------------------------------
    # Test 8: TrafficSnapshot is persisted
    # -------------------------------------------------------------------------
    async def test_08_traffic_snapshot_persists(self):
        """8. TrafficSnapshot is persisted with metrics in PostgreSQL."""
        now = datetime.now(timezone.utc)
        snap = TrafficSnapshot(
            camera_id="pg-cam-snap",
            active_vehicle_count=15,
            queue_length=4,
            moving_vehicles=6,
            slow_vehicles=4,
            stationary_vehicles=5,
            traffic_pressure=38.5,
            traffic_level="MEDIUM",
            timestamp=now,
            frame_number=90,
            metrics={"arrival_rate": 20.0, "road_occupancy": 18.5},
        )

        frame = FrameResult(
            frame_number=90,
            camera_id="pg-cam-snap",
            timestamp=now,
            snapshot=snap,
        )

        await self.service.ingest_frame_result(frame)
        await self.session.commit()

        stmt = select(TrafficSnapshotModel).where(TrafficSnapshotModel.camera_id == "pg-cam-snap")
        res = await self.session.execute(stmt)
        db_snap = res.scalars().first()
        self.assertIsNotNone(db_snap)
        self.assertEqual(db_snap.active_vehicle_count, 15)
        self.assertEqual(db_snap.queue_length, 4)
        self.assertEqual(db_snap.traffic_pressure, 38.5)
        self.assertEqual(db_snap.metrics["arrival_rate"], 20.0)

    # -------------------------------------------------------------------------
    # Test 9: SignalDecision is persisted
    # -------------------------------------------------------------------------
    async def test_09_signal_decision_persists(self):
        """9. SignalDecision is persisted and correctly links junction and approach."""
        now = datetime.now(timezone.utc)
        dec = SignalDecision(
            approach_id="pg-app-sig",
            priority_score=68.2,
            green_time=55,
            reason="Priority allocation based on queue pressure",
        )

        frame = FrameResult(
            frame_number=90,
            camera_id="pg-cam-sig",
            timestamp=now,
            signal_decisions=[dec],
        )

        await self.service.ingest_frame_result(frame, junction_id="pg-junc-sig")
        await self.session.commit()

        stmt = select(SignalDecisionModel).where(SignalDecisionModel.approach_id == "pg-app-sig")
        res = await self.session.execute(stmt)
        db_dec = res.scalars().first()
        self.assertIsNotNone(db_dec)
        self.assertEqual(db_dec.green_time, 55)
        self.assertEqual(db_dec.priority_score, 68.2)
        self.assertEqual(db_dec.junction_id, "pg-junc-sig")

    # -------------------------------------------------------------------------
    # Test 10: Re-ingesting same data does not blindly duplicate rows
    # -------------------------------------------------------------------------
    async def test_10_reingesting_does_not_duplicate_rows(self):
        """10. Re-ingesting the exact same frame result updates instead of duplicating rows."""
        now = datetime.now(timezone.utc)
        track = TrackedVehicle(
            track_id=10,
            vehicle_type="car",
            bbox=(10.0, 10.0, 80.0, 80.0),
            confidence=0.9,
            camera_id="pg-cam-idemp",
        )
        obs = PlateObservation(
            plate_text="MH12IDEMP1",
            detection_confidence=0.9,
            ocr_confidence=0.9,
            bbox=(20.0, 20.0, 60.0, 40.0),
            frame_number=1,
            camera_id="pg-cam-idemp",
            track_id=10,
            timestamp=now,
        )
        snap = TrafficSnapshot(
            camera_id="pg-cam-idemp",
            active_vehicle_count=1,
            queue_length=0,
            moving_vehicles=1,
            slow_vehicles=0,
            stationary_vehicles=0,
            traffic_pressure=10.0,
            traffic_level="LOW",
            timestamp=now,
            frame_number=1,
        )
        dec = SignalDecision(
            approach_id="pg-app-idemp",
            priority_score=12.0,
            green_time=30,
            reason="Low demand",
        )

        frame = FrameResult(
            frame_number=1,
            camera_id="pg-cam-idemp",
            timestamp=now,
            tracked_vehicle_contracts=[track],
            plate_observations=[obs],
            snapshot=snap,
            signal_decisions=[dec],
        )

        # Ingestion 1
        await self.service.ingest_frame_result(frame, junction_id="pg-junc-idemp")
        await self.session.commit()

        # Ingestion 2 (exact same frame)
        await self.service.ingest_frame_result(frame, junction_id="pg-junc-idemp")
        await self.session.commit()

        # Confirm counts in PostgreSQL
        res_t = await self.session.execute(select(VehicleTrack).where(VehicleTrack.camera_id == "pg-cam-idemp"))
        self.assertEqual(len(res_t.scalars().all()), 1)

        res_p = await self.session.execute(select(PlateObservationModel).where(PlateObservationModel.camera_id == "pg-cam-idemp"))
        self.assertEqual(len(res_p.scalars().all()), 1)

        res_s = await self.session.execute(select(TrafficSnapshotModel).where(TrafficSnapshotModel.camera_id == "pg-cam-idemp"))
        self.assertEqual(len(res_s.scalars().all()), 1)

        res_v = await self.session.execute(select(Vehicle).where(Vehicle.canonical_plate_text == "MH12IDEMP1"))
        self.assertEqual(len(res_v.scalars().all()), 1)

    # -------------------------------------------------------------------------
    # Test 11: Transaction failure rolls back all writes
    # -------------------------------------------------------------------------
    async def test_11_transaction_failure_rolls_back_all_writes(self):
        """11. An unhandled exception midway through batch ingestion rolls back all writes."""
        import unittest.mock

        track = TrackedVehicle(
            track_id=777,
            vehicle_type="car",
            bbox=(0.0, 0.0, 10.0, 10.0),
            confidence=0.85,
            camera_id="pg-cam-rollback",
        )
        obs = PlateObservation(
            plate_text="MH12ROLLBACK",
            detection_confidence=0.9,
            ocr_confidence=0.9,
            bbox=(0.0, 0.0, 5.0, 5.0),
            camera_id="pg-cam-rollback",
        )

        frame = FrameResult(
            frame_number=1,
            camera_id="pg-cam-rollback",
            tracked_vehicle_contracts=[track],
            plate_observations=[obs],
        )

        # Force a failure during plate observation ingestion
        with unittest.mock.patch.object(
            self.service,
            "ingest_plate_observations",
            side_effect=RuntimeError("Simulated PostgreSQL connection failure"),
        ):
            with self.assertRaises(RuntimeError):
                await self.service.ingest_frame_result(frame)

        # Verify track 777 was NOT committed to PostgreSQL
        stmt = select(VehicleTrack).where(VehicleTrack.local_track_id == 777)
        res = await self.session.execute(stmt)
        self.assertIsNone(res.scalars().first())


if __name__ == "__main__":
    unittest.main()
