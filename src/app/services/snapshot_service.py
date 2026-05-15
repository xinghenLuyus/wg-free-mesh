from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from app.core.errors import AppError
from app.data.application_snapshot import (
    SNAPSHOT_DATA_ENTRY,
    archive_has_database,
    export_database_payload,
    import_database_from_archive,
)
from app.domain.models import SnapshotInfo, new_id, now_utc
from app.data.database import backups_dir, data_dir, init_database, wireguard_dir
from app.data.repositories.snapshots import snapshot_repository

SNAPSHOT_MANIFEST = "snapshot_manifest.json"


class SnapshotService:
    def list_snapshots(self) -> list[SnapshotInfo]:
        return self.rebuild_index_from_disk()

    def create_snapshot(self, note: str) -> SnapshotInfo:
        created_at = now_utc()
        snapshot = SnapshotInfo(
            id=new_id("snap"),
            name=self._unique_snapshot_name(created_at),
            path="",
            size=0,
            note=note.strip(),
            created_at=created_at,
        )
        snapshot_path = backups_dir() / snapshot.name
        snapshot.path = str(snapshot_path)
        snapshot_repository.upsert_snapshot(snapshot)
        self._write_archive(snapshot_path, snapshot)
        finalized = snapshot.model_copy(update={"size": snapshot_path.stat().st_size})
        snapshot_repository.upsert_snapshot(finalized)
        return finalized

    def get_snapshot_path(self, snapshot_id: str) -> Path:
        return Path(snapshot_repository.get_snapshot(snapshot_id).path)

    def export_snapshot(self, snapshot_id: str) -> Path:
        path = self.get_snapshot_path(snapshot_id)
        if not path.exists():
            raise AppError("SNAPSHOT_NOT_FOUND", "Snapshot package not found", 404)
        return path

    def delete_snapshot(self, snapshot_id: str) -> None:
        snapshot = snapshot_repository.get_snapshot(snapshot_id)
        path = Path(snapshot.path)
        if path.exists():
            path.unlink()
        snapshot_repository.delete_snapshot(snapshot_id)

    def update_snapshot_note(self, snapshot_id: str, note: str) -> SnapshotInfo:
        snapshot = snapshot_repository.get_snapshot(snapshot_id)
        normalized_note = note.strip()
        self._rewrite_manifest(Path(snapshot.path), normalized_note)
        return snapshot_repository.update_snapshot_note(snapshot_id, normalized_note)

    def restore_snapshot(self, snapshot_id: str) -> None:
        snapshot = snapshot_repository.get_snapshot(snapshot_id)
        self.restore_snapshot_archive(Path(snapshot.path))

    def restore_snapshot_archive(self, path: Path) -> None:
        archive_path = Path(path)
        self._validate_archive(archive_path)
        self._clear_wireguard_dir()
        with ZipFile(archive_path, "r") as archive:
            import_database_from_archive(archive)
            self._safe_extract(archive, Path.cwd())
        init_database()
        self.rebuild_index_from_disk()

    def import_snapshot(self, uploaded_path: Path, original_name: str | None = None) -> SnapshotInfo:
        source_path = Path(uploaded_path)
        self._validate_archive(source_path)
        target_name = self._unique_import_name(original_name or source_path.name)
        target_path = backups_dir() / target_name
        shutil.copy2(source_path, target_path)
        snapshots = self.rebuild_index_from_disk()
        imported = next((item for item in snapshots if Path(item.path) == target_path), None)
        if imported is None:
            raise AppError("SNAPSHOT_IMPORT_FAILED", "Imported snapshot was not indexed", 500)
        return imported

    def rebuild_index_from_disk(self) -> list[SnapshotInfo]:
        backup_root = backups_dir()
        existing_by_path = {Path(item.path): item for item in snapshot_repository.list_snapshots()}
        scanned: list[SnapshotInfo] = []
        used_ids: set[str] = set()
        for path in sorted(backup_root.glob("*.zip")):
            snapshot = self._snapshot_from_archive(path, existing_by_path.get(path), used_ids)
            scanned.append(snapshot)
            used_ids.add(snapshot.id)
        snapshot_repository.replace_snapshots(scanned)
        return snapshot_repository.list_snapshots()

    def _unique_snapshot_name(self, created_at) -> str:
        base = created_at.strftime("snapshot_%Y%m%d_%H%M%S")
        candidate = f"{base}.zip"
        index = 1
        while (backups_dir() / candidate).exists():
            candidate = f"{base}_{index}.zip"
            index += 1
        return candidate

    def _unique_import_name(self, filename: str) -> str:
        source_name = Path(filename or "snapshot_import.zip").name or "snapshot_import.zip"
        if not source_name.lower().endswith(".zip"):
            source_name = f"{source_name}.zip"
        stem = Path(source_name).stem
        suffix = Path(source_name).suffix or ".zip"
        candidate = source_name
        index = 1
        while (backups_dir() / candidate).exists():
            candidate = f"{stem}_{index}{suffix}"
            index += 1
        return candidate

    def _write_archive(self, snapshot_path: Path, snapshot: SnapshotInfo) -> None:
        with ZipFile(snapshot_path, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(SNAPSHOT_DATA_ENTRY, export_database_payload())
            for file in wireguard_dir().rglob("*"):
                if file.is_file():
                    archive.write(file, arcname=str(file.relative_to(Path.cwd())))
            archive.writestr(SNAPSHOT_MANIFEST, self._manifest_text(snapshot))

    def _clear_wireguard_dir(self) -> None:
        target = wireguard_dir().resolve()
        data_root = data_dir().resolve()
        if target == data_root or data_root not in target.parents:
            raise AppError("SNAPSHOT_RESTORE_UNSAFE_PATH", "WireGuard data path is unsafe", 500)
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)

    def _rewrite_manifest(self, archive_path: Path, note: str) -> None:
        if not archive_path.exists():
            raise AppError("SNAPSHOT_NOT_FOUND", "Snapshot package not found", 404)
        snapshot = self._snapshot_from_archive(archive_path, snapshot_repository.get_snapshot_by_path(archive_path), set())
        updated = snapshot.model_copy(update={"note": note})
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip", dir=archive_path.parent) as temp_file:
            temp_path = Path(temp_file.name)
        try:
            with ZipFile(archive_path, "r") as source, ZipFile(temp_path, "w", compression=ZIP_DEFLATED) as target:
                for info in source.infolist():
                    if info.filename == SNAPSHOT_MANIFEST:
                        continue
                    target.writestr(info, source.read(info.filename))
                target.writestr(SNAPSHOT_MANIFEST, self._manifest_text(updated))
            temp_path.replace(archive_path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _snapshot_from_archive(
        self,
        path: Path,
        existing: SnapshotInfo | None,
        used_ids: set[str],
    ) -> SnapshotInfo:
        stat = path.stat()
        manifest = self._read_manifest(path)
        created_at = self._manifest_created_at(manifest) or (existing.created_at if existing else now_utc())
        note = self._manifest_note(manifest)
        if note is None:
            note = existing.note if existing else ""
        snapshot_id = self._normalize_snapshot_id(manifest, path, used_ids)
        return SnapshotInfo(
            id=snapshot_id,
            name=path.name,
            path=str(path),
            size=stat.st_size,
            note=note,
            created_at=created_at,
        )

    def _normalize_snapshot_id(self, manifest: dict[str, object] | None, path: Path, used_ids: set[str]) -> str:
        raw_id = str(manifest.get("id")).strip() if manifest and manifest.get("id") else ""
        candidate = raw_id or f"snap_file_{path.stem}"
        while candidate in used_ids:
            candidate = new_id("snap")
        return candidate

    def _manifest_text(self, snapshot: SnapshotInfo) -> str:
        return json.dumps(
            {
                "version": 1,
                "id": snapshot.id,
                "name": snapshot.name,
                "created_at": snapshot.created_at.isoformat(),
                "note": snapshot.note,
            },
            ensure_ascii=False,
            indent=2,
        )

    def _read_manifest(self, path: Path) -> dict[str, object] | None:
        try:
            with ZipFile(path, "r") as archive:
                try:
                    payload = archive.read(SNAPSHOT_MANIFEST)
                except KeyError:
                    return None
        except BadZipFile as exc:
            raise AppError("SNAPSHOT_INVALID_ARCHIVE", "Snapshot archive is invalid", 400) from exc
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _manifest_created_at(self, manifest: dict[str, object] | None):
        if not manifest:
            return None
        created_at = manifest.get("created_at")
        if not isinstance(created_at, str) or not created_at.strip():
            return None
        try:
            return datetime.fromisoformat(created_at)
        except ValueError:
            return None

    def _manifest_note(self, manifest: dict[str, object] | None) -> str | None:
        if not manifest:
            return None
        note = manifest.get("note")
        return str(note).strip() if note is not None else None

    def _validate_archive(self, path: Path) -> None:
        if not path.exists():
            raise AppError("SNAPSHOT_NOT_FOUND", "Snapshot package not found", 404)
        try:
            with ZipFile(path, "r") as archive:
                has_database = archive_has_database(archive)
        except BadZipFile as exc:
            raise AppError("SNAPSHOT_INVALID_ARCHIVE", "Snapshot archive is invalid", 400) from exc
        if not has_database:
            raise AppError("SNAPSHOT_INVALID_ARCHIVE", "Snapshot archive is invalid", 400)

    def _safe_extract(self, archive: ZipFile, destination: Path) -> None:
        root = destination.resolve()
        skipped = {SNAPSHOT_MANIFEST, SNAPSHOT_DATA_ENTRY}
        members = [
            member
            for member in archive.infolist()
            if member.filename not in skipped and not member.filename.endswith("wg_free_mesh.db")
        ]
        for member in members:
            target_path = (root / member.filename).resolve()
            if target_path != root and root not in target_path.parents:
                raise AppError("SNAPSHOT_INVALID_ARCHIVE", "Snapshot archive is invalid", 400)
        archive.extractall(root, members=members)


snapshot_service = SnapshotService()
