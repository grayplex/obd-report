from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.trip import Trip
from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryRead, TelemetryBulkRead

router = APIRouter()


@router.get("/{trip_id}", response_model=TelemetryBulkRead)
async def get_telemetry(
    trip_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(10000, ge=1, le=100000),
    downsample: int = Query(1, ge=1, description="Return every Nth point"),
    db: AsyncSession = Depends(get_db),
):
    # Verify trip exists
    trip_result = await db.execute(select(Trip).where(Trip.id == trip_id))
    if not trip_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Trip not found")

    # Get telemetry data
    query = (
        select(Telemetry)
        .where(Telemetry.trip_id == trip_id)
        .order_by(Telemetry.time)
    )

    result = await db.execute(query)
    all_rows = result.scalars().all()

    # Apply downsampling
    if downsample > 1:
        rows = all_rows[skip::downsample][:limit]
    else:
        rows = all_rows[skip:skip + limit]

    return TelemetryBulkRead(
        trip_id=trip_id,
        data=[TelemetryRead.model_validate(row) for row in rows],
        count=len(rows),
    )


@router.get("/{trip_id}/gps")
async def get_gps_points(
    trip_id: UUID,
    downsample: int = Query(1, ge=1, description="Return every Nth point"),
    db: AsyncSession = Depends(get_db),
):
    # Verify trip exists
    trip_result = await db.execute(select(Trip).where(Trip.id == trip_id))
    if not trip_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Trip not found")

    # Get GPS data
    result = await db.execute(
        select(Telemetry.latitude, Telemetry.longitude, Telemetry.elapsed_seconds, Telemetry.speed_mph)
        .where(Telemetry.trip_id == trip_id)
        .where(Telemetry.latitude.isnot(None))
        .where(Telemetry.longitude.isnot(None))
        .order_by(Telemetry.time)
    )
    all_rows = result.all()

    # Apply downsampling
    if downsample > 1:
        rows = all_rows[::downsample]
    else:
        rows = all_rows

    return {
        "trip_id": str(trip_id),
        "points": [
            {
                "lat": row.latitude,
                "lng": row.longitude,
                "elapsed_seconds": row.elapsed_seconds,
                "speed_mph": row.speed_mph,
            }
            for row in rows
        ],
        "count": len(rows),
    }
