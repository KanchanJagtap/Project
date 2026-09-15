"""
Video Processing Orchestration Service (Milestones 2F & 2G).

Manages continuous and single-camera video processing runs in the background
without blocking FastAPI request handlers, bridging:
SingleCameraPipeline -> FrameResult -> IngestionService -> PostgreSQL

Architecture (Milestone 2G):
- CameraWorker: Encapsulates the lifecycle, background task, state machine,
  cooperative stop, deterministic generator cleanup, and in-memory latest-frame
  snapshot for an individual camera stream.
- ProcessingService / ProcessingManager: Lightweight in-process manager
  maintaining multiple concurrent camera workers with clean isolation,
  deterministic default resolution, and backward-compatible singleton interface.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ai.pipeline.single_camera_pipeline import FrameResult, SingleCameraPipeline
from backend.app.db.session import async_session_factory
from backend.app.schemas.processing import (
    CamerasListResponse,
    LatestFrameSnapshot,
    ProcessingOverviewResponse,
    ProcessingState,
    ProcessingStatusResponse,
)
from backend.app.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

# Resolve repository root
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Default model weights
DEFAULT_TRACKER_PATH = (
    PROJECT_ROOT / "runs" / "detect" / "runs" / "cctv" / "uvh26_80ep-2" / "weights" / "best.pt"
)
if not DEFAULT_TRACKER_PATH.exists():
    DEFAULT_TRACKER_PATH = PROJECT_ROOT / "yolo11n.pt"

DEFAULT_PLATE_PATH = PROJECT_ROOT / "ai" / "models" / "license_plate.pt"


def _default_pipeline_factory(
    camera_id: str,
    tracker_model_path: str,
    plate_model_path: str,
    approach_id: Optional[str] = None,
    anpr_every_n_frames: int = 5,
) -> SingleCameraPipeline:
    """Instantiate the production SingleCameraPipeline."""
    return SingleCameraPipeline(
        camera_id=camera_id,
        tracker_model_path=tracker_model_path,
        plate_model_path=plate_model_path,
        approach_id=approach_id,
        anpr_every_n_frames=anpr_every_n_frames,
    )


def _build_latest_frame_snapshot(frame_result: FrameResult) -> LatestFrameSnapshot:
    """Build an immutable LatestFrameSnapshot directly from FrameResult contracts.

    No values are invented or estimated:
    - active_vehicle_count comes from tracked_vehicle_contracts (or active_vehicles).
    - plate_observations_count and plate_texts come directly from plate_observations.
    - traffic_pressure and traffic_level come from snapshot (if present).
    - signal_green_time and signal_reason come from signal_decisions (if present).
    """
    plate_texts = [
        obs.plate_text
        for obs in frame_result.plate_observations
        if obs.plate_text and obs.plate_text.strip()
    ]

    pressure: Optional[float] = None
    level: Optional[str] = None
    queue_len: Optional[int] = None
    moving_veh: Optional[int] = None
    stat_veh: Optional[int] = None
    if frame_result.snapshot is not None:
        pressure = round(float(frame_result.snapshot.traffic_pressure), 2)
        level = frame_result.snapshot.traffic_level
        queue_len = int(frame_result.snapshot.queue_length)
        moving_veh = int(frame_result.snapshot.moving_vehicles)
        stat_veh = int(frame_result.snapshot.stationary_vehicles)

    green_time: Optional[int] = None
    reason: Optional[str] = None
    if frame_result.signal_decisions:
        first_dec = frame_result.signal_decisions[0]
        green_time = int(first_dec.green_time)
        reason = first_dec.reason

    vehicle_count = len(frame_result.tracked_vehicle_contracts) or len(
        frame_result.active_vehicles
    )

    return LatestFrameSnapshot(
        frame_number=frame_result.frame_number,
        timestamp=frame_result.timestamp,
        processing_time_ms=float(frame_result.processing_time_ms),
        active_vehicle_count=vehicle_count,
        plate_observations_count=len(frame_result.plate_observations),
        plate_texts=plate_texts,
        traffic_pressure=pressure,
        traffic_level=level,
        signal_green_time=green_time,
        signal_reason=reason,
        queue_length=queue_len,
        moving_vehicles=moving_veh,
        stationary_vehicles=stat_veh,
    )


class CameraWorker:
    """Manages the background execution and lifecycle of a single camera stream.

    Supports continuous and finite video processing runs, coordinating:
    Frame decoding -> AI pipeline -> FrameResult -> IngestionService -> PostgreSQL

    Lifecycle states:
        IDLE -> STARTING -> RUNNING -> (STOPPING -> STOPPED) / COMPLETED / FAILED

    Resource and concurrency guarantees:
    - Generator is deterministically closed via generator.close() on all exit paths.
    - Cooperative stop allows in-flight synchronous YOLO inference to complete cleanly.
    - Task-reference race safety: worker only clears self._task if it is still the current task.
    - Clean restart: resets all counters, stop event, task, timestamps, error, and latest frame.
    - In-memory latest frame snapshot is frozen and immutable for safe concurrent reads.
    """

    def __init__(
        self,
        camera_id: str,
        session_factory: Optional[Callable[[], AsyncSession]] = None,
        pipeline_factory: Optional[Callable[..., Any]] = None,
        tracker_model_path: Optional[str] = None,
        plate_model_path: Optional[str] = None,
    ) -> None:
        self.camera_id = camera_id
        self._session_factory = session_factory or async_session_factory
        self._pipeline_factory = pipeline_factory or _default_pipeline_factory
        self._tracker_model_path = (
            Path(tracker_model_path) if tracker_model_path else DEFAULT_TRACKER_PATH
        )
        self._plate_model_path = (
            Path(plate_model_path) if plate_model_path else DEFAULT_PLATE_PATH
        )

        # Lifecycle state
        self._state: ProcessingState = ProcessingState.IDLE
        self._source: Optional[str] = None
        self._junction_id: Optional[str] = None
        self._max_frames: Optional[int] = None
        self._anpr_every_n_frames: int = 5
        self._processed_frames: int = 0
        self._started_at: Optional[datetime] = None
        self._finished_at: Optional[datetime] = None
        self._error: Optional[str] = None

        # Runtime latest frame state
        self._latest_frame: Optional[LatestFrameSnapshot] = None
        self._last_frame_processed_at: Optional[datetime] = None
        self._total_frame_processing_time_ms: float = 0.0

        # Concurrency and task control
        self._task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def is_active(self) -> bool:
        """True if the worker is in an active non-terminal state."""
        return self._state in (
            ProcessingState.STARTING,
            ProcessingState.RUNNING,
            ProcessingState.STOPPING,
        )

    @property
    def average_frame_latency_ms(self) -> Optional[float]:
        """Average per-frame processing latency in ms, if any frames processed."""
        if self._processed_frames > 0 and self._total_frame_processing_time_ms > 0:
            return round(self._total_frame_processing_time_ms / self._processed_frames, 2)
        return None

    def get_status(self) -> ProcessingStatusResponse:
        """Return the current processing worker status snapshot with runtime metrics."""
        now = datetime.now(timezone.utc)
        elapsed: Optional[float] = None
        fps: Optional[float] = None

        if self._started_at is not None:
            end_time = self._finished_at or now
            elapsed_delta = (end_time - self._started_at).total_seconds()
            elapsed = max(0.0, round(elapsed_delta, 3))
            if elapsed > 0 and self._processed_frames > 0:
                fps = round(self._processed_frames / elapsed, 2)

        seconds_since_last: Optional[float] = None
        if self._last_frame_processed_at is not None:
            seconds_since_last = max(
                0.0,
                round((now - self._last_frame_processed_at).total_seconds(), 3),
            )

        return ProcessingStatusResponse(
            state=self._state,
            source=self._source,
            camera_id=self.camera_id,
            junction_id=self._junction_id,
            processed_frames=self._processed_frames,
            max_frames=self._max_frames,
            started_at=self._started_at,
            finished_at=self._finished_at,
            error=self._error,
            elapsed_seconds=elapsed,
            fps=fps,
            latest_frame=self._latest_frame,
            last_frame_processed_at=self._last_frame_processed_at,
            seconds_since_last_frame_processed=seconds_since_last,
        )

    async def start(
        self,
        source: str,
        max_frames: Optional[int] = None,
        junction_id: Optional[str] = None,
        anpr_every_n_frames: int = 5,
    ) -> ProcessingStatusResponse:
        """Initiate background video processing for this camera.

        Returns immediately with status STARTING without waiting for video completion.
        If a processing run is already active, raises RuntimeError.
        A clean restart resets all counters, timestamps, errors, and task references.
        """
        async with self._lock:
            if self.is_active:
                raise RuntimeError(
                    f"A processing job for camera '{self.camera_id}' is already active."
                )

            # Genuine clean restart: reset all state
            self._stop_event = asyncio.Event()
            self._state = ProcessingState.STARTING
            self._source = source
            self._junction_id = junction_id or f"junction-{self.camera_id}"
            self._max_frames = max_frames
            self._anpr_every_n_frames = anpr_every_n_frames
            self._processed_frames = 0
            self._started_at = datetime.now(timezone.utc)
            self._finished_at = None
            self._error = None
            self._latest_frame = None
            self._last_frame_processed_at = None
            self._total_frame_processing_time_ms = 0.0

            self._task = asyncio.create_task(
                self._run_worker(
                    source=source,
                    max_frames=max_frames,
                    junction_id=self._junction_id,
                    anpr_every_n_frames=anpr_every_n_frames,
                )
            )

            return self.get_status()

    async def stop(self) -> ProcessingStatusResponse:
        """Request a clean, cooperative stop of the active processing run.

        Lifecycle:
        stop requested -> current synchronous inference may finish ->
        current frame ingestion may finish -> worker observes stop event -> STOPPED.
        """
        async with self._lock:
            if self._state in (ProcessingState.STARTING, ProcessingState.RUNNING):
                self._state = ProcessingState.STOPPING
                self._stop_event.set()

        return self.get_status()

    def reset(self) -> None:
        """Reset worker back to IDLE if not currently active."""
        if self.is_active:
            raise RuntimeError(
                f"Cannot reset an active processing job for camera '{self.camera_id}'. Stop it first."
            )

        self._state = ProcessingState.IDLE
        self._source = None
        self._junction_id = None
        self._max_frames = None
        self._processed_frames = 0
        self._started_at = None
        self._finished_at = None
        self._error = None
        self._latest_frame = None
        self._last_frame_processed_at = None
        self._total_frame_processing_time_ms = 0.0
        self._task = None
        self._stop_event = asyncio.Event()

    async def wait_for_completion(
        self, timeout: Optional[float] = None
    ) -> ProcessingStatusResponse:
        """Wait until background worker completes or timeout expires."""
        if self._task is not None:
            try:
                if timeout is not None:
                    await asyncio.wait_for(asyncio.shield(self._task), timeout=timeout)
                else:
                    await self._task
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        return self.get_status()

    async def _run_worker(
        self,
        source: str,
        max_frames: Optional[int],
        junction_id: str,
        anpr_every_n_frames: int,
    ) -> None:
        """Internal background worker executing video inference and ingestion."""
        current_task = asyncio.current_task()
        generator = None

        try:
            # Handle continuous / stream sources vs local video files
            is_stream = source.startswith(
                ("rtsp://", "rtsps://", "http://", "https://")
            )
            if not is_stream:
                src_path = Path(source)
                if not src_path.is_absolute():
                    src_path = (PROJECT_ROOT / src_path).resolve()

                if not src_path.exists():
                    raise FileNotFoundError(f"Video source not found: {source}")
                video_source_str = str(src_path)
            else:
                # Stream source URL passed directly to OpenCV cv2.VideoCapture.
                # Note: RTSP/stream ingestion is supported by OpenCV but unverified in this unit suite.
                video_source_str = source

            async with self._lock:
                if self._stop_event.is_set():
                    self._state = ProcessingState.STOPPED
                    self._finished_at = datetime.now(timezone.utc)
                    return
                self._state = ProcessingState.RUNNING

            # Instantiate pipeline
            pipeline = self._pipeline_factory(
                camera_id=self.camera_id,
                tracker_model_path=str(self._tracker_model_path),
                plate_model_path=str(self._plate_model_path),
                approach_id=f"approach-{self.camera_id}",
                anpr_every_n_frames=anpr_every_n_frames,
            )

            # Process video stream
            generator = pipeline.process_video(
                video_source_str,
                max_frames=max_frames,
                print_every=0,
            )

            for frame_result in generator:
                # Cooperative check between frames.
                # A synchronous YOLO inference that was already in progress
                # will have finished by the time we reach this check.
                if self._stop_event.is_set():
                    break

                # Atomic per-frame database session
                async with self._session_factory() as session:
                    try:
                        ingest_svc = IngestionService(session, auto_register_metadata=True)
                        await ingest_svc.ingest_frame_result(
                            frame_result,
                            junction_id=junction_id,
                        )
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        raise

                self._processed_frames += 1
                self._last_frame_processed_at = datetime.now(timezone.utc)
                if frame_result.processing_time_ms is not None:
                    self._total_frame_processing_time_ms += float(frame_result.processing_time_ms)

                # Update immutable snapshot of latest frame state
                self._latest_frame = _build_latest_frame_snapshot(frame_result)

                # Yield to the event loop so concurrent tasks/requests can proceed.
                # NOTE: During the synchronous YOLO inference of each frame,
                # the event loop IS blocked. asyncio.sleep(0) yields control between frames.
                await asyncio.sleep(0)

            # Natural completion or cooperative stop
            async with self._lock:
                if self._stop_event.is_set():
                    self._state = ProcessingState.STOPPED
                else:
                    self._state = ProcessingState.COMPLETED
                self._finished_at = datetime.now(timezone.utc)

        except asyncio.CancelledError:
            logger.info("Processing worker task for camera %s was cancelled.", self.camera_id)
            async with self._lock:
                self._state = ProcessingState.STOPPED
                self._finished_at = datetime.now(timezone.utc)
            raise

        except Exception as exc:
            logger.error(
                "Processing worker failed for camera %s: %s",
                self.camera_id,
                exc,
                exc_info=True,
            )
            async with self._lock:
                self._state = ProcessingState.FAILED
                self._error = str(exc)
                self._finished_at = datetime.now(timezone.utc)

        finally:
            # Deterministically close generator to release any resources
            if generator is not None and hasattr(generator, "close"):
                try:
                    generator.close()
                except Exception:
                    logger.debug(
                        "Exception closing pipeline generator for camera %s",
                        self.camera_id,
                        exc_info=True,
                    )

            # Only clear the task reference if we are still the current task.
            if self._task is current_task:
                self._task = None


class ProcessingService:
    """Video Processing Orchestration Manager (Milestones 2F/2G).

    Manages concurrent camera workers across multiple CCTV feeds.
    Provides complete backward compatibility with the single-camera
    ProcessingService interface while supporting multi-camera registration.
    """

    def __init__(
        self,
        session_factory: Optional[Callable[[], AsyncSession]] = None,
        pipeline_factory: Optional[Callable[..., Any]] = None,
        tracker_model_path: Optional[str] = None,
        plate_model_path: Optional[str] = None,
    ) -> None:
        self._session_factory = session_factory or async_session_factory
        self._pipeline_factory = pipeline_factory or _default_pipeline_factory
        self._tracker_model_path = (
            Path(tracker_model_path) if tracker_model_path else DEFAULT_TRACKER_PATH
        )
        self._plate_model_path = (
            Path(plate_model_path) if plate_model_path else DEFAULT_PLATE_PATH
        )

        # Multi-camera registry
        self._workers: Dict[str, CameraWorker] = {}
        self._last_camera_id: Optional[str] = None
        self._lock: asyncio.Lock = asyncio.Lock()

        # Unconfigured initial IDLE state placeholder for backward compatibility
        self._initial_worker = CameraWorker(
            camera_id="cctv-cam-01",
            session_factory=self._session_factory,
            pipeline_factory=self._pipeline_factory,
            tracker_model_path=str(self._tracker_model_path),
            plate_model_path=str(self._plate_model_path),
        )

    # =========================================================================
    # Multi-Camera Worker Management
    # =========================================================================

    def _create_worker(self, camera_id: str) -> CameraWorker:
        """Instantiate a new CameraWorker with manager-level dependencies."""
        return CameraWorker(
            camera_id=camera_id,
            session_factory=self._session_factory,
            pipeline_factory=self._pipeline_factory,
            tracker_model_path=str(self._tracker_model_path),
            plate_model_path=str(self._plate_model_path),
        )

    def _get_default_or_last_worker(self) -> Optional[CameraWorker]:
        """Resolve the active or most recently used camera worker."""
        if not self._workers:
            return None
        if self._last_camera_id and self._last_camera_id in self._workers:
            return self._workers[self._last_camera_id]
        return next(iter(self._workers.values()))

    # =========================================================================
    # Status Inspection
    # =========================================================================

    def get_status(
        self, camera_id: Optional[str] = None
    ) -> ProcessingStatusResponse:
        """Return the status of the specified camera, or the single active/last camera.

        Deterministic default rule:
        - If camera_id is given, returns that camera's status (or IDLE if not registered).
        - If camera_id is omitted and 0 cameras are registered, returns unconfigured IDLE.
        - If camera_id is omitted and exactly 1 camera is registered, returns its status.
        - If camera_id is omitted and multiple cameras exist, returns the most recently
          started camera's status.
        """
        if camera_id is not None:
            worker = self._workers.get(camera_id)
            if worker is None:
                return ProcessingStatusResponse(
                    state=ProcessingState.IDLE, camera_id=camera_id
                )
            return worker.get_status()

        if not self._workers:
            # Unconfigured initial IDLE state has camera_id=None for 2F compatibility
            status = self._initial_worker.get_status()
            return ProcessingStatusResponse(
                state=status.state,
                source=status.source,
                camera_id=None,
                junction_id=status.junction_id,
                processed_frames=status.processed_frames,
                max_frames=status.max_frames,
                started_at=status.started_at,
                finished_at=status.finished_at,
                error=status.error,
            )

        worker = self._get_default_or_last_worker()
        return worker.get_status() if worker else self._initial_worker.get_status()

    def get_all_cameras(self) -> CamerasListResponse:
        """Return status for all registered camera workers."""
        statuses = [w.get_status() for w in self._workers.values()]
        active_count = sum(
            1
            for s in statuses
            if s.state
            in (
                ProcessingState.STARTING,
                ProcessingState.RUNNING,
                ProcessingState.STOPPING,
            )
        )
        return CamerasListResponse(cameras=statuses, active_count=active_count)

    def get_camera(self, camera_id: str) -> Optional[CameraWorker]:
        """Retrieve a specific camera worker if registered."""
        return self._workers.get(camera_id)

    def get_overview(self) -> ProcessingOverviewResponse:
        """Aggregate system-wide multi-camera runtime metrics for dashboard monitoring.

        Telemetry aggregation logic:
        - total_cameras: total registered workers in self._workers.
        - active_cameras: count in STARTING, RUNNING, STOPPING.
        - idle_cameras: count in IDLE.
        - stopped_cameras: count in STOPPED, COMPLETED.
        - failed_cameras: count in FAILED.
        - total_processed_frames: sum of processed_frames across ALL workers.
        - aggregate_fps: sum of fps across ACTIVE workers.
        - average_frame_latency_ms: genuine average frame processing latency across active workers
          computed as sum(active workers' total_frame_processing_time_ms) / sum(active workers' processed_frames).
          Returns None if no active frames have been processed yet.
        - total_active_vehicles: sum of active workers' latest-frame active_vehicle_count.
        - total_plates_detected: sum of active workers' latest-frame plate_observations_count.
        - system_status:
            'DEGRADED' if failed_cameras > 0
            'OPTIMAL' if active_cameras > 0 and failed_cameras == 0
            'IDLE' if active_cameras == 0 and failed_cameras == 0
        """
        now = datetime.now(timezone.utc)
        total_cameras = len(self._workers)
        active_cameras = 0
        idle_cameras = 0
        stopped_cameras = 0
        failed_cameras = 0
        total_processed_frames = 0
        aggregate_fps = 0.0
        active_total_time_ms = 0.0
        active_total_frames = 0
        total_active_vehicles = 0
        total_plates_detected = 0

        for worker in self._workers.values():
            status = worker.get_status()
            total_processed_frames += status.processed_frames

            if status.state in (
                ProcessingState.STARTING,
                ProcessingState.RUNNING,
                ProcessingState.STOPPING,
            ):
                active_cameras += 1
                if status.fps is not None:
                    aggregate_fps += status.fps
                active_total_time_ms += worker._total_frame_processing_time_ms
                active_total_frames += worker._processed_frames
                if worker._latest_frame is not None:
                    total_active_vehicles += worker._latest_frame.active_vehicle_count
                    total_plates_detected += worker._latest_frame.plate_observations_count
            elif status.state == ProcessingState.IDLE:
                idle_cameras += 1
            elif status.state in (ProcessingState.STOPPED, ProcessingState.COMPLETED):
                stopped_cameras += 1
            elif status.state == ProcessingState.FAILED:
                failed_cameras += 1

        avg_latency: Optional[float] = None
        if active_total_frames > 0 and active_total_time_ms > 0:
            avg_latency = round(active_total_time_ms / active_total_frames, 2)

        if failed_cameras > 0:
            system_status = "DEGRADED"
        elif active_cameras > 0:
            system_status = "OPTIMAL"
        else:
            system_status = "IDLE"

        return ProcessingOverviewResponse(
            total_cameras=total_cameras,
            active_cameras=active_cameras,
            idle_cameras=idle_cameras,
            stopped_cameras=stopped_cameras,
            failed_cameras=failed_cameras,
            total_processed_frames=total_processed_frames,
            aggregate_fps=round(aggregate_fps, 2),
            average_frame_latency_ms=avg_latency,
            total_active_vehicles=total_active_vehicles,
            total_plates_detected=total_plates_detected,
            system_status=system_status,
            timestamp=now,
        )

    # =========================================================================
    # Start Execution
    # =========================================================================

    async def start(
        self,
        source: str,
        camera_id: str = "cctv-cam-01",
        max_frames: Optional[int] = None,
        junction_id: Optional[str] = None,
        anpr_every_n_frames: int = 5,
    ) -> ProcessingStatusResponse:
        """Initiate background video processing for the specified camera.

        Returns immediately with status STARTING without waiting for video completion.
        If a processing run for this camera is already active, raises RuntimeError.
        A clean restart creates a fresh CameraWorker to guarantee zero state bleed.
        """
        async with self._lock:
            existing_worker = self._workers.get(camera_id)
            if existing_worker is not None and existing_worker.is_active:
                raise RuntimeError(
                    f"A processing job for camera '{camera_id}' is already active."
                )

            # Clean restart: instantiate a fresh worker to ensure complete isolation
            worker = self._create_worker(camera_id)
            self._workers[camera_id] = worker
            self._last_camera_id = camera_id

            return await worker.start(
                source=source,
                max_frames=max_frames,
                junction_id=junction_id,
                anpr_every_n_frames=anpr_every_n_frames,
            )

    # =========================================================================
    # Cooperative Stop Execution
    # =========================================================================

    async def stop(
        self, camera_id: Optional[str] = None
    ) -> ProcessingStatusResponse:
        """Request cooperative stop of an active camera processing run.

        Deterministic default rule when camera_id is omitted:
        - If 0 cameras registered: returns unconfigured IDLE.
        - If exactly 1 camera registered: stops that camera.
        - If multiple cameras registered:
          - If exactly 1 is active, stops that active camera.
          - If multiple are active, raises RuntimeError requiring explicit camera_id.
          - If none are active, stops the most recently started camera.
        """
        if camera_id is not None:
            worker = self._workers.get(camera_id)
            if worker is None:
                return ProcessingStatusResponse(
                    state=ProcessingState.IDLE, camera_id=camera_id
                )
            return await worker.stop()

        if not self._workers:
            return self._initial_worker.get_status()

        if len(self._workers) == 1:
            return await next(iter(self._workers.values())).stop()

        active_workers = [w for w in self._workers.values() if w.is_active]
        if len(active_workers) == 1:
            return await active_workers[0].stop()
        elif len(active_workers) > 1:
            raise RuntimeError(
                "Multiple cameras are currently active. Please specify camera_id to stop."
            )
        else:
            if self._last_camera_id and self._last_camera_id in self._workers:
                return await self._workers[self._last_camera_id].stop()
            return await next(iter(self._workers.values())).stop()

    async def stop_all(self) -> List[ProcessingStatusResponse]:
        """Request cooperative stop for all registered camera workers."""
        results = []
        for worker in list(self._workers.values()):
            results.append(await worker.stop())
        return results

    # =========================================================================
    # Reset
    # =========================================================================

    def reset(self, camera_id: Optional[str] = None) -> None:
        """Reset camera processing state back to IDLE.

        If camera_id is omitted, resets all inactive cameras and clears registry.
        """
        if camera_id is not None:
            worker = self._workers.get(camera_id)
            if worker is not None:
                worker.reset()
                del self._workers[camera_id]
        else:
            for w in list(self._workers.values()):
                if w.is_active:
                    raise RuntimeError(
                        f"Cannot reset active processing job for camera '{w.camera_id}'. Stop it first."
                    )
            self._workers.clear()
            self._last_camera_id = None
            self._initial_worker.reset()

    # =========================================================================
    # Await Completion Helper
    # =========================================================================

    async def wait_for_completion(
        self,
        camera_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ProcessingStatusResponse:
        """Wait until background task for the specified or default camera completes."""
        if camera_id is not None:
            worker = self._workers.get(camera_id)
        else:
            worker = self._get_default_or_last_worker()

        if worker is not None:
            return await worker.wait_for_completion(timeout=timeout)
        return self.get_status(camera_id=camera_id)

    async def wait_for_all(
        self, timeout: Optional[float] = None
    ) -> List[ProcessingStatusResponse]:
        """Wait for all registered camera workers to complete."""
        tasks = [
            worker.wait_for_completion(timeout=timeout)
            for worker in list(self._workers.values())
        ]
        if tasks:
            return await asyncio.gather(*tasks)
        return []

    # =========================================================================
    # Backward-Compatibility Attributes for 2F Tests
    # =========================================================================

    @property
    def _task(self) -> Optional[asyncio.Task]:
        worker = self._get_default_or_last_worker()
        return worker._task if worker else None

    @_task.setter
    def _task(self, task: Optional[asyncio.Task]) -> None:
        worker = self._get_default_or_last_worker()
        if worker:
            worker._task = task

    @property
    def _state(self) -> ProcessingState:
        worker = self._get_default_or_last_worker()
        return worker._state if worker else ProcessingState.IDLE

    @property
    def _stop_event(self) -> asyncio.Event:
        worker = self._get_default_or_last_worker()
        return worker._stop_event if worker else self._initial_worker._stop_event


# Type alias for clarity in multi-camera contexts
ProcessingManager = ProcessingService

# Singleton instance and FastAPI dependency provider
processing_service = ProcessingService()


def get_processing_service() -> ProcessingService:
    """FastAPI dependency for accessing the ProcessingService / ProcessingManager singleton."""
    return processing_service
