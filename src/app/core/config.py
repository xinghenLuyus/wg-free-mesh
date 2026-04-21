from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_prefix="WFM_",
        extra="ignore",
    )

    app_name: str = "WG Free Mesh API"
    app_version: str = "0.1.0"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    api_v0_prefix: str = "/api/v0"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    database_url: str = "sqlite:///./data/wg_free_mesh.db"
    mqtt_url: str = "mqtt://localhost:1883"
    auth_token_expire_minutes: int = 1440
    auth_download_token_expire_minutes: int = 5
    enable_dev_test_api: bool = False
    timezone: str = "Asia/Shanghai"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        timezone = value.strip() or "Asia/Shanghai"
        try:
            ZoneInfo(timezone)
        except Exception as exc:
            raise ValueError(f"Unsupported timezone: {timezone}") from exc
        return timezone

    @property
    def sqlite_path(self) -> str:
        if not self.database_url.startswith("sqlite:///"):
            return "./data/wg_free_mesh.db"
        return self.database_url.removeprefix("sqlite:///")

    @property
    def dev_test_api_enabled(self) -> bool:
        return self.enable_dev_test_api


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
