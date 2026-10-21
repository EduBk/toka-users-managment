"""Uniform error schema (``code``, ``message``, ``details``) and handlers.

Domain and application layers raise :class:`AppError` subclasses; the HTTP
status and the error code are resolved here, at the system boundary.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app_common.logging import reset_trace_id, set_trace_id

logger = logging.getLogger(__name__)

_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "too_many_requests",
    503: "service_unavailable",
}


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | list[Any] | None = None


class AppError(Exception):
    """Base class for expected application errors."""

    status_code = 500
    code = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | list[Any] | None = None,
        status_code: int | None = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class TooManyRequestsError(AppError):
    status_code = 429
    code = "rate_limited"


# Pydantic echoes the rejected value in ``input``; it may be a password or a token.
_VALIDATION_FIELDS = ("type", "loc", "msg", "ctx")


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code, message=exc.message, details=exc.details
        ).model_dump(),
        headers=exc.headers,
    )


async def _handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {key: error[key] for key in _VALIDATION_FIELDS if key in error}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code="validation_error",
            message="Request validation failed",
            details=jsonable_encoder(errors),
        ).model_dump(),
    )


async def _handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=_HTTP_CODES.get(exc.status_code, "http_error"), message=message
        ).model_dump(),
        headers=exc.headers,
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # This handler runs after the trace middleware reset the context, so the
    # trace id is restored from request.state to keep logs correlated.
    trace_id = getattr(request.state, "trace_id", None)
    token = set_trace_id(trace_id) if trace_id else None
    try:
        logger.exception(
            "unhandled error",
            extra={
                "extra_fields": {"method": request.method, "path": request.url.path}
            },
        )
    finally:
        if token is not None:
            reset_trace_id(token)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code="internal_error", message="Unexpected error"
        ).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_error)
