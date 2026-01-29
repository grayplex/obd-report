"""Add tables for trip analytics and driving events

Revision ID: 003
Revises: 002
Create Date: 2026-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add calculated analytics columns to trips table
    op.add_column("trips", sa.Column("distance_miles", sa.Float, nullable=True))
    op.add_column("trips", sa.Column("idle_time_seconds", sa.Float, nullable=True))
    op.add_column("trips", sa.Column("moving_time_seconds", sa.Float, nullable=True))
    op.add_column("trips", sa.Column("stop_count", sa.Integer, nullable=True))
    op.add_column("trips", sa.Column("avg_fuel_economy_mpg", sa.Float, nullable=True))
    op.add_column("trips", sa.Column("total_fuel_used_gal", sa.Float, nullable=True))

    # Create driving_events table for discrete events (hard brake, hard accel, etc.)
    op.create_table(
        "driving_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),  # 'hard_brake', 'hard_accel', 'idle_start', 'idle_end', 'cruise_engage', 'cruise_disengage'
        sa.Column("severity", sa.String(20), nullable=True),  # 'low', 'medium', 'high'
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("speed_mph", sa.Float, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),  # Store event-specific details
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_driving_events_trip_id", "driving_events", ["trip_id"])
    op.create_index("ix_driving_events_event_type", "driving_events", ["event_type"])
    op.create_index("ix_driving_events_event_time", "driving_events", ["event_time"])

    # Create trip_segments table for analyzing different driving modes
    op.create_table(
        "trip_segments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("segment_type", sa.String(50), nullable=False),  # 'city', 'highway', 'cruise', 'idle', 'stop'
        sa.Column("duration_seconds", sa.Float, nullable=False),
        sa.Column("distance_miles", sa.Float, nullable=True),
        sa.Column("avg_speed_mph", sa.Float, nullable=True),
        sa.Column("max_speed_mph", sa.Float, nullable=True),
        sa.Column("avg_rpm", sa.Float, nullable=True),
        sa.Column("avg_throttle_pct", sa.Float, nullable=True),
        sa.Column("avg_fuel_economy_mpg", sa.Float, nullable=True),
        sa.Column("fuel_used_gal", sa.Float, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
    )

    op.create_index("ix_trip_segments_trip_id", "trip_segments", ["trip_id"])
    op.create_index("ix_trip_segments_type", "trip_segments", ["segment_type"])


def downgrade() -> None:
    # Drop trip_segments table
    op.drop_index("ix_trip_segments_type")
    op.drop_index("ix_trip_segments_trip_id")
    op.drop_table("trip_segments")

    # Drop driving_events table
    op.drop_index("ix_driving_events_event_time")
    op.drop_index("ix_driving_events_event_type")
    op.drop_index("ix_driving_events_trip_id")
    op.drop_table("driving_events")

    # Drop added columns from trips table
    op.drop_column("trips", "total_fuel_used_gal")
    op.drop_column("trips", "avg_fuel_economy_mpg")
    op.drop_column("trips", "stop_count")
    op.drop_column("trips", "moving_time_seconds")
    op.drop_column("trips", "idle_time_seconds")
    op.drop_column("trips", "distance_miles")
