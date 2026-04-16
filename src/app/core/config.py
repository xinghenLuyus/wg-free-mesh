from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="WFM_", extra="ignore")

    app_name: str = "WG Free Mesh API"
    app_version: str = "0.1.0"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    database_url: str = "sqlite:///./data/wg_free_mesh.db"
    mqtt_url: str = "mqtt://localhost:1883"
    auth_token_expire_minutes: int = 1440

    @property
    def sqlite_path(self) -> str:
        if not self.database_url.startswith("sqlite:///"):
            return "./data/wg_free_mesh.db"
        return self.database_url.removeprefix("sqlite:///")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
