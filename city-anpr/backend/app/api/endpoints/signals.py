"""
Signal Decision REST API Endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.signal import SignalDecisionModel
from backend.app.schemas.signal import SignalDecisionResponse

router = APIRouter()


@router.get(
    "/latest",
    response_model=List[SignalDecisionResponse],
    summary="Get latest signal timing decisions",
    description=(
        "Retrieve the most recent signal optimization decisions. "
        "If junction_id is provided, returns decisions for that junction. "
        "If omitted, returns recent decisions across all junctions."
    ),
    responses={404: {"description": "No signal decisions found"}},
)
async def get_latest_signals(
    junction_id: Optional[str] = Query(None, description="Optional junction ID filter"),
    db: AsyncSession = Depends(get_db),
) -> List[SignalDecisionResponse]:
    if junction_id:
        stmt = (
            select(SignalDecisionModel)
            .where(SignalDecisionModel.junction_id == junction_id)
            .order_by(SignalDecisionModel.timestamp.desc())
            .limit(20)
        )
        result = await db.execute(stmt)
        decisions = result.scalars().all()
        if not decisions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No signal decisions found for junction '{junction_id}'",
            )
        return list(decisions)

    stmt = (
        select(SignalDecisionModel)
        .order_by(SignalDecisionModel.timestamp.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    decisions = result.scalars().all()
    return list(decisions)
