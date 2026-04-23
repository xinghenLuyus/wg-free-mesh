from __future__ import annotations

import asyncio
import json
import ssl
from typing import Any
from urllib.parse import urlparse

import aiomqtt

from app.core.config import settings
from app.domain.models import ControlStatus
from app.repositories.sqlite import store
from app.services.emqx_service import emqx_service
from app.services.realtime_service import realtime_service


def _dump(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[attr-defined]
    return value


class MqttIngressService:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._client: aiomqtt.Client | None = None

    def startup(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(self._run(), name="wfm-mqtt-ingress")

    async def shutdown(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                try:
                    response = await asyncio.to_thread(emqx_service.upsert_server_user)
                    if response.status_code >= 400:
                        await asyncio.sleep(5)
                        continue
                except Exception:
                    await asyncio.sleep(5)
                    continue
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)

    async def _connect_once(self) -> None:
        parsed = urlparse(settings.mqtt_url)
        hostname = parsed.hostname or "localhost"
        port = parsed.port or (8883 if parsed.scheme in {"mqtts", "ssl"} else 1883)
        tls_context: ssl.SSLContext | None = None
        if parsed.scheme in {"mqtts", "ssl"} or settings.mqtt_tls_enabled:
            tls_context = ssl.create_default_context()
            tls_context.check_hostname = False
            tls_context.verify_mode = ssl.CERT_NONE

        async with aiomqtt.Client(
            hostname=hostname,
            port=port,
            username=settings.emqx_username,
            password=settings.emqx_password,
            tls_context=tls_context,
        ) as client:
            self._client = client
            for topic in (
                "wfm/+/+/heartbeat",
                "wfm/+/+/event",
                "wfm/+/+/detect/ack",
                "wfm/+/+/config/push/ack",
                "wfm/+/+/control/ack",
            ):
                await client.subscribe(topic)
            async for message in client.messages:
                await self._handle_message(str(message.topic), bytes(message.payload))
        self._client = None

    async def _handle_message(self, topic: str, payload: bytes) -> None:
        parts = topic.split("/")
        if len(parts) < 4 or parts[0] != "wfm":
            return
        config_id, node_id = parts[1], parts[2]
        kind = "/".join(parts[3:])
        body = self._decode_payload(payload)
        boot_id = str(body.get("boot_id") or "")
        session_id = str(body.get("session_id") or "")
        if kind == "heartbeat":
            store.record_client_heartbeat(config_id, node_id, boot_id=boot_id, session_id=session_id)
        elif kind == "event":
            raw_payload = body.get("payload")
            nested = raw_payload if isinstance(raw_payload, dict) else {}
            event = str(nested.get("event") or body.get("event") or "event")
            message = str(nested.get("message") or body.get("message") or "")
            store.record_client_event(config_id, node_id, event=event, message=message, boot_id=boot_id, session_id=session_id)
        elif kind.endswith("/ack"):
            store.record_client_heartbeat(config_id, node_id, boot_id=boot_id, session_id=session_id)
            if kind == "control/ack":
                await self._handle_control_ack(config_id, node_id, body)
        await self._publish_node_state(config_id, node_id)

    async def _handle_control_ack(self, config_id: str, node_id: str, body: dict[str, Any]) -> None:
        request_id = str(body.get("request_id") or "")
        if not request_id:
            return
        raw_payload = body.get("payload")
        payload = raw_payload if isinstance(raw_payload, dict) else {}
        status_text = str(payload.get("status") or "acked")
        message = str(payload.get("message") or status_text)
        action = str(payload.get("action") or "")
        status = ControlStatus.failed if status_text == "failed" else ControlStatus.acked
        try:
            if status is ControlStatus.acked and action in {"start", "stop"}:
                row = store.complete_control_log(request_id, status, message)
                store.apply_control_action(row.config_id, row.node_id, action)
            else:
                row = store.complete_control_log(request_id, status, message)
            await realtime_service.publish(
                "control.log.updated",
                {"config_id": config_id, "node_id": node_id, "log": row.model_dump(mode="json")},
            )
        except Exception:
            return

    @staticmethod
    def _decode_payload(payload: bytes) -> dict[str, Any]:
        if not payload:
            return {}
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    async def _publish_node_state(self, config_id: str, node_id: str) -> None:
        try:
            status = store.get_node_endpoint_status(config_id, node_id)
        except Exception:
            return
        await realtime_service.publish(
            "endpoint.status.updated",
            {
                "config_id": config_id,
                "node_id": node_id,
                "status": {
                    "node": _dump(status["node"]),
                    "runtime": _dump(status["runtime"]),
                    "client_state": status["client_state"],
                    "config_state": status["config_state"],
                    "last_control": _dump(status["last_control"]) if status["last_control"] else None,
                },
            },
        )
        await realtime_service.publish("system.status.updated", store.system_status())

    async def publish_to_node(
        self,
        *,
        config_id: str,
        node_id: str,
        kind: str,
        payload: dict[str, Any],
    ) -> None:
        if self._client is None:
            raise RuntimeError("MQTT ingress client is not connected")
        topic = f"wfm/{config_id}/{node_id}/{kind}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        await self._client.publish(topic, payload=body, qos=1)


mqtt_ingress_service = MqttIngressService()
