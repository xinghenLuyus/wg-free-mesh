from __future__ import annotations

import base64
import re
import secrets

from app.core.errors import AppError
from app.domain.awg_signatures import packet_chain


VERSIONS = ("1.5", "2.0", "3.1")
CONFIG_OPTIONS = {"header_protection_key": "HeaderProtectionKey", "random_trailers": "RandomTrailers"}
RANDOM_OPTIONS = {"_random_direction": ("generic", "dns", "stun", "rtp", "quic"), "_random_intensity": ("low", "balanced", "high")}
NODE_OPTIONS = {
    "content_padding_addition": "ContentPaddingAddition",
    "rekey_after_time": "RekeyAfterTime",
    "rekey_timeout": "RekeyTimeout",
    "reject_after_time": "RejectAfterTime",
    "keepalive_timeout": "KeepaliveTimeout",
    "max_handshake_attempts": "MaxHandshakeAttempts",
    "random_trailers": "RandomTrailers",
    "disable_cookies": "DisableCookies",
}
LEGACY_OPTIONS = {"j1": "J1", "j2": "J2", "j3": "J3", "itime": "Itime"}


def version_value(value: object) -> str:
    version = str(value or "2.0")
    if version not in VERSIONS:
        raise AppError("INVALID_AWG_VERSION", "Unsupported AmneziaWG version", 400)
    return version


def wire_protocol(value: object) -> str:
    return "amneziawg_2" if str(value) in ("amneziawg", "amneziawg_2") else "wireguard"


def protocol_options() -> dict[str, object]:
    return {
        "default_awg_version": "3.1",
        "awg_versions": list(VERSIONS),
        "versions": {
            version: {
                "s_fields": ["awg_s1", "awg_s2"] if version == "1.5" else [f"awg_s{i}" for i in range(1, 5)],
                "h_format": "integer" if version == "1.5" else "range",
                "config_options": CONFIG_OPTIONS if version == "3.1" else {},
                "node_options": {key: label for key, label in NODE_OPTIONS.items() if key != "random_trailers"} if version == "3.1" else LEGACY_OPTIONS if version == "1.5" else {},
            } for version in VERSIONS
        },
    }


def merge_options(payload: dict[str, object], current: dict[str, object], version: str, config: bool) -> dict[str, object]:
    baseline = current.get("awg_options") or {}
    raw = payload.get("awg_options")
    if raw is None:
        return dict(baseline)
    if not isinstance(raw, dict):
        raise AppError("INVALID_AWG_PARAMETER", "AWG options must be an object", 400)
    supported = CONFIG_OPTIONS if config and version == "3.1" else NODE_OPTIONS if not config and version == "3.1" else LEGACY_OPTIONS if not config and version == "1.5" else {}
    if config:
        supported = {**supported, **RANDOM_OPTIONS}
    for key, value in raw.items():
        if key not in supported and value != baseline.get(key):
            raise AppError("INVALID_AWG_PARAMETER", f"{key} is not supported by AWG {version}", 400)
    return {**baseline, **raw}


def _options(payload: dict[str, object], config: bool, version: str) -> dict[str, object]:
    raw = payload.get("awg_options")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise AppError("INVALID_AWG_PARAMETER", "AWG options must be an object", 400)
    known = {**CONFIG_OPTIONS, **RANDOM_OPTIONS} if config else {**NODE_OPTIONS, **LEGACY_OPTIONS}
    if set(raw) - set(known):
        raise AppError("INVALID_AWG_PARAMETER", "Unknown AWG option", 400)
    values: dict[str, object] = {}
    for key, value in raw.items():
        if value is None or value == "":
            values[key] = None
        elif key in RANDOM_OPTIONS:
            if value not in RANDOM_OPTIONS[key]:
                raise AppError("INVALID_AWG_PARAMETER", f"Invalid {key}", 400)
            values[key] = value
        elif key == "header_protection_key":
            try:
                decoded = base64.b64decode(str(value), validate=True)
            except (ValueError, TypeError) as exc:
                raise AppError("INVALID_AWG_PARAMETER", "HeaderProtectionKey must be a 32-byte base64 key", 400) from exc
            if len(decoded) != 32 or not any(decoded):
                raise AppError("INVALID_AWG_PARAMETER", "HeaderProtectionKey must be a nonzero 32-byte key", 400)
            values[key] = str(value)
        elif key in ("random_trailers", "disable_cookies"):
            if not isinstance(value, bool):
                raise AppError("INVALID_AWG_PARAMETER", f"{key} must be boolean", 400)
            values[key] = value
        elif key in LEGACY_OPTIONS:
            values[key] = _optional_int(value, "Itime", 0, 4_294_967_295) if key == "itime" else _optional_text(value)
            if key != "itime":
                _validate_cps(str(value))
        else:
            text = str(value).strip()
            if not re.fullmatch(r"\d+(?:-\d+)?", text):
                raise AppError("INVALID_AWG_PARAMETER", f"{key} must be an integer or range", 400)
            start, end = _parse_h_range(text)
            if start > end or end > 65535:
                raise AppError("INVALID_AWG_PARAMETER", f"{key} range must be within uint16", 400)
            values[key] = text
    if not config and version == "3.1":
        rekey = values.get("rekey_after_time")
        reject = values.get("reject_after_time")
        if rekey and reject:
            _, rekey_end = _parse_h_range(str(rekey))
            reject_start, _ = _parse_h_range(str(reject))
            if rekey_end and reject_start and reject_start <= rekey_end:
                raise AppError("INVALID_AWG_PARAMETER", "RejectAfterTime must exceed RekeyAfterTime", 400)
    return values


def _validate_cps(value: str) -> None:
    if not value:
        return
    tags = re.findall(r"<(?:b 0x[0-9a-fA-F]+|t|(?:r|rc|rd) \d+)>", value)
    if "".join(tags) != value or tags.count("<t>") > 1:
        raise AppError("INVALID_AWG_PARAMETER", "Invalid CPS expression", 400)
    for tag in tags:
        if tag.startswith("<b ") and len(tag[5:-1]) % 2:
            raise AppError("INVALID_AWG_PARAMETER", "CPS hex bytes must have even length", 400)
        if re.match(r"<(r|rc|rd) ", tag) and int(tag.split()[1][:-1]) > 1000:
            raise AppError("INVALID_AWG_PARAMETER", "CPS random length must not exceed 1000", 400)


def random_config_params(version: str = "2.0") -> dict[str, object]:
    version = version_value(version)
    h_ranges = _random_non_overlapping_h_ranges()
    values: dict[str, object] = {
        "awg_s1": secrets.randbelow(50) + 15,
        "awg_s2": secrets.randbelow(50) + 15,
        "awg_s3": secrets.randbelow(50) + 15,
        "awg_s4": secrets.randbelow(33),
        "awg_h1": h_ranges[0],
        "awg_h2": h_ranges[1],
        "awg_h3": h_ranges[2],
        "awg_h4": h_ranges[3],
    }
    if version == "1.5":
        values.update(awg_s3=0, awg_s4=0)
        values.update({f"awg_h{i}": value.split("-", 1)[0] for i, value in enumerate(h_ranges, 1)})
    elif version == "3.1":
        prefix = secrets.randbelow(17) + 16
        values.update({f"awg_s{i}": prefix for i in range(1, 5)})
        values.update({f"awg_h{i}": value.split("-", 1)[0] for i, value in enumerate(h_ranges, 1)})
    return values


def random_node_params(version: str = "2.0", direction: str = "generic", intensity: str = "balanced") -> dict[str, object]:
    version = version_value(version)
    _validate_strategy(direction, intensity)
    count_min, count_max, size_max = {"low": (1, 3, 256), "balanced": (4, 7, 768), "high": (8, 10, 1024)}[intensity]
    jmin = _randint(64, min(256, size_max - 1))
    jmax = _randint(jmin + 1, size_max)
    i_packets = packet_chain(direction, intensity)
    return {
        "awg_jc": _randint(count_min, count_max),
        "awg_jmin": jmin,
        "awg_jmax": jmax,
        "awg_i1": i_packets[0],
        "awg_i2": i_packets[1],
        "awg_i3": i_packets[2],
        "awg_i4": i_packets[3],
        "awg_i5": i_packets[4],
    }


def validate_config_params(payload: dict[str, object], version: str = "2.0") -> dict[str, object]:
    version = version_value(version)
    values: dict[str, object] = {
        "awg_s1": _optional_int(payload.get("awg_s1"), "S1", 0, 65535),
        "awg_s2": _optional_int(payload.get("awg_s2"), "S2", 0, 65535),
        "awg_s3": _optional_int(payload.get("awg_s3"), "S3", 0, 65535),
        "awg_s4": _optional_int(payload.get("awg_s4"), "S4", 0, 65535),
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
    if version == "1.5":
        if values["awg_s3"] not in (None, 0) or values["awg_s4"] not in (None, 0):
            raise AppError("INVALID_AWG_PARAMETER", "AWG 1.5 compatibility mode requires S3=S4=0", 400)
        if any(value and "-" in str(value) for key, value in values.items() if key.startswith("awg_h")):
            raise AppError("INVALID_AWG_H_RANGE", "AWG 1.5 requires fixed H values", 400)
        if values["awg_s1"] is not None and values["awg_s2"] == int(str(values["awg_s1"])) + 56:
            raise AppError("INVALID_AWG_PARAMETER", "Init and response packet sizes must differ", 400)
    options = _options(payload, True, version)
    if version == "3.1" and options.get("header_protection_key"):
        if any(value is None or int(str(value)) < 12 for key, value in values.items() if key.startswith("awg_s")):
            raise AppError("INVALID_AWG_PARAMETER", "Header Protection requires S1-S4 >= 12", 400)
    values["awg_options"] = options
    return values


def validate_node_params(payload: dict[str, object], version: str = "2.0") -> dict[str, object]:
    version = version_value(version)
    jmin = _optional_int(payload.get("awg_jmin"), "Jmin", 0, 65535)
    jmax = _optional_int(payload.get("awg_jmax"), "Jmax", 0, 65535)
    if jmin is not None and jmax is not None and jmax <= jmin:
        raise AppError("INVALID_AWG_J_RANGE", "Jmax must be greater than Jmin", 400)
    values = {
        "awg_jc": _optional_int(payload.get("awg_jc"), "Jc", 0, 65535),
        "awg_jmin": jmin,
        "awg_jmax": jmax,
        "awg_i1": _optional_text(payload.get("awg_i1")),
        "awg_i2": _optional_text(payload.get("awg_i2")),
        "awg_i3": _optional_text(payload.get("awg_i3")),
        "awg_i4": _optional_text(payload.get("awg_i4")),
        "awg_i5": _optional_text(payload.get("awg_i5")),
    }
    for key, value in values.items():
        if key.startswith("awg_i") and value:
            _validate_cps(str(value))
    return {**values, "awg_options": _options(payload, False, version)}


def ensure_config_params(payload: dict[str, object], version: str = "2.0") -> dict[str, object]:
    random_values = random_config_params(version)
    combined = {**random_values, **{key: value for key, value in payload.items() if value is not None and value != ""}}
    options = _options(payload, True, version)
    if version == "3.1" and "header_protection_key" not in options:
        options["header_protection_key"] = base64.b64encode(secrets.token_bytes(32)).decode()
    combined["awg_options"] = options
    return validate_config_params(combined, version)


def ensure_node_params(payload: dict[str, object], version: str = "2.0", config_options: dict[str, object] | None = None) -> dict[str, object]:
    config_options = config_options or {}
    random_values = random_node_params(version, str(config_options.get("_random_direction") or "generic"), str(config_options.get("_random_intensity") or "balanced"))
    cleaned = validate_node_params(payload, version)
    if cleaned["awg_jmin"] is not None and cleaned["awg_jmax"] is None:
        lower = int(str(cleaned["awg_jmin"]))
        if lower == 65535:
            raise AppError("INVALID_AWG_J_RANGE", "No Jmax above Jmin within uint16", 400)
        random_values["awg_jmax"] = _randint(lower + 1, min(65535, max(lower + 128, int(str(random_values["awg_jmax"])))))
    elif cleaned["awg_jmin"] is None and cleaned["awg_jmax"] is not None:
        upper = int(str(cleaned["awg_jmax"]))
        if upper == 0:
            raise AppError("INVALID_AWG_J_RANGE", "No Jmin below Jmax within uint16", 400)
        random_values["awg_jmin"] = _randint(0, min(upper - 1, int(str(random_values["awg_jmin"]))))
    for key in cleaned:
        if cleaned[key] is None:
            cleaned[key] = random_values[key]
    if version == "3.1":
        options = {"random_trailers": config_options.get("random_trailers", True), "disable_cookies": False, **_random_node_options(str(config_options.get("_random_intensity") or "balanced")), **dict(cleaned["awg_options"])}
        cleaned["awg_options"] = options
    elif version == "1.5":
        cleaned["awg_options"] = {**_random_legacy_options(), **dict(cleaned["awg_options"])}
    return validate_node_params(cleaned, version)


def _randint(start: int, end: int) -> int:
    return start + secrets.randbelow(end - start + 1)


def _validate_strategy(direction: str, intensity: str) -> None:
    if direction not in RANDOM_OPTIONS["_random_direction"] or intensity not in RANDOM_OPTIONS["_random_intensity"]:
        raise AppError("INVALID_AWG_PARAMETER", "Invalid AWG generation strategy", 400)


def _random_node_options(intensity: str) -> dict[str, object]:
    padding_max = {"low": 16, "balanced": 64, "high": 128}[intensity]
    return {
        "content_padding_addition": f"{_randint(0, padding_max // 2)}-{_randint(padding_max // 2 + 1, padding_max)}",
        "rekey_after_time": f"{_randint(100, 115)}-{_randint(120, 135)}",
        "reject_after_time": f"{_randint(170, 180)}-{_randint(181, 195)}",
        "rekey_timeout": str(_randint(4, 6)),
        "keepalive_timeout": str(_randint(8, 12)),
        "max_handshake_attempts": str(_randint(16, 20)),
    }


def _random_legacy_options() -> dict[str, object]:
    return {**{key: f"<r {_randint(32, 128)}>" for key in ("j1", "j2", "j3")}, "itime": _randint(10, 50)}


def _generation_node_options(node: dict[str, object], version: str) -> dict[str, object]:
    raw = node.get("awg_options")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise AppError("INVALID_AWG_PARAMETER", "AWG options must be an object", 400)
    regenerated = set(NODE_OPTIONS) - {"random_trailers", "disable_cookies"} if version == "3.1" else set(LEGACY_OPTIONS) if version == "1.5" else set()
    # Bad draft values being replaced must not prevent the user from regenerating them.
    return _options({"awg_options": {key: value for key, value in raw.items() if key not in regenerated}}, False, version)


def generate_draft(payload: dict[str, object], nodes: dict[str, dict[str, object]], version: str, direction: str, intensity: str, scope: str = "all") -> dict[str, object]:
    """Pure generation: no writes, no key rotation, and no runtime regeneration."""
    version = version_value(version)
    _validate_strategy(direction, intensity)
    if scope not in ("all", "node") or (scope == "node" and len(nodes) != 1):
        raise AppError("INVALID_AWG_PARAMETER", "Node-only generation requires exactly one endpoint", 400)
    options = _options(payload, True, version)
    if scope == "all":
        options.update(_random_direction=direction, _random_intensity=intensity)
    if scope == "all" and version == "3.1":
        flags = {_generation_node_options(node, version).get("random_trailers", True) for node in nodes.values()}
        if options.get("random_trailers") is None:
            if len(flags) > 1:
                raise AppError("INVALID_AWG_PARAMETER", "Choose a shared RandomTrailers value before generation", 400)
            options["random_trailers"] = next(iter(flags), True)
        if "header_protection_key" not in options:
            options["header_protection_key"] = base64.b64encode(secrets.token_bytes(32)).decode()
    shared = random_config_params(version) if scope == "all" else dict(payload)
    prefix_max = {"low": 24, "balanced": 48, "high": 96}[intensity]
    if scope == "all" and version == "3.1":
        prefix = _randint(12 if options.get("header_protection_key") else 0, prefix_max)
        shared.update({f"awg_s{i}": prefix for i in range(1, 5)})
    elif scope == "all":
        shared.update({f"awg_s{i}": _randint(0, prefix_max) for i in range(1, 3 if version == "1.5" else 5)})
        if version == "1.5" and shared["awg_s2"] == shared["awg_s1"] + 56:
            shared["awg_s2"] = 0
    shared = validate_config_params({**shared, "awg_options": options}, version)
    generated = {}
    for node_id, node in nodes.items():
        local = random_node_params(version, direction, intensity)
        local_options = _generation_node_options(node, version)
        if version == "3.1":
            local_options.update(_random_node_options(intensity))
            if scope == "all":
                local_options["random_trailers"] = options["random_trailers"]
                local_options.setdefault("disable_cookies", False)
        elif version == "1.5":
            local_options.update(_random_legacy_options())
        local = validate_node_params({**local, "awg_options": local_options}, version)
        validate_mesh_options(shared, local, version)
        generated[node_id] = local
    return {"config": shared, "nodes": generated}


def empty_config_params() -> dict[str, object]:
    return {**{key: None for key in ("awg_s1", "awg_s2", "awg_s3", "awg_s4", "awg_h1", "awg_h2", "awg_h3", "awg_h4")}, "awg_options": {}}


def convert_config_params(payload: dict[str, object], source: str | None, target: str) -> dict[str, object]:
    target = version_value(target)
    if source is not None:
        version_value(source)
    values = {key: value for key, value in payload.items() if key.startswith("awg_")}
    if source != target:
        if target == "1.5":
            values.update(awg_s3=0, awg_s4=0)
            for i in range(1, 5):
                value = values.get(f"awg_h{i}")
                if value:
                    values[f"awg_h{i}"] = str(value).split("-", 1)[0]
            if values.get("awg_s1") is not None and values.get("awg_s2") == int(str(values["awg_s1"])) + 56:
                values["awg_s2"] = 15
        elif target == "3.1":
            values.update(random_config_params(target))
        elif source == "1.5":
            generated = random_config_params(target)
            values.update({key: generated[key] for key in ("awg_s3", "awg_s4")})
    converted = ensure_config_params(values, target)
    # A conversion response is an editable draft, not a source of dormant history.
    supported = {**(CONFIG_OPTIONS if target == "3.1" else {}), **RANDOM_OPTIONS}
    converted["awg_options"] = {key: value for key, value in _options(converted, True, target).items() if key in supported}
    return converted


def render_lines(config, node) -> list[str]:
    version = version_value(config.awg_version)
    fields = [("Jc", node.awg_jc), ("Jmin", node.awg_jmin), ("Jmax", node.awg_jmax)]
    fields += [(f"S{i}", getattr(config, f"awg_s{i}")) for i in range(1, 3 if version == "1.5" else 5)]
    fields += [(f"H{i}", getattr(config, f"awg_h{i}")) for i in range(1, 5)]
    fields += [(f"I{i}", getattr(node, f"awg_i{i}")) for i in range(1, 6)]
    if version == "3.1":
        fields += [(label, config.awg_options.get(key)) for key, label in CONFIG_OPTIONS.items()]
        fields += [(label, node.awg_options.get(key)) for key, label in NODE_OPTIONS.items() if key != "random_trailers"]
        if config.awg_options.get("random_trailers") is None:
            fields += [("RandomTrailers", node.awg_options.get("random_trailers"))]
    elif version == "1.5":
        fields += [(label, node.awg_options.get(key)) for key, label in LEGACY_OPTIONS.items()]
    return [f"{key} = {('on' if value else 'off') if isinstance(value, bool) else value}" for key, value in fields if value is not None and value != ""]


def validate_mesh_options(params: dict[str, object], node_params: dict[str, object], version: str) -> None:
    options = node_params.get("awg_options") or {}
    shared_options = params.get("awg_options") or {}
    if version == "3.1" and shared_options.get("random_trailers") is not None:
        if options.get("random_trailers") is not None and options["random_trailers"] != shared_options["random_trailers"]:
            raise AppError("INVALID_AWG_PARAMETER", "RandomTrailers must match the shared configuration", 400)
        options = {**options, "random_trailers": shared_options["random_trailers"]}
    if version == "3.1" and isinstance(options, dict) and options.get("random_trailers"):
        if len({params.get(f"awg_s{i}") for i in range(1, 5)}) != 1:
            raise AppError("INVALID_AWG_PARAMETER", "RandomTrailers requires equal S1-S4 in this system", 400)


def empty_node_params() -> dict[str, object]:
    return {"awg_options": {}, **{
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
    }}


def _optional_int(value: object, label: str, minimum: int, maximum: int) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(str(value))
    except (ValueError, TypeError) as exc:
        raise AppError("INVALID_AWG_PARAMETER", f"{label} must be an integer", 400) from exc
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
