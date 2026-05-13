from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
import sqlite3

from app.core.config import settings
from app.domain.models import WgRuntimeState, now_utc


def data_dir() -> Path:
    return workspace_path("data")


def wireguard_dir() -> Path:
    path = data_dir() / "wireguard"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def workspace_path(relative: str) -> Path:
    return Path.cwd() / relative


def _database_path() -> Path:
    path = Path(settings.sqlite_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_database() -> None:
    wireguard_dir()
    backups_dir()
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS configs (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              description TEXT NOT NULL DEFAULT '',
              enabled INTEGER NOT NULL DEFAULT 1,
              virtual_subnet TEXT NOT NULL,
              default_listen_port INTEGER NOT NULL,
              default_mtu INTEGER,
              default_dns TEXT,
              auto_sync INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS nodes (
              id TEXT PRIMARY KEY,
              config_id TEXT NOT NULL,
              name TEXT NOT NULL,
              ipv4_address TEXT,
              ipv6_address TEXT,
              listen_port INTEGER,
              virtual_ip TEXT,
              mtu INTEGER,
              dns TEXT,
              auto_sync INTEGER NOT NULL DEFAULT 1,
              enabled INTEGER NOT NULL DEFAULT 1,
              node_type TEXT NOT NULL,
              public_key TEXT NOT NULL,
              private_key TEXT NOT NULL,
              tags_json TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (config_id) REFERENCES configs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS config_tags (
              config_id TEXT NOT NULL,
              name TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (config_id, name),
              FOREIGN KEY (config_id) REFERENCES configs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS peer_links (
              id TEXT PRIMARY KEY,
              config_id TEXT NOT NULL,
              local_node_id TEXT NOT NULL,
              peer_node_id TEXT NOT NULL,
              link_group_id TEXT NOT NULL,
              direction TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              allowed_ips TEXT NOT NULL,
              persistent_keepalive INTEGER,
              preshared_key TEXT,
              endpoint_mode TEXT NOT NULL,
              endpoint_ref_family TEXT,
              endpoint_manual_host TEXT,
              endpoint_port_mode TEXT NOT NULL,
              endpoint_manual_port INTEGER,
              notes TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (config_id) REFERENCES configs(id) ON DELETE CASCADE,
              FOREIGN KEY (local_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
              FOREIGN KEY (peer_node_id) REFERENCES nodes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS node_config_state (
              id TEXT PRIMARY KEY,
              config_id TEXT NOT NULL,
              node_id TEXT NOT NULL UNIQUE,
              desired_text TEXT NOT NULL DEFAULT '',
              desired_sha256 TEXT NOT NULL DEFAULT '',
              desired_version INTEGER NOT NULL DEFAULT 0,
              staged_text TEXT NOT NULL DEFAULT '',
              staged_sha256 TEXT NOT NULL DEFAULT '',
              staged_version INTEGER NOT NULL DEFAULT 0,
              confirmed_text TEXT NOT NULL DEFAULT '',
              confirmed_sha256 TEXT NOT NULL DEFAULT '',
              confirmed_version INTEGER NOT NULL DEFAULT 0,
              reported_local_sha256 TEXT NOT NULL DEFAULT '',
              reported_local_version INTEGER NOT NULL DEFAULT 0,
              desired_generated_at TEXT,
              staged_updated_at TEXT,
              confirmed_updated_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (config_id) REFERENCES configs(id) ON DELETE CASCADE,
              FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS endpoint_runtime_status (
              id TEXT PRIMARY KEY,
              config_id TEXT NOT NULL,
              node_id TEXT NOT NULL UNIQUE,
              online INTEGER NOT NULL DEFAULT 0,
              connectivity_state TEXT NOT NULL,
              wg_running INTEGER NOT NULL DEFAULT 0,
              wg_runtime_state TEXT NOT NULL,
              config_sync_state TEXT NOT NULL,
              peers_online INTEGER NOT NULL DEFAULT 0,
              peers_total INTEGER NOT NULL DEFAULT 0,
              last_seen TEXT,
              last_probe_sent_at TEXT,
              last_probe_ack_at TEXT,
              last_control_channel_seen_at TEXT,
              heartbeat_client_online INTEGER NOT NULL DEFAULT 0,
              heartbeat_wg_online INTEGER NOT NULL DEFAULT 0,
              detect_client_online INTEGER NOT NULL DEFAULT 0,
              detect_wg_online INTEGER NOT NULL DEFAULT 0,
              last_config_sync_error TEXT NOT NULL DEFAULT '',
              last_connectivity_reason TEXT NOT NULL DEFAULT '',
              client_downloaded INTEGER NOT NULL DEFAULT 0,
              client_downloaded_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (config_id) REFERENCES configs(id) ON DELETE CASCADE,
              FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS node_client_state (
              node_id TEXT PRIMARY KEY,
              config_id TEXT NOT NULL,
              client_initialized INTEGER NOT NULL DEFAULT 0,
              client_platform TEXT NOT NULL DEFAULT '',
              client_version TEXT NOT NULL DEFAULT '',
              client_hostname TEXT NOT NULL DEFAULT '',
              mqtt_username TEXT NOT NULL DEFAULT '',
              mqtt_client_id TEXT NOT NULL DEFAULT '',
              bind_token_hash TEXT NOT NULL DEFAULT '',
              bind_token_expires_at TEXT,
              bind_token_used_at TEXT,
              client_presence_state TEXT NOT NULL DEFAULT 'offline',
              boot_id TEXT NOT NULL DEFAULT '',
              session_id TEXT NOT NULL DEFAULT '',
              last_heartbeat_at TEXT,
              last_detect_ack_at TEXT,
              last_reachable_at TEXT,
              last_offline_at TEXT,
              last_will_at TEXT,
              last_event TEXT NOT NULL DEFAULT '',
              last_event_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (config_id) REFERENCES configs(id) ON DELETE CASCADE,
              FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS endpoint_control_logs (
              id TEXT PRIMARY KEY,
              request_id TEXT NOT NULL UNIQUE,
              config_id TEXT NOT NULL,
              node_id TEXT NOT NULL,
              action TEXT NOT NULL,
              status TEXT NOT NULL,
              requested_by TEXT NOT NULL,
              summary TEXT NOT NULL DEFAULT '',
              detail TEXT NOT NULL DEFAULT '',
              requested_at TEXT NOT NULL,
              ack_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (config_id) REFERENCES configs(id) ON DELETE CASCADE,
              FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS system_settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS backups (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              path TEXT NOT NULL,
              size INTEGER NOT NULL DEFAULT 0,
              note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_config_id ON nodes(config_id);
            CREATE INDEX IF NOT EXISTS idx_peer_links_config_id ON peer_links(config_id);
            CREATE INDEX IF NOT EXISTS idx_peer_links_local_enabled ON peer_links(config_id, local_node_id, enabled);
            CREATE INDEX IF NOT EXISTS idx_peer_links_peer_node ON peer_links(config_id, peer_node_id);
            CREATE INDEX IF NOT EXISTS idx_runtime_status_config_id ON endpoint_runtime_status(config_id);
            CREATE INDEX IF NOT EXISTS idx_runtime_status_config_node ON endpoint_runtime_status(config_id, node_id);
            CREATE INDEX IF NOT EXISTS idx_node_config_state_config_id ON node_config_state(config_id);
            CREATE INDEX IF NOT EXISTS idx_client_state_config_id ON node_client_state(config_id);
            CREATE INDEX IF NOT EXISTS idx_endpoint_control_logs_config_node_created
              ON endpoint_control_logs(config_id, node_id, created_at DESC);
            """
        )

        _ensure_column(connection, "node_client_state", "client_platform", "client_platform TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "node_client_state", "client_version", "client_version TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "node_client_state", "client_hostname", "client_hostname TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "node_client_state", "last_reachable_at", "last_reachable_at TEXT")
        _ensure_column(connection, "node_client_state", "last_offline_at", "last_offline_at TEXT")
        _ensure_column(connection, "endpoint_runtime_status", "heartbeat_client_online", "heartbeat_client_online INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "endpoint_runtime_status", "heartbeat_wg_online", "heartbeat_wg_online INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "endpoint_runtime_status", "detect_client_online", "detect_client_online INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "endpoint_runtime_status", "detect_wg_online", "detect_wg_online INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "nodes", "enabled", "enabled INTEGER NOT NULL DEFAULT 1")
        now = now_utc().isoformat()
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
        mqtt_row = connection.execute(
            "SELECT key FROM system_settings WHERE key = 'mqtt_client'"
        ).fetchone()
        if mqtt_row is None:
            connection.execute(
                "INSERT INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)",
                (
                    "mqtt_client",
                    '{"host":"","port":8883,"tls":true,"username":"","password":""}',
                    now,
                ),
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
