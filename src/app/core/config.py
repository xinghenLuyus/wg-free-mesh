from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from pydantic import field_validator, model_validator
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
    public_origin: str = ""
    extra_allowed_origins: list[str] = Field(default_factory=list)
    database_url: str = "sqlite:///./data/wg_free_mesh.db"
    mqtt_url: str = "mqtt://localhost:1883"
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
    database: str = ""

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
        if not self.database.startswith("sqlite:///"):
            return "./data/wg_free_mesh.db"
        return self.database.removeprefix("sqlite:///")

    @model_validator(mode="after")
    def normalize_database(self) -> "Settings":
        self.database = self.database.strip() or self.database_url.strip() or "sqlite:///./data/wg_free_mesh.db"
        return self

    @property
    def app_version(self) -> str:
        return read_project_version()

    @property
    def dev_test_api_enabled(self) -> bool:
        return self.enable_dev_test_api

    @property
    def mqtt_bind_port(self) -> int:
        return self.mqtt_public_tls_port if self.mqtt_tls_enabled else self.mqtt_public_port

    @property
    def allowed_origins(self) -> list[str]:
        ordered = [self.public_origin, *self.extra_allowed_origins]
        return list(dict.fromkeys(origin.strip().rstrip("/") for origin in ordered if origin.strip()))

    @property
    def public_origin_host(self) -> str:
        parsed = urlparse(self.public_origin.strip())
        return parsed.netloc.lower()

    @property
    def mqtt_public_host(self) -> str:
        parsed = urlparse(self.public_origin.strip())
        return parsed.hostname or "localhost"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
