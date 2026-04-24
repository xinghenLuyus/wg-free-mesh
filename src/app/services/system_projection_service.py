from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from app.domain.models import Config, now_utc
from app.services.config_projection_service import ConfigProjectionSnapshot


class SystemProjectionService:
    def build(self, snapshots: Sequence[ConfigProjectionSnapshot], *, mqtt_status: str) -> dict[str, object]:
        invalid_configs: list[dict[str, object]] = []
        invalid_node_ids: set[str] = set()
        summary_configs = 0
        summary_nodes = 0
        summary_dynamic_nodes = 0
        summary_online_nodes = 0
        summary_pending_sync_nodes = 0

        for snapshot in snapshots:
            overview = snapshot.overview
            config = cast(Config, overview["config"])
            stats = cast(dict[str, object], overview["stats"])
            topology = cast(dict[str, object], overview["topology"])
            summary_configs += 1
            summary_nodes += cast(int, stats["total_nodes"])
            summary_dynamic_nodes += cast(int, stats["dynamic_nodes"])
            if config.enabled:
                summary_online_nodes += cast(int, stats["online_nodes"])
                summary_pending_sync_nodes += cast(int, stats["pending_sync_nodes"])
                if not bool(topology["valid"]):
                    topology_invalid_node_ids = cast(list[str], topology.get("invalid_node_ids", []))
                    invalid_node_ids.update(topology_invalid_node_ids)
                    invalid_configs.append(
                        {
                            "config_id": config.id,
                            "config_name": config.name,
                            "error_count": cast(int, topology["error_count"]),
                            "invalid_node_count": cast(int, topology["invalid_node_count"]),
                            "errors": cast(list[str], topology["errors"]),
                        }
                    )

        return {
            "summary": {
                "configs": summary_configs,
                "nodes": summary_nodes,
                "dynamic_nodes": summary_dynamic_nodes,
                "online_nodes": summary_online_nodes,
                "pending_sync_nodes": summary_pending_sync_nodes,
            },
            "topology": {
                "valid": not invalid_configs,
                "invalid_config_count": len(invalid_configs),
                "invalid_node_count": len(invalid_node_ids),
                "invalid_configs": invalid_configs,
            },
            "services": {"database": "ok", "mqtt": mqtt_status, "wireguard": "deferred"},
            "timestamp": now_utc(),
        }


system_projection_service = SystemProjectionService()
