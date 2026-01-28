"""Initial schema with trips and telemetry tables

Revision ID: 001
Revises:
Create Date: 2026-01-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create trips table
    op.create_table(
        "trips",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float, nullable=False),
        sa.Column("max_speed_mph", sa.Float, nullable=True),
        sa.Column("avg_speed_mph", sa.Float, nullable=True),
        sa.Column("sensor_columns", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("row_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index("ix_trips_start_time", "trips", ["start_time"])
    op.create_index("ix_trips_name", "trips", ["name"])

    # Create telemetry table
    op.create_table(
        "telemetry",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("elapsed_seconds", sa.Float, nullable=False),
        sa.Column("speed_mph", sa.Float, nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("sensors", JSONB, nullable=True),
        sa.PrimaryKeyConstraint("time", "trip_id"),
    )

    op.create_index("ix_telemetry_trip_id", "telemetry", ["trip_id"])

    # Convert telemetry to TimescaleDB hypertable
    op.execute("SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE)")


def downgrade() -> None:
    op.drop_table("telemetry")
    op.drop_table("trips")
