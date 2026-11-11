"""Regression coverage for already-versioned databases missing a runtime column."""

import pytest
from alembic import command
from sqlalchemy import inspect, text

from app.core.config import settings
from app.data.connection import get_engine, reset_engine
from app.data.database import _alembic_config, _upgrade_database_schema
from app.data.schema import configs, endpoint_runtime_status, nodes
from app.data.store import store
from app.services.runtime_observation_service import endpoint_state


@pytest.mark.parametrize("has_observed_at", [False, True])
def test_versioned_runtime_timestamp_upgrade(monkeypatch, has_observed_at):
    monkeypatch.setattr(settings, "database", "sqlite:///:memory:")
    monkeypatch.setattr(settings, "enable_mqtt_services", True)
    reset_engine()
    try:
        _upgrade_database_schema()
        command.downgrade(_alembic_config(), "0008_runtime_observations")
        engine = get_engine()
        timestamp = "2026-01-01T00:00:00+00:00"
        with engine.begin() as connection:
            if not has_observed_at:
                connection.execute(text(
                    "ALTER TABLE endpoint_runtime_status DROP COLUMN wg_observed_at"
                ))
            connection.execute(configs.insert().values(
                id="cfg_migration", name="migration", virtual_subnet="10.66.0.0/24",
                default_listen_port=51820, created_at=timestamp, updated_at=timestamp,
            ))
            connection.execute(nodes.insert().values(
                id="node_migration", config_id="cfg_migration", name="migration",
                node_type="dynamic", public_key="public", private_key="private",
                created_at=timestamp, updated_at=timestamp,
            ))
            values = dict(
                id="runtime_migration", config_id="cfg_migration", node_id="node_migration",
                online=1, connectivity_state="online", wg_running=1,
                wg_runtime_state="running", config_sync_state="in_sync",
                created_at=timestamp, updated_at=timestamp,
            )
            if has_observed_at:
                values["wg_observed_at"] = timestamp
            connection.execute(endpoint_runtime_status.insert().values(**values))

        _upgrade_database_schema()
        _upgrade_database_schema()
        assert "wg_observed_at" in {
            column["name"] for column in inspect(engine).get_columns("endpoint_runtime_status")
        }
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
                "0010_delete_revoked_mcp_tokens"
            )
            row = connection.execute(text("SELECT * FROM endpoint_runtime_status")).mappings().one()
            assert row["wg_observed_at"] == (timestamp if has_observed_at else None)
            assert row["wg_running"] == 1
            assert row["wg_runtime_state"] == "running"
            assert row["updated_at"] == timestamp

        # Both ACK paths must persist fresh evidence after the schema upgrade.
        store.record_client_heartbeat("cfg_migration", "node_migration", wg_online=True)
        assert endpoint_state(store.get_runtime("cfg_migration", "node_migration")) == "online"
        store.record_detect_ack("cfg_migration", "node_migration", wg_online=True)
        assert endpoint_state(store.get_runtime("cfg_migration", "node_migration")) == "online"
    finally:
        reset_engine()
