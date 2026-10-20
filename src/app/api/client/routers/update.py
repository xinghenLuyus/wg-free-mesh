from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from app.core.responses import ApiResponse, ok
from app.services.client_update_service import client_update_service

router = APIRouter(prefix="/update", tags=["client-update"])
basic = HTTPBasic()


class UpdateCheck(BaseModel):
    config_id: str
    node_id: str
    goos: str
    goarch: str


class UpdateArtifact(UpdateCheck):
    version: str
    source: Literal["github_release", "local_build"]


@router.post("/check")
def check_update(payload: UpdateCheck, credentials: Annotated[HTTPBasicCredentials, Depends(basic)]) -> ApiResponse[dict[str, object]]:
    client_update_service.authorize(payload.config_id, payload.node_id, credentials.username, credentials.password)
    return ok(client_update_service.check(payload.goos, payload.goarch))


@router.post("/artifact")
def prepare_update(payload: UpdateArtifact, credentials: Annotated[HTTPBasicCredentials, Depends(basic)]) -> ApiResponse[dict[str, object]]:
    client_update_service.authorize(payload.config_id, payload.node_id, credentials.username, credentials.password)
    return ok(client_update_service.artifact(payload.source, payload.goos, payload.goarch, payload.version, payload.node_id))
