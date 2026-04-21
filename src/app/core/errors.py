from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.responses import ApiErrorResponse, ErrorBody


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        detail: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}


def _error_response(
    status_code: int,
    code: str,
    message: str,
    detail: dict[str, object] | None = None,
) -> JSONResponse:
    body = ApiErrorResponse(error=ErrorBody(code=code, message=message, detail=detail or {}))
    return JSONResponse(status_code=status_code, content=body.model_dump())


FIELD_LABELS = {
    "name": "Name",
    "description": "Description",
    "virtual_subnet": "Virtual subnet",
    "default_dns": "Default DNS",
    "ipv4_address": "Public IPv4",
    "ipv6_address": "Public IPv6",
    "listen_port": "Listen port",
    "virtual_ip": "Virtual IP",
    "dns": "DNS",
    "private_key": "Private key",
    "public_key": "Public key",
    "tag": "Tag",
    "tags": "Tags",
    "peer_node_id": "Peer node",
    "local_node_id": "Local node",
    "allowed_ips": "AllowedIPs",
    "endpoint_manual_host": "Manual Host",
    "endpoint_manual_port": "Manual Port",
    "host": "Host",
    "port": "Port",
    "current_password": "Current password",
    "new_password": "New password",
    "username": "Username",
    "password": "Password",
}


def _field_label(error: dict[str, object]) -> str:
    loc = error.get("loc")
    if not isinstance(loc, (list, tuple)):
        return "Field"
    for item in reversed(loc):
        if isinstance(item, str) and item not in {"body", "query", "path"}:
            return FIELD_LABELS.get(item, item)
    return "Field"


def _clean_validation_message(message: str) -> str:
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message


def _validation_message(error: dict[str, object]) -> str:
    message = _clean_validation_message(str(error.get("msg") or "").strip())
    if message and message not in {"Field required", "Input should be a valid string"}:
        return message

    field = _field_label(error)
    error_type = str(error.get("type") or "")
    context = error.get("ctx")
    ctx = context if isinstance(context, dict) else {}

    if error_type == "missing":
        return f"{field} is required"
    if error_type == "string_too_short":
        return f"{field} is required"
    if error_type == "string_too_long":
        return f"{field} is too long"
    if error_type == "greater_than_equal":
        return f"{field} must be greater than or equal to {ctx.get('ge')}"
    if error_type == "less_than_equal":
        return f"{field} must be less than or equal to {ctx.get('le')}"
    if error_type == "int_parsing":
        return f"{field} must be a number"
    if error_type == "string_pattern_mismatch":
        return f"{field} format is invalid"
    if error_type == "literal_error":
        return f"{field} value is invalid"
    return f"{field} is invalid"


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, exc.detail)

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first_error = errors[0] if errors else {}
        message = _validation_message(first_error)
        return _error_response(
            422,
            "VALIDATION_ERROR",
            message,
            {"errors": errors},
        )
