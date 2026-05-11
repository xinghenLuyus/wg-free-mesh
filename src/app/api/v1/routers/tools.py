from __future__ import annotations

from typing import Annotated, Any

from fastapi import Body, Query
from fastapi.responses import FileResponse

from app.api.v1.routing import SessionProtectedAPIRouter
from app.core.responses import ApiResponse, ok
from app.services.download_tools_service import download_tools_service

router = SessionProtectedAPIRouter(prefix="/tools", tags=["tools"])


@router.get("/download/client-options")
def client_download_options() -> ApiResponse[dict[str, object]]:
    return ok(download_tools_service.client_options())


@router.post("/download/client-artifacts/build")
def build_client_artifact(payload: Annotated[dict[str, Any], Body()]) -> ApiResponse[dict[str, object]]:
    return ok(
        download_tools_service.build_client_artifact(
            str(payload.get("source") or ""),
            str(payload.get("goos") or ""),
            str(payload.get("goarch") or ""),
        )
    )


@router.get("/download/client-artifacts/{artifact_id}")
def download_client_artifact(artifact_id: str) -> FileResponse:
    path, filename = download_tools_service.client_artifact_file(artifact_id)
    return FileResponse(path=str(path), filename=filename, media_type="application/zip")


@router.get("/download/config-bulk/options")
def config_bulk_options(config_id: Annotated[str | None, Query()] = None) -> ApiResponse[dict[str, object]]:
    return ok(download_tools_service.config_bulk_options(config_id))


@router.post("/download/config-bulk/package")
def create_config_bulk_package(payload: Annotated[dict[str, Any], Body()]) -> ApiResponse[dict[str, object]]:
    node_ids = payload.get("node_ids")
    return ok(
        download_tools_service.create_config_bulk_package(
            str(payload.get("config_id") or ""),
            [str(item) for item in node_ids] if isinstance(node_ids, list) else [],
        )
    )


@router.get("/download/config-bulk/{package_id}")
def download_config_bulk_package(package_id: str) -> FileResponse:
    path = download_tools_service.config_bulk_file(package_id)
    return FileResponse(path=str(path), filename=path.name, media_type="application/zip")
