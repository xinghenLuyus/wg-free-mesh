from __future__ import annotations

import ipaddress


def strip_required_text(value: str, label: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def strip_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def normalize_string_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = value.strip()
        if text:
            normalized.append(text)
    return normalized


def normalize_cidr(value: str | None, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    try:
        return str(ipaddress.ip_network(text, strict=False))
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid CIDR subnet") from exc
