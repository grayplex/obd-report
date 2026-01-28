from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://obd:obd_secret@localhost:5432/obd_telemetry"
    cors_origins: str = "http://localhost:8501"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
