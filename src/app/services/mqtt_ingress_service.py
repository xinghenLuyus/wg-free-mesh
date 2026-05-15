from __future__ import annotations

import asyncio
import json
import ssl
from typing import Any
from urllib.parse import urlparse
from datetime import UTC, datetime
from uuid import uuid4

import aiomqtt

from app.core.config import settings
from app.data.store import store
from app.services.emqx_service import emqx_service
from app.services.node_runtime_service import node_runtime_service
from app.services.realtime_service import realtime_service

DETECT_INTERVAL_SECONDS = 120
DETECT_ACK_TIMEOUT_SECONDS = 10


class MqttIngressService:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._detect_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._client: aiomqtt.Client | None = None
        self._connected = False
        self._last_error = ""
        self._last_connected_at: str | None = None

    async def _publish_system_status_update(self) -> None:
        from app.services.control_plane_service import control_plane_service

        await control_plane_service.publish_system_status()

    async def _apply_status(
        self,
        *,
        connected: bool | None = None,
        last_error: str | None = None,
        last_connected_at: str | None = None,
    ) -> None:
        changed = False
        if connected is not None and self._connected != connected:
            self._connected = connected
            changed = True
        if last_error is not None and self._last_error != last_error:
            self._last_error = last_error
            changed = True
        if last_connected_at is not None and self._last_connected_at != last_connected_at:
            self._last_connected_at = last_connected_at
            changed = True
        if changed:
            await self._publish_system_status_update()

    def is_enabled(self) -> bool:
        return settings.enable_mqtt_services

    def status_summary(self) -> dict[str, object]:
        if not settings.enable_mqtt_services:
            return {"enabled": False, "connected": False, "status": "disabled", "last_error": "", "last_connected_at": None}
        if not self.is_enabled():
            return {"enabled": False, "connected": False, "status": "disabled", "last_error": "", "last_connected_at": None}
        return {
            "enabled": True,
            "connected": self._connected,
            "status": "connected" if self._connected else "error" if self._last_error else "connecting",
            "last_error": self._last_error,
            "last_connected_at": self._last_connected_at,
        }

    def startup(self) -> None:
        if not self.is_enabled():
            self._connected = False
            self._last_error = ""
            return
        if self._task is None or self._task.done():
            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(self._run(), name="wfm-mqtt-ingress")
        if self._detect_task is None or self._detect_task.done():
            self._detect_task = asyncio.create_task(self._detect_loop(), name="wfm-mqtt-detect")

    async def shutdown(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._detect_task is not None:
            self._detect_task.cancel()
            try:
                await self._detect_task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._detect_task = None
        self._client = None
        await self._apply_status(connected=False)

    async def reconcile(self) -> None:
        if self.is_enabled():
            self.startup()
            return
        await self.shutdown()

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            if not self.is_enabled():
                await self._apply_status(connected=False, last_error="")
                return
            try:
                try:
                    response = await asyncio.to_thread(emqx_service.upsert_server_user)
                    if response.status_code >= 400:
                        await self._apply_status(
                            connected=False,
                            last_error=f"Failed to sync MQTT server user ({response.status_code})",
                        )
                        await asyncio.sleep(5)
                        continue
                except Exception:
                    await self._apply_status(connected=False, last_error="Failed to sync MQTT server user")
                    await asyncio.sleep(5)
                    continue
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                await self._apply_status(connected=False, last_error="MQTT ingress connection loop failed")
                await asyncio.sleep(5)

    async def _connect_once(self) -> None:
        parsed = urlparse(settings.mqtt_url)
        hostname = parsed.hostname or "localhost"
        port = parsed.port or (8883 if parsed.scheme in {"mqtts", "ssl"} else 1883)
        tls_context: ssl.SSLContext | None = None
        if parsed.scheme in {"mqtts", "ssl"}:
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
            await self._apply_status(connected=True, last_error="", last_connected_at=datetime.now(UTC).isoformat())
            for topic in (
                "wfm/+/+/heartbeat",
                "wfm/+/+/event",
                "wfm/+/+/detect/ack",
                "wfm/+/+/info/ack",
                "wfm/+/+/config/push/ack",
                "wfm/+/+/control/ack",
            ):
                await client.subscribe(topic)
            async for message in client.messages:
                await self._handle_message(str(message.topic), bytes(message.payload))
        self._client = None
        await self._apply_status(connected=False)

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
            await node_runtime_service.apply_heartbeat(config_id, node_id, body, boot_id=boot_id, session_id=session_id)
        elif kind == "event":
            raw_payload = body.get("payload")
            nested = raw_payload if isinstance(raw_payload, dict) else {}
            event = str(nested.get("event") or body.get("event") or "event")
            message = str(nested.get("message") or body.get("message") or "")
            request_id = str(nested.get("request_id") or body.get("request_id") or "")
            action = str(nested.get("action") or body.get("action") or "")
            output = str(nested.get("output") or body.get("output") or "")
            await node_runtime_service.apply_event(
                config_id,
                node_id,
                event=event,
                message=message,
                boot_id=boot_id,
                session_id=session_id,
                request_id=request_id,
                action=action,
                output=output,
            )
        elif kind.endswith("/ack"):
            if kind == "detect/ack":
                await node_runtime_service.apply_detect_ack(config_id, node_id, body, boot_id=boot_id, session_id=session_id)
                return
            if kind == "info/ack":
                await node_runtime_service.apply_info_ack(config_id, node_id, body, boot_id=boot_id, session_id=session_id)
                return
            if kind == "control/ack":
                await node_runtime_service.apply_control_ack(config_id, node_id, body, boot_id=boot_id, session_id=session_id)
                return
            if kind == "config/push/ack":
                await node_runtime_service.apply_config_push_ack(config_id, node_id, body, boot_id=boot_id, session_id=session_id)
                return
            await node_runtime_service.apply_generic_ack(config_id, node_id, boot_id=boot_id, session_id=session_id)
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

    async def _detect_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=DETECT_INTERVAL_SECONDS)
                break
            except asyncio.TimeoutError:
                pass
            if not self.is_enabled() or self._client is None or realtime_service.subscriber_count <= 0:
                continue
            await self._probe_bound_clients()

    async def _probe_bound_clients(self) -> None:
        store.reconcile_client_timeouts()
        targets = store.list_detect_targets()
        if not targets:
            return
        await asyncio.gather(*(self._probe_target(item["config_id"], item["node_id"]) for item in targets))

    async def _probe_target(self, config_id: str, node_id: str) -> None:
        request_id = uuid4().hex
        store.record_detect_sent(config_id, node_id)
        payload = {
            "type": "detect",
            "request_id": request_id,
            "config_id": config_id,
            "node_id": node_id,
            "boot_id": "",
            "session_id": "",
            "sent_at": datetime.now(UTC).isoformat(),
            "payload": {},
        }
        try:
            await self.publish_to_node(config_id=config_id, node_id=node_id, kind="detect", payload=payload)
        except Exception:
            store.record_detect_timeout(config_id, node_id)
            await node_runtime_service._publish_runtime_scope(config_id, node_id)
            return
        await asyncio.sleep(DETECT_ACK_TIMEOUT_SECONDS)
        runtime = store.get_runtime(config_id, node_id)
        if runtime.last_probe_ack_at is None or runtime.last_probe_sent_at is None or runtime.last_probe_ack_at < runtime.last_probe_sent_at:
            store.record_detect_timeout(config_id, node_id)
            await node_runtime_service._publish_runtime_scope(config_id, node_id)

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
