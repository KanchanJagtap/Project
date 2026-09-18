import unittest
import asyncio
from datetime import datetime, timezone, timedelta
import uuid
import logging

from sqlalchemy import select
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
from ai.identity.contracts import AssociationStatus

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
        
        self.log_handler = LogCaptureHandler()
        logging.getLogger("backend.app.services.trajectory_service").addHandler(self.log_handler)
        logging.getLogger("backend.app.services.trajectory_service").setLevel(logging.INFO)
        
        await self._seed_network()

    async def asyncTearDown(self):
        await self.session.close()
        logging.getLogger("backend.app.services.trajectory_service").removeHandler(self.log_handler)
        
    async def _seed_network(self):
        j1 = Junction(junction_id="J1", name="J1")
        j2 = Junction(junction_id="J2", name="J2")
        j3 = Junction(junction_id="J3", name="J3")
        
        app_a = JunctionApproach(approach_id="AppA", junction_id="J1", direction_name="A", camera_id="CamA")
        app_b = JunctionApproach(approach_id="AppB", junction_id="J2", direction_name="B", camera_id="CamB")
        app_c = JunctionApproach(approach_id="AppC", junction_id="J3", direction_name="C", camera_id="CamC")
        
        cam_a = CameraModel(camera_id="CamA", source="a", name="Camera A")
        cam_b = CameraModel(camera_id="CamB", source="b", name="Camera B")
        cam_c = CameraModel(camera_id="CamC", source="c", name="Camera C")
        
        edge1 = TopologyEdge(source_junction_id="J1", target_junction_id="J2", distance_meters=1000, min_travel_time_sec=60, max_travel_time_sec=120)
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
        await self._add_track("CamA", 1, t1, plate="MH12AB1234")
        await self.service.stitch_unassociated_tracks()
        
        t2 = t1 + timedelta(seconds=90)
        await self._add_track("CamB", 2, t2, plate="MH12AB1234")
        result = await self.service.stitch_unassociated_tracks()
        
        events = result.events
        arrival_events = [e for e in events if e["event_type"] == "VEHICLE_CAMERA_ARRIVAL"]
        self.assertEqual(len(arrival_events), 1)
        self.assertEqual(arrival_events[0]["from_camera_id"], "CamA")
        self.assertEqual(arrival_events[0]["to_camera_id"], "CamB")

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
        
        journey = traj["journey"]
        self.assertEqual(len(journey), 5)
        self.assertEqual(journey[0]["type"], "track")
        self.assertEqual(journey[1]["type"], "transition")
        self.assertEqual(journey[1]["from_camera_id"], "CamA")
        self.assertEqual(journey[1]["to_camera_id"], "CamB")
        self.assertEqual(journey[2]["type"], "track")
        self.assertEqual(journey[3]["type"], "transition")
        self.assertEqual(journey[3]["from_camera_id"], "CamB")
        self.assertEqual(journey[3]["to_camera_id"], "CamC")

    async def test_different_vehicles_at_a_and_b(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamA", 1, t1, plate="MH12AB1234")
        await self._add_track("CamB", 2, t1 + timedelta(seconds=90), plate="MH99XX9999")
        
        await self.service.stitch_unassociated_tracks()
        
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 2)

    async def test_impossible_topology_transition(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        emb = [1.0, 0.0]
        await self._add_track("CamA", 1, t1, plate="MH12AB1234", emb=emb)
        await self.service.stitch_unassociated_tracks()
        
        # Track 2 at CamC has NO plate, but same embedding
        # Because there's no topology A->C, it won't be retrieved as a candidate.
        await self._add_track("CamC", 2, t1 + timedelta(seconds=90), plate=None, emb=emb)
        
        await self.service.stitch_unassociated_tracks()
        
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 1)
        
        tracks_res = await self.session.execute(select(VehicleTrack).order_by(VehicleTrack.first_seen_at))
        tracks = tracks_res.scalars().all()
        self.assertEqual(tracks[1].association_status, "ANONYMOUS")
        self.assertIsNone(tracks[1].vehicle_id)

    async def test_impossible_travel_time_transition(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamA", 1, t1, plate="MH12AB1234")
        await self._add_track("CamB", 2, t1 + timedelta(seconds=5), plate="MH12AB1234")
        
        await self.service.stitch_unassociated_tracks()
        
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 1)
        
        tracks_res = await self.session.execute(select(VehicleTrack).order_by(VehicleTrack.first_seen_at))
        tracks = tracks_res.scalars().all()
        self.assertEqual(tracks[1].association_status, "ANONYMOUS")
        self.assertIsNone(tracks[1].vehicle_id)

    async def test_hard_rejected_transition_does_not_create_new_canonical_vehicle(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamA", 1, t1, plate="MH12AB1234")
        await self._add_track("CamB", 2, t1 + timedelta(seconds=5), plate="MH12AB1234")
        
        await self.service.stitch_unassociated_tracks()
        
        t_res = await self.session.execute(select(VehicleTrack).order_by(VehicleTrack.first_seen_at))
        tracks = t_res.scalars().all()
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0].association_status, "NEW_VEHICLE")
        self.assertIsNotNone(tracks[0].vehicle_id)
        
        self.assertEqual(tracks[1].association_status, "ANONYMOUS")
        self.assertIsNone(tracks[1].vehicle_id)
        
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 1)

    async def test_reid_supported_association_without_exact_plate(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        emb = [1.0, 0.0]
        await self._add_track("CamA", 1, t1, plate="MH12AB1234", emb=emb)
        t2 = t1 + timedelta(seconds=90)
        await self._add_track("CamB", 2, t2, plate=None, emb=emb)
        
        await self.service.stitch_unassociated_tracks()
        
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 1)
        
        tracks_res = await self.session.execute(select(VehicleTrack).order_by(VehicleTrack.first_seen_at))
        tracks = tracks_res.scalars().all()
        self.assertEqual(tracks[1].association_status, "PROBABLE")
        self.assertEqual(tracks[1].association_method, "RE_ID")

    async def test_uncertain_conflicting_candidates(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamA", 1, t1, plate="V1", emb=[1.0, 0.0])
        await self._add_track("CamA", 2, t1, plate="V2", emb=[1.0, 0.0])
        await self.service.stitch_unassociated_tracks()
        
        t2 = t1 + timedelta(seconds=90)
        await self._add_track("CamB", 3, t2, plate=None, emb=[1.0, 0.0])
        
        await self.service.stitch_unassociated_tracks()
        
        tracks_res = await self.session.execute(select(VehicleTrack).where(VehicleTrack.local_track_id == 3))
        t3 = tracks_res.scalars().first()
        self.assertEqual(t3.association_status, "UNCERTAIN")
        self.assertIsNone(t3.vehicle_id)

    async def test_repeated_local_track_ids_across_cameras(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamA", 5, t1, plate="V1")
        await self._add_track("CamB", 5, t1 + timedelta(seconds=90), plate="V1")
        
        await self.service.stitch_unassociated_tracks()
        
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 1)
        traj = await self.service.get_trajectory(vehicles[0].vehicle_id)
        
        # journey: track A, transition A->B, track B
        self.assertEqual(traj["journey"][0]["camera_id"], "CamA")
        self.assertEqual(traj["journey"][2]["camera_id"], "CamB")

    async def test_missing_topology(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await self._add_track("CamC", 1, t1, plate="MH12AB1234")
        await self._add_track("CamB", 2, t1 + timedelta(minutes=10), plate="MH12AB1234")
        
        await self.service.stitch_unassociated_tracks()
        
        v_res = await self.session.execute(select(Vehicle))
        vehicles = v_res.scalars().all()
        self.assertEqual(len(vehicles), 1)
