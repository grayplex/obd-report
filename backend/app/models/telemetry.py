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
    sensors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    trip = relationship("Trip", back_populates="telemetry")
