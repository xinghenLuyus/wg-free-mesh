from pydantic import BaseModel


class SystemSettingsRead(BaseModel):
    mqtt_url: str
    database_url: str
    registration_enabled: bool

