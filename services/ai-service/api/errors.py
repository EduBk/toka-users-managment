"""Translate agent exceptions into the shared error schema."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app_common.errors import ErrorResponse
from application.exceptions import (
    AiModelUnavailable,
    AiNotConfigured,
    AiRateLimited,
    AiUnavailable,
    ReindexFailed,
)
from domain.agent.exceptions import InvalidQuestion


def _error_response(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(code=code, message=message).model_dump(),
        headers=headers,
    )


def register_ai_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidQuestion)
    async def _invalid_question(
        _request: Request, exc: InvalidQuestion
    ) -> JSONResponse:
        return _error_response(400, "invalid_question", str(exc))

    @app.exception_handler(AiNotConfigured)
    async def _ai_not_configured(
        _request: Request, exc: AiNotConfigured
    ) -> JSONResponse:
        return _error_response(503, "ai_not_configured", str(exc))

    @app.exception_handler(AiModelUnavailable)
    async def _ai_model_unavailable(
        _request: Request, exc: AiModelUnavailable
    ) -> JSONResponse:
        return _error_response(503, "ai_model_unavailable", str(exc))

    @app.exception_handler(AiUnavailable)
    async def _ai_unavailable(
        _request: Request, exc: AiUnavailable
    ) -> JSONResponse:
        return _error_response(503, "ai_unavailable", str(exc))

    @app.exception_handler(AiRateLimited)
    async def _ai_rate_limited(
        _request: Request, exc: AiRateLimited
    ) -> JSONResponse:
        return _error_response(
            429,
            "ai_rate_limited",
            str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    @app.exception_handler(ReindexFailed)
    async def _reindex_failed(
        _request: Request, exc: ReindexFailed
    ) -> JSONResponse:
        return _error_response(503, "reindex_failed", str(exc))

    @app.exception_handler(FileNotFoundError)
    async def _documentation_missing(
        _request: Request, exc: FileNotFoundError
    ) -> JSONResponse:
        return _error_response(
            500, "documentation_unavailable", "the documentation corpus is unavailable"
        )
