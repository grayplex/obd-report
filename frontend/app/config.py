import os


class Settings:
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    @property
    def api_url(self) -> str:
        return f"{self.backend_url}/api/v1"


settings = Settings()
