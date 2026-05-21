from __future__ import annotations

from app.data.repositories.client_state import ClientStateRepositoryMixin
from app.data.repositories.common import normalize_allowed_ips
from app.data.repositories.config_mesh import ConfigMeshRepositoryMixin
from app.data.repositories.endpoint_helpers import EndpointHelpersRepositoryMixin
from app.data.repositories.port_forwards import PortForwardRepositoryMixin
from app.data.repositories.runtime_state import RuntimeStateRepositoryMixin
from app.data.repositories.sync_settings import SyncSettingsRepositoryMixin


class Store(
    ClientStateRepositoryMixin,
    ConfigMeshRepositoryMixin,
    EndpointHelpersRepositoryMixin,
    PortForwardRepositoryMixin,
    RuntimeStateRepositoryMixin,
    SyncSettingsRepositoryMixin,
):
    """Unified application repository."""


store = Store()

__all__ = ["Store", "normalize_allowed_ips", "store"]
