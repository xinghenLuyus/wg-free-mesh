from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.version import read_project_version


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_prefix="WFM_",
        extra="ignore",
    )

    app_name: str = "WG Free Mesh API"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    api_v0_prefix: str = "/api/v0"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    database_url: str = "sqlite:///./data/wg_free_mesh.db"
    mqtt_url: str = "mqtt://localhost:1883"
    mqtt_public_host: str = "localhost"
    mqtt_public_port: int = 1883
    mqtt_public_tls_port: int = 8883
    mqtt_tls_enabled: bool = False
    enable_mqtt_services: bool = True
    emqx_api_base_url: str = "http://localhost:18083"
    emqx_username: str = "admin"
    emqx_password: str = "public"
    emqx_authz_shared_key: str = "wfm-internal-emqx-authz"
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
    def app_version(self) -> str:
        return read_project_version()

    @property
    def dev_test_api_enabled(self) -> bool:
        return self.enable_dev_test_api

    @property
    def mqtt_bind_port(self) -> int:
        return self.mqtt_public_tls_port if self.mqtt_tls_enabled else self.mqtt_public_port


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
