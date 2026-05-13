from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from zipfile import ZIP_DEFLATED, ZipFile

from app.core.config import settings
from app.core.errors import AppError
from app.domain.models import new_id, now_utc
from app.infrastructure.database import data_dir
from app.repositories.naming import config_artifact_name_segment, node_config_artifact_stem
from app.repositories.sqlite import store


SUPPORTED_CLIENT_SYSTEMS = {
    "windows": "Windows",
    "linux": "Linux",
    "darwin": "macOS",
}
SUPPORTED_CLIENT_ARCHES = {
    "amd64": "x86_64 / amd64",
    "arm64": "ARM64",
}
CLIENT_DOWNLOAD_SOURCES = [
    {
        "value": "local_build",
        "label": "Local source build",
        "available": True,
        "description": "Build wfmctl and wfm-agent from the server-side client source tree.",
    },
    {
        "value": "github_release",
        "label": "GitHub release",
        "available": False,
        "description": "Reserved for future official release artifacts.",
    },
]


class DownloadToolsService:
    def __init__(self) -> None:
        self._build_locks: dict[str, threading.Lock] = {}
        self._build_locks_guard = threading.Lock()
        self._config_bulk_lock = threading.Lock()

    @property
    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @property
    def _artifact_root(self) -> Path:
        path = data_dir() / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def _client_artifact_root(self) -> Path:
        path = self._artifact_root / "clients"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def _config_bulk_root(self) -> Path:
        path = self._artifact_root / "config-bulk"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def client_options(self) -> dict[str, object]:
        return {
            "sources": CLIENT_DOWNLOAD_SOURCES,
            "systems": [{"value": value, "label": label} for value, label in SUPPORTED_CLIENT_SYSTEMS.items()],
            "architectures": [{"value": value, "label": label} for value, label in SUPPORTED_CLIENT_ARCHES.items()],
            "defaults": {"source": "local_build", "goos": "windows", "goarch": "amd64"},
            "version": settings.app_version,
        }

    def _validate_client_target(self, source: str, goos: str, goarch: str) -> None:
        if source not in {"local_build", "github_release"}:
            raise AppError("INVALID_DOWNLOAD_SOURCE", "Download source is invalid", 400)
        if source == "github_release":
            raise AppError("DOWNLOAD_SOURCE_UNAVAILABLE", "GitHub release source is not available yet", 501)
        if goos not in SUPPORTED_CLIENT_SYSTEMS:
            raise AppError("INVALID_CLIENT_SYSTEM", "Client system is invalid", 400)
        if goarch not in SUPPORTED_CLIENT_ARCHES:
            raise AppError("INVALID_CLIENT_ARCH", "Client architecture is invalid", 400)

    def _client_artifact_id(self, source: str, goos: str, goarch: str) -> str:
        return f"{source}-{settings.app_version}-{goos}-{goarch}"

    def _client_artifact_filename(self, goos: str, goarch: str) -> str:
        return f"wfm-client-{goos}-{goarch}-v{settings.app_version}.zip"

    def _client_artifact_path(self, artifact_id: str) -> Path:
        path = self._client_artifact_root / f"{artifact_id}.zip"
        if path.parent != self._client_artifact_root or not path.name.endswith(".zip"):
            raise AppError("CLIENT_ARTIFACT_NOT_FOUND", "Client artifact not found", 404)
        return path

    def _lock_for(self, key: str) -> threading.Lock:
        with self._build_locks_guard:
            if key not in self._build_locks:
                self._build_locks[key] = threading.Lock()
            return self._build_locks[key]

    def build_client_artifact(self, source: str, goos: str, goarch: str) -> dict[str, object]:
        self._validate_client_target(source, goos, goarch)
        artifact_id = self._client_artifact_id(source, goos, goarch)
        artifact_path = self._client_artifact_path(artifact_id)
        filename = self._client_artifact_filename(goos, goarch)

        if artifact_path.exists():
            return self._client_artifact_payload(artifact_id, filename, source, goos, goarch, cached=True)

        with self._lock_for(artifact_id):
            if artifact_path.exists():
                return self._client_artifact_payload(artifact_id, filename, source, goos, goarch, cached=True)
            self._build_local_client_artifact(artifact_path, filename, goos, goarch)
        return self._client_artifact_payload(artifact_id, filename, source, goos, goarch, cached=False)

    def _client_artifact_payload(self, artifact_id: str, filename: str, source: str, goos: str, goarch: str, *, cached: bool) -> dict[str, object]:
        return {
            "artifact_id": artifact_id,
            "filename": filename,
            "download_path": f"/api/v1/tools/download/client-artifacts/{artifact_id}",
            "source": source,
            "goos": goos,
            "goarch": goarch,
            "version": settings.app_version,
            "cached": cached,
        }

    def _build_local_client_artifact(self, artifact_path: Path, filename: str, goos: str, goarch: str) -> None:
        client_dir = self._repo_root / "client"
        if not client_dir.exists():
            raise AppError("CLIENT_SOURCE_NOT_FOUND", "Client source tree not found", 500)

        executable_suffix = ".exe" if goos == "windows" else ""
        env = os.environ.copy()
        env["GOOS"] = goos
        env["GOARCH"] = goarch
        env["CGO_ENABLED"] = "0"

        with tempfile.TemporaryDirectory(prefix="wfm-client-build-") as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            ctl_path = temp_dir / f"wfmctl{executable_suffix}"
            agent_path = temp_dir / f"wfm-agent{executable_suffix}"
            self._run_go_build(client_dir, env, ctl_path, "./cmd/ctl", settings.app_version)
            self._run_go_build(client_dir, env, agent_path, "./cmd/agent", settings.app_version)

            temp_zip = artifact_path.with_suffix(".tmp")
            with ZipFile(temp_zip, "w", ZIP_DEFLATED) as archive:
                archive.write(ctl_path, arcname=ctl_path.name)
                archive.write(agent_path, arcname=agent_path.name)
                archive.writestr(
                    "README.txt",
                    "\n".join(
                        [
                            "WG Free Mesh client package",
                            f"Version: {settings.app_version}",
                            f"Target: {goos}/{goarch}",
                            "",
                            "Run wfmctl install from this directory to install and start the system service.",
                        ]
                    ),
                )
            temp_zip.replace(artifact_path)

    def _run_go_build(self, client_dir: Path, env: dict[str, str], output_path: Path, package: str, version: str) -> None:
        try:
            result = subprocess.run(
                [
                    "go",
                    "build",
                    "-trimpath",
                    "-ldflags",
                    f"-X wfm/client/internal/bind.Version={version}",
                    "-o",
                    str(output_path),
                    package,
                ],
                cwd=client_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except FileNotFoundError as exc:
            raise AppError("GO_TOOLCHAIN_NOT_FOUND", "Go toolchain is not available on the server", 500) from exc
        except subprocess.TimeoutExpired as exc:
            raise AppError("CLIENT_BUILD_TIMEOUT", "Client build timed out", 500) from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()[-4000:]
            raise AppError("CLIENT_BUILD_FAILED", "Client build failed", 500, {"message": detail})

    def client_artifact_file(self, artifact_id: str) -> tuple[Path, str]:
        path = self._client_artifact_path(artifact_id)
        if not path.exists():
            raise AppError("CLIENT_ARTIFACT_NOT_FOUND", "Client artifact not found", 404)
        return path, path.name

    def config_bulk_options(self, config_id: str | None = None) -> dict[str, object]:
        configs = [
            {
                "id": config.id,
                "name": config.name,
                "enabled": config.enabled,
                "node_count": config.node_count,
                "dynamic_node_count": config.dynamic_node_count,
                "disabled_node_count": config.disabled_node_count,
            }
            for config in store.list_configs()
        ]
        nodes: list[dict[str, object]] = []
        if config_id:
            store.get_config(config_id)
            sync_by_node_id = {str(item["node_id"]): item for item in store.get_sync_status_for_config(config_id)}
            for node in store.list_nodes(config_id):
                if not node.enabled:
                    continue
                sync_status = sync_by_node_id.get(node.id, {})
                nodes.append(
                    {
                        "id": node.id,
                        "name": node.name,
                        "node_type": node.node_type,
                        "virtual_ip": node.virtual_ip,
                        "auto_sync": node.auto_sync,
                        "can_download": bool(sync_status.get("staged_sha256")),
                        "staged_version": sync_status.get("staged_version", 0),
                        "staged_sha256": sync_status.get("staged_sha256", ""),
                        "sync_status": sync_status.get("status", "unknown"),
                    }
                )
        return {"configs": configs, "nodes": nodes}

    def create_config_bulk_package(self, config_id: str, node_ids: list[str]) -> dict[str, object]:
        config = store.get_config(config_id)
        unique_node_ids = list(dict.fromkeys(node_ids))
        if not unique_node_ids:
            raise AppError("CONFIG_BULK_EMPTY_SELECTION", "Select at least one endpoint", 400)

        entries: list[dict[str, object]] = []
        unavailable: list[dict[str, str]] = []
        filenames: set[str] = set()
        for node_id in unique_node_ids:
            node = store.get_node(node_id)
            if node.config_id != config_id:
                raise AppError("NODE_CONFIG_MISMATCH", "Node does not belong to this config", 400)
            if not node.enabled:
                raise AppError("NODE_DISABLED", "Disabled endpoint cannot download config", 409)
            package = store.download_package(config_id, node_id)
            content = str(package.get("content") or "")
            state = store.get_node_config_state(config_id, node_id)
            if not content.strip() or not state.staged_sha256:
                unavailable.append({"node_id": node.id, "node_name": node.name})
                continue
            filename = self._deduplicate_filename(f"{node_config_artifact_stem(config.name, node.name)}.conf", filenames)
            entries.append(
                {
                    "node_id": node.id,
                    "node_name": node.name,
                    "filename": filename,
                    "content": content,
                    "staged_version": state.staged_version,
                    "staged_sha256": state.staged_sha256,
                }
            )

        if unavailable:
            raise AppError("CONFIG_BULK_NODE_NOT_READY", "Some endpoints have no staged config", 409, {"nodes": unavailable})
        if not entries:
            raise AppError("CONFIG_BULK_EMPTY_SELECTION", "Select at least one downloadable endpoint", 400)

        package_id = new_id("bulk")
        filename = f"wg-configs-{config_artifact_name_segment(config.name, 'config')}-{now_utc().strftime('%Y%m%d-%H%M%S')}.zip"
        path = self._config_bulk_root / f"{package_id}.zip"
        manifest = {
            "config_id": config.id,
            "config_name": config.name,
            "generated_at": now_utc().isoformat(),
            "nodes": [
                {
                    "node_id": entry["node_id"],
                    "node_name": entry["node_name"],
                    "filename": entry["filename"],
                    "staged_version": entry["staged_version"],
                    "staged_sha256": entry["staged_sha256"],
                }
                for entry in entries
            ],
        }
        with self._config_bulk_lock:
            self._remove_existing_config_bulk_packages()
            with ZipFile(path, "w", ZIP_DEFLATED) as archive:
                for entry in entries:
                    archive.writestr(str(entry["filename"]), str(entry["content"]))
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=True, indent=2))

        return {
            "package_id": package_id,
            "filename": filename,
            "download_path": f"/api/v1/tools/download/config-bulk/{package_id}",
            "config_id": config.id,
            "config_name": config.name,
            "node_count": len(entries),
        }

    @staticmethod
    def _deduplicate_filename(filename: str, used: set[str]) -> str:
        if filename not in used:
            used.add(filename)
            return filename
        stem = filename.removesuffix(".conf")
        index = 2
        while f"{stem}-{index}.conf" in used:
            index += 1
        next_name = f"{stem}-{index}.conf"
        used.add(next_name)
        return next_name

    def config_bulk_file(self, package_id: str) -> Path:
        path = self._config_bulk_root / f"{package_id}.zip"
        if path.parent != self._config_bulk_root or not path.exists():
            raise AppError("CONFIG_BULK_PACKAGE_NOT_FOUND", "Config bulk package not found", 404)
        return path

    def _remove_existing_config_bulk_packages(self) -> None:
        for path in self._config_bulk_root.glob("*.zip"):
            path.unlink(missing_ok=True)


download_tools_service = DownloadToolsService()
