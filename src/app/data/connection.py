from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
import re
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine, Result
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.data.paths import data_dir


_ENGINE: Engine | None = None


class ResultProxy:
    def __init__(self, result: Result[Any]):
        self._result = result

    def fetchone(self) -> Any | None:
        row = self._result.fetchone()
        return self._row_dict(row) if row is not None else None

    def fetchall(self) -> list[Any]:
        return [self._row_dict(row) for row in self._result.fetchall()]

    def _row_dict(self, row: Any) -> dict[str, Any]:
        keys = getattr(row, "_fields", self._result.keys())
        return {str(key): row[index] for index, key in enumerate(keys)}


class ConnectionProxy:
    def __init__(self, connection: Connection):
        self._connection = connection

    @property
    def dialect_name(self) -> str:
        return self._connection.dialect.name

    def execute(self, statement: str, params: Sequence[Any] | dict[str, Any] | None = None) -> ResultProxy:
        sql, bound = self._prepare(statement, params)
        return ResultProxy(self._connection.execute(text(sql), bound))

    def executemany(self, statement: str, rows: Sequence[Sequence[Any] | dict[str, Any]]) -> None:
        for row in rows:
            self.execute(statement, row)

    def _prepare(
        self,
        statement: str,
        params: Sequence[Any] | dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        sql = _normalize_sql(statement, self.dialect_name)
        if params is None:
            return sql, {}
        if isinstance(params, dict):
            return sql, {key: _bind_value(value) for key, value in params.items()}
        values = list(params)
        index = 0

        def replace(_: re.Match[str]) -> str:
            nonlocal index
            key = f"p{index}"
            index += 1
            return f":{key}"

        sql = re.sub(r"\?", replace, sql)
        return sql, {f"p{i}": _bind_value(value) for i, value in enumerate(values)}


def _database_url() -> str:
    url = settings.database
    if url.startswith("sqlite:///"):
        raw_path = url.removeprefix("sqlite:///")
        if raw_path.startswith("./"):
            data_dir().mkdir(parents=True, exist_ok=True)
    return url


def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        url = _database_url()
        connect_args: dict[str, Any] = {}
        pool_options: dict[str, Any] = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            if ":memory:" in url:
                pool_options["poolclass"] = StaticPool
        _ENGINE = create_engine(url, future=True, connect_args=connect_args, **pool_options)
        if _ENGINE.dialect.name == "sqlite":
            _install_sqlite_pragmas(_ENGINE)
    return _ENGINE


def reset_engine() -> None:
    global _ENGINE
    if _ENGINE is not None:
        _ENGINE.dispose()
        _ENGINE = None


def _install_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()


@contextmanager
def connect() -> Iterator[ConnectionProxy]:
    with get_engine().begin() as connection:
        yield ConnectionProxy(connection)


def _normalize_sql(statement: str, dialect_name: str) -> str:
    sql = statement
    if dialect_name == "postgresql":
        sql = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", sql, flags=re.IGNORECASE)
        if re.search(r"\bINSERT\s+INTO\b", sql, flags=re.IGNORECASE) and "ON CONFLICT" not in sql.upper():
            # Only statements originally using INSERT OR IGNORE should reach here with a DO NOTHING need.
            if " OR IGNORE " in statement.upper():
                sql = f"{sql.rstrip()} ON CONFLICT DO NOTHING"
        sql = sql.replace("LIMIT -1", "LIMIT ALL")
    return sql


def _bind_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    return value
