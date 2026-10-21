"""User routes: validate input, delegate to use cases, map the result."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from api.deps import (
    get_create_user,
    get_deactivate_user,
    get_get_user,
    get_list_users,
    get_update_user,
)
from api.schemas import (
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app_common.jwt_auth import TokenClaims, require_scopes
from app_common.logging import get_trace_id
from application.dto import (
    CreateUserCommand,
    DeactivateUserCommand,
    ListUsersQuery,
    UpdateUserCommand,
)
from application.use_cases.create_user import CreateUser
from application.use_cases.deactivate_user import DeactivateUser
from application.use_cases.get_user import GetUser
from application.use_cases.list_users import ListUsers
from application.use_cases.update_user import UpdateUser

router = APIRouter(prefix="/users", tags=["users"])

UserRead = Annotated[TokenClaims, Depends(require_scopes("users:read"))]
UserWrite = Annotated[TokenClaims, Depends(require_scopes("users:write"))]


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
)
async def create_user(
    payload: UserCreateRequest,
    _claims: UserWrite,
    use_case: CreateUser = Depends(get_create_user),
) -> UserResponse:
    user = await use_case.execute(
        CreateUserCommand(
            email=payload.email,
            name=payload.name,
            profile=payload.profile,
            correlation_id=get_trace_id(),
        )
    )
    return UserResponse.from_domain(user)


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users with offset pagination",
)
async def list_users(
    _claims: UserRead,
    use_case: ListUsers = Depends(get_list_users),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> UserListResponse:
    result = await use_case.execute(
        ListUsersQuery(page=page, page_size=page_size)
    )
    return UserListResponse(
        items=[UserResponse.from_domain(user) for user in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get a user by id",
)
async def get_user(
    user_id: UUID,
    _claims: UserRead,
    use_case: GetUser = Depends(get_get_user),
) -> UserResponse:
    return UserResponse.from_domain(await use_case.execute(user_id))


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user",
)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    _claims: UserWrite,
    use_case: UpdateUser = Depends(get_update_user),
) -> UserResponse:
    user = await use_case.execute(
        UpdateUserCommand(
            user_id=user_id,
            email=payload.email,
            name=payload.name,
            profile=payload.profile,
            correlation_id=get_trace_id(),
        )
    )
    return UserResponse.from_domain(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a user (logical delete)",
)
async def deactivate_user(
    user_id: UUID,
    _claims: UserWrite,
    use_case: DeactivateUser = Depends(get_deactivate_user),
) -> Response:
    await use_case.execute(
        DeactivateUserCommand(
            user_id=user_id, correlation_id=get_trace_id()
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
