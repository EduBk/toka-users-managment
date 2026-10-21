"""Role routes: validate input, delegate to use cases, map the result."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from api.deps import (
    get_assign_role_to_user,
    get_create_role,
    get_get_user_permissions,
    get_get_user_roles,
    get_list_roles,
    get_revoke_role_from_user,
    get_update_role_permissions,
)
from api.schemas import (
    AssignmentRequest,
    RoleCreateRequest,
    RolePermissionsRequest,
    RoleResponse,
    UserPermissionsResponse,
)
from app_common.jwt_auth import (
    CurrentClaims,
    TokenClaims,
    require_roles,
    require_scopes,
)
from app_common.logging import get_trace_id
from application.dto import (
    AssignRoleToUserCommand,
    CreateRoleCommand,
    RevokeRoleFromUserCommand,
    UpdateRolePermissionsCommand,
)
from application.use_cases.assign_role_to_user import AssignRoleToUser
from application.use_cases.create_role import CreateRole
from application.use_cases.get_user_permissions import GetUserPermissions
from application.use_cases.get_user_roles import GetUserRoles
from application.use_cases.list_roles import ListRoles
from application.use_cases.revoke_role_from_user import RevokeRoleFromUser
from application.use_cases.update_role_permissions import UpdateRolePermissions

router = APIRouter(tags=["roles"])

AdminClaims = Annotated[TokenClaims, Depends(require_roles("admin"))]
RolesReadClaims = Annotated[TokenClaims, Depends(require_scopes("roles:read"))]


@router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a role",
)
async def create_role(
    payload: RoleCreateRequest,
    _claims: AdminClaims,
    use_case: CreateRole = Depends(get_create_role),
) -> RoleResponse:
    role = await use_case.execute(
        CreateRoleCommand(
            name=payload.name,
            description=payload.description,
            permissions=tuple(payload.permissions),
        )
    )
    return RoleResponse.from_domain(role)


@router.get(
    "/roles",
    response_model=list[RoleResponse],
    summary="List roles",
)
async def list_roles(
    _claims: CurrentClaims,
    use_case: ListRoles = Depends(get_list_roles),
) -> list[RoleResponse]:
    roles = await use_case.execute()
    return [RoleResponse.from_domain(role) for role in roles]


@router.put(
    "/roles/{role_id}/permissions",
    response_model=RoleResponse,
    summary="Replace the permissions of a role",
)
async def update_role_permissions(
    role_id: UUID,
    payload: RolePermissionsRequest,
    _claims: AdminClaims,
    use_case: UpdateRolePermissions = Depends(get_update_role_permissions),
) -> RoleResponse:
    role = await use_case.execute(
        UpdateRolePermissionsCommand(
            role_id=role_id, permissions=tuple(payload.permissions)
        )
    )
    return RoleResponse.from_domain(role)


@router.post(
    "/users/{user_id}/roles",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign a role to an account (idempotent)",
)
async def assign_role_to_user(
    user_id: UUID,
    payload: AssignmentRequest,
    _claims: AdminClaims,
    use_case: AssignRoleToUser = Depends(get_assign_role_to_user),
) -> Response:
    await use_case.execute(
        AssignRoleToUserCommand(
            user_id=user_id,
            role_id=payload.role_id,
            correlation_id=get_trace_id(),
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/users/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a role from an account (idempotent)",
)
async def revoke_role_from_user(
    user_id: UUID,
    role_id: UUID,
    _claims: AdminClaims,
    use_case: RevokeRoleFromUser = Depends(get_revoke_role_from_user),
) -> Response:
    await use_case.execute(
        RevokeRoleFromUserCommand(
            user_id=user_id,
            role_id=role_id,
            correlation_id=get_trace_id(),
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/users/{user_id}/roles",
    response_model=list[RoleResponse],
    summary="List the roles assigned to an account",
)
async def get_user_roles(
    user_id: UUID,
    _claims: RolesReadClaims,
    use_case: GetUserRoles = Depends(get_get_user_roles),
) -> list[RoleResponse]:
    roles = await use_case.execute(user_id)
    return [RoleResponse.from_domain(role) for role in roles]


@router.get(
    "/users/{user_id}/permissions",
    response_model=UserPermissionsResponse,
    summary="Effective permissions of an account",
)
async def get_user_permissions(
    user_id: UUID,
    _claims: RolesReadClaims,
    use_case: GetUserPermissions = Depends(get_get_user_permissions),
) -> UserPermissionsResponse:
    return UserPermissionsResponse(
        user_id=user_id,
        permissions=list(await use_case.execute(user_id)),
    )
