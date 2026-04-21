from fastapi import APIRouter

from app.core.responses import ApiResponse, ok
from app.schemas.auth import AuthStateRead
from app.services.auth_service import auth_service

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/reset-bootstrap")
def reset_bootstrap() -> ApiResponse[dict[str, object]]:
    state = AuthStateRead.model_validate(auth_service.reset_bootstrap_state())
    return ok(
        {
            "message": "Bootstrap state has been reset",
            "auth_state": state.model_dump(mode="json"),
        }
    )
