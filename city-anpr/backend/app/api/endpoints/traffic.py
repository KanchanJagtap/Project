"""
Traffic Snapshot REST API Endpoints.
"""

from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.traffic import TrafficSnapshotModel
from backend.app.schemas.traffic import TrafficSnapshotResponse

router = APIRouter()


@router.get(
    "/latest",
    response_model=Union[TrafficSnapshotResponse, List[TrafficSnapshotResponse]],
    summary="Get latest traffic snapshot(s)",
    description=(
        "Retrieve the latest persisted traffic snapshot. "
        "If camera_id is provided, returns the single latest snapshot for that camera. "
        "If omitted, returns the latest snapshots across all cameras."
    ),
    responses={404: {"description": "No traffic snapshots found"}},
)
async def get_latest_traffic(
    camera_id: Optional[str] = Query(None, description="Optional camera ID filter"),
    db: AsyncSession = Depends(get_db),
) -> Union[TrafficSnapshotResponse, List[TrafficSnapshotResponse]]:
    if camera_id:
        stmt = (
            select(TrafficSnapshotModel)
            .where(TrafficSnapshotModel.camera_id == camera_id)
            .order_by(TrafficSnapshotModel.timestamp.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        snapshot = result.scalars().first()
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No traffic snapshot found for camera '{camera_id}'",
            )
        return snapshot

    stmt = (
        select(TrafficSnapshotModel)
        .order_by(TrafficSnapshotModel.timestamp.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    snapshots = result.scalars().all()
    return list(snapshots)
