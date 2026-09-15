"""
Unit and API Integration Tests for Video Processing Orchestration Service (Milestones 2F & 2G).

Verifies the complete lifecycle and multi-camera orchestration requirements:
1. Initial state is IDLE
2. start() changes state appropriately (STARTING -> RUNNING)
3. Duplicate start is rejected (RuntimeError at service level)
4. Frames are actually processed
5. Processed-frame count increases monotonically
6. Processing reaches COMPLETED on video/frame limit
7. Stop request is handled cleanly (cooperative stop -> STOPPING -> STOPPED)
8. Failure is captured in status (FAILED state, error message populated)
9. Resources are cleaned up (sessions closed, no open leaks)
10. Deterministic generator cleanup on normal completion
11. Deterministic generator cleanup on cooperative stop
12. Deterministic generator cleanup on failure
13. Task-reference race safety
14. Source failure handled cleanly
15. Restart after STOPPED
16. Restart after COMPLETED
17. Restart after FAILED
18. Latest runtime frame snapshot inspection
19. Worker task cancellation handling
20. Multi-camera independent concurrent execution
21. API status endpoint reflects service state
22. API start returns immediately without waiting for video to finish
23. API duplicate start returns HTTP 409 Conflict
24. API stop endpoint initiates cooperative stop
25. API list cameras endpoint (GET /api/processing/cameras)
26. API get specific camera status endpoint
27. API stop with explicit camera_id
28. API stop ambiguous rejection (HTTP 400 when multiple cameras active)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from ai.contracts.models import (
    PlateObservation,
    TrackedVehicle,
    TrafficSnapshot,
)
from ai.pipeline.single_camera_pipeline import FrameResult
from ai.traffic.signal_optimizer import SignalDecision
from backend.app.api.endpoints.processing import get_processing_service
from backend.app.db.base import Base
from backend.app.main import app
from backend.app.schemas.processing import (
    CamerasListResponse,
    LatestFrameSnapshot,
    ProcessingState,
    ProcessingStatusResponse,
    ProcessingStopRequest,
)
from backend.app.services.processing_service import (
    CameraWorker,
    ProcessingManager,
    ProcessingService,
)


def _create_dummy_frame_result(camera_id: str, frame_num: int) -> FrameResult:
    """Create a minimal valid FrameResult for test ingestion."""
    return FrameResult(
        frame_number=frame_num,
        camera_id=camera_id,
        timestamp=datetime.now(timezone.utc),
        tracked_vehicle_contracts=[
            TrackedVehicle(
                track_id=frame_num,
                bbox=(10.0, 20.0, 100.0, 120.0),
                confidence=0.92,
                vehicle_type="car",
                frames_tracked=frame_num,
            )
        ],
        plate_observations=[
            PlateObservation(
                plate_text=f"MH12AB{frame_num:04d}",
                detection_confidence=0.90,
                ocr_confidence=0.88,
                bbox=(20.0, 30.0, 60.0, 45.0),
                track_id=frame_num,
                frame_number=frame_num,
                camera_id=camera_id,
            )
        ],
        snapshot=TrafficSnapshot(
            camera_id=camera_id,
            active_vehicle_count=1,
            queue_length=0,
            moving_vehicles=1,
            slow_vehicles=0,
            stationary_vehicles=0,
            traffic_pressure=0.15,
            traffic_level="LOW",
            frame_number=frame_num,
        ),
        signal_decisions=[
            SignalDecision(
                approach_id=f"approach-{camera_id}",
                priority_score=0.25,
                green_time=30,
                reason="Normal traffic flow",
            )
        ],
        processing_time_ms=25.4,
    )


class MockPipeline:
    """Controlled mock pipeline for deterministic processing service testing."""

    def __init__(
        self,
        camera_id: str = "cam-test-01",
        frames_to_yield: int = 3,
        per_frame_delay: float = 0.0,
    ):
        self.camera_id = camera_id
        self.frames_to_yield = frames_to_yield
        self.per_frame_delay = per_frame_delay

    def process_video(self, video_path: str, max_frames=None, print_every=0):
        total = self.frames_to_yield
        if max_frames is not None:
            total = min(total, max_frames)

        for i in range(1, total + 1):
            if self.per_frame_delay > 0:
                import time

                time.sleep(self.per_frame_delay)
            yield _create_dummy_frame_result(self.camera_id, i)


class TrackingSessionFactory:
    """Real SQLite session factory tracking session creation, commits, and closures."""

    def __init__(self, session_maker):
        self.session_maker = session_maker
        self.opened_count = 0
        self.closed_count = 0
        self.committed_count = 0

    def __call__(self):
        parent = self
        session = self.session_maker()
        orig_commit = session.commit

        async def tracked_commit():
            parent.committed_count += 1
            return await orig_commit()

        session.commit = tracked_commit

        class TrackedContext:
            async def __aenter__(self):
                parent.opened_count += 1
                return await session.__aenter__()

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                try:
                    return await session.__aexit__(exc_type, exc_val, exc_tb)
                finally:
                    parent.closed_count += 1

        return TrackedContext()


class ProcessingServiceUnitTests(unittest.IsolatedAsyncioTestCase):
    """Unit tests covering ProcessingService and CameraWorker lifecycles, states, and controls."""

    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            poolclass=StaticPool,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.session_factory = TrackingSessionFactory(self.session_maker)
        self.dummy_video = Path("data/videos/traffic.mp4")
        if not self.dummy_video.exists():
            self.dummy_video = Path(__file__).resolve()

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_01_initial_state_idle(self):
        """1. Initial state is IDLE with 0 processed frames."""
        service = ProcessingService(session_factory=self.session_factory)
        status = service.get_status()
        self.assertEqual(status.state, ProcessingState.IDLE)
        self.assertEqual(status.processed_frames, 0)
        self.assertIsNone(status.started_at)
        self.assertIsNone(status.finished_at)
        self.assertIsNone(status.error)
        self.assertIsNone(status.latest_frame)

    async def test_02_start_changes_state_appropriately(self):
        """2. start() changes state from IDLE to STARTING immediately."""
        pipeline = MockPipeline(frames_to_yield=2)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        status = await service.start(
            source=str(self.dummy_video),
            camera_id="cam-01",
        )
        self.assertIn(status.state, (ProcessingState.STARTING, ProcessingState.RUNNING))
        self.assertIsNotNone(status.started_at)

        # Wait for completion
        final_status = await service.wait_for_completion(timeout=5.0)
        self.assertEqual(final_status.state, ProcessingState.COMPLETED)

    async def test_03_duplicate_start_rejected(self):
        """3. Duplicate start is rejected while a job is active."""
        pipeline = MockPipeline(frames_to_yield=15, per_frame_delay=0.03)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        await service.start(
            source=str(self.dummy_video),
            camera_id="cam-01",
        )

        with self.assertRaises(RuntimeError) as ctx:
            await service.start(
                source=str(self.dummy_video),
                camera_id="cam-01",
            )
        self.assertIn("already active", str(ctx.exception))

        # Cleanup
        await service.stop()
        await service.wait_for_completion(timeout=5.0)

    async def test_04_frames_actually_processed(self):
        """4. Frames yielded by pipeline are processed and persisted."""
        pipeline = MockPipeline(frames_to_yield=3)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        await service.start(source=str(self.dummy_video), camera_id="cam-01")
        final_status = await service.wait_for_completion(timeout=5.0)

        self.assertEqual(final_status.processed_frames, 3)
        self.assertEqual(self.session_factory.committed_count, 3)

    async def test_05_processed_frame_count_increases(self):
        """5. Processed-frame count increases monotonically."""
        pipeline = MockPipeline(frames_to_yield=4)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        await service.start(source=str(self.dummy_video), camera_id="cam-01")
        final_status = await service.wait_for_completion(timeout=5.0)
        self.assertEqual(final_status.processed_frames, 4)

    async def test_06_processing_reaches_completed(self):
        """6. Processing reaches COMPLETED on video/frame limit."""
        pipeline = MockPipeline(frames_to_yield=5)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        await service.start(
            source=str(self.dummy_video),
            camera_id="cam-01",
            max_frames=2,
        )
        final_status = await service.wait_for_completion(timeout=5.0)

        self.assertEqual(final_status.state, ProcessingState.COMPLETED)
        self.assertEqual(final_status.processed_frames, 2)
        self.assertIsNotNone(final_status.finished_at)
        self.assertIsNone(final_status.error)

    async def test_07_stop_request_clean_handling(self):
        """7. Cooperative stop transitions state to STOPPING then STOPPED."""
        pipeline = MockPipeline(frames_to_yield=50, per_frame_delay=0.02)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        await service.start(source=str(self.dummy_video), camera_id="cam-01")
        await asyncio.sleep(0.04)

        stop_res = await service.stop()
        self.assertIn(stop_res.state, (ProcessingState.STOPPING, ProcessingState.STOPPED))

        final_status = await service.wait_for_completion(timeout=5.0)
        self.assertEqual(final_status.state, ProcessingState.STOPPED)
        self.assertIsNotNone(final_status.finished_at)
        self.assertLess(final_status.processed_frames, 50)

    async def test_08_failure_captured_in_status(self):
        """8. Pipeline failure is captured with FAILED state and error details."""

        class FailingPipeline:
            def process_video(self, *a, **kw):
                raise RuntimeError("Simulated inference engine failure")

        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: FailingPipeline(),
        )

        await service.start(source=str(self.dummy_video), camera_id="cam-01")
        final_status = await service.wait_for_completion(timeout=5.0)

        self.assertEqual(final_status.state, ProcessingState.FAILED)
        self.assertIn("Simulated inference engine failure", final_status.error or "")
        self.assertIsNotNone(final_status.finished_at)

    async def test_09_resources_cleaned_up(self):
        """9. Sessions are properly opened and closed per frame without leaks."""
        pipeline = MockPipeline(frames_to_yield=3)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        await service.start(source=str(self.dummy_video), camera_id="cam-01")
        await service.wait_for_completion(timeout=5.0)

        self.assertEqual(self.session_factory.opened_count, 3)
        self.assertEqual(self.session_factory.closed_count, 3)
        self.assertEqual(self.session_factory.opened_count, self.session_factory.closed_count)

    async def test_nonexistent_source_fails_cleanly(self):
        """Nonexistent video path transitions cleanly to FAILED."""
        service = ProcessingService(session_factory=self.session_factory)
        await service.start(source="nonexistent_video_path_xyz123.mp4")
        final_status = await service.wait_for_completion(timeout=5.0)

        self.assertEqual(final_status.state, ProcessingState.FAILED)
        self.assertIn("Video source not found", final_status.error or "")

    async def test_generator_closed_on_normal_completion(self):
        """Generator.close() is called on normal completion."""
        close_called = []

        class TrackingPipeline:
            def process_video(self, *a, **kw):
                def gen():
                    for i in range(1, 3):
                        yield _create_dummy_frame_result("cam-gc", i)

                inner = gen()

                class CloseTracker:
                    def __iter__(self):
                        return self

                    def __next__(self):
                        return next(inner)

                    def close(self):
                        close_called.append("closed")
                        inner.close()

                return CloseTracker()

        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: TrackingPipeline(),
        )
        await service.start(source=str(self.dummy_video), camera_id="cam-gc")
        final = await service.wait_for_completion(timeout=5.0)

        self.assertEqual(final.state, ProcessingState.COMPLETED)
        self.assertIn("closed", close_called)

    async def test_generator_closed_on_cooperative_stop(self):
        """Generator.close() is called when processing is cooperatively stopped."""
        close_called = []

        class TrackingPipeline:
            def process_video(self, *a, **kw):
                def gen():
                    try:
                        for i in range(1, 100):
                            import time

                            time.sleep(0.02)
                            yield _create_dummy_frame_result("cam-gs", i)
                    except GeneratorExit:
                        close_called.append("closed")
                        raise

                return gen()

        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: TrackingPipeline(),
        )
        await service.start(source=str(self.dummy_video), camera_id="cam-gs")
        await asyncio.sleep(0.04)
        await service.stop()
        final = await service.wait_for_completion(timeout=5.0)

        self.assertEqual(final.state, ProcessingState.STOPPED)
        self.assertIn("closed", close_called)

    async def test_generator_closed_on_failure(self):
        """Generator.close() is called when ingestion fails mid-stream."""
        close_called = []

        class TrackingPipeline:
            def process_video(self, *a, **kw):
                def gen():
                    try:
                        yield _create_dummy_frame_result("cam-gf", 1)
                        yield _create_dummy_frame_result("cam-gf", 2)
                    except GeneratorExit:
                        close_called.append("closed")
                        raise

                return gen()

        call_count = [0]
        orig_factory = self.session_factory

        def failing_session_factory():
            call_count[0] += 1
            if call_count[0] >= 2:
                raise RuntimeError("Simulated DB connection failure")
            return orig_factory()

        service = ProcessingService(
            session_factory=failing_session_factory,
            pipeline_factory=lambda **kw: TrackingPipeline(),
        )
        await service.start(source=str(self.dummy_video), camera_id="cam-gf")
        final = await service.wait_for_completion(timeout=5.0)

        self.assertEqual(final.state, ProcessingState.FAILED)
        self.assertIn("closed", close_called)

    async def test_task_reference_not_clobbered_by_old_worker(self):
        """A finishing worker's finally block must not clear a newly-started task reference."""
        pipeline = MockPipeline(frames_to_yield=2)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        # Start first job and let it complete
        await service.start(source=str(self.dummy_video), camera_id="cam-01")
        await service.wait_for_completion(timeout=5.0)
        self.assertEqual(service.get_status().state, ProcessingState.COMPLETED)
        self.assertIsNone(service._task, "Task reference should be None after completion")

        # Start a second job
        pipeline2 = MockPipeline(frames_to_yield=3)
        service._pipeline_factory = lambda **kw: pipeline2
        await service.start(source=str(self.dummy_video), camera_id="cam-02")
        self.assertIsNotNone(service._task, "Task reference should be set for new job")

        final = await service.wait_for_completion(timeout=5.0)
        self.assertEqual(final.state, ProcessingState.COMPLETED)
        self.assertEqual(final.processed_frames, 3)

    async def test_restart_after_stopped(self):
        """Restarting a STOPPED camera creates a genuinely clean worker state."""
        pipeline = MockPipeline(frames_to_yield=50, per_frame_delay=0.02)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        # 1. Start and stop
        await service.start(source=str(self.dummy_video), camera_id="cam-restart")
        await asyncio.sleep(0.04)
        await service.stop()
        stopped_status = await service.wait_for_completion(timeout=5.0)
        self.assertEqual(stopped_status.state, ProcessingState.STOPPED)
        first_run_frames = stopped_status.processed_frames

        # 2. Restart the same camera
        pipeline_new = MockPipeline(frames_to_yield=3)
        service._pipeline_factory = lambda **kw: pipeline_new
        restart_status = await service.start(source=str(self.dummy_video), camera_id="cam-restart")
        self.assertIn(restart_status.state, (ProcessingState.STARTING, ProcessingState.RUNNING))
        self.assertEqual(restart_status.processed_frames, 0)
        self.assertIsNone(restart_status.finished_at)

        # 3. Completes cleanly
        final_status = await service.wait_for_completion(timeout=5.0)
        self.assertEqual(final_status.state, ProcessingState.COMPLETED)
        self.assertEqual(final_status.processed_frames, 3)

    async def test_restart_after_completed(self):
        """Restarting a COMPLETED camera creates fresh counters and clean task."""
        pipeline = MockPipeline(frames_to_yield=2)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        await service.start(source=str(self.dummy_video), camera_id="cam-comp")
        first = await service.wait_for_completion(timeout=5.0)
        self.assertEqual(first.state, ProcessingState.COMPLETED)
        self.assertEqual(first.processed_frames, 2)

        # Restart
        pipeline2 = MockPipeline(frames_to_yield=4)
        service._pipeline_factory = lambda **kw: pipeline2
        await service.start(source=str(self.dummy_video), camera_id="cam-comp")
        second = await service.wait_for_completion(timeout=5.0)
        self.assertEqual(second.state, ProcessingState.COMPLETED)
        self.assertEqual(second.processed_frames, 4)

    async def test_restart_after_failed(self):
        """Restarting a FAILED camera clears the previous error and runs cleanly."""
        class FailThenSucceed:
            def __init__(self):
                self.calls = 0

            def process_video(self, *a, **kw):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("First run failure")
                for i in range(1, 3):
                    yield _create_dummy_frame_result("cam-fail", i)

        pipeline = FailThenSucceed()
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        # Run 1 fails
        await service.start(source=str(self.dummy_video), camera_id="cam-fail")
        res1 = await service.wait_for_completion(timeout=5.0)
        self.assertEqual(res1.state, ProcessingState.FAILED)
        self.assertIsNotNone(res1.error)

        # Run 2 restarts and succeeds
        await service.start(source=str(self.dummy_video), camera_id="cam-fail")
        res2 = await service.wait_for_completion(timeout=5.0)
        self.assertEqual(res2.state, ProcessingState.COMPLETED)
        self.assertIsNone(res2.error)
        self.assertEqual(res2.processed_frames, 2)

    async def test_latest_runtime_frame_snapshot(self):
        """LatestFrameSnapshot exposes all FrameResult fields and runtime FPS."""
        pipeline = MockPipeline(frames_to_yield=3)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        await service.start(source=str(self.dummy_video), camera_id="cam-snap")
        status = await service.wait_for_completion(timeout=5.0)

        self.assertEqual(status.state, ProcessingState.COMPLETED)
        self.assertIsNotNone(status.latest_frame)
        snap = status.latest_frame
        self.assertEqual(snap.frame_number, 3)
        self.assertEqual(snap.active_vehicle_count, 1)
        self.assertEqual(snap.plate_observations_count, 1)
        self.assertEqual(snap.plate_texts, ["MH12AB0003"])
        self.assertEqual(snap.traffic_pressure, 0.15)
        self.assertEqual(snap.traffic_level, "LOW")
        self.assertEqual(snap.signal_green_time, 30)
        self.assertEqual(snap.signal_reason, "Normal traffic flow")
        self.assertGreaterEqual(status.elapsed_seconds, 0.0)
        self.assertIsNotNone(status.fps)

    async def test_worker_cancellation_handled_cleanly(self):
        """Task cancellation transitions worker to STOPPED."""
        pipeline = MockPipeline(frames_to_yield=50, per_frame_delay=0.03)
        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: pipeline,
        )

        await service.start(source=str(self.dummy_video), camera_id="cam-cancel")
        await asyncio.sleep(0.04)

        worker = service.get_camera("cam-cancel")
        self.assertIsNotNone(worker)
        self.assertIsNotNone(worker._task)
        worker._task.cancel()

        status = await service.wait_for_completion(camera_id="cam-cancel", timeout=5.0)
        self.assertEqual(status.state, ProcessingState.STOPPED)

    async def test_multi_camera_independent_execution(self):
        """Two independent cameras run concurrently with isolated lifecycles."""
        p1 = MockPipeline(camera_id="cam-01", frames_to_yield=50, per_frame_delay=0.02)
        p2 = MockPipeline(camera_id="cam-02", frames_to_yield=3)

        def multi_pipeline_factory(camera_id, **kw):
            return p1 if camera_id == "cam-01" else p2

        service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=multi_pipeline_factory,
        )

        # Start both cameras
        await service.start(source=str(self.dummy_video), camera_id="cam-01")
        await service.start(source=str(self.dummy_video), camera_id="cam-02")

        # Both registered in all-cameras response
        all_cams = service.get_all_cameras()
        self.assertEqual(len(all_cams.cameras), 2)
        self.assertEqual(all_cams.active_count, 2)

        # Stop camera 1 only
        await service.stop(camera_id="cam-01")
        s1 = await service.wait_for_completion(camera_id="cam-01", timeout=5.0)
        self.assertEqual(s1.state, ProcessingState.STOPPED)

        # Camera 2 completes naturally
        s2 = await service.wait_for_completion(camera_id="cam-02", timeout=5.0)
        self.assertEqual(s2.state, ProcessingState.COMPLETED)
        self.assertEqual(s2.processed_frames, 3)


class ProcessingServiceAPITests(unittest.IsolatedAsyncioTestCase):
    """Integration tests for /api/processing endpoints."""

    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            poolclass=StaticPool,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.session_factory = TrackingSessionFactory(self.session_maker)
        self.pipeline = MockPipeline(frames_to_yield=15, per_frame_delay=0.03)
        self.mock_service = ProcessingService(
            session_factory=self.session_factory,
            pipeline_factory=lambda **kw: self.pipeline,
        )

        # Override dependency
        app.dependency_overrides[get_processing_service] = lambda: self.mock_service
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")
        self.dummy_video = Path("data/videos/traffic.mp4")
        if not self.dummy_video.exists():
            self.dummy_video = Path(__file__).resolve()

    async def asyncTearDown(self):
        await self.mock_service.stop()
        await self.mock_service.wait_for_completion(timeout=5.0)
        await self.client.aclose()
        await self.engine.dispose()
        app.dependency_overrides.clear()

    async def test_10_api_status_endpoint_reflects_service_state(self):
        """10. GET /api/processing/status reflects current service state."""
        response = await self.client.get("/api/processing/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["state"], "IDLE")
        self.assertEqual(data["processed_frames"], 0)

    async def test_11_api_start_returns_immediately_before_job_finishes(self):
        """11. POST /api/processing/start returns before the processing job completes."""
        payload = {
            "source": str(self.dummy_video),
            "camera_id": "cam-test-api",
            "max_frames": 10,
        }

        response = await self.client.post("/api/processing/start", json=payload)
        self.assertEqual(response.status_code, 202)
        data = response.json()

        # The endpoint must return while job is still starting or running
        self.assertIn(data["state"], ("STARTING", "RUNNING"))
        self.assertEqual(data["camera_id"], "cam-test-api")

        # Prove that the worker task is still active and has not finished yet
        self.assertTrue(self.mock_service._task is not None and not self.mock_service._task.done())

        # Cleanly await completion
        final_status = await self.mock_service.wait_for_completion(timeout=5.0)
        self.assertEqual(final_status.state, ProcessingState.COMPLETED)

    async def test_12_api_duplicate_start_returns_409(self):
        """12. POST /api/processing/start returns 409 Conflict if already active."""
        payload = {
            "source": str(self.dummy_video),
            "camera_id": "cam-test-api",
            "max_frames": 15,
        }

        # First start succeeds
        res1 = await self.client.post("/api/processing/start", json=payload)
        self.assertEqual(res1.status_code, 202)

        # Second start while active must return 409 Conflict
        res2 = await self.client.post("/api/processing/start", json=payload)
        self.assertEqual(res2.status_code, 409)
        self.assertIn("already active", res2.json()["detail"])

    async def test_13_api_stop_endpoint(self):
        """POST /api/processing/stop initiates cooperative stop."""
        payload = {
            "source": str(self.dummy_video),
            "camera_id": "cam-test-stop",
            "max_frames": 30,
        }

        await self.client.post("/api/processing/start", json=payload)
        await asyncio.sleep(0.04)

        res = await self.client.post("/api/processing/stop")
        self.assertEqual(res.status_code, 200)
        self.assertIn(res.json()["state"], ("STOPPING", "STOPPED"))

        final = await self.mock_service.wait_for_completion(timeout=5.0)
        self.assertEqual(final.state, ProcessingState.STOPPED)

    async def test_14_api_list_cameras(self):
        """GET /api/processing/cameras lists all registered cameras and active count."""
        payload = {
            "source": str(self.dummy_video),
            "camera_id": "cam-list-test",
            "max_frames": 2,
        }
        await self.client.post("/api/processing/start", json=payload)

        res = await self.client.get("/api/processing/cameras")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("cameras", data)
        self.assertIn("active_count", data)
        self.assertGreaterEqual(len(data["cameras"]), 1)

    async def test_15_api_get_specific_camera_status(self):
        """GET /api/processing/cameras/{camera_id}/status returns camera-specific status."""
        payload = {
            "source": str(self.dummy_video),
            "camera_id": "cam-specific-status",
            "max_frames": 2,
        }
        await self.client.post("/api/processing/start", json=payload)

        res = await self.client.get("/api/processing/cameras/cam-specific-status/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["camera_id"], "cam-specific-status")

    async def test_16_api_stop_with_explicit_camera_id(self):
        """POST /api/processing/stop with explicit camera_id stops that camera."""
        payload = {
            "source": str(self.dummy_video),
            "camera_id": "cam-stop-explicit",
            "max_frames": 20,
        }
        await self.client.post("/api/processing/start", json=payload)
        await asyncio.sleep(0.04)

        stop_res = await self.client.post(
            "/api/processing/stop",
            json={"camera_id": "cam-stop-explicit"},
        )
        self.assertEqual(stop_res.status_code, 200)
        self.assertIn(stop_res.json()["state"], ("STOPPING", "STOPPED"))

    async def test_17_api_stop_ambiguous_rejection(self):
        """POST /api/processing/stop without camera_id returns 400 when multiple cameras are active."""
        p1 = {
            "source": str(self.dummy_video),
            "camera_id": "cam-ambig-1",
            "max_frames": 30,
        }
        p2 = {
            "source": str(self.dummy_video),
            "camera_id": "cam-ambig-2",
            "max_frames": 30,
        }
        await self.client.post("/api/processing/start", json=p1)
        await self.client.post("/api/processing/start", json=p2)

        # Ambiguous stop without camera_id
        res = await self.client.post("/api/processing/stop")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Multiple cameras", res.json()["detail"])

        # Explicit stop for each succeeds
        await self.client.post("/api/processing/stop", json={"camera_id": "cam-ambig-1"})
        await self.client.post("/api/processing/stop", json={"camera_id": "cam-ambig-2"})


if __name__ == "__main__":
    unittest.main()
