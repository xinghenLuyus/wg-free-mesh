from __future__ import annotations

from typing import Any

from app.domain.models import ControlStatus
from app.repositories.sqlite import store
from app.services.realtime_service import realtime_service


class NodeRuntimeService:
    async def apply_heartbeat(self, config_id: str, node_id: str, *, boot_id: str = "", session_id: str = "") -> None:
        store.record_client_heartbeat(config_id, node_id, boot_id=boot_id, session_id=session_id)
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
    ) -> None:
        store.record_client_event(config_id, node_id, event=event, message=message, boot_id=boot_id, session_id=session_id)
        log = store.append_client_event_log(
            config_id,
            node_id,
            summary=f"Client event: {event}",
            detail=message,
        )
        await realtime_service.publish(
            "control.log.created",
            {"config_id": config_id, "node_id": node_id, "log": log.model_dump(mode="json")},
        )
        await self._publish_runtime_scope(config_id, node_id)

    async def apply_detect_ack(self, config_id: str, node_id: str, *, boot_id: str = "", session_id: str = "") -> None:
        store.record_client_heartbeat(config_id, node_id, boot_id=boot_id, session_id=session_id)
        store.record_detect_ack(config_id, node_id, boot_id=boot_id, session_id=session_id)
        await self._publish_runtime_scope(config_id, node_id)

    async def apply_generic_ack(self, config_id: str, node_id: str, *, boot_id: str = "", session_id: str = "") -> None:
        store.record_client_heartbeat(config_id, node_id, boot_id=boot_id, session_id=session_id)
        await self._publish_runtime_scope(config_id, node_id)

    async def apply_control_ack(self, config_id: str, node_id: str, body: dict[str, Any]) -> None:
        request_id = str(body.get("request_id") or "")
        if not request_id:
            await self._publish_runtime_scope(config_id, node_id)
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
            pass
        await self._publish_runtime_scope(config_id, node_id)

    async def _publish_runtime_scope(self, config_id: str, node_id: str) -> None:
        from app.services.control_plane_service import control_plane_service

        try:
            await control_plane_service.publish_runtime_scope(config_id, node_id)
        except Exception:
            return


node_runtime_service = NodeRuntimeService()
