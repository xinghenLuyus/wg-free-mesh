from __future__ import annotations

import hashlib

from app.core.config import settings
from app.core.errors import AppError
from app.data.store import store
from app.services.auth_service import auth_service
from app.services.download_tools_service import GITHUB_RELEASE_REPOSITORY, download_tools_service


class ClientUpdateService:
    def authorize(self, config_id: str, node_id: str, username: str, password: str) -> None:
        download_tools_service._require_client_tools()
        if not store.verify_client_update_credentials(config_id, node_id, username, password):
            raise AppError("CLIENT_UPDATE_UNAUTHORIZED", "Client binding credentials are invalid", 401)

    def check(self, goos: str, goarch: str) -> dict[str, object]:
        download_tools_service._validate_client_target("github_release", goos, goarch)
        return {"version": settings.app_version, "goos": goos, "goarch": goarch}

    def artifact(self, source: str, goos: str, goarch: str, version: str, node_id: str) -> dict[str, object]:
        download_tools_service._validate_client_target(source, goos, goarch)
        if version != settings.app_version:
            raise AppError("CLIENT_UPDATE_VERSION_CHANGED", "Server version changed; run update again", 409)
        filename = download_tools_service._client_artifact_filename(goos, goarch)
        if source == "github_release":
            url = f"https://github.com/{GITHUB_RELEASE_REPOSITORY}/releases/download/v{version}/{filename}"
            return {**self.check(goos, goarch), "source": source, "filename": filename,
                    "download_url": url, "checksum_url": f"{url}.sha256"}
        artifact = download_tools_service.build_client_artifact(source, goos, goarch)
        path, _ = download_tools_service.client_artifact_file(str(artifact["artifact_id"]))
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        grant = auth_service.create_file_download_token(
            kind="client_artifact", resource_id=str(artifact["artifact_id"]), subject=f"client:{node_id}"
        )
        return {**artifact, "sha256": digest.hexdigest(), "download_token": grant["access_token"]}


client_update_service = ClientUpdateService()
