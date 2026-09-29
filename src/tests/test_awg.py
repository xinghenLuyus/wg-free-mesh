from types import SimpleNamespace

import pytest

from app.core.errors import AppError
from app.domain import awg


def test_random_node_params_include_editable_i_chain() -> None:
    values = awg.random_node_params()

    assert 4 <= values["awg_jc"] <= 7
    assert 64 <= values["awg_jmin"] < values["awg_jmax"] <= 1024
    for key in ("awg_i1", "awg_i2", "awg_i3"):
        assert isinstance(values[key], str)
        assert values[key]
    assert values["awg_i4"] is None and values["awg_i5"] is None


@pytest.mark.parametrize("version", awg.VERSIONS)
def test_version_defaults_and_rendering(version: str) -> None:
    config = awg.ensure_config_params({}, version)
    node = awg.ensure_node_params({}, version)
    awg.validate_mesh_options(config, node, version)
    lines = awg.render_lines(SimpleNamespace(awg_version=version, **config), SimpleNamespace(**node))
    assert any(line.startswith("I1 = ") for line in lines)
    assert not any(line.startswith("I5 = ") for line in lines)
    assert any(line.startswith("S3 = ") for line in lines) == (version != "1.5")
    assert any(line.startswith("HeaderProtectionKey = ") for line in lines) == (version == "3.1")
    if version == "3.1":
        assert "RandomTrailers = on" in lines
        assert "DisableCookies = off" in lines
        assert any(line.startswith("ContentPaddingAddition = ") for line in lines)
        assert len({config[f"awg_h{i}"] for i in range(1, 5)}) == 4
        assert all(int(config[f"awg_h{i}"]) >= 1024 for i in range(1, 5))


@pytest.mark.parametrize("source", awg.VERSIONS)
@pytest.mark.parametrize("target", awg.VERSIONS)
def test_all_version_transitions(source: str, target: str) -> None:
    original = awg.ensure_config_params({}, source)
    converted = awg.convert_config_params(original, source, target)
    assert awg.validate_config_params(converted, target) == converted
    if source == target:
        assert converted == original
    node = awg.ensure_node_params(awg.ensure_node_params({}, source), target)
    awg.validate_mesh_options(converted, node, target)


def test_legacy_2_rendering_is_unchanged() -> None:
    config = awg.ensure_config_params({}, "2.0")
    node = awg.ensure_node_params({}, "2.0")
    # Even dormant extensions must not leak into a legacy config.
    config["awg_options"] = {"header_protection_key": "unused"}
    node["awg_options"] = {"random_trailers": True}
    actual = awg.render_lines(SimpleNamespace(awg_version="2.0", **config), SimpleNamespace(**node))
    expected = [f"{label} = {value}" for label, value in (
        [("Jc", node["awg_jc"]), ("Jmin", node["awg_jmin"]), ("Jmax", node["awg_jmax"])]
        + [(f"S{i}", config[f"awg_s{i}"]) for i in range(1, 5)]
        + [(f"H{i}", config[f"awg_h{i}"]) for i in range(1, 5)]
        + [(f"I{i}", node[f"awg_i{i}"]) for i in range(1, 6)]
    ) if value is not None]
    assert actual == expected


@pytest.mark.parametrize("target", ["1.5", "2.0"])
def test_conversion_draft_omits_unsupported_config_options(target: str) -> None:
    original = awg.ensure_config_params({}, "3.1")
    original["awg_options"].update(random_trailers=True, _random_direction="dns")
    converted = awg.convert_config_params(original, "3.1", target)
    assert converted["awg_options"] == {"_random_direction": "dns"}
    assert "header_protection_key" in original["awg_options"]
    # A new WireGuard config can save the target draft without dormant history.
    assert awg.merge_options(converted, awg.empty_config_params(), target, True) == converted["awg_options"]


def test_3_key_is_preserved_and_can_be_disabled() -> None:
    config = awg.ensure_config_params({}, "3.1")
    assert awg.ensure_config_params(config, "3.1") == config
    config["awg_options"] = {"header_protection_key": None}
    assert awg.ensure_config_params(config, "3.1")["awg_options"] == {"header_protection_key": None}


@pytest.mark.parametrize("options", [
    {"header_protection_key": "not-base64"},
    {"header_protection_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="},
    {"unknown": 1},
])
def test_invalid_config_extensions_are_rejected(options: dict) -> None:
    with pytest.raises(AppError):
        awg.ensure_config_params({"awg_options": options}, "3.1")


def test_version_specific_writes_and_dormant_options() -> None:
    current = {"awg_options": {"random_trailers": True}}
    assert awg.merge_options(current, current, "2.0", False) == current["awg_options"]
    with pytest.raises(AppError):
        awg.merge_options({"awg_options": {"random_trailers": False}}, current, "2.0", False)
    with pytest.raises(AppError):
        awg.version_value("3.0")


def test_3_mesh_and_timing_constraints() -> None:
    config = awg.ensure_config_params({}, "3.1")
    config["awg_s1"] = 12
    with pytest.raises(AppError):
        awg.validate_mesh_options(config, {"awg_options": {"random_trailers": True}}, "3.1")
    with pytest.raises(AppError):
        awg.ensure_node_params({"awg_options": {"rekey_after_time": "120-130", "reject_after_time": "125"}}, "3.1")
    with pytest.raises(AppError):
        awg.ensure_node_params({"awg_options": {"content_padding_addition": "65536"}}, "3.1")


@pytest.mark.parametrize("version", awg.VERSIONS)
@pytest.mark.parametrize("direction", ["generic", "dns", "stun", "rtp", "quic"])
@pytest.mark.parametrize("intensity", ["low", "balanced", "high"])
def test_unified_draft_is_valid_and_preserves_key_and_switches(version, direction, intensity) -> None:
    import copy

    config = awg.ensure_config_params({}, version)
    if version == "3.1":
        config["awg_options"]["random_trailers"] = False
    nodes = {"a": awg.ensure_node_params({}, version), "b": awg.ensure_node_params({}, version)}
    if version == "3.1":
        for node in nodes.values():
            node["awg_options"].update(random_trailers=False, disable_cookies=True)
    original = copy.deepcopy((config, nodes))
    draft = awg.generate_draft(config, nodes, version, direction, intensity)
    assert (config, nodes) == original
    assert awg.validate_config_params(draft["config"], version) == draft["config"]
    assert draft["config"]["awg_options"]["_random_direction"] == direction
    for node in draft["nodes"].values():
        assert awg.validate_node_params(node, version) == node
        awg.validate_mesh_options(draft["config"], node, version)
        if version == "3.1":
            assert node["awg_options"]["random_trailers"] is False
            assert node["awg_options"]["disable_cookies"] is True
            assert draft["config"]["awg_options"]["header_protection_key"] == config["awg_options"]["header_protection_key"]


def test_manual_configuration_is_not_constrained_by_generation_direction() -> None:
    config = awg.ensure_config_params({}, "2.0")
    config["awg_s1"] = 1024
    config["awg_options"].update(_random_direction="dns", _random_intensity="low")
    assert awg.validate_config_params(config, "2.0") == config
    local = awg.validate_node_params({"awg_jc": 20, "awg_jmin": 20, "awg_jmax": 2048, "awg_i1": "<r 20>", "awg_i2": ""}, "2.0")
    assert local["awg_i2"] is None


def test_generation_requires_explicit_choice_for_conflicting_historical_switches() -> None:
    config = awg.ensure_config_params({}, "3.1")
    nodes = {"a": {"awg_options": {"random_trailers": True}}, "b": {"awg_options": {"random_trailers": False}}}
    with pytest.raises(AppError):
        awg.generate_draft(config, nodes, "3.1", "generic", "balanced")
    config["awg_options"]["random_trailers"] = False
    draft = awg.generate_draft(config, nodes, "3.1", "generic", "balanced")
    assert all(node["awg_options"]["random_trailers"] is False for node in draft["nodes"].values())


def test_saved_strategy_initializes_new_endpoints_but_does_not_render_metadata() -> None:
    draft = awg.generate_draft({}, {}, "3.1", "rtp", "low")
    config = draft["config"]
    node = awg.ensure_node_params({}, "3.1", config["awg_options"])
    assert 1 <= node["awg_jc"] <= 3
    assert node["awg_i1"].startswith("<b 0x8000")
    assert node["awg_i2"] is None
    lines = awg.render_lines(SimpleNamespace(awg_version="3.1", **config), SimpleNamespace(**node))
    assert not any("_random" in line for line in lines)
    assert sum(line.startswith("RandomTrailers = ") for line in lines) == 1


@pytest.mark.parametrize("direction,intensity", [("unknown", "low"), ("dns", "unknown")])
def test_invalid_generation_strategy(direction, intensity) -> None:
    with pytest.raises(AppError):
        awg.generate_draft({}, {}, "3.1", direction, intensity)


def test_partial_j_values_are_backfilled_without_inverting_the_range() -> None:
    high_min = awg.ensure_node_params({"awg_jmin": 2000}, "2.0")
    assert high_min["awg_jmax"] > high_min["awg_jmin"]
    low_max = awg.ensure_node_params({"awg_jmax": 20}, "2.0")
    assert low_max["awg_jmin"] < low_max["awg_jmax"]
    for payload in ({"awg_jmin": 65535}, {"awg_jmax": 0}):
        with pytest.raises(AppError):
            awg.ensure_node_params(payload, "2.0")


def test_regeneration_replaces_invalid_numeric_draft_fields() -> None:
    nodes = {"a": {"awg_jmax": -1, "awg_i1": "invalid", "awg_options": {"content_padding_addition": "invalid", "rekey_after_time": "200", "reject_after_time": "100", "disable_cookies": True}}}
    draft = awg.generate_draft({}, nodes, "3.1", "stun", "balanced")
    assert awg.validate_node_params(draft["nodes"]["a"], "3.1") == draft["nodes"]["a"]
    assert draft["nodes"]["a"]["awg_options"]["disable_cookies"] is True


@pytest.mark.parametrize("version", awg.VERSIONS)
def test_node_only_generation_preserves_shared_parameters_and_switches(version, monkeypatch) -> None:
    import copy

    config = awg.ensure_config_params({}, version)
    config["awg_options"].update(_random_direction="dns", _random_intensity="low")
    node = awg.ensure_node_params({}, version)
    if version == "3.1":
        node["awg_options"].update(random_trailers=False, disable_cookies=True)
        # Node-only generation must not create a missing shared key or infer a shared switch.
        config["awg_options"].pop("header_protection_key")
    original = copy.deepcopy((config, node))
    def forbid_shared_randomization(*args, **kwargs):
        pytest.fail("Node-only generation must not randomize shared parameters")
    monkeypatch.setattr(awg, "random_config_params", forbid_shared_randomization)
    draft = awg.generate_draft(config, {"a": node}, version, "dns", "low", scope="node")
    assert draft["config"] == config
    assert (config, node) == original
    assert set(draft["nodes"]) == {"a"}
    assert 1 <= draft["nodes"]["a"]["awg_jc"] <= 3
    assert draft["nodes"]["a"]["awg_i1"].startswith("<r 2><b 0x0100")
    if version == "3.1":
        assert draft["nodes"]["a"]["awg_options"]["random_trailers"] is False
        assert draft["nodes"]["a"]["awg_options"]["disable_cookies"] is True


@pytest.mark.parametrize("nodes", [{}, {"a": {}, "b": {}}])
def test_node_only_generation_requires_exactly_one_node(nodes) -> None:
    with pytest.raises(AppError):
        awg.generate_draft({}, nodes, "3.1", "dns", "low", scope="node")
