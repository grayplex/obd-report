"""Advanced analytics for detailed driving insights."""
import uuid
from typing import List, Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict

from app.models.trip import Trip
from app.models.telemetry import Telemetry


class AdvancedAnalytics:
    """Advanced trip analysis including speed ranges, throttle patterns, cruise stats."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_speed_ranges(self, trip_id: uuid.UUID) -> Dict:
        """
        Analyze time spent at different speed ranges.
        Returns breakdown of city driving (0-35 mph), suburban (35-55 mph), highway (55+ mph).
        """
        telemetry_result = await self.db.execute(
            select(Telemetry)
            .where(Telemetry.trip_id == trip_id)
            .order_by(Telemetry.time)
        )
        telemetry_points = telemetry_result.scalars().all()

        # Speed range buckets (in mph)
        ranges = {
            "stopped": {"min": 0, "max": 2, "time": 0.0, "distance": 0.0},
            "city": {"min": 2, "max": 35, "time": 0.0, "distance": 0.0},
            "suburban": {"min": 35, "max": 55, "time": 0.0, "distance": 0.0},
            "highway": {"min": 55, "max": 150, "time": 0.0, "distance": 0.0},
        }

        prev_time = None
        for point in telemetry_points:
            if prev_time and point.speed_mph is not None:
                time_diff = (point.time - prev_time).total_seconds()

                # Determine which range
                for range_name, range_data in ranges.items():
                    if range_data["min"] <= point.speed_mph < range_data["max"]:
                        ranges[range_name]["time"] += time_diff
                        # Approximate distance = speed * time
                        ranges[range_name]["distance"] += (point.speed_mph / 3600) * time_diff
                        break

            prev_time = point.time

        # Calculate percentages
        total_time = sum(r["time"] for r in ranges.values())
        for range_data in ranges.values():
            if total_time > 0:
                range_data["percentage"] = (range_data["time"] / total_time) * 100
            else:
                range_data["percentage"] = 0.0

        return ranges

    async def analyze_throttle_patterns(self, trip_id: uuid.UUID) -> Dict:
        """
        Analyze throttle input patterns to determine driving aggressiveness.
        """
        telemetry_result = await self.db.execute(
            select(Telemetry)
            .where(Telemetry.trip_id == trip_id)
            .where(Telemetry.throttle_position_pct.isnot(None))
            .order_by(Telemetry.time)
        )
        telemetry_points = telemetry_result.scalars().all()

        if not telemetry_points:
            return {}

        throttle_values = [p.throttle_position_pct for p in telemetry_points if p.throttle_position_pct]
        accel_pedal_values = [
            p.accelerator_pedal_position_pct
            for p in telemetry_points
            if p.accelerator_pedal_position_pct
        ]

        # Aggressiveness thresholds
        GENTLE_THRESHOLD = 30  # %
        MODERATE_THRESHOLD = 60  # %
        AGGRESSIVE_THRESHOLD = 80  # %

        throttle_distribution = {
            "gentle": 0,  # 0-30%
            "moderate": 0,  # 30-60%
            "aggressive": 0,  # 60-80%
            "very_aggressive": 0,  # 80-100%
        }

        for throttle in throttle_values:
            if throttle < GENTLE_THRESHOLD:
                throttle_distribution["gentle"] += 1
            elif throttle < MODERATE_THRESHOLD:
                throttle_distribution["moderate"] += 1
            elif throttle < AGGRESSIVE_THRESHOLD:
                throttle_distribution["aggressive"] += 1
            else:
                throttle_distribution["very_aggressive"] += 1

        total_samples = len(throttle_values)

        # Analyze throttle changes (how quickly throttle input changes)
        prev_time = None
        prev_throttle = None
        throttle_change_rates = []

        for point in telemetry_points:
            if prev_time and prev_throttle is not None and point.throttle_position_pct is not None:
                time_diff = (point.time - prev_time).total_seconds()
                if time_diff > 0:
                    throttle_change = abs(point.throttle_position_pct - prev_throttle)
                    change_rate = throttle_change / time_diff
                    throttle_change_rates.append(change_rate)

            prev_time = point.time
            prev_throttle = point.throttle_position_pct

        avg_change_rate = sum(throttle_change_rates) / len(throttle_change_rates) if throttle_change_rates else 0

        return {
            "avg_throttle": sum(throttle_values) / len(throttle_values) if throttle_values else 0,
            "max_throttle": max(throttle_values) if throttle_values else 0,
            "avg_pedal_position": (
                sum(accel_pedal_values) / len(accel_pedal_values) if accel_pedal_values else 0
            ),
            "distribution": {
                "gentle_pct": (throttle_distribution["gentle"] / total_samples * 100) if total_samples else 0,
                "moderate_pct": (throttle_distribution["moderate"] / total_samples * 100) if total_samples else 0,
                "aggressive_pct": (throttle_distribution["aggressive"] / total_samples * 100) if total_samples else 0,
                "very_aggressive_pct": (throttle_distribution["very_aggressive"] / total_samples * 100)
                if total_samples
                else 0,
            },
            "avg_change_rate": avg_change_rate,
            "aggressiveness_score": self._calculate_aggressiveness_score(throttle_distribution, total_samples),
        }

    def _calculate_aggressiveness_score(self, distribution: Dict, total: int) -> float:
        """Calculate overall aggressiveness score (0-100)."""
        if total == 0:
            return 0

        score = (
            (distribution["gentle"] * 0)
            + (distribution["moderate"] * 30)
            + (distribution["aggressive"] * 70)
            + (distribution["very_aggressive"] * 100)
        ) / total

        return score

    async def analyze_cruise_control(self, trip_id: uuid.UUID) -> Dict:
        """
        Analyze cruise control usage: when engaged, at what speeds, for how long.
        """
        telemetry_result = await self.db.execute(
            select(Telemetry)
            .where(Telemetry.trip_id == trip_id)
            .order_by(Telemetry.time)
        )
        telemetry_points = telemetry_result.scalars().all()

        cruise_sessions = []
        cruise_start = None
        cruise_start_speed = None
        total_cruise_time = 0.0
        cruise_speeds = []

        prev_time = None

        for point in telemetry_points:
            # Check if cruise is active
            is_cruise_active = False
            if point.sensors:
                status = point.sensors.get("status_of_the_cruise_control_no_or_yes")
                set_speed = point.sensors.get("cruise_control_vehicle_speed")
                # Consider cruise active if status is 1 or Yes, or if set speed exists
                if status == 1.0 or status == "Yes" or (set_speed and set_speed > 0):
                    is_cruise_active = True

            if is_cruise_active and not cruise_start:
                # Cruise engaged
                cruise_start = point.time
                cruise_start_speed = point.speed_mph
            elif not is_cruise_active and cruise_start:
                # Cruise disengaged
                duration = (prev_time - cruise_start).total_seconds() if prev_time else 0
                if duration > 5:  # Only count sessions > 5 seconds
                    cruise_sessions.append({
                        "start_time": cruise_start,
                        "end_time": prev_time,
                        "duration": duration,
                        "avg_speed": sum(cruise_speeds) / len(cruise_speeds) if cruise_speeds else cruise_start_speed,
                        "set_speed": cruise_start_speed,
                    })
                    total_cruise_time += duration

                cruise_start = None
                cruise_start_speed = None
                cruise_speeds = []
            elif is_cruise_active and cruise_start:
                # Cruise still active, record speed
                if point.speed_mph:
                    cruise_speeds.append(point.speed_mph)

            prev_time = point.time

        # Handle if cruise is still active at end
        if cruise_start and prev_time:
            duration = (prev_time - cruise_start).total_seconds()
            if duration > 5:
                cruise_sessions.append({
                    "start_time": cruise_start,
                    "end_time": prev_time,
                    "duration": duration,
                    "avg_speed": sum(cruise_speeds) / len(cruise_speeds) if cruise_speeds else cruise_start_speed,
                    "set_speed": cruise_start_speed,
                })
                total_cruise_time += duration

        return {
            "total_cruise_time": total_cruise_time,
            "session_count": len(cruise_sessions),
            "sessions": [
                {
                    "start": s["start_time"].isoformat(),
                    "end": s["end_time"].isoformat(),
                    "duration": s["duration"],
                    "avg_speed": s["avg_speed"],
                    "set_speed": s["set_speed"],
                }
                for s in cruise_sessions
            ],
            "avg_session_duration": total_cruise_time / len(cruise_sessions) if cruise_sessions else 0,
        }

    async def analyze_fuel_efficiency_insights(self, trip_id: uuid.UUID) -> Dict:
        """
        Analyze fuel efficiency: heavy throttle events, optimal cruising, stop-and-go traffic.
        """
        telemetry_result = await self.db.execute(
            select(Telemetry)
            .where(Telemetry.trip_id == trip_id)
            .order_by(Telemetry.time)
        )
        telemetry_points = telemetry_result.scalars().all()

        heavy_throttle_events = []
        optimal_cruising_segments = []
        stop_and_go_periods = []

        # Heavy throttle detection
        prev_time = None
        stop_and_go_start = None
        stop_and_go_count = 0

        for i, point in enumerate(telemetry_points):
            # Heavy throttle events (> 80% throttle)
            if point.throttle_position_pct and point.throttle_position_pct > 80:
                heavy_throttle_events.append({
                    "time": point.time.isoformat(),
                    "throttle": point.throttle_position_pct,
                    "speed": point.speed_mph,
                    "mpg": point.instant_mpg,
                })

            # Optimal cruising (steady speed 50-70 mph, low throttle, high MPG)
            if (
                point.speed_mph
                and 50 <= point.speed_mph <= 70
                and point.throttle_position_pct
                and point.throttle_position_pct < 40
                and point.instant_mpg
                and point.instant_mpg > 30
            ):
                # Check if speed is relatively steady (next few points similar)
                if i < len(telemetry_points) - 5:
                    next_speeds = [p.speed_mph for p in telemetry_points[i:i+5] if p.speed_mph]
                    if next_speeds:
                        speed_variation = max(next_speeds) - min(next_speeds)
                        if speed_variation < 5:  # Steady speed
                            optimal_cruising_segments.append({
                                "time": point.time.isoformat(),
                                "speed": point.speed_mph,
                                "mpg": point.instant_mpg,
                                "throttle": point.throttle_position_pct,
                            })

            # Stop-and-go traffic detection (frequent stops and starts)
            if point.speed_mph is not None:
                if point.speed_mph < 5:
                    if not stop_and_go_start:
                        stop_and_go_start = point.time
                elif stop_and_go_start and prev_time:
                    # Speed increased from stopped
                    duration = (prev_time - stop_and_go_start).total_seconds()
                    if duration > 2:  # Was stopped for > 2 seconds
                        stop_and_go_count += 1
                    stop_and_go_start = None

            prev_time = point.time

        return {
            "heavy_throttle_events": {
                "count": len(heavy_throttle_events),
                "events": heavy_throttle_events[:20],  # Limit to first 20
            },
            "optimal_cruising": {
                "count": len(optimal_cruising_segments),
                "avg_mpg": (
                    sum(s["mpg"] for s in optimal_cruising_segments) / len(optimal_cruising_segments)
                    if optimal_cruising_segments
                    else 0
                ),
                "total_time": len(optimal_cruising_segments) * 0.1,  # Rough estimate (10Hz sampling)
            },
            "stop_and_go": {
                "event_count": stop_and_go_count,
                "estimated_time": stop_and_go_count * 5,  # Rough estimate
            },
        }

    async def get_speed_throttle_correlation(self, trip_id: uuid.UUID) -> Dict:
        """
        Analyze correlation between throttle position and speed changes.
        """
        telemetry_result = await self.db.execute(
            select(Telemetry)
            .where(Telemetry.trip_id == trip_id)
            .where(Telemetry.throttle_position_pct.isnot(None))
            .where(Telemetry.speed_mph.isnot(None))
            .order_by(Telemetry.time)
        )
        telemetry_points = telemetry_result.scalars().all()

        if len(telemetry_points) < 10:
            return {}

        # Calculate correlation data points
        prev_speed = None
        prev_throttle = None
        prev_time = None
        correlation_points = []

        for point in telemetry_points:
            if prev_speed is not None and prev_time:
                time_diff = (point.time - prev_time).total_seconds()
                if time_diff > 0:
                    speed_change = point.speed_mph - prev_speed
                    throttle_level = point.throttle_position_pct

                    correlation_points.append({
                        "throttle": throttle_level,
                        "speed_change": speed_change,
                        "speed": point.speed_mph,
                    })

            prev_speed = point.speed_mph
            prev_throttle = point.throttle_position_pct
            prev_time = point.time

        # Simple correlation coefficient
        if len(correlation_points) > 1:
            throttles = [p["throttle"] for p in correlation_points]
            speed_changes = [p["speed_change"] for p in correlation_points]

            # Calculate means
            mean_throttle = sum(throttles) / len(throttles)
            mean_speed_change = sum(speed_changes) / len(speed_changes)

            # Calculate correlation
            numerator = sum(
                (t - mean_throttle) * (s - mean_speed_change)
                for t, s in zip(throttles, speed_changes)
            )
            denom_t = sum((t - mean_throttle) ** 2 for t in throttles) ** 0.5
            denom_s = sum((s - mean_speed_change) ** 2 for s in speed_changes) ** 0.5

            correlation = numerator / (denom_t * denom_s) if (denom_t * denom_s) > 0 else 0

            return {
                "correlation_coefficient": correlation,
                "sample_points": correlation_points[:100],  # Limit to 100 points
            }

        return {}
