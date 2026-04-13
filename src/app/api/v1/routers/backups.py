from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi import APIRouter, Body, File, UploadFile
from fastapi.responses import FileResponse

from app.core.responses import ApiResponse, ok
from app.services.control_plane_service import control_plane_service

router = APIRouter(prefix="/backups", tags=["backups"])


@router.post("/snapshot")
def create_snapshot(note: str = Body(default="")) -> ApiResponse[dict[str, object]]:
    return ok(control_plane_service.create_snapshot(note).model_dump(mode="json"))


@router.get("/list")
def list_snapshots() -> ApiResponse[list[dict[str, object]]]:
    return ok([item.model_dump(mode="json") for item in control_plane_service.list_snapshots()])


@router.get("/download/{snapshot_id}")
def download_snapshot(snapshot_id: str) -> FileResponse:
    path = control_plane_service.get_snapshot_path(snapshot_id)
    return FileResponse(path=str(path), filename=path.name, media_type="application/octet-stream")


@router.post("/restore/{snapshot_id}")
def restore_snapshot(snapshot_id: str) -> ApiResponse[dict[str, str]]:
    control_plane_service.restore_snapshot(snapshot_id)
    return ok({"message": "快照已恢复"})


@router.post("/upload")
async def upload_snapshot(file: UploadFile = File(...)) -> ApiResponse[dict[str, str]]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
        temp_file.write(await file.read())
        temp_path = Path(temp_file.name)
    try:
        control_plane_service.restore_uploaded_snapshot(temp_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return ok({"message": "上传快照已恢复"})


@router.delete("/{snapshot_id}")
def delete_snapshot(snapshot_id: str) -> ApiResponse[dict[str, str]]:
    control_plane_service.delete_snapshot(snapshot_id)
    return ok({"message": "快照已删除"})


@router.put("/{snapshot_id}/note")
def update_snapshot_note(snapshot_id: str, note: str = Body(default="")) -> ApiResponse[dict[str, object]]:
    return ok(control_plane_service.update_snapshot_note(snapshot_id, note).model_dump(mode="json"))
