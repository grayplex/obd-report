from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.trip import Trip
from app.models.telemetry import Telemetry
from app.schemas.trip import TripRead, TripUpdate, TripList

router = APIRouter()


@router.get("/", response_model=list[TripList])
async def list_trips(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trip).order_by(Trip.start_time.desc()).offset(skip).limit(limit)
    )
    trips = result.scalars().all()
    return trips


@router.get("/{trip_id}", response_model=TripRead)
async def get_trip(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.patch("/{trip_id}", response_model=TripRead)
async def update_trip(
    trip_id: UUID,
    trip_update: TripUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    update_data = trip_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(trip, field, value)

    await db.commit()
    await db.refresh(trip)
    return trip


@router.delete("/{trip_id}")
async def delete_trip(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    await db.delete(trip)
    await db.commit()
    return {"status": "deleted", "id": str(trip_id)}
