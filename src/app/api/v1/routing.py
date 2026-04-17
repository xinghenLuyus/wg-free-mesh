from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.v1.deps import require_current_user


class SessionProtectedAPIRouter(APIRouter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        dependencies = list(kwargs.pop("dependencies", []))
        dependencies.append(Depends(require_current_user))
        super().__init__(*args, dependencies=dependencies, **kwargs)
