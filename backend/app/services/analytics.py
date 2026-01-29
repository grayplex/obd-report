"""Analytics service for trip and driving behavior analysis."""
import math
import uuid
from datetime import datetime
from typing import List, Tuple, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trip import Trip
from app.models.telemetry import Telemetry
from app.models.driving_event import DrivingEvent
from app.models.trip_segment import TripSegment


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on earth in miles.
    Uses the Haversine formula.
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    # Radius of earth in miles
    r = 3956.0

    return c * r


class TripAnalytics:
    """Calculate trip-level analytics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_all(self, trip_id: uuid.UUID) -> Trip:
        """Calculate all analytics for a trip."""
        # Get the trip
        result = await self.db.execute(select(Trip).where(Trip.id == trip_id))
        trip = result.scalar_one()

        # Get telemetry data
        telemetry_result = await self.db.execute(
            select(Telemetry)
            .where(Telemetry.trip_id == trip_id)
            .order_by(Telemetry.time)
        )
        telemetry_points = telemetry_result.scalars().all()

        if not telemetry_points:
            return trip

        # Calculate distance from GPS
        distance = await self._calculate_distance(telemetry_points)

        # Calculate idle time and moving time
        idle_time, moving_time, stop_count = await self._calculate_idle_and_stops(telemetry_points)

        # Calculate fuel economy
        avg_mpg, total_fuel = await self._calculate_fuel_economy(telemetry_points)

        # Update trip record
        trip.distance_miles = distance
        trip.idle_time_seconds = idle_time
        trip.moving_time_seconds = moving_time
        trip.stop_count = stop_count
        trip.avg_fuel_economy_mpg = avg_mpg
        trip.total_fuel_used_gal = total_fuel

        await self.db.commit()
        await self.db.refresh(trip)

        return trip

    async def _calculate_distance(self, telemetry_points: List[Telemetry]) -> float:
        """Calculate total distance traveled using speed-based integration (more accurate than GPS)."""
        total_distance = 0.0
        prev_time = None

        for point in telemetry_points:
            if prev_time and point.speed_mph is not None:
                time_diff_hours = (point.time - prev_time).total_seconds() / 3600.0
                # Distance = speed * time
                segment_distance = point.speed_mph * time_diff_hours
                total_distance += segment_distance

            prev_time = point.time

        return total_distance

    async def _calculate_idle_and_stops(
        self, telemetry_points: List[Telemetry]
    ) -> Tuple[float, float, int]:
        """
        Calculate idle time (engine running, not moving), moving time, and stop count.
        Returns: (idle_time_seconds, moving_time_seconds, stop_count)
        """
        IDLE_SPEED_THRESHOLD = 2.0  # mph - below this is considered idle
        STOP_DURATION_THRESHOLD = 3.0  # seconds - how long stopped to count as a stop

        idle_time = 0.0
        moving_time = 0.0
        stop_count = 0

        current_stop_duration = 0.0
        prev_time = None
        in_stop = False

        for point in telemetry_points:
            if prev_time:
                time_diff = (point.time - prev_time).total_seconds()

                # Use GPS speed if available, otherwise OBD speed
                speed = point.gps_speed_mph if point.gps_speed_mph else point.speed_mph

                if speed is not None and speed < IDLE_SPEED_THRESHOLD:
                    # Check if engine is running (RPM > 0)
                    if point.engine_rpm and point.engine_rpm > 0:
                        idle_time += time_diff
                        current_stop_duration += time_diff

                        # Count as a stop if we've been idle long enough
                        if not in_stop and current_stop_duration >= STOP_DURATION_THRESHOLD:
                            stop_count += 1
                            in_stop = True
                    else:
                        # Engine off, reset stop tracking
                        current_stop_duration = 0.0
                        in_stop = False
                else:
                    # Moving
                    moving_time += time_diff
                    current_stop_duration = 0.0
                    in_stop = False

            prev_time = point.time

        return idle_time, moving_time, stop_count

    async def _calculate_fuel_economy(
        self, telemetry_points: List[Telemetry]
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate average fuel economy and total fuel used.
        Uses OBD Fusion calculated values if available.
        Returns: (avg_mpg, total_fuel_gallons)
        """
        mpg_values = []
        total_fuel = 0.0
        prev_time = None

        for point in telemetry_points:
            # Use instant MPG for averaging
            if point.instant_mpg and point.instant_mpg > 0:
                mpg_values.append(point.instant_mpg)

            # Integrate fuel rate over time
            if point.fuel_rate_gal_hr and prev_time:
                time_diff_hours = (point.time - prev_time).total_seconds() / 3600.0
                total_fuel += point.fuel_rate_gal_hr * time_diff_hours

            prev_time = point.time

        avg_mpg = sum(mpg_values) / len(mpg_values) if mpg_values else None

        return avg_mpg, total_fuel if total_fuel > 0 else None


class DrivingBehaviorAnalytics:
    """Detect and analyze driving behavior events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_events(self, trip_id: uuid.UUID) -> List[DrivingEvent]:
        """Detect all driving events for a trip."""
        # Get telemetry data
        telemetry_result = await self.db.execute(
            select(Telemetry)
            .where(Telemetry.trip_id == trip_id)
            .order_by(Telemetry.time)
        )
        telemetry_points = telemetry_result.scalars().all()

        events = []

        # Detect hard acceleration/braking
        events.extend(await self._detect_acceleration_events(trip_id, telemetry_points))

        # Detect idle periods
        events.extend(await self._detect_idle_events(trip_id, telemetry_points))

        # Detect cruise control usage
        events.extend(await self._detect_cruise_events(trip_id, telemetry_points))

        # Store events
        self.db.add_all(events)
        await self.db.commit()

        return events

    async def _detect_acceleration_events(
        self, trip_id: uuid.UUID, telemetry_points: List[Telemetry]
    ) -> List[DrivingEvent]:
        """Detect hard acceleration and hard braking events."""
        HARD_ACCEL_THRESHOLD = 0.35  # g (about 11 ft/s²)
        HARD_BRAKE_THRESHOLD = -0.45  # g (about -14.5 ft/s²)

        events = []

        for point in telemetry_points:
            if point.acceleration_g:
                severity = None
                event_type = None

                # Hard acceleration
                if point.acceleration_g > HARD_ACCEL_THRESHOLD:
                    event_type = "hard_accel"
                    if point.acceleration_g > 0.5:
                        severity = "high"
                    elif point.acceleration_g > 0.4:
                        severity = "medium"
                    else:
                        severity = "low"

                # Hard braking (negative acceleration)
                elif point.acceleration_g < HARD_BRAKE_THRESHOLD:
                    event_type = "hard_brake"
                    if point.acceleration_g < -0.6:
                        severity = "high"
                    elif point.acceleration_g < -0.5:
                        severity = "medium"
                    else:
                        severity = "low"

                if event_type:
                    events.append(
                        DrivingEvent(
                            id=uuid.uuid4(),
                            trip_id=trip_id,
                            event_time=point.time,
                            event_type=event_type,
                            severity=severity,
                            latitude=point.latitude,
                            longitude=point.longitude,
                            speed_mph=point.speed_mph,
                            metadata_={
                                "acceleration_g": point.acceleration_g,
                                "throttle_position": point.throttle_position_pct,
                            },
                        )
                    )

        return events

    async def _detect_idle_events(
        self, trip_id: uuid.UUID, telemetry_points: List[Telemetry]
    ) -> List[DrivingEvent]:
        """Detect idle start/stop events."""
        IDLE_SPEED_THRESHOLD = 2.0
        MIN_IDLE_DURATION = 5.0  # seconds

        events = []
        idle_start_point = None
        idle_duration = 0.0
        prev_time = None

        for point in telemetry_points:
            speed = point.gps_speed_mph if point.gps_speed_mph else point.speed_mph
            is_idle = (
                speed is not None
                and speed < IDLE_SPEED_THRESHOLD
                and point.engine_rpm
                and point.engine_rpm > 0
            )

            if is_idle and not idle_start_point:
                # Start of idle period
                idle_start_point = point
                idle_duration = 0.0
            elif is_idle and idle_start_point and prev_time:
                # Continue idle
                idle_duration += (point.time - prev_time).total_seconds()
            elif not is_idle and idle_start_point:
                # End of idle period
                if idle_duration >= MIN_IDLE_DURATION:
                    # Create idle_start event
                    events.append(
                        DrivingEvent(
                            id=uuid.uuid4(),
                            trip_id=trip_id,
                            event_time=idle_start_point.time,
                            event_type="idle_start",
                            latitude=idle_start_point.latitude,
                            longitude=idle_start_point.longitude,
                            speed_mph=idle_start_point.speed_mph,
                            metadata_={"duration_seconds": idle_duration},
                        )
                    )
                    # Create idle_end event
                    events.append(
                        DrivingEvent(
                            id=uuid.uuid4(),
                            trip_id=trip_id,
                            event_time=point.time,
                            event_type="idle_end",
                            latitude=point.latitude,
                            longitude=point.longitude,
                            speed_mph=point.speed_mph,
                            metadata_={"duration_seconds": idle_duration},
                        )
                    )

                idle_start_point = None
                idle_duration = 0.0

            prev_time = point.time

        return events

    async def _detect_cruise_events(
        self, trip_id: uuid.UUID, telemetry_points: List[Telemetry]
    ) -> List[DrivingEvent]:
        """Detect cruise control engagement/disengagement events."""
        events = []
        cruise_active = False
        cruise_start_point = None

        for point in telemetry_points:
            # Check cruise control status from sensors JSONB
            cruise_status = None
            if point.sensors:
                cruise_status = point.sensors.get("status_of_the_cruise_control_no_or_yes")

            # Cruise engaged (status changes to Yes or speed is set)
            is_cruise_active = (
                cruise_status == "Yes"
                or (point.sensors and point.sensors.get("cruise_control_vehicle_speed"))
            )

            if is_cruise_active and not cruise_active:
                # Cruise engaged
                cruise_start_point = point
                cruise_active = True
                events.append(
                    DrivingEvent(
                        id=uuid.uuid4(),
                        trip_id=trip_id,
                        event_time=point.time,
                        event_type="cruise_engage",
                        latitude=point.latitude,
                        longitude=point.longitude,
                        speed_mph=point.speed_mph,
                        metadata_={
                            "set_speed": point.sensors.get("cruise_control_vehicle_speed")
                            if point.sensors
                            else None,
                        },
                    )
                )
            elif not is_cruise_active and cruise_active:
                # Cruise disengaged
                duration = (
                    (point.time - cruise_start_point.time).total_seconds()
                    if cruise_start_point
                    else 0
                )
                cruise_active = False
                events.append(
                    DrivingEvent(
                        id=uuid.uuid4(),
                        trip_id=trip_id,
                        event_time=point.time,
                        event_type="cruise_disengage",
                        latitude=point.latitude,
                        longitude=point.longitude,
                        speed_mph=point.speed_mph,
                        metadata_={"duration_seconds": duration},
                    )
                )

        return events
