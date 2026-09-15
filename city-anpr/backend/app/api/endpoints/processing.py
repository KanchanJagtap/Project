"""
Processing Control & Status API Endpoints (Milestone 2F).

Provides REST endpoints to trigger, halt, and monitor the video processing
orchestration service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.schemas.processing import (
    ProcessingStartRequest,
    ProcessingStatusResponse,
)
from backend.app.services.processing_service import (
    ProcessingService,
    get_processing_service,
)

router = APIRouter()


@router.post(
    "/start",
    response_model=ProcessingStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Video Processing",
    description="Initiate background CCTV video processing. Returns immediately without waiting for video completion.",
)
async def start_processing(
    request: ProcessingStartRequest,
    service: ProcessingService = Depends(get_processing_service),
) -> ProcessingStatusResponse:
    """Start background video processing job."""
    try:
        return await service.start(
            source=request.source,
            camera_id=request.camera_id,
            max_frames=request.max_frames,
            junction_id=request.junction_id,
            anpr_every_n_frames=request.anpr_every_n_frames,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/stop",
    response_model=ProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Stop Video Processing",
    description="Cooperatively halt active video processing after the current frame finishes.",
)
async def stop_processing(
    service: ProcessingService = Depends(get_processing_service),
) -> ProcessingStatusResponse:
    """Request cooperative stop of the active video processing job."""
    return await service.stop()


@router.get(
    "/status",
    response_model=ProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Processing Status",
    description="Inspect the current lifecycle state, processed-frame count, and timestamps.",
)
async def get_processing_status(
    service: ProcessingService = Depends(get_processing_service),
) -> ProcessingStatusResponse:
    """Inspect active or recent processing job status."""
    return service.get_status()
