from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings
from app.data.store import store
from app.services.emqx_service import emqx_service

logger = logging.getLogger(__name__)

WFM_NODE_USER_PREFIX = "node_"


@dataclass(slots=True)
class EmqxReconcileResult:
    enabled: bool
    mqtt_credentials: int = 0
    server_users_synced: int = 0
    server_users_failed: int = 0
    node_users_synced: int = 0
    node_users_failed: int = 0
    node_users_deleted: int = 0
    node_users_delete_failed: int = 0

    def to_dict(self) -> dict[str, int | bool]:
        return {
            "enabled": self.enabled,
            "mqtt_credentials": self.mqtt_credentials,
            "server_users_synced": self.server_users_synced,
            "server_users_failed": self.server_users_failed,
            "node_users_synced": self.node_users_synced,
            "node_users_failed": self.node_users_failed,
            "node_users_deleted": self.node_users_deleted,
            "node_users_delete_failed": self.node_users_delete_failed,
        }


class EmqxReconcileService:
    def is_enabled(self) -> bool:
        return settings.enable_mqtt_services

    def reconcile_all(self, *, cleanup_stale: bool = True) -> EmqxReconcileResult:
        result = EmqxReconcileResult(enabled=self.is_enabled())
        credentials = store.list_restorable_mqtt_credentials()
        result.mqtt_credentials = len(credentials)
        if not result.enabled:
            return result

        try:
            response = emqx_service.upsert_server_user()
            if response.status_code >= 400:
                result.server_users_failed += 1
                logger.warning("Failed to sync EMQX server user: %s %s", response.status_code, response.text)
                return result
            result.server_users_synced += 1
        except Exception:
            result.server_users_failed += 1
            logger.exception("Failed to sync EMQX server user")
            return result

        expected_user_ids = {item["username"] for item in credentials}
        for item in credentials:
            if self._sync_user(item["username"], item["password"]):
                result.node_users_synced += 1
            else:
                result.node_users_failed += 1

        if cleanup_stale:
            deleted, failed = self._cleanup_stale_node_users(expected_user_ids)
            result.node_users_deleted += deleted
            result.node_users_delete_failed += failed
        return result

    def sync_node_user(self, *, user_id: str, password: str) -> bool:
        if not self.is_enabled():
            return False
        return self._sync_user(user_id, password)

    def revoke_node_user(self, *, node_id: str) -> dict[str, bool]:
        if not self.is_enabled():
            return {"deleted": False, "disconnected": False}
        deleted = self._delete_node_user(node_id)
        disconnected = self._disconnect_node_client(node_id)
        return {"deleted": deleted, "disconnected": disconnected}

    def _sync_user(self, user_id: str, password: str) -> bool:
        try:
            response = emqx_service.upsert_user(user_id=user_id, password=password)
            if response.status_code >= 400:
                logger.warning("Failed to sync EMQX node user %s: %s %s", user_id, response.status_code, response.text)
                return False
            return True
        except Exception:
            logger.exception("Failed to sync EMQX node user %s", user_id)
            return False

    def _cleanup_stale_node_users(self, expected_user_ids: set[str]) -> tuple[int, int]:
        try:
            user_ids = emqx_service.list_user_ids()
        except Exception:
            logger.exception("Failed to list EMQX users for stale cleanup")
            return 0, 1

        deleted = 0
        failed = 0
        for user_id in user_ids:
            if not self._is_wfm_node_user(user_id) or user_id in expected_user_ids:
                continue
            try:
                response = emqx_service.delete_user(user_id=user_id)
                if response.status_code in {200, 204, 404}:
                    deleted += 1
                    self._disconnect_node_client(user_id)
                else:
                    failed += 1
                    logger.warning("Failed to delete stale EMQX node user %s: %s %s", user_id, response.status_code, response.text)
            except Exception:
                failed += 1
                logger.exception("Failed to delete stale EMQX node user %s", user_id)
        return deleted, failed

    @staticmethod
    def _is_wfm_node_user(user_id: str) -> bool:
        return user_id.startswith(WFM_NODE_USER_PREFIX)

    def _delete_node_user(self, node_id: str) -> bool:
        try:
            response = emqx_service.delete_node_user(node_id=node_id)
            if response.status_code in {200, 204, 404}:
                return True
            logger.warning("Failed to delete EMQX node user %s: %s %s", node_id, response.status_code, response.text)
            return False
        except Exception:
            logger.exception("Failed to delete EMQX node user %s", node_id)
            return False

    def _disconnect_node_client(self, node_id: str) -> bool:
        try:
            response = emqx_service.disconnect_node_client(node_id=node_id)
            if response.status_code in {200, 204, 404}:
                return True
            logger.warning("Failed to disconnect EMQX node client %s: %s %s", node_id, response.status_code, response.text)
            return False
        except Exception:
            logger.exception("Failed to disconnect EMQX node client %s", node_id)
            return False


emqx_reconcile_service = EmqxReconcileService()
