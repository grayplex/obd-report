import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TripSegment(Base):
    __tablename__ = "trip_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    segment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    distance_miles: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_speed_mph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_speed_mph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_rpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_throttle_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_fuel_economy_mpg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fuel_used_gal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    trip = relationship("Trip", back_populates="segments")
