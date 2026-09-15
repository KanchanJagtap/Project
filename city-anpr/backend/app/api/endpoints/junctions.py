"""
Junction REST API Endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.session import get_db
from backend.app.models.junction import Junction
from backend.app.schemas.junction import JunctionResponse

router = APIRouter()


@router.get(
    "",
    response_model=List[JunctionResponse],
    summary="List all junctions",
    description="Retrieve all registered junctions with their approaches.",
)
async def list_junctions(
    db: AsyncSession = Depends(get_db),
) -> List[JunctionResponse]:
    stmt = (
        select(Junction)
        .options(selectinload(Junction.approaches))
        .order_by(Junction.junction_id)
    )
    result = await db.execute(stmt)
    junctions = result.scalars().all()
    return list(junctions)


@router.get(
    "/{junction_id}",
    response_model=JunctionResponse,
    summary="Get junction by ID",
    description="Retrieve a single junction by its unique junction_id.",
    responses={404: {"description": "Junction not found"}},
)
async def get_junction(
    junction_id: str,
    db: AsyncSession = Depends(get_db),
) -> JunctionResponse:
    stmt = (
        select(Junction)
        .options(selectinload(Junction.approaches))
        .where(Junction.junction_id == junction_id)
    )
    result = await db.execute(stmt)
    junction = result.scalars().first()
    if junction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Junction '{junction_id}' not found",
        )
    return junction
