"""Historical schema upgrade coverage; only isolated in-memory databases are used."""
import json
import pytest
from alembic import command
from sqlalchemy import inspect, text

from app.core.config import settings
from app.data.connection import get_engine, reset_engine
from app.data.database import _alembic_config, _upgrade_database_schema


REVISIONS = (
    "0001_initial_schema", "0002_tunnel_protocol_awg", "0003_mqtt_password",
    "0004_port_forward_rules", "0005_port_forward_enabled", "0006_mcp_access",
)


@pytest.mark.parametrize("revision", REVISIONS)
@pytest.mark.parametrize("unversioned", [False, True])
def test_upgrade_all_historical_schemas(monkeypatch, revision: str, unversioned: bool) -> None:
    monkeypatch.setattr(settings, "database", "sqlite:///:memory:")
    reset_engine()
    try:
        # Downgrading an empty current database produces each historical structure.
        _upgrade_database_schema()
        command.downgrade(_alembic_config(), revision)
        engine = get_engine()
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO configs (id, name, virtual_subnet, default_listen_port, created_at, updated_at)
                VALUES ('cfg_old', 'old', '10.66.0.0/24', 51820, '2026-01-01', '2026-01-01')
            """))
            if revision != REVISIONS[0]:
                connection.execute(text("UPDATE configs SET tunnel_protocol='amneziawg_2', awg_s1=19, awg_h1='1000-1100' WHERE id='cfg_old'"))
            connection.execute(text("""
                INSERT INTO nodes (id, config_id, name, node_type, public_key, private_key, created_at, updated_at)
                VALUES ('node_old', 'cfg_old', 'old', 'static', 'public', 'private', '2026-01-01', '2026-01-01')
            """))
            if revision != REVISIONS[0]:
                connection.execute(text("UPDATE nodes SET awg_jc=5, awg_i1='<r 12>' WHERE id='node_old'"))
            connection.execute(text("""
                INSERT INTO node_config_state (id, config_id, node_id, confirmed_text, confirmed_version, created_at, updated_at)
                VALUES ('state_old', 'cfg_old', 'node_old', 'original config', 7, '2026-01-01', '2026-01-01')
            """))
            if unversioned:
                connection.execute(text("DROP TABLE alembic_version"))
        _upgrade_database_schema()
        _upgrade_database_schema()  # Startup upgrades must be repeatable.
        with engine.connect() as connection:
            config = connection.execute(text("SELECT * FROM configs WHERE id='cfg_old'")).mappings().one()
            assert config["awg_options_json"] == "{}"
            if revision == REVISIONS[0]:
                assert config["tunnel_protocol"] == "wireguard"
                assert config["awg_version"] is None
            else:
                assert config["tunnel_protocol"] == "amneziawg"
                assert config["awg_version"] == "2.0"
                assert config["awg_s1"] == 19
                assert config["awg_h1"] == "1000-1100"
                node = connection.execute(text("SELECT * FROM nodes WHERE id='node_old'")).mappings().one()
                assert node["awg_jc"] == 5
                assert node["awg_i1"] == "<r 12>"
            state = connection.execute(text("SELECT * FROM node_config_state WHERE id='state_old'")).mappings().one()
            assert state["confirmed_text"] == "original config"
            assert state["confirmed_version"] == 7
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0007_awg_versions"
        assert "awg_options_json" in {column["name"] for column in inspect(engine).get_columns("nodes")}
    finally:
        reset_engine()


def test_legacy_snapshot_preserves_original_parameters(monkeypatch) -> None:
    from app.data.application_snapshot import export_database_payload, import_database_payload

    monkeypatch.setattr(settings, "database", "sqlite:///:memory:")
    reset_engine()
    try:
        _upgrade_database_schema()
        original = {
            "id": "cfg_snapshot", "name": "snapshot", "virtual_subnet": "10.66.0.0/24",
            "default_listen_port": 51820, "tunnel_protocol": "amneziawg_2",
            "awg_s1": 19, "awg_h1": "1000-1100", "created_at": "2026-01-01", "updated_at": "2026-01-01",
        }
        import_database_payload(json.dumps({"format": "application", "tables": {"configs": [original]}}))
        restored = json.loads(export_database_payload())["tables"]["configs"][0]
        assert restored["tunnel_protocol"] == "amneziawg"
        assert restored["awg_version"] == "2.0"
        assert restored["awg_options_json"] == "{}"
        for key in ("awg_s1", "awg_h1", "created_at", "updated_at"):
            assert restored[key] == original[key]
    finally:
        reset_engine()
