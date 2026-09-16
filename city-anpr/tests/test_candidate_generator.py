import unittest
from datetime import datetime, timezone
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from backend.app.db.base import Base

from backend.app.models.vehicle import Vehicle
from backend.app.models.tracking import VehicleTrack
from backend.app.models.camera import CameraModel
from backend.app.models.junction import Junction, JunctionApproach
from backend.app.models.topology import TopologyEdge
from backend.app.services.identity_resolver import SQLAlchemyCandidateGenerator

class CandidateGeneratorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.session = self.session_factory()
        self.generator = SQLAlchemyCandidateGenerator(self.session)
        
        await self._seed_data()

    async def _seed_data(self):
        # Create Junctions
        j_target = Junction(junction_id="J_TARGET", name="Target Junction")
        j_source_valid = Junction(junction_id="J_VALID", name="Valid Source")
        j_source_invalid = Junction(junction_id="J_INVALID", name="Invalid Source")
        
        self.session.add_all([j_target, j_source_valid, j_source_invalid])
        
        # Create Approaches
        a_target = JunctionApproach(approach_id="A_TARGET", junction_id="J_TARGET", direction_name="North")
        a_valid = JunctionApproach(approach_id="A_VALID", junction_id="J_VALID", direction_name="South")
        a_invalid = JunctionApproach(approach_id="A_INVALID", junction_id="J_INVALID", direction_name="East")
        
        self.session.add_all([a_target, a_valid, a_invalid])
        
        # Create Cameras
        cam_target = CameraModel(camera_id="CAM_TARGET", source="cam1", name="Cam T")
        cam_valid = CameraModel(camera_id="CAM_VALID", source="cam2", name="Cam V")
        cam_invalid = CameraModel(camera_id="CAM_INVALID", source="cam3", name="Cam I")
        
        cam_target.approach = a_target
        cam_valid.approach = a_valid
        cam_invalid.approach = a_invalid
        
        self.session.add_all([cam_target, cam_valid, cam_invalid])
        
        # Create TopologyEdge J_VALID -> J_TARGET
        edge = TopologyEdge(source_junction_id="J_VALID", target_junction_id="J_TARGET", distance_meters=100, min_travel_time_sec=10, max_travel_time_sec=100, is_active=True)
        self.session.add(edge)
        
        # Base Timestamp
        self.ts = datetime.fromtimestamp(2000, tz=timezone.utc)
        
        # Vehicle 1: Topology-valid recent track
        v1 = Vehicle(canonical_plate_text="V1", canonical_vehicle_type="car", first_detected_at=self.ts, last_detected_at=self.ts)
        t1 = VehicleTrack(camera_id="CAM_VALID", local_track_id=1, vehicle_type="car", confidence=0.9, first_seen_at=self.ts, last_seen_at=self.ts, first_seen_frame=0, last_seen_frame=0, frames_tracked=1, last_bbox=[0,0,0,0])
        t1.vehicle = v1
        self.session.add_all([v1, t1])
        
        # Vehicle 2: Wrong-source-junction recent track
        v2 = Vehicle(canonical_plate_text="V2", canonical_vehicle_type="car", first_detected_at=self.ts, last_detected_at=self.ts)
        t2 = VehicleTrack(camera_id="CAM_INVALID", local_track_id=2, vehicle_type="car", confidence=0.9, first_seen_at=self.ts, last_seen_at=self.ts, first_seen_frame=0, last_seen_frame=0, frames_tracked=1, last_bbox=[0,0,0,0])
        t2.vehicle = v2
        self.session.add_all([v2, t2])
        
        # Vehicle 3: Old track outside recent temporal window
        ts_old = datetime.fromtimestamp(100, tz=timezone.utc) # Much older
        v3 = Vehicle(canonical_plate_text="V3", canonical_vehicle_type="car", first_detected_at=ts_old, last_detected_at=ts_old)
        t3 = VehicleTrack(camera_id="CAM_VALID", local_track_id=3, vehicle_type="car", confidence=0.9, first_seen_at=ts_old, last_seen_at=ts_old, first_seen_frame=0, last_seen_frame=0, frames_tracked=1, last_bbox=[0,0,0,0])
        t3.vehicle = v3
        self.session.add_all([v3, t3])
        
        await self.session.commit()

    async def asyncTearDown(self):
        await self.session.close()
        await self.engine.dispose()

    async def test_01_topology_valid_recent_track(self):
        # We query from CAM_TARGET at ts=2010. v1 was seen at CAM_VALID (valid edge) at 2000.
        candidates = await self.generator.get_candidates(
            plate_texts=[],
            current_camera_id="CAM_TARGET",
            timestamp=datetime.fromtimestamp(2010, tz=timezone.utc)
        )
        # Should return v1
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].canonical_plate_text, "V1")

    async def test_02_exact_plate(self):
        # Query with plate V2, which is from invalid junction, but exact plate overrides topology constraint
        candidates = await self.generator.get_candidates(
            plate_texts=["V2"],
            current_camera_id="CAM_TARGET",
            timestamp=datetime.fromtimestamp(2010, tz=timezone.utc)
        )
        # Should return both V1 (topology) and V2 (exact plate)
        plates = [c.canonical_plate_text for c in candidates]
        self.assertIn("V1", plates)
        self.assertIn("V2", plates)
        self.assertEqual(len(candidates), 2)
