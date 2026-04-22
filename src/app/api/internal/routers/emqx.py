from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.services.mqtt_auth_service import mqtt_auth_service

router = APIRouter(prefix="/emqx", tags=["internal-emqx"])


class EmqxAuthzRequest(BaseModel):
    username: str
    clientid: str
    topic: str
    action: Literal["publish", "subscribe"]


class EmqxAuthzResponse(BaseModel):
    result: Literal["allow", "deny"]


@router.post("/authz")
def authorize(
    payload: EmqxAuthzRequest,
    internal_key: Annotated[str | None, Header(alias="x-wfm-internal-key")] = None,
) -> EmqxAuthzResponse:
    if internal_key != settings.emqx_authz_shared_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    allowed = mqtt_auth_service.authz_decision(
        username=payload.username,
        client_id=payload.clientid,
        topic=payload.topic,
        action=payload.action,
    )
    return EmqxAuthzResponse(result="allow" if allowed else "deny")
