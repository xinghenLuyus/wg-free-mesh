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


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, exc.detail)

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            422,
            "VALIDATION_ERROR",
            "请求参数不合法",
            {"errors": exc.errors()},
        )
