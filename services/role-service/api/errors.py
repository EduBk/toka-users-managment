"""Translate role exceptions into the shared error schema."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app_common.errors import ErrorResponse
from application.exceptions import RoleAlreadyExists, RoleNotFound
from domain.role.exceptions import (
    InvalidPermissionName,
    InvalidRoleDescription,
    InvalidRoleName,
)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(code=code, message=message).model_dump(),
    )


def register_role_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidRoleName)
    async def _invalid_name(
        _request: Request, exc: InvalidRoleName
    ) -> JSONResponse:
        return _error_response(400, "invalid_role_name", str(exc))

    @app.exception_handler(InvalidRoleDescription)
    async def _invalid_description(
        _request: Request, exc: InvalidRoleDescription
    ) -> JSONResponse:
        return _error_response(400, "invalid_role_description", str(exc))

    @app.exception_handler(InvalidPermissionName)
    async def _invalid_permission(
        _request: Request, exc: InvalidPermissionName
    ) -> JSONResponse:
        return _error_response(400, "invalid_permission_name", str(exc))

    @app.exception_handler(RoleAlreadyExists)
    async def _role_already_exists(
        _request: Request, exc: RoleAlreadyExists
    ) -> JSONResponse:
        return _error_response(409, "role_already_exists", str(exc))

    @app.exception_handler(RoleNotFound)
    async def _role_not_found(
        _request: Request, exc: RoleNotFound
    ) -> JSONResponse:
        return _error_response(404, "role_not_found", str(exc))
