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
    "name": "名称",
    "description": "描述",
    "virtual_subnet": "虚拟网段",
    "default_dns": "默认 DNS",
    "ipv4_address": "公网 IPv4",
    "ipv6_address": "公网 IPv6",
    "listen_port": "监听端口",
    "virtual_ip": "虚拟 IP",
    "dns": "DNS",
    "private_key": "私钥",
    "public_key": "公钥",
    "tag": "标签",
    "tags": "标签",
    "peer_node_id": "对端节点",
    "local_node_id": "本地节点",
    "allowed_ips": "AllowedIPs",
    "endpoint_manual_host": "手动 Host",
    "endpoint_manual_port": "手动 Port",
    "host": "Host",
    "port": "Port",
    "current_password": "当前密码",
    "new_password": "新密码",
    "username": "用户名",
    "password": "密码",
}


def _field_label(error: dict[str, object]) -> str:
    loc = error.get("loc")
    if not isinstance(loc, (list, tuple)):
        return "字段"
    for item in reversed(loc):
        if isinstance(item, str) and item not in {"body", "query", "path"}:
            return FIELD_LABELS.get(item, item)
    return "字段"


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
        return f"{field}不能为空"
    if error_type == "string_too_short":
        return f"{field}不能为空"
    if error_type == "string_too_long":
        return f"{field}长度超出限制"
    if error_type == "greater_than_equal":
        return f"{field}不能小于 {ctx.get('ge')}"
    if error_type == "less_than_equal":
        return f"{field}不能大于 {ctx.get('le')}"
    if error_type == "int_parsing":
        return f"{field}必须是数字"
    if error_type == "string_pattern_mismatch":
        return f"{field}格式不正确"
    if error_type == "literal_error":
        return f"{field}取值不合法"
    return f"{field}填写不正确"


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
