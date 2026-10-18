"""One public error envelope; exception/input text never crosses by accident."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from roadguard.schemas import ErrorResponse


logger = logging.getLogger(__name__)


class AppError(Exception):
    """Domain errors must supply a constant, safe public message and details."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[Any] | dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class StaleRevisionError(AppError):
    def __init__(self, expected: int, current: int) -> None:
        super().__init__(
            "stale_input_revision",
            "Planning inputs have changed. Read the current revision and retry.",
            409,
            {"expected_revision": expected, "current_revision": current},
        )


def _response(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(code=code, message=message, details=details).model_dump(mode="json"),
    )


def install_error_handlers(app: FastAPI) -> None:
    import sqlite3
    from roadguard.database import DatabaseStateError

    async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return _response(503, "database_unavailable", "The infrastructure database is unavailable.")

    app.add_exception_handler(sqlite3.Error, database_error_handler)
    app.add_exception_handler(DatabaseStateError, database_error_handler)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return _response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        messages = {
            404: ("not_found", "The requested resource was not found."),
            405: ("method_not_allowed", "The HTTP method is not allowed for this resource."),
        }
        code, message = messages.get(exc.status_code, ("http_error", "The request could not be completed."))
        response = _response(exc.status_code, code, message)
        if exc.status_code == 405 and exc.headers and "Allow" in exc.headers:
            response.headers["Allow"] = exc.headers["Allow"]
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _response(422, "validation_error", "Request validation failed.", {"error_count": len(exc.errors())})

    @app.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log only the exception class: exception messages can contain input/secrets.
        logger.error("Unhandled application exception: %s", type(exc).__name__)
        return _response(500, "internal_error", "An unexpected server error occurred.")
