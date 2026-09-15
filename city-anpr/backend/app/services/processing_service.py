"""
Video Processing Orchestration Service (Milestone 2F).

Manages continuous/single-camera video processing runs in the background
without blocking FastAPI request handlers, bridging:
SingleCameraPipeline -> FrameResult -> IngestionService -> PostgreSQL
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ai.pipeline.single_camera_pipeline import FrameResult, SingleCameraPipeline
from backend.app.db.session import async_session_factory
from backend.app.schemas.processing import ProcessingState, ProcessingStatusResponse
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


class ProcessingService:
    """
    Dedicated video processing orchestration service.

    Represents and manages a background single-camera video processing run,
    coordinating frame extraction, AI pipeline execution, and atomic PostgreSQL
    ingestion per frame.
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
        self._tracker_model_path = Path(tracker_model_path) if tracker_model_path else DEFAULT_TRACKER_PATH
        self._plate_model_path = Path(plate_model_path) if plate_model_path else DEFAULT_PLATE_PATH

        # Lifecycle state
        self._state: ProcessingState = ProcessingState.IDLE
        self._source: Optional[str] = None
        self._camera_id: Optional[str] = None
        self._junction_id: Optional[str] = None
        self._max_frames: Optional[int] = None
        self._processed_frames: int = 0
        self._started_at: Optional[datetime] = None
        self._finished_at: Optional[datetime] = None
        self._error: Optional[str] = None

        # Concurrency and cooperative task controls
        self._task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._lock: asyncio.Lock = asyncio.Lock()

    # =========================================================================
    # Status and State Inspection
    # =========================================================================

    def get_status(self) -> ProcessingStatusResponse:
        """Return the current processing service state snapshot."""
        return ProcessingStatusResponse(
            state=self._state,
            source=self._source,
            camera_id=self._camera_id,
            junction_id=self._junction_id,
            processed_frames=self._processed_frames,
            max_frames=self._max_frames,
            started_at=self._started_at,
            finished_at=self._finished_at,
            error=self._error,
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
        """
        Initiate a background video processing run.

        Returns immediately with status STARTING without waiting for the video
        to finish. If a processing run is already active, raises RuntimeError.
        """
        async with self._lock:
            if self._state in (
                ProcessingState.STARTING,
                ProcessingState.RUNNING,
                ProcessingState.STOPPING,
            ):
                raise RuntimeError("A processing job is already active.")

            self._state = ProcessingState.STARTING
            self._source = source
            self._camera_id = camera_id
            self._junction_id = junction_id or f"junction-{camera_id}"
            self._max_frames = max_frames
            self._processed_frames = 0
            self._started_at = datetime.now(timezone.utc)
            self._finished_at = None
            self._error = None
            self._stop_event.clear()

            self._task = asyncio.create_task(
                self._run_worker(
                    source=source,
                    camera_id=camera_id,
                    max_frames=max_frames,
                    junction_id=self._junction_id,
                    anpr_every_n_frames=anpr_every_n_frames,
                )
            )

            return self.get_status()

    # =========================================================================
    # Cooperative Stop Execution
    # =========================================================================

    async def stop(self) -> ProcessingStatusResponse:
        """
        Request a clean, cooperative stop of the active processing run.

        Lifecycle behavior:
        stop requested -> current synchronous inference may finish ->
        current frame ingestion may finish -> worker exits -> STOPPED.
        """
        async with self._lock:
            if self._state in (ProcessingState.STARTING, ProcessingState.RUNNING):
                self._state = ProcessingState.STOPPING
                self._stop_event.set()

        return self.get_status()

    # =========================================================================
    # Reset
    # =========================================================================

    def reset(self) -> None:
        """Reset service state back to IDLE if not currently active."""
        if self._state in (
            ProcessingState.STARTING,
            ProcessingState.RUNNING,
            ProcessingState.STOPPING,
        ):
            raise RuntimeError("Cannot reset an active processing job. Stop it first.")

        self._state = ProcessingState.IDLE
        self._source = None
        self._camera_id = None
        self._junction_id = None
        self._max_frames = None
        self._processed_frames = 0
        self._started_at = None
        self._finished_at = None
        self._error = None
        self._task = None
        self._stop_event.clear()

    # =========================================================================
    # Await Completion Helper (for testing / controlled scripts)
    # =========================================================================

    async def wait_for_completion(
        self,
        timeout: Optional[float] = None,
    ) -> ProcessingStatusResponse:
        """Wait until background task completes or timeout expires."""
        if self._task is not None:
            try:
                if timeout is not None:
                    await asyncio.wait_for(asyncio.shield(self._task), timeout=timeout)
                else:
                    await self._task
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        return self.get_status()

    # =========================================================================
    # Background Worker Loop
    # =========================================================================

    async def _run_worker(
        self,
        source: str,
        camera_id: str,
        max_frames: Optional[int],
        junction_id: str,
        anpr_every_n_frames: int,
    ) -> None:
        """Internal background worker executing video inference and ingestion.

        Resource cleanup guarantees:
        - The generator returned by pipeline.process_video() is explicitly
          closed via generator.close() in a finally block on all exit paths:
          normal completion, cooperative stop, pipeline failure, and task
          cancellation.
        - The task reference is only cleared when the finishing worker is
          still the current task, preventing a race where a newly-started
          task's reference could be clobbered by this worker's finally block.

        Cooperative stop semantics:
        - A synchronous YOLO inference already in progress will finish
          before the stop flag is observed. The stop_event is checked
          between frames, not during inference.
        """
        # Capture our own task reference so the finally block can compare
        # it against self._task to avoid clobbering a newly-started task.
        current_task = self._task

        # Track the generator so it can be deterministically closed on
        # all exit paths (completion, stop, failure, cancellation).
        generator = None

        try:
            # Resolve source path
            src_path = Path(source)
            if not src_path.is_absolute():
                src_path = (PROJECT_ROOT / src_path).resolve()

            if not src_path.exists():
                raise FileNotFoundError(f"Video source not found: {source}")

            async with self._lock:
                if self._stop_event.is_set():
                    self._state = ProcessingState.STOPPED
                    self._finished_at = datetime.now(timezone.utc)
                    return
                self._state = ProcessingState.RUNNING

            # Instantiate pipeline
            pipeline = self._pipeline_factory(
                camera_id=camera_id,
                tracker_model_path=str(self._tracker_model_path),
                plate_model_path=str(self._plate_model_path),
                approach_id=f"approach-{camera_id}",
                anpr_every_n_frames=anpr_every_n_frames,
            )

            # Process video stream
            generator = pipeline.process_video(
                str(src_path),
                max_frames=max_frames,
                print_every=0,
            )

            for frame_result in generator:
                # Cooperative check between frames. A synchronous YOLO
                # inference that was already in progress will have
                # finished by the time we reach this check.
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

                # Yield to the event loop so concurrent tasks/requests can proceed
                await asyncio.sleep(0)

            # Natural completion or cooperative stop
            async with self._lock:
                if self._stop_event.is_set():
                    self._state = ProcessingState.STOPPED
                else:
                    self._state = ProcessingState.COMPLETED
                self._finished_at = datetime.now(timezone.utc)

        except asyncio.CancelledError:
            logger.info("Processing worker task was cancelled.")
            async with self._lock:
                self._state = ProcessingState.STOPPED
                self._finished_at = datetime.now(timezone.utc)
            raise

        except Exception as exc:
            logger.error("Processing worker failed: %s", exc, exc_info=True)
            async with self._lock:
                self._state = ProcessingState.FAILED
                self._error = str(exc)
                self._finished_at = datetime.now(timezone.utc)

        finally:
            # Deterministically close the generator to release any
            # resources held by the pipeline (e.g. OpenCV VideoCapture).
            if generator is not None and hasattr(generator, "close"):
                try:
                    generator.close()
                except Exception:
                    logger.debug("Exception closing pipeline generator", exc_info=True)

            # Only clear the task reference if we are still the current
            # task. If start() was called again between our last frame
            # and this finally block, self._task now points to the new
            # worker and we must not clobber it.
            if self._task is current_task:
                self._task = None


# Singleton instance and FastAPI dependency provider
processing_service = ProcessingService()


def get_processing_service() -> ProcessingService:
    """FastAPI dependency for accessing the ProcessingService singleton."""
    return processing_service
