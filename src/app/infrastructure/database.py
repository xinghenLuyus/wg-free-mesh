from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from app.core.config import settings
from app.domain.models import ConnectivityState, ConfigSyncState, WgRuntimeState, derive_public_key, generate_private_key, new_id, now_utc


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


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
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
            """
        )

        now = now_utc().isoformat()
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

        existing = connection.execute("SELECT COUNT(*) AS count FROM configs").fetchone()
        if existing is not None and existing["count"] > 0:
            return

        config_id = new_id("cfg")
        edge_id = new_id("node")
        hub_id = new_id("node")
        ts = now

        connection.execute(
            """
            INSERT INTO configs
              (id, name, description, enabled, virtual_subnet, default_listen_port, default_mtu, default_dns, auto_sync, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                config_id,
                "mesh-main",
                "默认重构配置",
                1,
                "10.66.0.0/24",
                51820,
                1420,
                "1.1.1.1",
                1,
                ts,
                ts,
            ),
        )

        hub_private = generate_private_key()
        edge_private = generate_private_key()
        nodes = [
            (
                hub_id,
                config_id,
                "核心节点",
                "203.0.113.10",
                "",
                51820,
                "10.66.0.1/32",
                1420,
                "1.1.1.1",
                1,
                "static",
                derive_public_key(hub_private),
                hub_private,
                '["core"]',
                ts,
                ts,
            ),
            (
                edge_id,
                config_id,
                "边缘节点",
                "198.51.100.20",
                "",
                51821,
                "10.66.0.2/32",
                1420,
                "1.1.1.1",
                1,
                "dynamic",
                derive_public_key(edge_private),
                edge_private,
                '["edge"]',
                ts,
                ts,
            ),
        ]
        connection.executemany(
            """
            INSERT INTO nodes
              (id, config_id, name, ipv4_address, ipv6_address, listen_port, virtual_ip, mtu, dns, auto_sync, node_type, public_key, private_key, tags_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            nodes,
        )

        connection.executemany(
            """
            INSERT INTO peer_links
              (id, config_id, local_node_id, peer_node_id, link_group_id, direction, enabled, allowed_ips, persistent_keepalive, preshared_key, endpoint_mode, endpoint_ref_family, endpoint_manual_host, endpoint_port_mode, endpoint_manual_port, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    new_id("plink"),
                    config_id,
                    hub_id,
                    edge_id,
                    "seed-link",
                    "forward",
                    1,
                    "10.66.0.2/32",
                    25,
                    "",
                    "auto",
                    "ipv4",
                    "",
                    "ref_peer_listen_port",
                    None,
                    "默认双向链路",
                    ts,
                    ts,
                ),
                (
                    new_id("plink"),
                    config_id,
                    edge_id,
                    hub_id,
                    "seed-link",
                    "reverse",
                    1,
                    "10.66.0.1/32",
                    25,
                    "",
                    "auto",
                    "ipv4",
                    "",
                    "ref_peer_listen_port",
                    None,
                    "默认双向链路",
                    ts,
                    ts,
                ),
            ],
        )

        for node_id in (hub_id, edge_id):
            connection.execute(
                """
                INSERT INTO node_config_state
                  (id, config_id, node_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (new_id("ncs"), config_id, node_id, ts, ts),
            )
            connection.execute(
                """
                INSERT INTO endpoint_runtime_status
                  (id, config_id, node_id, online, connectivity_state, wg_running, wg_runtime_state, config_sync_state, peers_online, peers_total, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("rt"),
                    config_id,
                    node_id,
                    1 if node_id == hub_id else 0,
                    ConnectivityState.online if node_id == hub_id else ConnectivityState.offline,
                    1 if node_id == hub_id else 0,
                    WgRuntimeState.running if node_id == hub_id else WgRuntimeState.stopped,
                    ConfigSyncState.pending,
                    1 if node_id == hub_id else 0,
                    1,
                    ts,
                    ts,
                ),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO node_client_state
                  (node_id, config_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (node_id, config_id, ts, ts),
            )
