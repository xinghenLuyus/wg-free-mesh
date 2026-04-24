from __future__ import annotations

import ipaddress
import json
import re
from collections.abc import Iterable
from sqlite3 import Row

from app.core.errors import AppError
from app.domain.models import ControlAction, NodeType


def int_value(value: object, default: int) -> int:
    if value is None or value == "":
        return default
    return int(str(value))


def int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(str(value))


def str_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def is_ipv6_literal(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value.strip("[]")), ipaddress.IPv6Address)
    except ValueError:
        return False


def endpoint_family_or_none(payload: dict[str, object]) -> str | None:
    if str(payload.get("endpoint_mode", "auto")) != "auto":
        return None
    family = str(payload.get("endpoint_ref_family") or "ipv4")
    return "ipv6" if family == "ipv6" else "ipv4"


def endpoint_family_value(value: object) -> str:
    return "ipv6" if str(value or "ipv4") == "ipv6" else "ipv4"


def link_payload(payload: dict[str, object], direction: str, row: Row | None = None) -> dict[str, object]:
    nested = payload.get(direction)
    if isinstance(nested, dict):
        return nested

    local_node_id = payload.get("local_node_id", row["local_node_id"] if row else None)
    peer_node_id = payload.get("peer_node_id", row["peer_node_id"] if row else None)
    if direction == "reverse" and row is None:
        local_node_id = payload.get("peer_node_id")
        peer_node_id = payload.get("local_node_id")

    return {
        "local_node_id": local_node_id,
        "peer_node_id": peer_node_id,
        "allowed_ips": payload.get(
            "allowed_ips_forward" if direction == "forward" else "allowed_ips_reverse",
            row["allowed_ips"] if row else None,
        ),
        "persistent_keepalive": payload.get("persistent_keepalive", row["persistent_keepalive"] if row else None),
        "preshared_key": payload.get("preshared_key", row["preshared_key"] if row else None),
        "endpoint_mode": payload.get("endpoint_mode", row["endpoint_mode"] if row else "auto"),
        "endpoint_ref_family": payload.get("endpoint_ref_family", row["endpoint_ref_family"] if row else "ipv4"),
        "endpoint_manual_host": payload.get("endpoint_manual_host", row["endpoint_manual_host"] if row else None),
        "endpoint_port_mode": payload.get("endpoint_port_mode", row["endpoint_port_mode"] if row else "ref_peer_listen_port"),
        "endpoint_manual_port": payload.get("endpoint_manual_port", row["endpoint_manual_port"] if row else None),
        "enabled": payload.get("enabled", row["enabled"] if row else True),
    }


def normalize_tags(tags: Iterable[object]) -> list[str]:
    normalized: list[str] = []
    for item in tags:
        tag = str(item).strip()
        if tag and tag not in normalized:
            normalized.append(tag)
    return sorted(normalized)


def payload_tags(value: object, default: Iterable[str] = ()) -> list[str]:
    if value is None:
        return normalize_tags(default)
    if isinstance(value, str):
        return normalize_tags([value])
    if isinstance(value, Iterable):
        return normalize_tags(value)
    return normalize_tags([value])


def node_type_value(value: object) -> NodeType:
    if isinstance(value, NodeType):
        return value
    return NodeType(str(value))


def control_action_value(value: object) -> ControlAction:
    if isinstance(value, ControlAction):
        return value
    return ControlAction(str(value))


def normalize_allowed_ips(value: str) -> str:
    tokens = [item.strip() for item in value.split(",") if item.strip()]
    if not tokens:
        raise AppError("INVALID_ALLOWED_IPS", "allowed_ips is required", 400)
    normalized: list[str] = []
    for token in tokens:
        try:
            ipaddress.ip_network(token, strict=False)
        except ValueError as exc:
            raise AppError("INVALID_ALLOWED_IPS", f"Invalid CIDR: {token}", 400) from exc
        if token not in normalized:
            normalized.append(token)
    return ",".join(normalized)


ALLOWED_TAG_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
