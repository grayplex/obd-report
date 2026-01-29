"""Analytics API endpoints."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db
from app.models.trip import Trip
from app.models.driving_event import DrivingEvent
from app.services.analytics import TripAnalytics, DrivingBehaviorAnalytics
from app.services.advanced_analytics import AdvancedAnalytics

router = APIRouter()


@router.post("/trips/{trip_id}/analyze")
async def analyze_trip(trip_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Run analytics on a trip.
    Calculates distance, idle time, fuel economy, and detects driving events.
    """
    # Check if trip exists
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Run trip analytics
    trip_analytics = TripAnalytics(db)
    updated_trip = await trip_analytics.calculate_all(trip_id)

    # Run driving behavior analytics
    behavior_analytics = DrivingBehaviorAnalytics(db)
    events = await behavior_analytics.detect_events(trip_id)

    return {
        "message": "Analytics completed",
        "trip": {
            "id": str(updated_trip.id),
            "distance_miles": updated_trip.distance_miles,
            "idle_time_seconds": updated_trip.idle_time_seconds,
            "moving_time_seconds": updated_trip.moving_time_seconds,
            "stop_count": updated_trip.stop_count,
            "avg_fuel_economy_mpg": updated_trip.avg_fuel_economy_mpg,
            "total_fuel_used_gal": updated_trip.total_fuel_used_gal,
        },
        "events_detected": len(events),
    }


@router.get("/trips/{trip_id}/events")
async def get_trip_events(trip_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all driving events for a trip."""
    # Check if trip exists
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Get events
    events_result = await db.execute(
        select(DrivingEvent)
        .where(DrivingEvent.trip_id == trip_id)
        .order_by(DrivingEvent.event_time)
    )
    events = events_result.scalars().all()

    return {
        "trip_id": str(trip_id),
        "total_events": len(events),
        "events": [
            {
                "id": str(event.id),
                "time": event.event_time.isoformat(),
                "type": event.event_type,
                "severity": event.severity,
                "speed_mph": event.speed_mph,
                "latitude": event.latitude,
                "longitude": event.longitude,
                "metadata": event.metadata_,
            }
            for event in events
        ],
    }


@router.get("/trips/{trip_id}/summary")
async def get_trip_summary(trip_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get comprehensive trip analytics summary."""
    # Get trip
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Get event counts by type
    events_result = await db.execute(
        select(DrivingEvent).where(DrivingEvent.trip_id == trip_id)
    )
    events = events_result.scalars().all()

    event_counts = {}
    for event in events:
        event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

    # Calculate some derived metrics
    efficiency_score = None
    if trip.avg_fuel_economy_mpg and trip.avg_speed_mph:
        # Simple efficiency score (higher is better)
        efficiency_score = (trip.avg_fuel_economy_mpg / 30.0) * 100

    driving_score = None
    if trip.duration_seconds > 0:
        # Penalize for hard braking and hard acceleration
        hard_events = event_counts.get("hard_brake", 0) + event_counts.get("hard_accel", 0)
        events_per_minute = (hard_events / trip.duration_seconds) * 60
        driving_score = max(0, 100 - (events_per_minute * 10))

    return {
        "trip": {
            "id": str(trip.id),
            "name": trip.name,
            "start_time": trip.start_time.isoformat(),
            "end_time": trip.end_time.isoformat(),
            "duration_seconds": trip.duration_seconds,
        },
        "distance": {
            "total_miles": trip.distance_miles,
            "avg_speed_mph": trip.avg_speed_mph,
            "max_speed_mph": trip.max_speed_mph,
        },
        "time_breakdown": {
            "total_seconds": trip.duration_seconds,
            "moving_seconds": trip.moving_time_seconds,
            "idle_seconds": trip.idle_time_seconds,
            "idle_percentage": (
                (trip.idle_time_seconds / trip.duration_seconds * 100)
                if trip.duration_seconds and trip.idle_time_seconds
                else None
            ),
        },
        "fuel_economy": {
            "avg_mpg": trip.avg_fuel_economy_mpg,
            "total_fuel_gal": trip.total_fuel_used_gal,
            "efficiency_score": efficiency_score,
        },
        "driving_behavior": {
            "stop_count": trip.stop_count,
            "event_counts": event_counts,
            "driving_score": driving_score,
        },
    }


@router.get("/trips/{trip_id}/advanced")
async def get_advanced_analytics(trip_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get advanced analytics: speed ranges, throttle patterns, cruise stats, fuel insights."""
    # Check if trip exists
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    analytics = AdvancedAnalytics(db)

    # Run all advanced analytics
    speed_ranges = await analytics.analyze_speed_ranges(trip_id)
    throttle_patterns = await analytics.analyze_throttle_patterns(trip_id)
    cruise_stats = await analytics.analyze_cruise_control(trip_id)
    fuel_insights = await analytics.analyze_fuel_efficiency_insights(trip_id)
    correlation = await analytics.get_speed_throttle_correlation(trip_id)

    return {
        "trip_id": str(trip_id),
        "speed_ranges": speed_ranges,
        "throttle_patterns": throttle_patterns,
        "cruise_control": cruise_stats,
        "fuel_insights": fuel_insights,
        "correlation": correlation,
    }
