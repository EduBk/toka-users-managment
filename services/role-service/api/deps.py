"""Composition root: builds use cases with their adapters."""

from fastapi import Request

from application.use_cases.assign_role_to_user import AssignRoleToUser
from application.use_cases.create_role import CreateRole
from application.use_cases.get_user_permissions import GetUserPermissions
from application.use_cases.get_user_roles import GetUserRoles
from application.use_cases.list_roles import ListRoles
from application.use_cases.revoke_role_from_user import RevokeRoleFromUser
from application.use_cases.update_role_permissions import UpdateRolePermissions


def get_create_role(request: Request) -> CreateRole:
    return CreateRole(request.app.state.unit_of_work_factory)


def get_list_roles(request: Request) -> ListRoles:
    return ListRoles(request.app.state.unit_of_work_factory)


def get_update_role_permissions(request: Request) -> UpdateRolePermissions:
    return UpdateRolePermissions(request.app.state.unit_of_work_factory)


def get_assign_role_to_user(request: Request) -> AssignRoleToUser:
    return AssignRoleToUser(request.app.state.unit_of_work_factory)


def get_revoke_role_from_user(request: Request) -> RevokeRoleFromUser:
    return RevokeRoleFromUser(request.app.state.unit_of_work_factory)


def get_get_user_roles(request: Request) -> GetUserRoles:
    return GetUserRoles(request.app.state.unit_of_work_factory)


def get_get_user_permissions(request: Request) -> GetUserPermissions:
    return GetUserPermissions(request.app.state.unit_of_work_factory)
