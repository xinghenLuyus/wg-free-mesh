from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.api.v1.routing import SessionProtectedAPIRouter
from app.core.errors import AppError
from app.core.responses import ApiResponse, ok
from app.core.validation import strip_required_text
from app.services.control_plane_service import control_plane_service

router = SessionProtectedAPIRouter(prefix="/mcp-access", tags=["mcp-access"])


def _audit_time(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


class McpTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    permission: Literal["read", "write"]
    expires_at: datetime

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return strip_required_text(value, "Name")


class McpAuditDeleteRequest(BaseModel):
    created_from: datetime
    created_to: datetime


@router.get("/tokens")
def list_tokens() -> ApiResponse[list[dict[str, object]]]:
    return ok(control_plane_service.list_mcp_tokens())


@router.post("/tokens")
def create_token(payload: McpTokenRequest) -> ApiResponse[dict[str, object]]:
    return ok(control_plane_service.create_mcp_token(payload.model_dump(mode="json")))


@router.post("/tokens/{token_id}/revoke")
def revoke_token(token_id: str) -> ApiResponse[dict[str, object]]:
    return ok(control_plane_service.revoke_mcp_token(token_id))


@router.get("/audit")
def list_audit(
    limit: int = 100,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    token_name: str = "",
    target_name: str = "",
) -> ApiResponse[list[dict[str, object]]]:
    return ok(
        control_plane_service.list_mcp_audit_logs(
            limit,
            created_from=_audit_time(created_from),
            created_to=_audit_time(created_to),
            token_name=token_name,
            target_name=target_name,
        )
    )


@router.delete("/audit")
def delete_audit(payload: McpAuditDeleteRequest) -> ApiResponse[dict[str, object]]:
    if payload.created_to < payload.created_from:
        raise AppError("MCP_AUDIT_RANGE_INVALID", "Audit cleanup end time must be after start time", 400)
    return ok(
        control_plane_service.delete_mcp_audit_logs(
            created_from=_audit_time(payload.created_from) or "",
            created_to=_audit_time(payload.created_to) or "",
        )
    )
