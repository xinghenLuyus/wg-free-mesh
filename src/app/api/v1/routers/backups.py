from __future__ import annotations

from pathlib import Path
import tempfile

from typing import Annotated

from fastapi import APIRouter, Body, File, Header, Query, UploadFile
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse

from app.api.v1.routing import SessionProtectedAPIRouter
from app.api.v1.deps import require_file_download_or_user
from app.core.responses import ApiResponse, ok
from app.services.control_plane_service import control_plane_service

router = SessionProtectedAPIRouter(prefix="/backups", tags=["backups"])
download_router = APIRouter(prefix="/backups", tags=["backups"])


class SnapshotCreateRequest(BaseModel):
    note: str = ""
    password: str = Field(min_length=1)


class SnapshotRestoreRequest(BaseModel):
    password: str = Field(min_length=1)


async def _import_snapshot_file(file: UploadFile) -> dict[str, object]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
        temp_file.write(await file.read())
        temp_path = Path(temp_file.name)
    try:
        return control_plane_service.import_snapshot(temp_path, file.filename).model_dump(mode="json")
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.post("/snapshot")
async def create_snapshot(payload: SnapshotCreateRequest) -> ApiResponse[dict[str, object]]:
    snapshot = control_plane_service.create_snapshot(payload.note, payload.password).model_dump(mode="json")
    await control_plane_service.publish_snapshots()
    return ok(snapshot)


@router.get("/list")
def list_snapshots() -> ApiResponse[list[dict[str, object]]]:
    return ok([item.model_dump(mode="json") for item in control_plane_service.list_snapshots()])


@download_router.get("/download/{snapshot_id}")
def download_snapshot(
    snapshot_id: str,
    authorization: Annotated[str | None, Header()] = None,
    download_token: Annotated[str | None, Query()] = None,
) -> FileResponse:
    require_file_download_or_user("snapshot_export", snapshot_id, authorization, download_token)
    path = control_plane_service.export_snapshot(snapshot_id)
    return FileResponse(path=str(path), filename=path.name, media_type="application/octet-stream")


@download_router.get("/export/{snapshot_id}")
def export_snapshot(
    snapshot_id: str,
    authorization: Annotated[str | None, Header()] = None,
    download_token: Annotated[str | None, Query()] = None,
) -> FileResponse:
    require_file_download_or_user("snapshot_export", snapshot_id, authorization, download_token)
    path = control_plane_service.export_snapshot(snapshot_id)
    return FileResponse(path=str(path), filename=path.name, media_type="application/octet-stream")


@router.post("/restore/{snapshot_id}")
async def restore_snapshot(snapshot_id: str, payload: SnapshotRestoreRequest) -> ApiResponse[dict[str, object]]:
    control_plane_service.restore_snapshot(snapshot_id, payload.password)
    recovery = await control_plane_service.recover_after_snapshot_restore()
    await control_plane_service.publish_full_state()
    return ok({"message": "Snapshot restored", "recovery": recovery})


@router.post("/upload")
async def upload_snapshot(file: Annotated[UploadFile, File(...)]) -> ApiResponse[dict[str, object]]:
    snapshot = await _import_snapshot_file(file)
    await control_plane_service.publish_snapshots()
    return ok(snapshot)


@router.post("/import")
async def import_snapshot(file: Annotated[UploadFile, File(...)]) -> ApiResponse[dict[str, object]]:
    snapshot = await _import_snapshot_file(file)
    await control_plane_service.publish_snapshots()
    return ok(snapshot)


@router.delete("/{snapshot_id}")
async def delete_snapshot(snapshot_id: str) -> ApiResponse[dict[str, str]]:
    control_plane_service.delete_snapshot(snapshot_id)
    await control_plane_service.publish_snapshots()
    return ok({"message": "Snapshot deleted"})


@router.put("/{snapshot_id}/note")
async def update_snapshot_note(
    snapshot_id: str,
    note: Annotated[str, Body()] = "",
) -> ApiResponse[dict[str, object]]:
    snapshot = control_plane_service.update_snapshot_note(snapshot_id, note).model_dump(mode="json")
    await control_plane_service.publish_snapshots()
    return ok(snapshot)
