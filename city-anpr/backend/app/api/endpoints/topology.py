"""
Topology REST API Endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.topology import TopologyEdge
from backend.app.schemas.topology import TopologyEdgeResponse

router = APIRouter()

@router.get("/edges", response_model=List[TopologyEdgeResponse])
async def get_topology_edges(db: AsyncSession = Depends(get_db)):
    """Retrieve all topology edges."""
    stmt = select(TopologyEdge).order_by(TopologyEdge.source_junction_id, TopologyEdge.target_junction_id)
    result = await db.execute(stmt)
    return result.scalars().all()
