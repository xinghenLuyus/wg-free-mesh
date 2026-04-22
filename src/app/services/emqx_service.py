from __future__ import annotations

from typing import Any
from collections.abc import Sequence

import httpx

from app.core.config import settings
from app.services.mqtt_auth_service import mqtt_auth_service


class EmqxService:
    def __init__(self) -> None:
        self._base_url = settings.emqx_api_base_url.rstrip("/")
        self._auth = (settings.emqx_api_username, settings.emqx_api_password)

    def client_payload(
        self,
        *,
        username: str,
        password: str,
        client_id: str,
    ) -> dict[str, object]:
        return {
            "host": settings.mqtt_public_host,
            "port": settings.mqtt_bind_port,
            "tls": settings.mqtt_tls_enabled,
            "username": username,
            "password": password,
            "client_id": client_id,
        }

    def node_credentials_payload(self, *, config_id: str, node_id: str, password: str) -> dict[str, object]:
        return {
            **self.client_payload(
                username=mqtt_auth_service.node_username(node_id),
                password=password,
                client_id=mqtt_auth_service.node_client_id(node_id),
            ),
            "topics": mqtt_auth_service.allowed_topics(config_id, node_id),
        }

    def user_resource(self, username: str) -> str:
        return f"{self._base_url}/api/v5/authentication/password_based:built_in_database/users/{username}"

    def users_resource(self) -> str:
        return f"{self._base_url}/api/v5/authentication/password_based:built_in_database/users"

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
        params: dict[str, str | int | float | bool | None | Sequence[str | int | float | bool | None]] | None = None,
    ) -> httpx.Response:
        with httpx.Client(auth=self._auth, timeout=10.0) as client:
            return client.request(
                method,
                f"{self._base_url}{path}",
                json=json,
                params=params,
            )

    def ensure_user_payload(self, *, user_id: str, password: str) -> dict[str, object]:
        return {
            "user_id": user_id,
            "password": password,
            "is_superuser": False,
        }

    def authz_request_payload(
        self,
        *,
        username: str,
        clientid: str,
        topic: str,
        action: str,
    ) -> dict[str, str]:
        return {
            "username": username,
            "clientid": clientid,
            "topic": topic,
            "action": action,
        }

    def health_summary(self) -> dict[str, Any]:
        return {
            "api_base_url": self._base_url,
            "mqtt_host": settings.mqtt_public_host,
            "mqtt_port": settings.mqtt_bind_port,
            "mqtt_tls_enabled": settings.mqtt_tls_enabled,
        }

    def upsert_node_user(self, *, node_id: str, password: str) -> httpx.Response:
        user_id = mqtt_auth_service.node_username(node_id)
        payload = self.ensure_user_payload(user_id=user_id, password=password)
        response = self.request("PUT", f"/api/v5/authentication/password_based:built_in_database/users/{user_id}", json=payload)
        if response.status_code == 404:
            return self.request("POST", "/api/v5/authentication/password_based:built_in_database/users", json=payload)
        return response

    def delete_node_user(self, *, node_id: str) -> httpx.Response:
        user_id = mqtt_auth_service.node_username(node_id)
        return self.request("DELETE", f"/api/v5/authentication/password_based:built_in_database/users/{user_id}")


emqx_service = EmqxService()
