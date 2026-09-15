"""
Vehicle and Vehicle History REST API Endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.session import get_db
from backend.app.models.vehicle import Vehicle
from backend.app.schemas.vehicle import (
    VehicleHistoryResponse,
    VehicleResponse,
)

router = APIRouter()


def normalize_plate(plate: str) -> str:
    """Normalize plate text according to canonical ingestion rules."""
    return plate.strip().upper() if plate else ""


@router.get(
    "",
    response_model=List[VehicleResponse],
    summary="List canonical vehicles",
    description="Retrieve canonical vehicles with optional filters for plate, vehicle type, and pagination.",
)
async def list_vehicles(
    plate: Optional[str] = Query(None, description="Exact or partial canonical plate text"),
    vehicle_type: Optional[str] = Query(None, description="Vehicle classification filter (car, motorcycle, truck, bus)"),
    limit: int = Query(default=50, ge=1, le=100, description="Max records to return (1-100)"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
) -> List[VehicleResponse]:
    stmt = select(Vehicle)

    if plate:
        clean_plate = normalize_plate(plate)
        # Match canonical plate text exactly
        stmt = stmt.where(Vehicle.canonical_plate_text == clean_plate)

    if vehicle_type:
        clean_type = vehicle_type.strip().lower()
        stmt = stmt.where(Vehicle.canonical_vehicle_type == clean_type)

    stmt = stmt.order_by(Vehicle.last_detected_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    vehicles = result.scalars().all()
    return list(vehicles)


@router.get(
    "/{plate}",
    response_model=VehicleResponse,
    summary="Get vehicle by plate",
    description="Retrieve a single canonical vehicle by its license plate text.",
    responses={404: {"description": "Vehicle not found"}},
)
async def get_vehicle_by_plate(
    plate: str,
    db: AsyncSession = Depends(get_db),
) -> VehicleResponse:
    clean_plate = normalize_plate(plate)
    if not clean_plate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plate text cannot be empty",
        )

    stmt = select(Vehicle).where(Vehicle.canonical_plate_text == clean_plate)
    result = await db.execute(stmt)
    vehicle = result.scalars().first()
    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle with plate '{plate}' not found",
        )
    return vehicle


@router.get(
    "/{plate}/history",
    response_model=VehicleHistoryResponse,
    summary="Get vehicle history by plate",
    description="Retrieve full tracking history and plate observations across all cameras for a vehicle.",
    responses={404: {"description": "Vehicle not found"}},
)
async def get_vehicle_history(
    plate: str,
    db: AsyncSession = Depends(get_db),
) -> VehicleHistoryResponse:
    clean_plate = normalize_plate(plate)
    if not clean_plate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plate text cannot be empty",
        )

    stmt = (
        select(Vehicle)
        .options(
            selectinload(Vehicle.tracks),
            selectinload(Vehicle.plate_observations),
        )
        .where(Vehicle.canonical_plate_text == clean_plate)
    )
    result = await db.execute(stmt)
    vehicle = result.scalars().first()
    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle with plate '{plate}' not found",
        )

    # Sort tracks and observations chronologically (most recent first)
    sorted_tracks = sorted(vehicle.tracks, key=lambda t: t.first_seen_at, reverse=True)
    sorted_observations = sorted(
        vehicle.plate_observations, key=lambda o: o.timestamp, reverse=True
    )

    return VehicleHistoryResponse(
        vehicle=vehicle,
        tracks=sorted_tracks,
        plate_observations=sorted_observations,
    )
