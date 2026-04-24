from __future__ import annotations

from app.repositories.sqlite_client_state import SQLiteClientStateMixin
from app.repositories.sqlite_common import normalize_allowed_ips
from app.repositories.sqlite_config_mesh import SQLiteConfigMeshMixin
from app.repositories.sqlite_endpoint_helpers import SQLiteEndpointHelpersMixin
from app.repositories.sqlite_runtime_state import SQLiteRuntimeStateMixin
from app.repositories.sqlite_sync_settings import SQLiteSyncSettingsMixin


class SQLiteStore(
    SQLiteClientStateMixin,
    SQLiteConfigMeshMixin,
    SQLiteEndpointHelpersMixin,
    SQLiteRuntimeStateMixin,
    SQLiteSyncSettingsMixin,
):
    """Compatibility facade that keeps the public repository entrypoint stable."""


store = SQLiteStore()

__all__ = ["SQLiteStore", "normalize_allowed_ips", "store"]
