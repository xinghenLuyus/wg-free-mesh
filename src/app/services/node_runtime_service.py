from __future__ import annotations

from typing import Any

from app.domain.models import ControlStatus
from app.data.store import store
from app.services.realtime_service import realtime_service


def _payload(body: dict[str, Any]) -> dict[str, Any]:
    raw_payload = body.get("payload")
    return raw_payload if isinstance(raw_payload, dict) else {}


def _bool_payload(body: dict[str, Any], key: str, default: bool) -> bool:
    payload = _payload(body)
    value = payload.get(key, body.get(key, default))
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "online", "running"}


class NodeRuntimeService:
    async def apply_heartbeat(self, config_id: str, node_id: str, body: dict[str, Any], *, boot_id: str = "", session_id: str = "") -> None:
        store.record_client_heartbeat(
            config_id,
            node_id,
            boot_id=boot_id,
            session_id=session_id,
            client_online=_bool_payload(body, "client_online", True),
            wg_online=_bool_payload(body, "wg_online", False),
        )
        await self._publish_runtime_scope(config_id, node_id)

    async def apply_event(
        self,
        config_id: str,
        node_id: str,
        *,
        event: str,
        message: str = "",
        boot_id: str = "",
        session_id: str = "",
        request_id: str = "",
        action: str = "",
        output: str = "",
    ) -> None:
        store.record_client_event(config_id, node_id, event=event, message=message, boot_id=boot_id, session_id=session_id)
        detail = output or message
        if request_id:
            detail = f"request_id={request_id}\n{detail}".strip()
        log = store.append_client_event_log(
            config_id,
            node_id,
            summary=f"Client event: {event}",
            detail=detail,
        )
        await realtime_service.publish(
            "control.log.created",
            {"config_id": config_id, "node_id": node_id, "log": log.model_dump(mode="json")},
        )
        await self._publish_runtime_scope(config_id, node_id)

    async def apply_detect_ack(self, config_id: str, node_id: str, body: dict[str, Any], *, boot_id: str = "", session_id: str = "") -> None:
        client_online = _bool_payload(body, "client_online", True)
        wg_online = _bool_payload(body, "wg_online", False)
        store.record_detect_ack(config_id, node_id, boot_id=boot_id, session_id=session_id, client_online=client_online, wg_online=wg_online)
        await self._publish_runtime_scope(config_id, node_id)

    async def apply_generic_ack(self, config_id: str, node_id: str, *, boot_id: str = "", session_id: str = "") -> None:
        store.mark_client_reachable(config_id, node_id, reason="generic-ack", boot_id=boot_id, session_id=session_id)
        await self._publish_runtime_scope(config_id, node_id)

    async def apply_info_ack(
        self,
        config_id: str,
        node_id: str,
        body: dict[str, Any],
        *,
        boot_id: str = "",
        session_id: str = "",
    ) -> None:
        await self._apply_ack(config_id, node_id, body, default_action="wg_show", boot_id=boot_id, session_id=session_id)

    async def apply_control_ack(
        self,
        config_id: str,
        node_id: str,
        body: dict[str, Any],
        *,
        boot_id: str = "",
        session_id: str = "",
    ) -> None:
        await self._apply_ack(config_id, node_id, body, default_action="", boot_id=boot_id, session_id=session_id)

    async def apply_config_push_ack(
        self,
        config_id: str,
        node_id: str,
        body: dict[str, Any],
        *,
        boot_id: str = "",
        session_id: str = "",
    ) -> None:
        request_id = str(body.get("request_id") or "")
        if not request_id:
            store.mark_client_reachable(config_id, node_id, reason="config-push-ack", boot_id=boot_id, session_id=session_id)
            await self._publish_runtime_scope(config_id, node_id)
            return
        payload = _payload(body)
        status_text = str(payload.get("status") or "failed")
        message = str(payload.get("message") or status_text)
        try:
            row = store.confirm_config_push(request_id, status_text, message)
            await realtime_service.publish(
                "control.log.updated",
                {"config_id": config_id, "node_id": node_id, "log": row.model_dump(mode="json")},
            )
        except Exception:
            pass
        store.mark_client_reachable(config_id, node_id, reason="config-push-ack", boot_id=boot_id, session_id=session_id)
        await self._publish_runtime_scope(config_id, node_id)

    async def _apply_ack(
        self,
        config_id: str,
        node_id: str,
        body: dict[str, Any],
        *,
        default_action: str,
        boot_id: str = "",
        session_id: str = "",
    ) -> None:
        request_id = str(body.get("request_id") or "")
        if not request_id:
            reason = f"{default_action or 'control'}-ack"
            store.mark_client_reachable(config_id, node_id, reason=reason, boot_id=boot_id, session_id=session_id)
            await self._publish_runtime_scope(config_id, node_id)
            return
        payload = _payload(body)
        status_text = str(payload.get("status") or "acked")
        message = str(payload.get("message") or status_text)
        action = str(payload.get("action") or default_action)
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
            pass
        store.mark_client_reachable(
            config_id,
            node_id,
            reason=f"{action or default_action or 'control'}-ack",
            boot_id=boot_id,
            session_id=session_id,
        )
        await self._publish_runtime_scope(config_id, node_id)

    async def _publish_runtime_scope(self, config_id: str, node_id: str) -> None:
        from app.services.control_plane_service import control_plane_service

        try:
            await control_plane_service.publish_runtime_scope(config_id, node_id)
        except Exception:
            return


node_runtime_service = NodeRuntimeService()
