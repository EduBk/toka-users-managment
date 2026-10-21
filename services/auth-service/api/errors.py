"""Translate auth exceptions into the shared error schema."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app_common.errors import ErrorResponse
from application.exceptions import AccountNotFound, InvalidCredentials, InvalidToken
from domain.auth.exceptions import EmailAlreadyRegistered, InvalidEmail


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(code=code, message=message).model_dump(),
    )


def register_auth_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidEmail)
    async def _invalid_email(_request: Request, exc: InvalidEmail) -> JSONResponse:
        return _error_response(400, "invalid_email", str(exc))

    @app.exception_handler(EmailAlreadyRegistered)
    async def _email_already_registered(
        _request: Request, exc: EmailAlreadyRegistered
    ) -> JSONResponse:
        return _error_response(409, "email_already_registered", str(exc))

    @app.exception_handler(InvalidCredentials)
    async def _invalid_credentials(
        _request: Request, exc: InvalidCredentials
    ) -> JSONResponse:
        return _error_response(401, "invalid_credentials", str(exc))

    @app.exception_handler(InvalidToken)
    async def _invalid_token(_request: Request, exc: InvalidToken) -> JSONResponse:
        return _error_response(401, "invalid_token", str(exc))

    @app.exception_handler(AccountNotFound)
    async def _account_not_found(
        _request: Request, exc: AccountNotFound
    ) -> JSONResponse:
        return _error_response(404, "account_not_found", str(exc))
