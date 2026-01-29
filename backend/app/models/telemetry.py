import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Telemetry(Base):
    __tablename__ = "telemetry"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        primary_key=True,
    )
    elapsed_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    speed_mph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Tier 1: Core SAE PIDs
    engine_rpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mass_air_flow_rate_g_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calculated_load_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    throttle_position_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accelerator_pedal_position_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    engine_coolant_temp_f: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    intake_air_temp_f: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Tier 2: OBD Fusion Calculated
    instant_mpg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trip_mpg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fuel_rate_gal_hr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    engine_power_hp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    acceleration_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Tier 3: GPS + Sensors
    altitude_ft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_speed_mph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_bearing_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # All other PIDs (Toyota-specific, cruise, wheels, etc.) stored in JSONB
    sensors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    trip = relationship("Trip", back_populates="telemetry")
