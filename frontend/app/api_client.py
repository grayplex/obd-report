from typing import Optional
import requests

from app.config import settings


class APIClient:
    def __init__(self):
        self.base_url = settings.api_url

    def upload_csv(self, file, name: Optional[str] = None, description: Optional[str] = None) -> dict:
        """Upload a CSV file."""
        data = {}
        if name:
            data["name"] = name
        if description:
            data["description"] = description

        response = requests.post(
            f"{self.base_url}/upload/",
            files={"file": (file.name, file.getvalue(), "text/csv")},
            data=data,
        )
        response.raise_for_status()
        return response.json()

    def list_trips(self, skip: int = 0, limit: int = 100) -> list[dict]:
        """List all trips."""
        response = requests.get(
            f"{self.base_url}/trips/",
            params={"skip": skip, "limit": limit},
        )
        response.raise_for_status()
        return response.json()

    def get_trip(self, trip_id: str) -> dict:
        """Get a single trip."""
        response = requests.get(f"{self.base_url}/trips/{trip_id}")
        response.raise_for_status()
        return response.json()

    def update_trip(self, trip_id: str, name: Optional[str] = None, description: Optional[str] = None) -> dict:
        """Update a trip."""
        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        response = requests.patch(
            f"{self.base_url}/trips/{trip_id}",
            json=data,
        )
        response.raise_for_status()
        return response.json()

    def delete_trip(self, trip_id: str) -> dict:
        """Delete a trip."""
        response = requests.delete(f"{self.base_url}/trips/{trip_id}")
        response.raise_for_status()
        return response.json()

    def get_telemetry(self, trip_id: str, skip: int = 0, limit: int = 10000, downsample: int = 1) -> dict:
        """Get telemetry data for a trip."""
        response = requests.get(
            f"{self.base_url}/telemetry/{trip_id}",
            params={"skip": skip, "limit": limit, "downsample": downsample},
        )
        response.raise_for_status()
        return response.json()

    def get_gps_points(self, trip_id: str, downsample: int = 1) -> dict:
        """Get GPS points for a trip."""
        response = requests.get(
            f"{self.base_url}/telemetry/{trip_id}/gps",
            params={"downsample": downsample},
        )
        response.raise_for_status()
        return response.json()


api_client = APIClient()
