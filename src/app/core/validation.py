from __future__ import annotations


def strip_required_text(value: str, label: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{label}不能为空")
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
