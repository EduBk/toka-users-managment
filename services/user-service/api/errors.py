"""Translate user exceptions into the shared error schema."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app_common.errors import ErrorResponse
from application.exceptions import UserNotFound
from domain.user.exceptions import (
    EmailAlreadyExists,
    InvalidEmail,
    InvalidProfile,
    InvalidUserName,
    InvalidUserState,
    InvalidUserStatus,
)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(code=code, message=message).model_dump(),
    )


def register_user_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidEmail)
    async def _invalid_email(_request: Request, exc: InvalidEmail) -> JSONResponse:
        return _error_response(400, "invalid_email", str(exc))

    @app.exception_handler(InvalidUserName)
    async def _invalid_name(
        _request: Request, exc: InvalidUserName
    ) -> JSONResponse:
        return _error_response(400, "invalid_name", str(exc))

    @app.exception_handler(InvalidProfile)
    async def _invalid_profile(
        _request: Request, exc: InvalidProfile
    ) -> JSONResponse:
        return _error_response(400, "invalid_profile", str(exc))

    @app.exception_handler(InvalidUserStatus)
    async def _invalid_status(
        _request: Request, exc: InvalidUserStatus
    ) -> JSONResponse:
        return _error_response(400, "invalid_status", str(exc))

    @app.exception_handler(InvalidUserState)
    async def _invalid_state(
        _request: Request, exc: InvalidUserState
    ) -> JSONResponse:
        return _error_response(409, "invalid_user_state", str(exc))

    @app.exception_handler(EmailAlreadyExists)
    async def _email_already_exists(
        _request: Request, exc: EmailAlreadyExists
    ) -> JSONResponse:
        return _error_response(409, "email_already_exists", str(exc))

    @app.exception_handler(UserNotFound)
    async def _user_not_found(
        _request: Request, exc: UserNotFound
    ) -> JSONResponse:
        return _error_response(404, "user_not_found", str(exc))
