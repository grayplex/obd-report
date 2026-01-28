from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TripBase(BaseModel):
    name: str
    description: Optional[str] = None


class TripCreate(TripBase):
    pass


class TripUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TripRead(TripBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    max_speed_mph: Optional[float] = None
    avg_speed_mph: Optional[float] = None
    sensor_columns: Optional[list[str]] = None
    source_filename: Optional[str] = None
    row_count: Optional[int] = None
    created_at: datetime


class TripList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    start_time: datetime
    duration_seconds: float
    max_speed_mph: Optional[float] = None
    avg_speed_mph: Optional[float] = None
    row_count: Optional[int] = None
