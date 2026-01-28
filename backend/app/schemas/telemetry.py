from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    time: datetime
    trip_id: UUID
    elapsed_seconds: float
    speed_mph: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    sensors: Optional[dict] = None


class TelemetryBulkRead(BaseModel):
    trip_id: UUID
    data: list[TelemetryRead]
    count: int
