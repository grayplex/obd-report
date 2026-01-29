"""Expand telemetry table with explicit PID columns

Revision ID: 002
Revises: 001
Create Date: 2026-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tier 1: Core SAE PIDs (most frequently queried)
    op.add_column("telemetry", sa.Column("engine_rpm", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("mass_air_flow_rate_g_s", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("calculated_load_pct", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("throttle_position_pct", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("accelerator_pedal_position_pct", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("engine_coolant_temp_f", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("intake_air_temp_f", sa.Float, nullable=True))

    # Tier 2: OBD Fusion Calculated (high-value derived metrics)
    op.add_column("telemetry", sa.Column("instant_mpg", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("trip_mpg", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("fuel_rate_gal_hr", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("engine_power_hp", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("acceleration_g", sa.Float, nullable=True))

    # Tier 3: GPS + Sensors (context for analytics)
    op.add_column("telemetry", sa.Column("altitude_ft", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("gps_speed_mph", sa.Float, nullable=True))
    op.add_column("telemetry", sa.Column("gps_bearing_deg", sa.Float, nullable=True))

    # Create indexes on frequently filtered/aggregated columns
    op.create_index("ix_telemetry_engine_rpm", "telemetry", ["engine_rpm"])
    op.create_index("ix_telemetry_throttle_position", "telemetry", ["throttle_position_pct"])
    op.create_index("ix_telemetry_instant_mpg", "telemetry", ["instant_mpg"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_telemetry_instant_mpg")
    op.drop_index("ix_telemetry_throttle_position")
    op.drop_index("ix_telemetry_engine_rpm")

    # Drop Tier 3 columns
    op.drop_column("telemetry", "gps_bearing_deg")
    op.drop_column("telemetry", "gps_speed_mph")
    op.drop_column("telemetry", "altitude_ft")

    # Drop Tier 2 columns
    op.drop_column("telemetry", "acceleration_g")
    op.drop_column("telemetry", "engine_power_hp")
    op.drop_column("telemetry", "fuel_rate_gal_hr")
    op.drop_column("telemetry", "trip_mpg")
    op.drop_column("telemetry", "instant_mpg")

    # Drop Tier 1 columns
    op.drop_column("telemetry", "intake_air_temp_f")
    op.drop_column("telemetry", "engine_coolant_temp_f")
    op.drop_column("telemetry", "accelerator_pedal_position_pct")
    op.drop_column("telemetry", "throttle_position_pct")
    op.drop_column("telemetry", "calculated_load_pct")
    op.drop_column("telemetry", "mass_air_flow_rate_g_s")
    op.drop_column("telemetry", "engine_rpm")
