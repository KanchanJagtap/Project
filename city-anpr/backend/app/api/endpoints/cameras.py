"""
Camera REST API Endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.session import get_db
from backend.app.models.camera import CameraModel
from backend.app.schemas.camera import CameraResponse

router = APIRouter()


@router.get(
    "",
    response_model=List[CameraResponse],
    summary="List all cameras",
    description="Retrieve all registered CCTV cameras and their calibration configurations.",
)
async def list_cameras(
    db: AsyncSession = Depends(get_db),
) -> List[CameraResponse]:
    stmt = (
        select(CameraModel)
        .options(selectinload(CameraModel.approach))
        .order_by(CameraModel.camera_id)
    )
    result = await db.execute(stmt)
    cameras = result.scalars().all()
    return list(cameras)


@router.get(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Get camera by ID",
    description="Retrieve a single camera by its unique camera_id.",
    responses={404: {"description": "Camera not found"}},
)
async def get_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
) -> CameraResponse:
    stmt = (
        select(CameraModel)
        .options(selectinload(CameraModel.approach))
        .where(CameraModel.camera_id == camera_id)
    )
    result = await db.execute(stmt)
    camera = result.scalars().first()
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found",
        )
    return camera
