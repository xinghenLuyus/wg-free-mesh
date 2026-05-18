from __future__ import annotations

import json
from typing import Any
from zipfile import ZipFile

from sqlalchemy import delete, inspect, insert, select

from app.core.errors import AppError
from app.data.connection import get_engine
from app.data.database import reset_database_objects
from app.data.schema import metadata


SNAPSHOT_DATA_ENTRY = "database.json"


def export_database_payload() -> str:
    engine = get_engine()
    tables: dict[str, list[dict[str, Any]]] = {}
    with engine.begin() as connection:
        for table in metadata.sorted_tables:
            rows = [dict(row) for row in connection.execute(select(table)).mappings().all()]
            tables[table.name] = rows
    payload: dict[str, object] = {"format": "application", "tables": tables}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def import_database_payload(payload: str) -> None:
    parsed = json.loads(payload)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("tables"), dict):
        raise AppError("SNAPSHOT_INVALID_ARCHIVE", "Snapshot archive is invalid", 400)
    reset_database_objects()
    tables_payload = parsed["tables"]
    engine = get_engine()
    with engine.begin() as connection:
        for table in reversed(metadata.sorted_tables):
            connection.execute(delete(table))
        for table in metadata.sorted_tables:
            rows = tables_payload.get(table.name, [])
            if not isinstance(rows, list):
                raise AppError("SNAPSHOT_INVALID_ARCHIVE", "Snapshot archive is invalid", 400)
            if rows:
                connection.execute(insert(table), rows)


def import_database_from_archive(archive: ZipFile) -> None:
    names = set(archive.namelist())
    if SNAPSHOT_DATA_ENTRY in names:
        import_database_payload(archive.read(SNAPSHOT_DATA_ENTRY).decode("utf-8"))
        return
    raise AppError("SNAPSHOT_INVALID_ARCHIVE", "Snapshot archive is invalid", 400)


def archive_has_database(archive: ZipFile) -> bool:
    names = set(archive.namelist())
    return SNAPSHOT_DATA_ENTRY in names


def assert_schema_ready() -> None:
    current = set(inspect(get_engine()).get_table_names())
    required = {table.name for table in metadata.sorted_tables}
    missing = required - current
    if missing:
        raise RuntimeError(f"Database schema is missing tables: {', '.join(sorted(missing))}")
