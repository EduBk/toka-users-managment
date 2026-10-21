"""Composition root: builds use cases with their adapters."""

from fastapi import Request

from application.use_cases.authenticate_account import AuthenticateAccount
from application.use_cases.find_account_by_email import FindAccountByEmail
from application.use_cases.logout import Logout
from application.use_cases.refresh_tokens import RefreshTokens
from application.use_cases.register_account import RegisterAccount
from infrastructure.persistence.account_repository import SqlAlchemyAccountRepository


def get_register_account(request: Request) -> RegisterAccount:
    return RegisterAccount(
        accounts=SqlAlchemyAccountRepository(request.app.state.session_factory),
        password_hasher=request.app.state.password_hasher,
    )


def _accounts(request: Request) -> SqlAlchemyAccountRepository:
    return SqlAlchemyAccountRepository(request.app.state.session_factory)


def get_authenticate_account(request: Request) -> AuthenticateAccount:
    return AuthenticateAccount(
        accounts=_accounts(request),
        password_hasher=request.app.state.password_hasher,
        tokens=request.app.state.token_service,
        outbox=request.app.state.event_outbox,
        user_access=request.app.state.user_access_provider,
    )


def get_refresh_tokens(request: Request) -> RefreshTokens:
    return RefreshTokens(
        accounts=_accounts(request),
        tokens=request.app.state.token_service,
        revocations=request.app.state.revocation_store,
        user_access=request.app.state.user_access_provider,
    )


def get_find_account_by_email(request: Request) -> FindAccountByEmail:
    return FindAccountByEmail(_accounts(request))


def get_logout(request: Request) -> Logout:
    return Logout(
        tokens=request.app.state.token_service,
        revocations=request.app.state.revocation_store,
    )
