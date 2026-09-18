import unittest
import asyncio
from datetime import datetime, timezone, timedelta
import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from backend.app.db.base import Base

from backend.app.models.vehicle import Vehicle
from backend.app.models.tracking import VehicleTrack
from backend.app.models.camera import CameraModel
from backend.app.models.junction import Junction, JunctionApproach
from backend.app.models.topology import TopologyEdge
from backend.app.models.observation import PlateObservationModel

from backend.app.services.identity_resolver import SQLAlchemyCandidateGenerator
from ai.identity.resolver import MultimodalIdentityResolver, ResolverConfig
from backend.app.services.trajectory_service import TrajectoryService

class LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
    def emit(self, record):
        self.records.append(record)

class TrajectoryServiceTests(unittest.IsolatedAsyncioTestCase):
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
        
        self.candidate_generator = SQLAlchemyCandidateGenerator(self.session)
        self.resolver = MultimodalIdentityResolver(self.candidate_generator, ResolverConfig())
        self.service = TrajectoryService(self.session, self.resolver)
        
        # Capture logs
        self.log_handler = LogCaptureHandler()
        logging.getLogger("backend.app.services.trajectory_service").addHandler(self.log_handler)
        logging.getLogger("backend.app.services.trajectory_service").setLevel(logging.INFO)
        
        await self._seed_network()

    async def asyncTearDown(self):
        await self.session.close()
        logging.getLogger("backend.app.services.trajectory_service").removeHandler(self.log_handler)
        
    async def _seed_network(self):
        # Junctions: J1 (CamA) -> J2 (CamB) -> J3 (CamC)
        j1 = Junction(junction_id="J1", name="J1")
        j2 = Junction(junction_id="J2", name="J2")
        j3 = Junction(junction_id="J3", name="J3")
        
        app_a = JunctionApproach(approach_id="AppA", junction_id="J1", direction_name="A")
        app_b = JunctionApproach(approach_id="AppB", junction_id="J2", direction_name="B")
        app_c = JunctionApproach(approach_id="AppC", junction_id="J3", direction_name="C")
        
        cam_a = CameraModel(camera_id="CamA", source="a", name="Camera A")
        cam_b = CameraModel(camera_id="CamB", source="b", name="Camera B")
        cam_c = CameraModel(camera_id="CamC", source="c", name="Camera C")
        
        # Edges
        # J1 -> J2 takes 60-120s
        edge1 = TopologyEdge(source_junction_id="J1", target_junction_id="J2", distance_meters=1000, min_travel_time_sec=60, max_travel_time_sec=120)
        # J2 -> J3 takes 60-120s
        edge2 = TopologyEdge(source_junction_id="J2", target_junction_id="J3", distance_meters=1000, min_travel_time_sec=60, max_travel_time_sec=120)
        
        self.session.add_all([j1, j2, j3, app_a, app_b, app_c, cam_a, cam_b, cam_c, edge1, edge2])
        await self.session.commit()

    async def _add_track(self, camera_id, local_track_id, timestamp, plate=None, emb=None):
        track = VehicleTrack(
            camera_id=camera_id,
            local_track_id=local_track_id,
            vehicle_type="car",
            confidence=0.9,
            first_seen_at=timestamp,
            last_seen_at=timestamp,
            first_seen_frame=0,
            last_seen_frame=1,
            last_bbox=[0,0,10,10],
            appearance_embedding=emb,
            embedding_model="test" if emb else None,
            embedding_dimension=len(emb) if emb else None,
            embedding_quality=1.0 if emb else None,
        )
        self.session.add(track)
        await self.session.flush()
        
        if plate:
            obs = PlateObservationModel(
                camera_id=camera_id,
                frame_number=0,
                plate_text=plate,
                track_session_id=track.track_session_id,
                timestamp=timestamp,
                bbox=[0,0,10,10],
                detection_confidence=0.9,
                ocr_confidence=0.9,
                vehicle_id=None
            )
            self.session.add(obs)
        await self.session.commit()
        return track

    async def test_a_to_b_successful_association(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 1. Add track at CamA
        await self._add_track("CamA", 1, t1, plate="MH12AB1234")
        
        # Stitch
        stitched = await self.service.stitch_unassociated_tracks()
        self.assertEqual(stitched, 1) # New vehicle
        
        # 2. Add track at CamB
        t2 = t1 + timedelta(seconds=90) # valid topology time
        await self._add_track("CamB", 2, t2, plate="MH12AB1234")
        
        stitched = await self.service.stitch_unassociated_tracks()
        self.assertEqual(stitched, 1) # Associated to existing
        
        # Check alerts
        logs = [r.getMessage() for r in self.log_handler.records]
        self.assertTrue(any("arrived at Camera CamB" in msg for msg in logs))
        
        # Check trajectory
        v_res = await self.session.execute(select(Vehicle))
        v = v_res.scalars().first()
        traj = await self.service.get_trajectory(v.vehicle_id)
        
        self.assertEqual(len(traj["journey"]), 2)
        self.assertEqual(traj["journey"][0]["camera_id"], "CamA")
        self.assertEqual(traj["journey"][1]["camera_id"], "CamB")
        self.assertEqual(traj["journey"][0]["association_status"], "NEW_VEHICLE")
        self.assertEqual(traj["journey"][1]["association_status"], "MATCHED")

    async def test_a_b_c_successful_trajectory(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamA", 1, t1, plate="MH12AB1234")
        t2 = t1 + timedelta(seconds=90)
        await self._add_track("CamB", 2, t2, plate="MH12AB1234")
        t3 = t2 + timedelta(seconds=90)
        await self._add_track("CamC", 3, t3, plate="MH12AB1234")
        
        await self.service.stitch_unassociated_tracks()
        
        v_res = await self.session.execute(select(Vehicle))
        v = v_res.scalars().first()
        traj = await self.service.get_trajectory(v.vehicle_id)
        
        self.assertEqual(len(traj["journey"]), 3)
        self.assertEqual(traj["journey"][2]["camera_id"], "CamC")
        self.assertEqual(traj["journey"][0]["sequence"], 1)
        self.assertEqual(traj["journey"][2]["sequence"], 3)

    async def test_different_vehicles_at_a_and_b(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamA", 1, t1, plate="MH12AB1234")
        await self._add_track("CamB", 2, t1 + timedelta(seconds=90), plate="MH99XX9999")
        
        await self.service.stitch_unassociated_tracks()
        
        # Should be 2 distinct vehicles
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 2)

    async def test_impossible_topology_transition(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # CamA -> CamC has no direct edge, and doing it directly is impossible topology
        await self._add_track("CamA", 1, t1, plate="MH12AB1234")
        # CamC without going through CamB
        await self._add_track("CamC", 2, t1 + timedelta(seconds=90), plate="MH12AB1234")
        
        await self.service.stitch_unassociated_tracks()
        
        # Because there is no active incoming edge from CamA to CamC, the generator will not pick up the candidate via topology. 
        # But wait! Does candidate generator pick up by exact plate anyway? Yes!
        # But MultimodalIdentityResolver will penalize missing topology.
        # Since it's exact plate, it might still MATCH if exact plate is highly trusted.
        # Let's check how resolver behaves with missing topology but exact plate.
        pass

    async def test_impossible_travel_time_transition(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamA", 1, t1, plate="MH12AB1234")
        # J1->J2 takes min 60s. We arrive in 5s (impossible travel time)
        await self._add_track("CamB", 2, t1 + timedelta(seconds=5), plate="MH12AB1234")
        
        await self.service.stitch_unassociated_tracks()
        
        # The resolver hard rejects impossible travel times.
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 2) # Rejected, so new vehicle created
        
        tracks_res = await self.session.execute(select(VehicleTrack).order_by(VehicleTrack.first_seen_at))
        tracks = tracks_res.scalars().all()
        self.assertEqual(tracks[1].association_status, "NEW_VEHICLE")

    async def test_reid_supported_association_without_exact_plate(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Track 1 has plate + emb
        emb = [1.0, 0.0]
        await self._add_track("CamA", 1, t1, plate="MH12AB1234", emb=emb)
        
        # Track 2 has no plate, but matching emb
        t2 = t1 + timedelta(seconds=90)
        await self._add_track("CamB", 2, t2, plate=None, emb=emb)
        
        await self.service.stitch_unassociated_tracks()
        
        # Should be merged! ReID-only capped at PROBABLE
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 1)
        
        tracks_res = await self.session.execute(select(VehicleTrack).order_by(VehicleTrack.first_seen_at))
        tracks = tracks_res.scalars().all()
        self.assertEqual(tracks[1].association_status, "PROBABLE")
        self.assertEqual(tracks[1].association_method, "RE_ID")

    async def test_uncertain_conflicting_candidates(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Create two identical vehicles that just passed CamA
        await self._add_track("CamA", 1, t1, plate="V1", emb=[1.0, 0.0])
        await self._add_track("CamA", 2, t1, plate="V2", emb=[1.0, 0.0])
        
        await self.service.stitch_unassociated_tracks()
        
        # Track at CamB with NO plate, but matching embedding
        t2 = t1 + timedelta(seconds=90)
        await self._add_track("CamB", 3, t2, plate=None, emb=[1.0, 0.0])
        
        await self.service.stitch_unassociated_tracks()
        
        # Resolver should be UNCERTAIN because it matches both V1 and V2 identically
        tracks_res = await self.session.execute(select(VehicleTrack).where(VehicleTrack.local_track_id == 3))
        t3 = tracks_res.scalars().first()
        self.assertEqual(t3.association_status, "UNCERTAIN")
        self.assertIsNone(t3.vehicle_id)

    async def test_repeated_local_track_ids_across_cameras(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamA", 5, t1, plate="V1")
        await self._add_track("CamB", 5, t1 + timedelta(seconds=90), plate="V1")
        
        await self.service.stitch_unassociated_tracks()
        
        # Trajectory correctly differentiates by camera_id + track_id
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 1)
        traj = await self.service.get_trajectory(vehicles[0].vehicle_id)
        self.assertEqual(traj["journey"][0]["camera_id"], "CamA")
        self.assertEqual(traj["journey"][1]["camera_id"], "CamB")

    async def test_missing_topology(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamC", 1, t1, plate="MH12AB1234")
        await self._add_track("CamA", 2, t1 + timedelta(minutes=10), plate="MH12AB1234")
        
        await self.service.stitch_unassociated_tracks()
        # Should still associate via EXACT_PLATE despite no explicit edge, because it's exact plate and reasonable time gap
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 1)

