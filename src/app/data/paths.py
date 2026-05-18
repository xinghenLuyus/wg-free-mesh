from __future__ import annotations

from pathlib import Path


def workspace_path(relative: str) -> Path:
    return Path.cwd() / relative


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

