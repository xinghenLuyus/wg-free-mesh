from __future__ import annotations

import secrets

from app.core.errors import AppError


def random_config_params() -> dict[str, object]:
    h_ranges = _random_non_overlapping_h_ranges()
    return {
        "awg_s1": secrets.randbelow(50) + 15,
        "awg_s2": secrets.randbelow(50) + 15,
        "awg_s3": secrets.randbelow(50) + 15,
        "awg_s4": secrets.randbelow(33),
        "awg_h1": h_ranges[0],
        "awg_h2": h_ranges[1],
        "awg_h3": h_ranges[2],
        "awg_h4": h_ranges[3],
    }


def random_node_params() -> dict[str, object]:
    jmin = secrets.randbelow(193) + 64
    jmax = secrets.randbelow(1024 - max(jmin + 1, 256) + 1) + max(jmin + 1, 256)
    return {
        "awg_jc": secrets.randbelow(7) + 4,
        "awg_jmin": jmin,
        "awg_jmax": jmax,
        "awg_i1": None,
        "awg_i2": None,
        "awg_i3": None,
        "awg_i4": None,
        "awg_i5": None,
    }


def validate_config_params(payload: dict[str, object]) -> dict[str, object]:
    values: dict[str, object] = {
        "awg_s1": _optional_int(payload.get("awg_s1"), "S1", 0, 64),
        "awg_s2": _optional_int(payload.get("awg_s2"), "S2", 0, 64),
        "awg_s3": _optional_int(payload.get("awg_s3"), "S3", 0, 64),
        "awg_s4": _optional_int(payload.get("awg_s4"), "S4", 0, 32),
        "awg_h1": _optional_h(payload.get("awg_h1"), "H1"),
        "awg_h2": _optional_h(payload.get("awg_h2"), "H2"),
        "awg_h3": _optional_h(payload.get("awg_h3"), "H3"),
        "awg_h4": _optional_h(payload.get("awg_h4"), "H4"),
    }
    ranges = [(_parse_h_range(str(value)), key) for key, value in values.items() if key.startswith("awg_h") and value]
    for index, (left, left_key) in enumerate(ranges):
        for right, right_key in ranges[index + 1:]:
            if left[0] <= right[1] and right[0] <= left[1]:
                raise AppError("INVALID_AWG_H_RANGE", f"{left_key.upper()} overlaps with {right_key.upper()}", 400)
    return values


def validate_node_params(payload: dict[str, object]) -> dict[str, object]:
    jmin = _optional_int(payload.get("awg_jmin"), "Jmin", 64, 1024)
    jmax = _optional_int(payload.get("awg_jmax"), "Jmax", 64, 1024)
    if jmin is not None and jmax is not None and jmax <= jmin:
        raise AppError("INVALID_AWG_J_RANGE", "Jmax must be greater than Jmin", 400)
    return {
        "awg_jc": _optional_int(payload.get("awg_jc"), "Jc", 0, 10),
        "awg_jmin": jmin,
        "awg_jmax": jmax,
        "awg_i1": _optional_text(payload.get("awg_i1")),
        "awg_i2": _optional_text(payload.get("awg_i2")),
        "awg_i3": _optional_text(payload.get("awg_i3")),
        "awg_i4": _optional_text(payload.get("awg_i4")),
        "awg_i5": _optional_text(payload.get("awg_i5")),
    }


def ensure_config_params(payload: dict[str, object]) -> dict[str, object]:
    random_values = random_config_params()
    cleaned = validate_config_params(payload)
    return {key: cleaned[key] if cleaned[key] is not None else random_values[key] for key in cleaned}


def ensure_node_params(payload: dict[str, object]) -> dict[str, object]:
    random_values = random_node_params()
    cleaned = validate_node_params(payload)
    for key in ("awg_jc", "awg_jmin", "awg_jmax"):
        if cleaned[key] is None:
            cleaned[key] = random_values[key]
    return cleaned


def empty_config_params() -> dict[str, object]:
    return {key: None for key in ("awg_s1", "awg_s2", "awg_s3", "awg_s4", "awg_h1", "awg_h2", "awg_h3", "awg_h4")}


def empty_node_params() -> dict[str, object]:
    return {
        key: None
        for key in (
            "awg_jc",
            "awg_jmin",
            "awg_jmax",
            "awg_i1",
            "awg_i2",
            "awg_i3",
            "awg_i4",
            "awg_i5",
        )
    }


def _optional_int(value: object, label: str, minimum: int, maximum: int) -> int | None:
    if value is None or value == "":
        return None
    parsed = int(str(value))
    if parsed < minimum or parsed > maximum:
        raise AppError("INVALID_AWG_PARAMETER", f"{label} must be between {minimum} and {maximum}", 400)
    return parsed


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_h(value: object, label: str) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    start, end = _parse_h_range(text)
    if start > end:
        raise AppError("INVALID_AWG_H_RANGE", f"{label} range start must not exceed end", 400)
    return text


def _parse_h_range(value: str) -> tuple[int, int]:
    parts = [item.strip() for item in value.split("-", 1)]
    try:
        start = int(parts[0])
        end = int(parts[1]) if len(parts) == 2 else start
    except ValueError as exc:
        raise AppError("INVALID_AWG_H_RANGE", "H value must be an integer or start-end range", 400) from exc
    if start < 0 or end > 4_294_967_295:
        raise AppError("INVALID_AWG_H_RANGE", "H range must be within uint32", 400)
    return start, end


def _random_non_overlapping_h_ranges() -> list[str]:
    ranges: list[tuple[int, int]] = []
    while len(ranges) < 4:
        start = secrets.randbelow(4_294_900_000) + 1024
        width = secrets.randbelow(512) + 64
        end = min(start + width, 4_294_967_295)
        if any(start <= existing_end and existing_start <= end for existing_start, existing_end in ranges):
            continue
        ranges.append((start, end))
    return [f"{start}-{end}" for start, end in ranges]
