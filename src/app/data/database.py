from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import time

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from app.data.connection import connect, get_engine, reset_engine
from app.data.paths import backups_dir, data_dir, wireguard_dir, workspace_path
from app.data.schema import metadata
from app.domain.models import WgRuntimeState, now_utc


def init_database() -> None:
    wireguard_dir()
    backups_dir()
    _with_database_retry(_create_schema_and_defaults)


def _create_schema_and_defaults() -> None:
    _upgrade_database_schema()
    _post_migrate_defaults()


def _upgrade_database_schema() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if not existing_tables:
        metadata.create_all(engine)
        _stamp_database("head")
        return
    inferred_revision = _infer_existing_revision(inspector)
    current_revision = _current_alembic_revision() if "alembic_version" in existing_tables else ""
    if _revision_rank(inferred_revision) > _revision_rank(current_revision):
        _stamp_database(inferred_revision)
    command.upgrade(_alembic_config(), "head")


def _infer_existing_revision(inspector) -> str:
    config_columns = _column_names(inspector, "configs")
    node_columns = _column_names(inspector, "nodes")
    client_columns = _column_names(inspector, "node_client_state")
    port_forward_columns = _column_names(inspector, "port_forward_rules")
    if "enabled" in port_forward_columns:
        return "0005_port_forward_enabled"
    if inspector.has_table("port_forward_rules"):
        return "0004_port_forward_rules"
    if "mqtt_password" in client_columns:
        return "0003_mqtt_password"
    if "tunnel_protocol" in config_columns and "pre_up_json" in node_columns:
        return "0002_tunnel_protocol_awg"
    return "0001_initial_schema"


def _column_names(inspector, table_name: str) -> set[str]:
    if not inspector.has_table(table_name):
        return set()
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def _current_alembic_revision() -> str:
    with get_engine().begin() as connection:
        row = connection.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    return str(row[0]) if row is not None else ""


def _revision_rank(revision: str) -> int:
    ranks = {
        "": 0,
        "0001_initial_schema": 1,
        "0002_tunnel_protocol_awg": 2,
        "0003_mqtt_password": 3,
        "0004_port_forward_rules": 4,
        "0005_port_forward_enabled": 5,
        "0006_mcp_access": 6,
    }
    return ranks.get(revision, 0)


def _stamp_database(revision: str) -> None:
    command.stamp(_alembic_config(), revision)


def _alembic_config() -> Config:
    src_dir = Path(__file__).resolve().parents[2]
    config = Config(str(src_dir / "alembic.ini"))
    config.set_main_option("script_location", str(src_dir / "migrations"))
    config.attributes["configure_logger"] = False
    return config


def _with_database_retry(action) -> None:
    deadline = time.monotonic() + 60
    while True:
        try:
            action()
            return
        except OperationalError:
            if time.monotonic() >= deadline:
                raise
            reset_engine()
            time.sleep(1)


def _post_migrate_defaults() -> None:
    now = now_utc().isoformat()
    with connect() as connection:
        if connection.dialect_name == "postgresql":
            connection.execute(
                """
                UPDATE node_client_state
                SET last_reachable_at = NULLIF(
                        GREATEST(
                            coalesce(last_heartbeat_at, ''),
                            coalesce(last_detect_ack_at, ''),
                            CASE
                                WHEN last_event NOT LIKE 'offline:%' THEN coalesce(last_event_at, '')
                                ELSE ''
                            END
                        ),
                        ''
                    )
                WHERE last_reachable_at IS NULL
                """
            )
        else:
            connection.execute(
                """
                UPDATE node_client_state
                SET last_reachable_at = NULLIF(
                        max(
                            coalesce(last_heartbeat_at, ''),
                            coalesce(last_detect_ack_at, ''),
                            CASE
                                WHEN last_event NOT LIKE 'offline:%' THEN coalesce(last_event_at, '')
                                ELSE ''
                            END
                        ),
                        ''
                    )
                WHERE last_reachable_at IS NULL
                """
            )
        connection.execute(
            """
            UPDATE node_client_state
            SET last_offline_at = last_will_at
            WHERE last_offline_at IS NULL AND last_will_at IS NOT NULL
            """
        )
        connection.execute(
            """
            UPDATE endpoint_runtime_status
            SET online = 1,
                connectivity_state = 'online',
                last_seen = (
                    SELECT s.last_reachable_at
                    FROM node_client_state s
                    WHERE s.config_id = endpoint_runtime_status.config_id
                      AND s.node_id = endpoint_runtime_status.node_id
                ),
                last_connectivity_reason = 'migration-reachable-signal',
                updated_at = ?
            WHERE online = 0
              AND EXISTS (
                SELECT 1
                FROM node_client_state s
                JOIN nodes n ON n.id = s.node_id
                WHERE s.config_id = endpoint_runtime_status.config_id
                  AND s.node_id = endpoint_runtime_status.node_id
                  AND s.client_initialized = 1
                  AND n.enabled = 1
                  AND n.node_type = 'dynamic'
                  AND s.last_reachable_at IS NOT NULL
                  AND (s.last_offline_at IS NULL OR s.last_reachable_at > s.last_offline_at)
                  AND s.last_reachable_at >= ?
              )
            """,
            (now, (now_utc() - timedelta(minutes=90)).isoformat()),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO node_client_state
              (node_id, config_id, created_at, updated_at)
            SELECT id, config_id, ?, ? FROM nodes
            """,
            (now, now),
        )
        connection.execute(
            """
            UPDATE endpoint_runtime_status
            SET wg_running = 0, wg_runtime_state = ?, updated_at = ?
            WHERE online = 0
               OR node_id IN (SELECT id FROM nodes WHERE node_type = 'static')
               OR node_id IN (SELECT node_id FROM node_client_state WHERE client_initialized = 0)
            """,
            (WgRuntimeState.unknown.value, now),
        )


def reset_database_objects() -> None:
    engine = get_engine()
    metadata.drop_all(engine)
    metadata.create_all(engine)


def table_names() -> list[str]:
    return sorted(inspect(get_engine()).get_table_names())


__all__ = [
    "backups_dir",
    "connect",
    "data_dir",
    "init_database",
    "reset_database_objects",
    "reset_engine",
    "table_names",
    "wireguard_dir",
    "workspace_path",
]
