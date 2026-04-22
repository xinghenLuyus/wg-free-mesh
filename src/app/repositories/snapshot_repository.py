from __future__ import annotations

from pathlib import Path

from app.core.errors import AppError
from app.domain.models import SnapshotInfo
from app.infrastructure.database import connect
from app.repositories.row_mappers import snapshot_from_row as _snapshot_from_row


class SnapshotRepository:
    def list_snapshots(self) -> list[SnapshotInfo]:
        with connect() as connection:
            rows = connection.execute("SELECT * FROM backups ORDER BY created_at DESC").fetchall()
        return [_snapshot_from_row(row) for row in rows]

    def get_snapshot(self, snapshot_id: str) -> SnapshotInfo:
        with connect() as connection:
            row = connection.execute("SELECT * FROM backups WHERE id = ?", (snapshot_id,)).fetchone()
        if row is None:
            raise AppError("SNAPSHOT_NOT_FOUND", "Snapshot not found", 404)
        return _snapshot_from_row(row)

    def get_snapshot_by_path(self, path: Path) -> SnapshotInfo | None:
        with connect() as connection:
            row = connection.execute("SELECT * FROM backups WHERE path = ?", (str(path),)).fetchone()
        return _snapshot_from_row(row) if row is not None else None

    def snapshot_id_exists(self, snapshot_id: str) -> bool:
        with connect() as connection:
            row = connection.execute("SELECT 1 FROM backups WHERE id = ?", (snapshot_id,)).fetchone()
        return row is not None

    def upsert_snapshot(self, snapshot: SnapshotInfo) -> SnapshotInfo:
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO backups (id, name, path, size, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  name = excluded.name,
                  path = excluded.path,
                  size = excluded.size,
                  note = excluded.note,
                  created_at = excluded.created_at
                """,
                (
                    snapshot.id,
                    snapshot.name,
                    snapshot.path,
                    snapshot.size,
                    snapshot.note,
                    snapshot.created_at.isoformat(),
                ),
            )
        return self.get_snapshot(snapshot.id)

    def delete_snapshot(self, snapshot_id: str) -> None:
        with connect() as connection:
            connection.execute("DELETE FROM backups WHERE id = ?", (snapshot_id,))

    def update_snapshot_note(self, snapshot_id: str, note: str) -> SnapshotInfo:
        self.get_snapshot(snapshot_id)
        with connect() as connection:
            connection.execute("UPDATE backups SET note = ? WHERE id = ?", (note, snapshot_id))
        return self.get_snapshot(snapshot_id)

    def replace_snapshots(self, snapshots: list[SnapshotInfo]) -> list[SnapshotInfo]:
        with connect() as connection:
            connection.execute("DELETE FROM backups")
            connection.executemany(
                "INSERT INTO backups (id, name, path, size, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        snapshot.id,
                        snapshot.name,
                        snapshot.path,
                        snapshot.size,
                        snapshot.note,
                        snapshot.created_at.isoformat(),
                    )
                    for snapshot in snapshots
                ],
            )
        return self.list_snapshots()


snapshot_repository = SnapshotRepository()
