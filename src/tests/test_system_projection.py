from app.domain.models import Config, Node, NodeType
from app.services.config_projection_service import ConfigProjectionSnapshot
from app.services.system_projection_service import SystemProjectionService


def _snapshot(config: Config, nodes: list[Node], sync_status: list[dict[str, object]]) -> ConfigProjectionSnapshot:
    return ConfigProjectionSnapshot(
        config_id=config.id,
        overview={
            "config": config,
            "stats": {
                "total_nodes": len(nodes),
                "dynamic_nodes": len([node for node in nodes if node.node_type == NodeType.dynamic]),
                "online_nodes": 0,
            },
            "nodes": nodes,
            "sync_status": sync_status,
            "topology": {
                "valid": True,
                "error_count": 0,
                "invalid_node_count": 0,
                "invalid_node_ids": [],
                "errors": [],
            },
        },
        tags=[],
    )


def test_system_status_reports_only_auto_sync_enabled_sync_issues() -> None:
    config = Config(id="cfg_test", name="test")
    dynamic_issue = Node(config_id=config.id, id="node_dynamic", name="dynamic", public_key="pub", private_key="priv")
    static_issue = Node(
        config_id=config.id,
        id="node_static",
        name="static",
        node_type=NodeType.static,
        public_key="pub",
        private_key="priv",
    )
    manual_node = Node(
        config_id=config.id,
        id="node_manual",
        name="manual",
        auto_sync=False,
        public_key="pub",
        private_key="priv",
    )
    disabled_node = Node(
        config_id=config.id,
        id="node_disabled",
        name="disabled",
        enabled=False,
        public_key="pub",
        private_key="priv",
    )
    snapshot = _snapshot(
        config,
        [dynamic_issue, static_issue, manual_node, disabled_node],
        [
            {"node_id": dynamic_issue.id, "node_name": dynamic_issue.name, "node_type": "dynamic", "status": "pending", "topology_valid": True, "topology_messages": []},
            {"node_id": static_issue.id, "node_name": static_issue.name, "node_type": "static", "status": "pending", "topology_valid": True, "topology_messages": []},
            {"node_id": manual_node.id, "node_name": manual_node.name, "node_type": "dynamic", "status": "pending", "topology_valid": True, "topology_messages": []},
            {"node_id": disabled_node.id, "node_name": disabled_node.name, "node_type": "dynamic", "status": "pending", "topology_valid": True, "topology_messages": []},
        ],
    )

    status = SystemProjectionService().build([snapshot], mqtt_status="disabled")

    issues = status["sync"]["issues"]
    assert status["sync"]["issue_count"] == 2
    assert {item["node_id"] for item in issues} == {dynamic_issue.id, static_issue.id}
    assert "pending_sync_nodes" not in status["summary"]
