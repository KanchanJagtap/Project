"""
API Unit and Integration Tests for Milestone 2D (FastAPI Backend Foundation).

Verifies all 13 core requirements:
1. GET /health returns 200.
2. GET /api/junctions returns successfully.
3. GET /api/junctions/{id} returns a known junction.
4. Missing junction returns 404.
5. GET /api/cameras returns successfully.
6. Known camera can be retrieved.
7. Missing camera returns 404.
8. GET /api/vehicles returns successfully (plate, vehicle_type, limit, offset filters).
9. Known plate can be retrieved (case-insensitive normalization).
10. Missing plate returns 404.
11. Vehicle history endpoint returns tracks and plate observations.
12. Traffic latest endpoint returns snapshots (camera_id filter and all).
13. Signal latest endpoint returns decisions (junction_id filter and all).
14. OpenAPI schema & docs endpoints (/openapi.json, /docs).
15. End-to-end integration against live PostgreSQL database.
"""

import asyncio
import unittest
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.db.base import Base
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


class FastAPIApiTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests for FastAPI endpoints using isolated in-memory SQLite database."""

    async def asyncSetUp(self):
        # Create an in-memory SQLite engine with StaticPool to keep schema & data persistent
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # Seed initial test data
        async with self.session_factory() as session:
            # 1. Junction & Approach
            junction = Junction(
                junction_id="junc-demo",
                name="Shivaji Nagar Chowk",
                latitude=18.5314,
                longitude=73.8446,
                target_cycle_seconds=120,
                status="NORMAL",
            )
            camera = CameraModel(
                camera_id="cam-demo",
                source="rtsp://10.0.0.1:554/live",
                name="North Gate Camera",
                resolution_width=1920,
                resolution_height=1080,
                fps=30.0,
                enabled=True,
            )
            approach = JunctionApproach(
                approach_id="app-north",
                junction_id="junc-demo",
                camera_id="cam-demo",
                direction_name="Northbound Entry",
                cardinal_direction="N",
            )
            session.add_all([junction, camera, approach])

            # 2. Canonical Vehicle
            now = datetime.now(timezone.utc)
            vehicle = Vehicle(
                vehicle_id=uuid.uuid4(),
                canonical_plate_text="MH12AB1234",
                canonical_vehicle_type="car",
                first_detected_at=now,
                last_detected_at=now,
                total_detections_count=5,
            )
            session.add(vehicle)
            await session.flush()

            # 3. Vehicle Track
            track = VehicleTrack(
                track_session_id=uuid.uuid4(),
                vehicle_id=vehicle.vehicle_id,
                camera_id="cam-demo",
                local_track_id=101,
                vehicle_type="car",
                confidence=0.92,
                best_confidence=0.95,
                first_seen_at=now,
                last_seen_at=now,
                first_seen_frame=1,
                last_seen_frame=15,
                frames_tracked=15,
                last_bbox=[100.0, 100.0, 200.0, 200.0],
                center=[150.0, 150.0],
                trajectory_summary=[[150.0, 150.0]],
                type_history=["car"],
            )
            session.add(track)
            await session.flush()

            # 3b. Vehicle Track without Camera relationship
            track2 = VehicleTrack(
                track_session_id=uuid.uuid4(),
                vehicle_id=vehicle.vehicle_id,
                camera_id="cam-demo", # Assuming cam-demo exists but let's change junction? No, let's just make a new camera with no junction.
                local_track_id=102,
                vehicle_type="bus",
                confidence=0.88,
                first_seen_at=now,
                last_seen_at=now,
                first_seen_frame=1,
                last_seen_frame=10,
                frames_tracked=10,
                last_bbox=[0,0,0,0],
                type_history=["bus"],
            )
            # Actually, to test nullable metadata, we need a camera with no junction.
            camera2 = CameraModel(
                camera_id="cam-isolated",
                source="rtsp://10.0.0.2",
                name=None,
            )
            track2.camera_id = "cam-isolated"
            session.add(camera2)
            session.add(track2)
            await session.flush()

            # 4. Plate Observation
            obs = PlateObservationModel(
                observation_id=uuid.uuid4(),
                plate_text="MH12AB1234",
                raw_plate_text="MH12AB1234",
                camera_id="cam-demo",
                track_session_id=track.track_session_id,
                vehicle_id=vehicle.vehicle_id,
                frame_number=10,
                timestamp=now,
                detection_confidence=0.96,
                ocr_confidence=0.94,
                association_confidence=0.91,
                bbox=[120.0, 180.0, 160.0, 200.0],
                vehicle_bbox=[100.0, 100.0, 200.0, 200.0],
                ocr_variant="standard",
                coordinate_space="frame",
            )
            session.add(obs)

            # 5. Traffic Snapshot
            snapshot = TrafficSnapshotModel(
                snapshot_id=uuid.uuid4(),
                camera_id="cam-demo",
                timestamp=now,
                frame_number=100,
                active_vehicle_count=12,
                queue_length=4,
                moving_vehicles=8,
                slow_vehicles=0,
                stationary_vehicles=4,
                traffic_pressure=0.45,
                traffic_level="MEDIUM",
                metrics={"pressure_score": 0.45, "queue_factor": 0.3},
            )
            session.add(snapshot)

            # 6. Signal Decision
            decision = SignalDecisionModel(
                decision_id=uuid.uuid4(),
                junction_id="junc-demo",
                approach_id="app-north",
                timestamp=now,
                priority_score=0.75,
                green_time=45,
                reason="High queue detected on approach-north",
                is_emergency_override=False,
            )
            session.add(decision)
            await session.commit()

        # Dependency override to inject the test session
        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self.engine.dispose()

    # -------------------------------------------------------------------------
    # 1. Health Check
    # -------------------------------------------------------------------------
    async def test_01_health_check(self):
        """1. GET /health returns 200 and {'status': 'ok'}."""
        res = await self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})

        # Sub-router health also works
        res_api = await self.client.get("/api/health")
        self.assertEqual(res_api.status_code, 200)
        self.assertEqual(res_api.json(), {"status": "ok"})

    async def test_01b_system_health_check(self):
        """1b. GET /api/system/health returns comprehensive system and model status."""
        res = await self.client.get("/api/system/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("database", data)
        self.assertIn("models", data)
        self.assertIn("active_workers", data)
        self.assertEqual(data["database"]["status"], "ok")
        self.assertIsInstance(data["active_workers"], int)
        self.assertIn(data["status"], ("healthy", "unhealthy"))


    # -------------------------------------------------------------------------
    # 2. GET /api/junctions
    # -------------------------------------------------------------------------
    async def test_02_get_junctions(self):
        """2. GET /api/junctions returns list of junctions."""
        res = await self.client.get("/api/junctions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        junc = data[0]
        self.assertEqual(junc["junction_id"], "junc-demo")
        self.assertEqual(junc["name"], "Shivaji Nagar Chowk")
        self.assertEqual(len(junc["approaches"]), 1)
        self.assertEqual(junc["approaches"][0]["approach_id"], "app-north")

    # -------------------------------------------------------------------------
    # 3. GET /api/junctions/{junction_id}
    # -------------------------------------------------------------------------
    async def test_03_get_junction_by_id_success(self):
        """3. GET /api/junctions/{id} returns a known junction."""
        res = await self.client.get("/api/junctions/junc-demo")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["junction_id"], "junc-demo")
        self.assertEqual(data["name"], "Shivaji Nagar Chowk")
        self.assertAlmostEqual(data["latitude"], 18.5314, places=4)
        self.assertAlmostEqual(data["longitude"], 73.8446, places=4)
        self.assertEqual(len(data["approaches"]), 1)

    # -------------------------------------------------------------------------
    # 4. Missing Junction -> 404
    # -------------------------------------------------------------------------
    async def test_04_get_junction_by_id_not_found(self):
        """4. Missing junction returns 404."""
        res = await self.client.get("/api/junctions/nonexistent-junc")
        self.assertEqual(res.status_code, 404)
        self.assertIn("detail", res.json())

    # -------------------------------------------------------------------------
    # 5. GET /api/cameras
    # -------------------------------------------------------------------------
    async def test_05_get_cameras(self):
        """5. GET /api/cameras returns successfully."""
        res = await self.client.get("/api/cameras")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        cam = data[0]
        self.assertEqual(cam["camera_id"], "cam-demo")
        self.assertEqual(cam["source"], "rtsp://10.0.0.1:554/live")
        self.assertTrue(cam["enabled"])
        self.assertIsNotNone(cam["approach"])
        self.assertEqual(cam["approach"]["approach_id"], "app-north")

    # -------------------------------------------------------------------------
    # 6. GET /api/cameras/{camera_id}
    # -------------------------------------------------------------------------
    async def test_06_get_camera_by_id_success(self):
        """6. Known camera can be retrieved."""
        res = await self.client.get("/api/cameras/cam-demo")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["camera_id"], "cam-demo")
        self.assertEqual(data["name"], "North Gate Camera")
        self.assertEqual(data["resolution_width"], 1920)
        self.assertEqual(data["resolution_height"], 1080)

    # -------------------------------------------------------------------------
    # 7. Missing Camera -> 404
    # -------------------------------------------------------------------------
    async def test_07_get_camera_by_id_not_found(self):
        """7. Missing camera returns 404."""
        res = await self.client.get("/api/cameras/nonexistent-cam")
        self.assertEqual(res.status_code, 404)
        self.assertIn("detail", res.json())

    # -------------------------------------------------------------------------
    # 8. GET /api/vehicles (with filters & pagination)
    # -------------------------------------------------------------------------
    async def test_08_get_vehicles_filtering(self):
        """8. GET /api/vehicles returns successfully with filtering and pagination."""
        # Unfiltered
        res = await self.client.get("/api/vehicles")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

        # Filter by plate
        res_plate = await self.client.get("/api/vehicles?plate=MH12AB1234")
        self.assertEqual(res_plate.status_code, 200)
        self.assertEqual(len(res_plate.json()), 1)
        self.assertEqual(res_plate.json()[0]["canonical_plate_text"], "MH12AB1234")

        # Filter by vehicle_type
        res_type = await self.client.get("/api/vehicles?vehicle_type=car")
        self.assertEqual(res_type.status_code, 200)
        self.assertGreaterEqual(len(res_type.json()), 1)

        # Non-matching type filter
        res_bus = await self.client.get("/api/vehicles?vehicle_type=bus")
        self.assertEqual(res_bus.status_code, 200)
        self.assertEqual(len(res_bus.json()), 0)

        # Pagination
        res_page = await self.client.get("/api/vehicles?limit=1&offset=0")
        self.assertEqual(res_page.status_code, 200)
        self.assertLessEqual(len(res_page.json()), 1)

    # -------------------------------------------------------------------------
    # 9. GET /api/vehicles/{plate}
    # -------------------------------------------------------------------------
    async def test_09_get_vehicle_by_plate_success(self):
        """9. Known plate can be retrieved (case-insensitive normalization)."""
        # Exact plate
        res = await self.client.get("/api/vehicles/MH12AB1234")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["canonical_plate_text"], "MH12AB1234")
        self.assertEqual(data["canonical_vehicle_type"], "car")
        self.assertEqual(data["total_detections_count"], 5)

        # Lowercase should be normalized
        res_lower = await self.client.get("/api/vehicles/mh12ab1234")
        self.assertEqual(res_lower.status_code, 200)
        self.assertEqual(res_lower.json()["canonical_plate_text"], "MH12AB1234")

    # -------------------------------------------------------------------------
    # 10. Missing Plate -> 404
    # -------------------------------------------------------------------------
    async def test_10_get_vehicle_by_plate_not_found(self):
        """10. Missing plate returns 404."""
        res = await self.client.get("/api/vehicles/DL01XY9999")
        self.assertEqual(res.status_code, 404)
        self.assertIn("detail", res.json())

    # -------------------------------------------------------------------------
    # 11. GET /api/vehicles/{plate}/history
    # -------------------------------------------------------------------------
    async def test_11_get_vehicle_history(self):
        """11. Vehicle history endpoint returns tracks and plate observations."""
        res = await self.client.get("/api/vehicles/MH12AB1234/history")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("vehicle", data)
        self.assertIn("tracks", data)
        self.assertIn("plate_observations", data)

        self.assertEqual(data["vehicle"]["canonical_plate_text"], "MH12AB1234")
        
        cam_demo_track = next((t for t in data["tracks"] if t["camera_id"] == "cam-demo"), None)
        self.assertIsNotNone(cam_demo_track)
        self.assertEqual(cam_demo_track["camera_name"], "North Gate Camera")
        self.assertEqual(cam_demo_track["junction_id"], "junc-demo")
        self.assertEqual(cam_demo_track["junction_name"], "Shivaji Nagar Chowk")
        self.assertEqual(cam_demo_track["frames_tracked"], 15)
        
        # Test the isolated track (no junction, no camera name)
        self.assertEqual(len(data["tracks"]), 2)
        isolated_track = next((t for t in data["tracks"] if t["camera_id"] == "cam-isolated"), None)
        self.assertIsNotNone(isolated_track)
        self.assertIsNone(isolated_track["camera_name"])
        self.assertIsNone(isolated_track["junction_id"])
        self.assertIsNone(isolated_track["junction_name"])

        self.assertEqual(len(data["plate_observations"]), 1)
        self.assertEqual(data["plate_observations"][0]["plate_text"], "MH12AB1234")
        self.assertEqual(data["plate_observations"][0]["frame_number"], 10)

        # Nonexistent plate history returns 404
        res_missing = await self.client.get("/api/vehicles/UNKNOWN/history")
        self.assertEqual(res_missing.status_code, 404)

    # -------------------------------------------------------------------------
    # 12. GET /api/traffic/latest
    # -------------------------------------------------------------------------
    async def test_12_get_traffic_latest(self):
        """12. Traffic latest endpoint works (with and without camera_id filter)."""
        # All latest snapshots
        res_all = await self.client.get("/api/traffic/latest")
        self.assertEqual(res_all.status_code, 200)
        data_all = res_all.json()
        self.assertIsInstance(data_all, list)
        self.assertGreaterEqual(len(data_all), 1)
        self.assertEqual(data_all[0]["camera_id"], "cam-demo")
        self.assertEqual(data_all[0]["active_vehicle_count"], 12)

        # Single camera filter
        res_cam = await self.client.get("/api/traffic/latest?camera_id=cam-demo")
        self.assertEqual(res_cam.status_code, 200)
        data_cam = res_cam.json()
        self.assertIsInstance(data_cam, dict)
        self.assertEqual(data_cam["camera_id"], "cam-demo")
        self.assertEqual(data_cam["traffic_level"], "MEDIUM")
        self.assertEqual(data_cam["queue_length"], 4)

        # Nonexistent camera returns 404
        res_none = await self.client.get("/api/traffic/latest?camera_id=nonexistent-camera")
        self.assertEqual(res_none.status_code, 404)

    # -------------------------------------------------------------------------
    # 13. GET /api/signals/latest
    # -------------------------------------------------------------------------
    async def test_13_get_signals_latest(self):
        """13. Signal latest endpoint works (with and without junction_id filter)."""
        # All latest decisions
        res_all = await self.client.get("/api/signals/latest")
        self.assertEqual(res_all.status_code, 200)
        data_all = res_all.json()
        self.assertIsInstance(data_all, list)
        self.assertGreaterEqual(len(data_all), 1)
        self.assertEqual(data_all[0]["junction_id"], "junc-demo")
        self.assertEqual(data_all[0]["green_time"], 45)

        # Filter by junction_id
        res_junc = await self.client.get("/api/signals/latest?junction_id=junc-demo")
        self.assertEqual(res_junc.status_code, 200)
        data_junc = res_junc.json()
        self.assertIsInstance(data_junc, list)
        self.assertGreaterEqual(len(data_junc), 1)
        self.assertEqual(data_junc[0]["approach_id"], "app-north")

        # Nonexistent junction returns 404
        res_none = await self.client.get("/api/signals/latest?junction_id=nonexistent-junc")
        self.assertEqual(res_none.status_code, 404)

    # -------------------------------------------------------------------------
    # 14. OpenAPI & Docs
    # -------------------------------------------------------------------------
    async def test_14_openapi_and_docs(self):
        """14. Verify OpenAPI specification and Swagger UI endpoints."""
        res_docs = await self.client.get("/docs")
        self.assertEqual(res_docs.status_code, 200)

        res_openapi = await self.client.get("/openapi.json")
        self.assertEqual(res_openapi.status_code, 200)
        schema = res_openapi.json()
        self.assertEqual(schema["info"]["title"], "City-Wide ANPR & Traffic Analytics Engine")
        expected_paths = [
            "/health",
            "/api/junctions",
            "/api/junctions/{junction_id}",
            "/api/cameras",
            "/api/cameras/{camera_id}",
            "/api/vehicles",
            "/api/vehicles/{plate}",
            "/api/vehicles/{plate}/history",
            "/api/traffic/latest",
            "/api/signals/latest",
        ]
        for path in expected_paths:
            self.assertIn(path, schema["paths"])


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
    f"PostgreSQL is not reachable at {settings.DATABASE_URL}. Skipping live PostgreSQL API tests.",
)
class RealPostgresApiTests(unittest.IsolatedAsyncioTestCase):
    """
    Integration verification of the FastAPI REST API against a REAL live PostgreSQL database.
    Seeds synthetic test data into city_anpr, verifies API queries, and cleans up.
    """

    async def asyncSetUp(self):
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
        # Purge any stale test records first
        await self._cleanup_data()

        # Seed real PostgreSQL test records
        async with self.session_factory() as session:
            now = datetime.now(timezone.utc)
            junction = Junction(
                junction_id="pg-junc-api",
                name="Pune University Circle",
                latitude=18.5529,
                longitude=73.8267,
                target_cycle_seconds=120,
                status="NORMAL",
            )
            camera = CameraModel(
                camera_id="pg-cam-api",
                source="rtsp://192.168.1.100:554/feed1",
                name="Pashan Road Approach",
                resolution_width=1920,
                resolution_height=1080,
                fps=25.0,
                enabled=True,
            )
            approach = JunctionApproach(
                approach_id="pg-app-api-w",
                junction_id="pg-junc-api",
                camera_id="pg-cam-api",
                direction_name="Westbound Inflow",
                cardinal_direction="W",
            )
            vehicle = Vehicle(
                vehicle_id=uuid.uuid4(),
                canonical_plate_text="MH12CD5678",
                canonical_vehicle_type="car",
                first_detected_at=now,
                last_detected_at=now,
                total_detections_count=3,
            )
            session.add_all([junction, camera, approach, vehicle])
            await session.flush()

            track = VehicleTrack(
                track_session_id=uuid.uuid4(),
                vehicle_id=vehicle.vehicle_id,
                camera_id="pg-cam-api",
                local_track_id=202,
                vehicle_type="car",
                confidence=0.94,
                best_confidence=0.96,
                first_seen_at=now,
                last_seen_at=now,
                first_seen_frame=1,
                last_seen_frame=20,
                frames_tracked=20,
                last_bbox=[200.0, 150.0, 350.0, 300.0],
                center=[275.0, 225.0],
                trajectory_summary=[[275.0, 225.0]],
                type_history=["car"],
            )
            obs = PlateObservationModel(
                observation_id=uuid.uuid4(),
                plate_text="MH12CD5678",
                raw_plate_text="MH12CD5678",
                camera_id="pg-cam-api",
                track_session_id=track.track_session_id,
                vehicle_id=vehicle.vehicle_id,
                frame_number=12,
                timestamp=now,
                detection_confidence=0.97,
                ocr_confidence=0.95,
                association_confidence=0.93,
                bbox=[220.0, 240.0, 280.0, 265.0],
                vehicle_bbox=[200.0, 150.0, 350.0, 300.0],
            )
            snapshot = TrafficSnapshotModel(
                snapshot_id=uuid.uuid4(),
                camera_id="pg-cam-api",
                timestamp=now,
                frame_number=200,
                active_vehicle_count=18,
                queue_length=7,
                moving_vehicles=11,
                slow_vehicles=0,
                stationary_vehicles=7,
                traffic_pressure=0.62,
                traffic_level="HIGH",
                metrics={"pressure_score": 0.62},
            )
            decision = SignalDecisionModel(
                decision_id=uuid.uuid4(),
                junction_id="pg-junc-api",
                approach_id="pg-app-api-w",
                timestamp=now,
                priority_score=0.88,
                green_time=50,
                reason="High queue at west approach",
            )
            session.add_all([track, obs, snapshot, decision])
            await session.commit()

        # Connect AsyncClient to real PostgreSQL session
        async def override_get_db_pg() -> AsyncGenerator[AsyncSession, None]:
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db_pg
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self._cleanup_data()
        await self.engine.dispose()

    async def _cleanup_data(self):
        async with self.session_factory() as session:
            await session.execute(
                delete(SignalDecisionModel).where(SignalDecisionModel.junction_id == "pg-junc-api")
            )
            await session.execute(
                delete(TrafficSnapshotModel).where(TrafficSnapshotModel.camera_id == "pg-cam-api")
            )
            await session.execute(
                delete(PlateObservationModel).where(PlateObservationModel.camera_id == "pg-cam-api")
            )
            await session.execute(
                delete(VehicleTrack).where(VehicleTrack.camera_id == "pg-cam-api")
            )
            await session.execute(
                delete(Vehicle).where(Vehicle.canonical_plate_text == "MH12CD5678")
            )
            await session.execute(
                delete(JunctionApproach).where(JunctionApproach.junction_id == "pg-junc-api")
            )
            await session.execute(
                delete(CameraModel).where(CameraModel.camera_id == "pg-cam-api")
            )
            await session.execute(
                delete(Junction).where(Junction.junction_id == "pg-junc-api")
            )
            await session.commit()

    async def test_real_postgres_api_endpoints(self):
        """End-to-end API retrieval against live PostgreSQL instance."""
        # 1. Junction
        res_j = await self.client.get("/api/junctions/pg-junc-api")
        self.assertEqual(res_j.status_code, 200)
        self.assertEqual(res_j.json()["name"], "Pune University Circle")
        self.assertEqual(len(res_j.json()["approaches"]), 1)

        # 2. Camera
        res_c = await self.client.get("/api/cameras/pg-cam-api")
        self.assertEqual(res_c.status_code, 200)
        self.assertEqual(res_c.json()["name"], "Pashan Road Approach")

        # 3. Vehicle by plate (case-insensitive)
        res_v = await self.client.get("/api/vehicles/mh12cd5678")
        self.assertEqual(res_v.status_code, 200)
        self.assertEqual(res_v.json()["canonical_plate_text"], "MH12CD5678")

        # 4. Vehicle History
        res_h = await self.client.get("/api/vehicles/MH12CD5678/history")
        self.assertEqual(res_h.status_code, 200)
        self.assertEqual(len(res_h.json()["tracks"]), 1)
        self.assertEqual(len(res_h.json()["plate_observations"]), 1)

        # 5. Traffic latest for camera
        res_t = await self.client.get("/api/traffic/latest?camera_id=pg-cam-api")
        self.assertEqual(res_t.status_code, 200)
        self.assertEqual(res_t.json()["traffic_level"], "HIGH")
        self.assertAlmostEqual(res_t.json()["traffic_pressure"], 0.62, places=2)

        # 6. Signal latest for junction
        res_s = await self.client.get("/api/signals/latest?junction_id=pg-junc-api")
        self.assertEqual(res_s.status_code, 200)
        self.assertEqual(len(res_s.json()), 1)
        self.assertEqual(res_s.json()[0]["green_time"], 50)


if __name__ == "__main__":
    unittest.main()
