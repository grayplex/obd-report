import re
import csv
import io
from datetime import datetime, timedelta
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


def parse_start_time(comment_line: str) -> Optional[datetime]:
    """Parse start time from CSV comment header."""
    # Format: # StartTime = MM/DD/YYYY HH:MM:SS.xxxx AM/PM
    match = re.search(
        r"StartTime\s*=\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\.\d+\s*[AP]M)",
        comment_line,
        re.IGNORECASE,
    )
    if match:
        time_str = match.group(1)
        try:
            return datetime.strptime(time_str, "%m/%d/%Y %I:%M:%S.%f %p")
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
            start_time = datetime.utcnow()

        # Parse CSV data
        csv_content = "\n".join(lines[data_start_idx:])
        reader = csv.DictReader(io.StringIO(csv_content))

        # Get and normalize column names
        original_columns = reader.fieldnames or []
        column_mapping = {col: normalize_column_name(col) for col in original_columns}

        # Core column names (normalized)
        time_col = None
        speed_col = None
        lat_col = None
        lng_col = None

        for orig, norm in column_mapping.items():
            orig_lower = orig.lower()
            # Check original column name for time (e.g., "Time (sec)")
            if ("time" in orig_lower and "sec" in orig_lower) or norm == "time":
                time_col = orig
            elif norm == "vehicle_speed" or "vehicle speed" in orig_lower:
                speed_col = orig
            elif "latitude" in norm or "latitude" in orig_lower:
                lat_col = orig
            elif "longitude" in norm or "longitude" in orig_lower:
                lng_col = orig

        # Parse rows
        rows = list(reader)
        if not rows:
            raise ValueError("CSV file contains no data rows")

        # Calculate trip statistics
        speeds = []
        max_elapsed = 0.0

        telemetry_records = []
        trip_id = uuid.uuid4()

        for row in rows:
            elapsed = float(row.get(time_col, 0) or 0) if time_col else 0
            speed = float(row.get(speed_col, 0) or 0) if speed_col else None
            lat = float(row.get(lat_col, 0) or 0) if lat_col else None
            lng = float(row.get(lng_col, 0) or 0) if lng_col else None

            if speed is not None:
                speeds.append(speed)
            max_elapsed = max(max_elapsed, elapsed)

            # Build sensors dict with all other columns
            sensors = {}
            for orig_col in original_columns:
                norm_col = column_mapping[orig_col]
                if orig_col not in (time_col, speed_col, lat_col, lng_col):
                    try:
                        sensors[norm_col] = float(row[orig_col])
                    except (ValueError, TypeError):
                        sensors[norm_col] = row[orig_col]

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
