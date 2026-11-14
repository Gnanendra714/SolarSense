from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/solarsense.db"
    cors_origins: str = "http://localhost:5173"
    device_api_key: str = "replace-with-a-long-random-secret"
    admin_api_key: str = "replace-with-a-different-long-random-secret"
    environment: str = "development"
    max_panel_temp_c: float = 65.0
    min_light_for_output_lux: float = 8000.0
    min_power_ratio: float = 0.20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"


settings = Settings()
