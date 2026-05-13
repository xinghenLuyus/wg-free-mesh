from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import tomllib


@lru_cache
def read_project_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    version = str(project.get("version", "")).strip()
    if not version:
        raise RuntimeError("Project version is missing in src/pyproject.toml")
    return version

