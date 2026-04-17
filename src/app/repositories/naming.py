from __future__ import annotations

import re
from app.core.errors import AppError

CONFIG_NAME_RE = re.compile(r"^[a-zA-Z0-9_=+.-]{1,32}$")
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def validate_config_name(name: str) -> None:
    if not name.strip():
        raise AppError("INVALID_CONFIG_NAME", "名称不能为空", 400)
    if not CONFIG_NAME_RE.match(name):
        raise AppError("INVALID_CONFIG_NAME", "配置名称不是有效的 WireGuard 隧道名", 400)
    upper_name = name.upper()
    if upper_name in RESERVED_NAMES or upper_name.split(".", 1)[0] in RESERVED_NAMES:
        raise AppError("INVALID_CONFIG_NAME", "配置名称不能使用系统保留名", 400)


def config_artifact_name_segment(value: str, default: str) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    parts: list[str] = []
    for char in text:
        if char.isascii() and (char.isalnum() or char in "-_."):
            parts.append(char)
        else:
            parts.append(f"u{ord(char):04x}")
    encoded = "".join(parts).strip("-_.")
    return encoded or default


def node_config_artifact_stem(config_name: str, node_name: str) -> str:
    return (
        f"{config_artifact_name_segment(config_name, 'wireguard')}"
        f"-{config_artifact_name_segment(node_name, 'node')}"
    )
