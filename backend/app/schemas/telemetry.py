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

    # Tier 1: Core SAE PIDs
    engine_rpm: Optional[float] = None
    mass_air_flow_rate_g_s: Optional[float] = None
    calculated_load_pct: Optional[float] = None
    throttle_position_pct: Optional[float] = None
    accelerator_pedal_position_pct: Optional[float] = None
    engine_coolant_temp_f: Optional[float] = None
    intake_air_temp_f: Optional[float] = None

    # Tier 2: OBD Fusion Calculated
    instant_mpg: Optional[float] = None
    trip_mpg: Optional[float] = None
    fuel_rate_gal_hr: Optional[float] = None
    engine_power_hp: Optional[float] = None
    acceleration_g: Optional[float] = None

    # Tier 3: GPS + Sensors
    altitude_ft: Optional[float] = None
    gps_speed_mph: Optional[float] = None
    gps_bearing_deg: Optional[float] = None

    sensors: Optional[dict] = None


class TelemetryBulkRead(BaseModel):
    trip_id: UUID
    data: list[TelemetryRead]
    count: int
