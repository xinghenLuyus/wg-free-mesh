from app.domain.models import Config
from app.repositories.sqlite import store


class ConfigService:
    def list_configs(self) -> list[Config]:
        return store.list_configs()

    def get_config(self, config_id: str) -> Config:
        return store.get_config(config_id)

    def create_config(self, name: str, description: str) -> Config:
        return store.create_config(name, description)


config_service = ConfigService()
