"""
Processing Control & Status API Endpoints (Milestones 2F & 2G).

Provides REST endpoints to trigger, halt, and monitor camera video processing
runs, supporting continuous feeds, multi-camera status inspection, and
backward-compatible single-camera operation.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File

from backend.app.schemas.processing import (
    CamerasListResponse,
    ProcessingOverviewResponse,
    ProcessingStartRequest,
    ProcessingStatusResponse,
    ProcessingStopRequest,
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
    """Start background video processing job for a camera."""
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
    payload: Optional[ProcessingStopRequest] = None,
    camera_id: Optional[str] = Query(default=None, description="Optional camera ID to stop"),
    service: ProcessingService = Depends(get_processing_service),
) -> ProcessingStatusResponse:
    """Request cooperative stop of the active video processing job."""
    target_camera_id = (
        payload.camera_id if payload and payload.camera_id else None
    ) or camera_id

    try:
        return await service.stop(camera_id=target_camera_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/status",
    response_model=ProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Processing Status",
    description="Inspect current lifecycle state, processed-frame count, timestamps, and latest frame snapshot.",
)
async def get_processing_status(
    camera_id: Optional[str] = Query(default=None, description="Optional camera ID to query"),
    service: ProcessingService = Depends(get_processing_service),
) -> ProcessingStatusResponse:
    """Inspect active or recent processing job status."""
    return service.get_status(camera_id=camera_id)


@router.get(
    "/cameras",
    response_model=CamerasListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Camera Processing Workers",
    description="Inspect status of all registered camera processing workers and active worker count.",
)
async def list_camera_workers(
    service: ProcessingService = Depends(get_processing_service),
) -> CamerasListResponse:
    """List all registered camera processing workers."""
    return service.get_all_cameras()


@router.get(
    "/cameras/{camera_id}/status",
    response_model=ProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Camera Processing Status",
    description="Inspect status of a specific camera processing worker.",
)
async def get_camera_status(
    camera_id: str,
    service: ProcessingService = Depends(get_processing_service),
) -> ProcessingStatusResponse:
    """Inspect status of a specific camera processing worker."""
    return service.get_status(camera_id=camera_id)


@router.get(
    "/overview",
    response_model=ProcessingOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Processing Overview",
    description="Inspect system-wide aggregated telemetry and active metrics across all camera feeds.",
)
async def get_processing_overview(
    service: ProcessingService = Depends(get_processing_service),
) -> ProcessingOverviewResponse:
    """Inspect system-wide aggregated multi-camera runtime metrics."""
    return service.get_overview()


import cv2
import numpy as np

@router.post(
    "/anpr_scan",
    status_code=status.HTTP_200_OK,
    summary="Real ANPR Image Scan",
    description="Process an uploaded image using the actual ANPR pipeline.",
)
async def process_anpr_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        if not contents:
            raise ValueError("Uploaded file is empty")

        image_array = np.frombuffer(contents, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Uploaded file is not a valid image")

        height, width = image.shape[:2]

        from ai.anpr.anpr_pipeline import ANPRPipeline
        pipeline = ANPRPipeline()
        results = pipeline.detect_and_read(image)

        if not results:
            return {
                "status": "success",
                "filename": file.filename,
                "image_width": width,
                "image_height": height,
                "detection_count": 0,
                "detections": [],
                "mode": "real"
            }

        result = results[0]
        x1, y1, x2, y2 = result["bbox"]
        detection = {
            "plate_number": result["text"],
            "detection_confidence": result["detection_confidence"],
            "ocr_confidence": result["ocr_confidence"],
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "vehicle": None,
            "vehicle_found": False,
            "mode": "real",
        }

        return {
            "status": "success",
            "filename": file.filename,
            "image_width": width,
            "image_height": height,
            "detection_count": 1,
            "detections": [detection],
            "mode": "real",
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
