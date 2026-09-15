"""
Unit Tests for Database Models and Schema (Milestone 2A).

Lightweight tests using in-memory SQLite to verify:
1. Tables can be created
2. Foreign keys are valid
3. A junction can have multiple approaches
4. A camera belongs to an approach
5. A vehicle can have multiple vehicle_tracks
6. A vehicle_track can have multiple plate_observations
7. Plate_observation can exist without a matched vehicle
8. Canonical_plate_text can be null
9. Traffic snapshots can be inserted with timestamps
10. Signal decisions reference junction + approach correctly
11. AI contracts to ORM model adapters work cleanly
"""

import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ai.contracts.models import (
    Camera,
    PlateObservation,
    TrackedVehicle,
    TrafficSnapshot,
)
from ai.traffic.signal_optimizer import SignalDecision

from backend.app.adapters import (
    camera_contract_to_model,
    plate_observation_to_model,
    signal_decision_to_model,
    tracked_vehicle_to_model,
    traffic_snapshot_to_model,
)
from backend.app.db.base import Base, utc_now
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


class DatabaseModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite engine for fast, self-contained model testing
        cls.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(cls.engine)

    def setUp(self):
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.rollback()
        self.session.close()

    def test_01_tables_created(self):
        """1. Verify all 8 core tables exist in the metadata."""
        expected_tables = {
            "junctions",
            "junction_approaches",
            "cameras",
            "vehicles",
            "vehicle_tracks",
            "plate_observations",
            "traffic_snapshots",
            "signal_decisions",
        }
        actual_tables = set(Base.metadata.tables.keys())
        self.assertTrue(
            expected_tables.issubset(actual_tables),
            f"Missing tables: {expected_tables - actual_tables}",
        )

    def test_02_foreign_keys_valid(self):
        """2. Verify foreign key constraints point to correct parent columns."""
        tables = Base.metadata.tables

        # junction_approaches -> junctions & cameras
        approaches_fks = {
            (fk.parent.name, fk.target_fullname)
            for fk in tables["junction_approaches"].foreign_keys
        }
        self.assertIn(("junction_id", "junctions.junction_id"), approaches_fks)
        self.assertIn(("camera_id", "cameras.camera_id"), approaches_fks)

        # vehicle_tracks -> cameras & vehicles
        tracks_fks = {
            (fk.parent.name, fk.target_fullname)
            for fk in tables["vehicle_tracks"].foreign_keys
        }
        self.assertIn(("camera_id", "cameras.camera_id"), tracks_fks)
        self.assertIn(("vehicle_id", "vehicles.vehicle_id"), tracks_fks)

        # plate_observations -> cameras, tracks, vehicles
        plates_fks = {
            (fk.parent.name, fk.target_fullname)
            for fk in tables["plate_observations"].foreign_keys
        }
        self.assertIn(("camera_id", "cameras.camera_id"), plates_fks)
        self.assertIn(("track_session_id", "vehicle_tracks.track_session_id"), plates_fks)
        self.assertIn(("vehicle_id", "vehicles.vehicle_id"), plates_fks)

        # traffic_snapshots -> cameras
        snapshots_fks = {
            (fk.parent.name, fk.target_fullname)
            for fk in tables["traffic_snapshots"].foreign_keys
        }
        self.assertIn(("camera_id", "cameras.camera_id"), snapshots_fks)

        # signal_decisions -> junctions & approaches
        signals_fks = {
            (fk.parent.name, fk.target_fullname)
            for fk in tables["signal_decisions"].foreign_keys
        }
        self.assertIn(("junction_id", "junctions.junction_id"), signals_fks)
        self.assertIn(("approach_id", "junction_approaches.approach_id"), signals_fks)

    def test_03_junction_multiple_approaches(self):
        """3. A junction can have multiple approaches."""
        junction = Junction(
            junction_id="junc-01",
            name="Swargate Chowk",
            latitude=18.5018,
            longitude=73.8636,
            target_cycle_seconds=120,
        )
        self.session.add(junction)

        app_north = JunctionApproach(
            approach_id="app-01-n",
            junction_id="junc-01",
            direction_name="Northbound Shivaji Road",
            cardinal_direction="N",
        )
        app_south = JunctionApproach(
            approach_id="app-01-s",
            junction_id="junc-01",
            direction_name="Southbound Satara Road",
            cardinal_direction="S",
        )
        self.session.add_all([app_north, app_south])
        self.session.commit()

        queried = self.session.get(Junction, "junc-01")
        self.assertIsNotNone(queried)
        self.assertEqual(len(queried.approaches), 2)
        approach_ids = [a.approach_id for a in queried.approaches]
        self.assertIn("app-01-n", approach_ids)
        self.assertIn("app-01-s", approach_ids)

    def test_04_camera_belongs_to_approach(self):
        """4. A camera can be assigned to an intersection approach."""
        junction = Junction(junction_id="junc-02", name="University Circle")
        camera = CameraModel(
            camera_id="cam-uni-01",
            source="rtsp://192.168.1.10:554/live",
            name="University North Entry",
        )
        self.session.add_all([junction, camera])
        self.session.flush()

        approach = JunctionApproach(
            approach_id="app-uni-north",
            junction_id="junc-02",
            camera_id="cam-uni-01",
            direction_name="Ganeshkhind Northbound",
            cardinal_direction="N",
        )
        self.session.add(approach)
        self.session.commit()

        queried_cam = self.session.get(CameraModel, "cam-uni-01")
        self.assertIsNotNone(queried_cam)
        self.assertIsNotNone(queried_cam.approach)
        self.assertEqual(queried_cam.approach.approach_id, "app-uni-north")

    def test_05_vehicle_multiple_tracks(self):
        """5. A single physical vehicle can have multiple tracks across cameras."""
        vehicle = Vehicle(
            canonical_plate_text="MH12DE1234",
            canonical_vehicle_type="car",
        )
        cam1 = CameraModel(camera_id="cam-track-01", source="file:///cam1.mp4")
        cam2 = CameraModel(camera_id="cam-track-02", source="file:///cam2.mp4")
        self.session.add_all([vehicle, cam1, cam2])
        self.session.flush()

        track1 = VehicleTrack(
            vehicle_id=vehicle.vehicle_id,
            camera_id="cam-track-01",
            local_track_id=101,
            vehicle_type="car",
            confidence=0.92,
            first_seen_frame=10,
            last_seen_frame=50,
            last_bbox=[100.0, 150.0, 250.0, 300.0],
            trajectory_summary=[[150, 200], [175, 225]],
            type_history=["car", "car"],
        )
        track2 = VehicleTrack(
            vehicle_id=vehicle.vehicle_id,
            camera_id="cam-track-02",
            local_track_id=45,
            vehicle_type="car",
            confidence=0.88,
            first_seen_frame=120,
            last_seen_frame=180,
            last_bbox=[200.0, 220.0, 350.0, 380.0],
            trajectory_summary=[[250, 300]],
            type_history=["car"],
        )
        self.session.add_all([track1, track2])
        self.session.commit()

        queried_veh = self.session.get(Vehicle, vehicle.vehicle_id)
        self.assertIsNotNone(queried_veh)
        self.assertEqual(len(queried_veh.tracks), 2)
        track_cams = [t.camera_id for t in queried_veh.tracks]
        self.assertIn("cam-track-01", track_cams)
        self.assertIn("cam-track-02", track_cams)

    def test_06_vehicle_track_multiple_plate_observations(self):
        """6. A vehicle track can have multiple plate observations over time."""
        cam = CameraModel(camera_id="cam-plate-01", source="file:///cam.mp4")
        track = VehicleTrack(
            camera_id="cam-plate-01",
            local_track_id=7,
            vehicle_type="bus",
            confidence=0.95,
            first_seen_frame=1,
            last_seen_frame=30,
            last_bbox=[50.0, 50.0, 400.0, 400.0],
            trajectory_summary=[[200, 200]],
            type_history=["bus"],
        )
        self.session.add_all([cam, track])
        self.session.flush()

        obs1 = PlateObservationModel(
            plate_text="MH14AZ9999",
            camera_id="cam-plate-01",
            track_session_id=track.track_session_id,
            frame_number=10,
            detection_confidence=0.85,
            ocr_confidence=0.78,
            bbox=[120.0, 300.0, 220.0, 340.0],
        )
        obs2 = PlateObservationModel(
            plate_text="MH14AZ9999",
            camera_id="cam-plate-01",
            track_session_id=track.track_session_id,
            frame_number=20,
            detection_confidence=0.91,
            ocr_confidence=0.94,
            bbox=[130.0, 310.0, 235.0, 355.0],
        )
        self.session.add_all([obs1, obs2])
        self.session.commit()

        queried_track = self.session.get(VehicleTrack, track.track_session_id)
        self.assertIsNotNone(queried_track)
        self.assertEqual(len(queried_track.plate_observations), 2)
        confs = [o.ocr_confidence for o in queried_track.plate_observations]
        self.assertIn(0.78, confs)
        self.assertIn(0.94, confs)

    def test_07_plate_observation_without_matched_vehicle(self):
        """7. PlateObservation can exist independently without a matched vehicle or track."""
        cam = CameraModel(camera_id="cam-unmatched-01", source="rtsp://cam/live")
        self.session.add(cam)
        self.session.flush()

        orphan_obs = PlateObservationModel(
            plate_text="DL01AB5678",
            raw_plate_text="dl 01 ab 5678",
            camera_id="cam-unmatched-01",
            track_session_id=None,
            vehicle_id=None,
            frame_number=45,
            detection_confidence=0.89,
            ocr_confidence=0.92,
            bbox=[100.0, 100.0, 180.0, 130.0],
        )
        self.session.add(orphan_obs)
        self.session.commit()

        queried = self.session.get(PlateObservationModel, orphan_obs.observation_id)
        self.assertIsNotNone(queried)
        self.assertIsNone(queried.vehicle_id)
        self.assertIsNone(queried.track_session_id)
        self.assertEqual(queried.plate_text, "DL01AB5678")

    def test_08_canonical_plate_text_can_be_null(self):
        """8. Multiple vehicles with canonical_plate_text=NULL can exist without unique collision."""
        veh_unidentified_1 = Vehicle(
            canonical_plate_text=None,
            canonical_vehicle_type="motorcycle",
        )
        veh_unidentified_2 = Vehicle(
            canonical_plate_text=None,
            canonical_vehicle_type="auto",
        )
        self.session.add_all([veh_unidentified_1, veh_unidentified_2])
        self.session.commit()

        v1 = self.session.get(Vehicle, veh_unidentified_1.vehicle_id)
        v2 = self.session.get(Vehicle, veh_unidentified_2.vehicle_id)
        self.assertIsNotNone(v1)
        self.assertIsNotNone(v2)
        self.assertIsNone(v1.canonical_plate_text)
        self.assertIsNone(v2.canonical_plate_text)
        self.assertNotEqual(v1.vehicle_id, v2.vehicle_id)

    def test_09_traffic_snapshots_with_timestamps(self):
        """9. TrafficSnapshotModel can be inserted with timezone-aware timestamps and metrics."""
        cam = CameraModel(camera_id="cam-snap-01", source="rtsp://cam/live")
        self.session.add(cam)
        self.session.flush()

        now_utc = datetime.now(timezone.utc)
        snapshot = TrafficSnapshotModel(
            camera_id="cam-snap-01",
            timestamp=now_utc,
            frame_number=150,
            active_vehicle_count=12,
            queue_length=3,
            moving_vehicles=4,
            slow_vehicles=3,
            stationary_vehicles=5,
            traffic_pressure=34.5,
            traffic_level="MEDIUM",
            metrics={
                "raw_pressure": 32.1,
                "arrival_rate": 18.0,
                "occupancy": 15.2,
            },
        )
        self.session.add(snapshot)
        self.session.commit()

        queried = self.session.get(TrafficSnapshotModel, snapshot.snapshot_id)
        self.assertIsNotNone(queried)
        self.assertEqual(queried.traffic_level, "MEDIUM")
        self.assertEqual(queried.metrics["arrival_rate"], 18.0)
        self.assertEqual(queried.queue_length, 3)

    def test_10_signal_decisions_reference_junction_and_approach(self):
        """10. SignalDecisionModel correctly references both junction and approach."""
        junction = Junction(junction_id="junc-sig-01", name="Chandani Chowk")
        approach = JunctionApproach(
            approach_id="app-sig-01",
            junction_id="junc-sig-01",
            direction_name="Paud Road Entry",
        )
        self.session.add_all([junction, approach])
        self.session.flush()

        decision = SignalDecisionModel(
            junction_id="junc-sig-01",
            approach_id="app-sig-01",
            priority_score=78.5,
            green_time=45,
            reason="High queue spillback detected",
            is_emergency_override=False,
        )
        self.session.add(decision)
        self.session.commit()

        queried = self.session.get(SignalDecisionModel, decision.decision_id)
        self.assertIsNotNone(queried)
        self.assertEqual(queried.junction.name, "Chandani Chowk")
        self.assertEqual(queried.approach.direction_name, "Paud Road Entry")
        self.assertEqual(queried.green_time, 45)

    def test_11_contract_to_model_adapters(self):
        """11. Verify conversion helpers between AI contracts and ORM models."""
        # Camera
        contract_cam = Camera(camera_id="cam-adap-01", source="rtsp://adap/live", fps=25.0)
        model_cam = camera_contract_to_model(contract_cam)
        self.assertEqual(model_cam.camera_id, "cam-adap-01")
        self.assertEqual(model_cam.fps, 25.0)

        # TrackedVehicle
        contract_track = TrackedVehicle(
            track_id=99,
            vehicle_type="truck",
            bbox=(10.0, 20.0, 100.0, 200.0),
            confidence=0.88,
            camera_id="cam-adap-01",
        )
        model_track = tracked_vehicle_to_model(contract_track)
        self.assertEqual(model_track.local_track_id, 99)
        self.assertEqual(model_track.vehicle_type, "truck")

        # PlateObservation
        contract_plate = PlateObservation(
            plate_text="MH12CD5678",
            detection_confidence=0.9,
            ocr_confidence=0.85,
            bbox=(10.0, 20.0, 50.0, 40.0),
            camera_id="cam-adap-01",
        )
        model_plate = plate_observation_to_model(contract_plate)
        self.assertEqual(model_plate.plate_text, "MH12CD5678")

        # TrafficSnapshot
        contract_snap = TrafficSnapshot(
            camera_id="cam-adap-01",
            active_vehicle_count=5,
            queue_length=1,
            moving_vehicles=2,
            slow_vehicles=1,
            stationary_vehicles=2,
            traffic_pressure=18.0,
            traffic_level="LOW",
        )
        model_snap = traffic_snapshot_to_model(contract_snap)
        self.assertEqual(model_snap.traffic_pressure, 18.0)

        # SignalDecision
        contract_sig = SignalDecision(
            approach_id="app-adap-01",
            priority_score=65.0,
            green_time=35,
            reason="Priority allocation",
        )
        model_sig = signal_decision_to_model(contract_sig, junction_id="junc-adap-01")
        self.assertEqual(model_sig.green_time, 35)
        self.assertEqual(model_sig.junction_id, "junc-adap-01")


if __name__ == "__main__":
    unittest.main()
