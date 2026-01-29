import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Float, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    max_speed_mph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_speed_mph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Trip analytics
    distance_miles: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    idle_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moving_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_fuel_economy_mpg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_fuel_used_gal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    sensor_columns: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    source_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    telemetry = relationship("Telemetry", back_populates="trip", cascade="all, delete-orphan")
    driving_events = relationship("DrivingEvent", back_populates="trip", cascade="all, delete-orphan")
    segments = relationship("TripSegment", back_populates="trip", cascade="all, delete-orphan")
