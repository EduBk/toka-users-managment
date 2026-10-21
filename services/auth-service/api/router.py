"""Auth routes: validate input, delegate to use cases, map the result."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from api.deps import (
    get_authenticate_account,
    get_find_account_by_email,
    get_logout,
    get_refresh_tokens,
    get_register_account,
)
from api.schemas import (
    AccountResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app_common.jwt_auth import CurrentClaims, TokenClaims, require_roles
from app_common.logging import get_trace_id
from app_common.rate_limit import limit_by_client_ip
from application.dto import (
    AuthenticateAccountCommand,
    LogoutCommand,
    RefreshTokensCommand,
    RegisterAccountCommand,
)
from application.use_cases.authenticate_account import AuthenticateAccount
from application.use_cases.find_account_by_email import FindAccountByEmail
from application.use_cases.logout import Logout
from application.use_cases.refresh_tokens import RefreshTokens
from application.use_cases.register_account import RegisterAccount

router = APIRouter(prefix="/auth", tags=["auth"])

AdminClaims = Annotated[TokenClaims, Depends(require_roles("admin"))]


@router.post(
    "/register",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an account",
    dependencies=[Depends(limit_by_client_ip("auth:register"))],
)
async def register(
    payload: RegisterRequest,
    use_case: RegisterAccount = Depends(get_register_account),
) -> AccountResponse:
    account = await use_case.execute(
        RegisterAccountCommand(email=payload.email, password=payload.password)
    )
    return AccountResponse.from_domain(account)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Validate credentials and issue access/refresh tokens",
    dependencies=[Depends(limit_by_client_ip("auth:login"))],
)
async def login(
    payload: LoginRequest,
    use_case: AuthenticateAccount = Depends(get_authenticate_account),
) -> TokenResponse:
    result = await use_case.execute(
        AuthenticateAccountCommand(
            email=payload.email,
            password=payload.password,
            correlation_id=get_trace_id(),
        )
    )
    return TokenResponse.from_result(result)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate a refresh token",
    dependencies=[Depends(limit_by_client_ip("auth:refresh"))],
)
async def refresh(
    payload: RefreshRequest,
    use_case: RefreshTokens = Depends(get_refresh_tokens),
) -> TokenResponse:
    result = await use_case.execute(
        RefreshTokensCommand(refresh_token=payload.refresh_token)
    )
    return TokenResponse.from_result(result)


@router.get(
    "/accounts",
    response_model=AccountResponse,
    summary="Find the account registered with an email (admin only)",
)
async def find_account(
    _claims: AdminClaims,
    email: str = Query(min_length=3, max_length=254),
    use_case: FindAccountByEmail = Depends(get_find_account_by_email),
) -> AccountResponse:
    return AccountResponse.from_domain(await use_case.execute(email))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the access and refresh tokens of the session",
)
async def logout(
    payload: LogoutRequest,
    claims: CurrentClaims,
    use_case: Logout = Depends(get_logout),
) -> Response:
    await use_case.execute(
        LogoutCommand(refresh_token=payload.refresh_token, access_claims=claims)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
