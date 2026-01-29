import re
import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trip import Trip
from app.models.telemetry import Telemetry


def normalize_column_name(name: str) -> str:
    """Convert column name to snake_case."""
    # Remove units in parentheses
    name = re.sub(r"\s*\([^)]*\)", "", name)
    # Replace spaces and special chars with underscore
    name = re.sub(r"[\s/]+", "_", name)
    # Remove consecutive underscores
    name = re.sub(r"_+", "_", name)
    # Remove leading/trailing underscores
    name = name.strip("_")
    # Convert to lowercase
    return name.lower()


# Mapping of CSV columns to database explicit columns
# Tier 1-3 PIDs get their own columns, everything else goes to sensors JSONB
EXPLICIT_COLUMN_MAPPING = {
    # Core columns (already handled separately)
    "time": "time",
    "vehicle_speed": "speed_mph",
    "latitude": "latitude",
    "longitude": "longitude",

    # Tier 1: Core SAE PIDs
    "engine_rpm": "engine_rpm",
    "mass_air_flow_rate": "mass_air_flow_rate_g_s",  # Will convert lb/min to g/s
    "calculated_load_value": "calculated_load_pct",
    "absolute_throttle_position": "throttle_position_pct",
    "accelerator_pedal_position_d": "accelerator_pedal_position_pct",
    "engine_coolant_temperature": "engine_coolant_temp_f",
    "intake_air_temperature": "intake_air_temp_f",

    # Tier 2: OBD Fusion Calculated
    "instant_fuel_economy": "instant_mpg",
    "trip_fuel_economy": "trip_mpg",
    "fuel_rate": "fuel_rate_gal_hr",
    "engine_power": "engine_power_hp",
    "acceleration": "acceleration_g",  # Will convert ft/s² to g

    # Tier 3: GPS + Sensors
    "altitude": "altitude_ft",
    "gps_speed": "gps_speed_mph",
    "bearing": "gps_bearing_deg",
}


def convert_units(column_name: str, value: float) -> float:
    """Convert units where needed."""
    if column_name == "mass_air_flow_rate_g_s":
        # Convert lb/min to g/s: 1 lb/min = 7.5598728 g/s
        return value * 7.5598728
    elif column_name == "acceleration_g":
        # Convert ft/s² to g: 1g = 32.174 ft/s²
        return value / 32.174
    return value


def parse_start_time(comment_line: str) -> Optional[datetime]:
    """Parse start time from CSV comment header. Assumes local timezone."""
    # Format: # StartTime = MM/DD/YYYY HH:MM:SS.xxxx AM/PM
    match = re.search(
        r"StartTime\s*=\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\.\d+\s*[AP]M)",
        comment_line,
        re.IGNORECASE,
    )
    if match:
        time_str = match.group(1)
        try:
            # Parse as naive datetime (local time), then make it UTC-aware for database
            naive_dt = datetime.strptime(time_str, "%m/%d/%Y %I:%M:%S.%f %p")
            return naive_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


class CSVParser:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def parse_and_store(
        self,
        csv_text: str,
        filename: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Trip:
        lines = csv_text.strip().split("\n")

        # Parse start time from comment header
        start_time = None
        data_start_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("#"):
                parsed_time = parse_start_time(line)
                if parsed_time:
                    start_time = parsed_time
                data_start_idx = i + 1
            else:
                break

        if not start_time:
            start_time = datetime.now(timezone.utc)

        # Parse CSV data
        csv_content = "\n".join(lines[data_start_idx:])
        reader = csv.DictReader(io.StringIO(csv_content))

        # Get and normalize column names
        original_columns = reader.fieldnames or []
        column_mapping = {col: normalize_column_name(col) for col in original_columns}

        # Build reverse mapping: normalized -> original column name
        norm_to_orig = {norm: orig for orig, norm in column_mapping.items()}

        # Identify core columns (time, speed, lat, lng)
        time_col = None
        speed_col = None
        lat_col = None
        lng_col = None

        for orig, norm in column_mapping.items():
            orig_lower = orig.lower()
            # Time column can be "Time" or "Time (sec)"
            if orig_lower.strip() == "time" or ("time" in orig_lower and "sec" in orig_lower):
                time_col = orig
            elif norm == "vehicle_speed" or "vehicle speed" in orig_lower:
                speed_col = orig
            elif "latitude" in norm or "latitude" in orig_lower:
                lat_col = orig
            elif "longitude" in norm or "longitude" in orig_lower:
                lng_col = orig

        # Build mapping for explicit DB columns (Tier 1-3)
        explicit_cols = {}  # normalized_name -> original_csv_name
        for norm_name, db_col_name in EXPLICIT_COLUMN_MAPPING.items():
            if norm_name in norm_to_orig and norm_name not in ("time", "vehicle_speed", "latitude", "longitude"):
                explicit_cols[norm_name] = (norm_to_orig[norm_name], db_col_name)

        # Parse rows
        rows = list(reader)
        if not rows:
            raise ValueError("CSV file contains no data rows")

        # Detect time format: check if first row's time value is a timestamp or float
        time_is_timestamp = False
        first_timestamp = None
        if time_col and rows:
            first_time_value = rows[0].get(time_col, "")
            try:
                float(first_time_value)
                time_is_timestamp = False
            except ValueError:
                time_is_timestamp = True
                # Parse the first timestamp to use as reference (local time, make UTC-aware)
                try:
                    naive_dt = datetime.strptime(first_time_value.strip(), "%m/%d/%Y %I:%M:%S.%f %p")
                    first_timestamp = naive_dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    try:
                        naive_dt = datetime.strptime(first_time_value.strip(), "%m/%d/%Y %I:%M:%S %p")
                        first_timestamp = naive_dt.replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass

        # Calculate trip statistics
        speeds = []
        max_elapsed = 0.0

        telemetry_records = []
        trip_id = uuid.uuid4()

        for row in rows:
            # Parse elapsed time
            if time_is_timestamp and time_col and first_timestamp:
                time_str = row.get(time_col, "")
                try:
                    # Parse as naive (local time), make UTC-aware
                    naive_dt = datetime.strptime(time_str.strip(), "%m/%d/%Y %I:%M:%S.%f %p")
                    row_time = naive_dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    try:
                        naive_dt = datetime.strptime(time_str.strip(), "%m/%d/%Y %I:%M:%S %p")
                        row_time = naive_dt.replace(tzinfo=timezone.utc)
                    except ValueError:
                        row_time = first_timestamp
                elapsed = (row_time - first_timestamp).total_seconds()
            else:
                elapsed = float(row.get(time_col, 0) or 0) if time_col else 0

            speed = float(row.get(speed_col, 0) or 0) if speed_col else None

            # Parse and filter GPS coordinates (filter out 0,0 and None)
            try:
                lat = float(row.get(lat_col, 0) or 0) if lat_col else None
                lng = float(row.get(lng_col, 0) or 0) if lng_col else None
                # Filter out 0,0 coordinates (invalid GPS data)
                if lat == 0.0 and lng == 0.0:
                    lat = None
                    lng = None
            except (ValueError, TypeError):
                lat = None
                lng = None

            if speed is not None:
                speeds.append(speed)
            max_elapsed = max(max_elapsed, elapsed)

            # Extract explicit DB columns (Tier 1-3)
            explicit_data = {}
            for norm_name, (csv_col, db_col) in explicit_cols.items():
                try:
                    value = float(row.get(csv_col, "") or 0)
                    if value != 0:  # Only convert non-zero values
                        value = convert_units(db_col, value)
                    explicit_data[db_col] = value if value != 0 else None
                except (ValueError, TypeError):
                    explicit_data[db_col] = None

            # Build sensors dict with remaining columns (Tier 4-5)
            sensors = {}
            handled_cols = {time_col, speed_col, lat_col, lng_col}
            handled_cols.update(csv_col for csv_col, _ in explicit_cols.values())

            for orig_col in original_columns:
                if orig_col not in handled_cols:
                    norm_col = column_mapping[orig_col]
                    try:
                        value = float(row[orig_col])
                        sensors[norm_col] = value if value != 0 else None
                    except (ValueError, TypeError):
                        sensors[norm_col] = row[orig_col] if row[orig_col] else None

            record_time = start_time + timedelta(seconds=elapsed)

            telemetry_records.append(
                Telemetry(
                    time=record_time,
                    trip_id=trip_id,
                    elapsed_seconds=elapsed,
                    speed_mph=speed,
                    latitude=lat,
                    longitude=lng,
                    sensors=sensors,
                    **explicit_data,  # Unpack Tier 1-3 columns
                )
            )

        # Calculate statistics
        end_time = start_time + timedelta(seconds=max_elapsed)
        max_speed = max(speeds) if speeds else None
        avg_speed = sum(speeds) / len(speeds) if speeds else None

        # Use filename as default name if not provided
        if not name:
            name = filename.replace(".csv", "").replace("_", " ")

        # Create trip record
        trip = Trip(
            id=trip_id,
            name=name,
            description=description,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=max_elapsed,
            max_speed_mph=max_speed,
            avg_speed_mph=avg_speed,
            sensor_columns=list(column_mapping.values()),
            source_filename=filename,
            row_count=len(rows),
        )

        # Store in database
        self.db.add(trip)
        self.db.add_all(telemetry_records)
        await self.db.commit()
        await self.db.refresh(trip)

        return trip
