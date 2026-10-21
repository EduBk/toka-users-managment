"""Composition root: builds use cases with their adapters."""

from fastapi import Request

from application.use_cases.create_user import CreateUser
from application.use_cases.deactivate_user import DeactivateUser
from application.use_cases.get_user import GetUser
from application.use_cases.list_users import ListUsers
from application.use_cases.update_user import UpdateUser


def get_create_user(request: Request) -> CreateUser:
    return CreateUser(
        request.app.state.unit_of_work_factory, request.app.state.user_cache
    )


def get_get_user(request: Request) -> GetUser:
    return GetUser(
        request.app.state.unit_of_work_factory, request.app.state.user_cache
    )


def get_list_users(request: Request) -> ListUsers:
    return ListUsers(
        request.app.state.unit_of_work_factory, request.app.state.user_cache
    )


def get_update_user(request: Request) -> UpdateUser:
    return UpdateUser(
        request.app.state.unit_of_work_factory, request.app.state.user_cache
    )


def get_deactivate_user(request: Request) -> DeactivateUser:
    return DeactivateUser(
        request.app.state.unit_of_work_factory, request.app.state.user_cache
    )
