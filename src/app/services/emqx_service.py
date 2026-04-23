from __future__ import annotations

from typing import Any
from collections.abc import Sequence

import httpx

from app.core.config import settings
from app.services.mqtt_auth_service import mqtt_auth_service


class EmqxService:
    def __init__(self) -> None:
        self._base_url = settings.emqx_api_base_url.rstrip("/")
        self._auth = (settings.emqx_username, settings.emqx_password)

    def client_payload(
        self,
        *,
        username: str,
        password: str,
        client_id: str,
    ) -> dict[str, object]:
        from app.repositories.sqlite import store

        mqtt_settings = store.read_setting_json(
            "mqtt_client",
            {
                "host": settings.mqtt_public_host,
                "port": settings.mqtt_bind_port,
                "tls": settings.mqtt_tls_enabled,
            },
        )
        raw_port = mqtt_settings.get("port") or settings.mqtt_bind_port
        port = int(str(raw_port))
        return {
            "host": str(mqtt_settings.get("host") or settings.mqtt_public_host),
            "port": port,
            "tls": bool(mqtt_settings.get("tls", settings.mqtt_tls_enabled)),
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

    def create_user_payload(self, *, user_id: str, password: str, is_superuser: bool = False) -> dict[str, object]:
        return {
            "user_id": user_id,
            "password": password,
            "is_superuser": is_superuser,
        }

    def update_user_payload(self, *, password: str, is_superuser: bool = False) -> dict[str, object]:
        return {
            "password": password,
            "is_superuser": is_superuser,
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
        create_payload = self.create_user_payload(user_id=user_id, password=password)
        response = self.request("POST", "/api/v5/authentication/password_based:built_in_database/users", json=create_payload)
        if response.status_code == 409:
            update_payload = self.update_user_payload(password=password)
            return self.request(
                "PUT",
                f"/api/v5/authentication/password_based:built_in_database/users/{user_id}",
                json=update_payload,
            )
        return response

    def upsert_server_user(self) -> httpx.Response:
        create_payload = self.create_user_payload(
            user_id=settings.emqx_username,
            password=settings.emqx_password,
            is_superuser=True,
        )
        response = self.request("POST", "/api/v5/authentication/password_based:built_in_database/users", json=create_payload)
        if response.status_code == 409:
            update_payload = self.update_user_payload(password=settings.emqx_password, is_superuser=True)
            return self.request(
                "PUT",
                f"/api/v5/authentication/password_based:built_in_database/users/{settings.emqx_username}",
                json=update_payload,
            )
        return response

    def delete_node_user(self, *, node_id: str) -> httpx.Response:
        user_id = mqtt_auth_service.node_username(node_id)
        return self.request("DELETE", f"/api/v5/authentication/password_based:built_in_database/users/{user_id}")


emqx_service = EmqxService()
