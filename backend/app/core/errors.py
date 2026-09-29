from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


class NotFound(AppError):
    def __init__(self, message: str = "not found") -> None:
        super().__init__(404, "not_found", message)


class Unauthorized(AppError):
    def __init__(self, message: str = "unauthorized") -> None:
        super().__init__(401, "unauthorized", message)


class Conflict(AppError):
    def __init__(self, message: str = "conflict") -> None:
        super().__init__(409, "conflict", message)


def _error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", error=str(exc), exc_info=exc)
        return _error_response(500, "internal_error", "something went wrong")
