"""Rotate a refresh token: revoke the old one and issue a new pair."""

from uuid import UUID

from application.dto import AuthenticationResult, RefreshTokensCommand
from application.exceptions import InvalidToken
from application.ports.token_revocation import TokenRevocationStore
from application.ports.token_service import TokenService
from application.ports.user_access import UserAccessProvider
from application.use_cases.revocation import revoke_token
from domain.auth.repository import AccountRepository

_INVALID_TOKEN = "invalid refresh token"


class RefreshTokens:
    def __init__(
        self,
        accounts: AccountRepository,
        tokens: TokenService,
        revocations: TokenRevocationStore,
        user_access: UserAccessProvider,
    ) -> None:
        self._accounts = accounts
        self._tokens = tokens
        self._revocations = revocations
        self._user_access = user_access

    async def execute(
        self, command: RefreshTokensCommand
    ) -> AuthenticationResult:
        claims = self._tokens.decode(command.refresh_token)
        if claims.token_type != "refresh":
            raise InvalidToken(_INVALID_TOKEN)
        if await self._revocations.is_revoked(claims.jti):
            raise InvalidToken(_INVALID_TOKEN)

        try:
            account_id = UUID(claims.sub)
        except ValueError as exc:
            raise InvalidToken(_INVALID_TOKEN) from exc

        account = await self._accounts.get_by_id(account_id)
        if account is None or not account.is_active:
            raise InvalidToken(_INVALID_TOKEN)

        await revoke_token(self._revocations, claims)
        access = await self._user_access.access_for(account.id)
        return AuthenticationResult(
            account=account,
            access_token=self._tokens.issue_access_token(
                account, roles=access.roles, scopes=access.scopes
            ),
            refresh_token=self._tokens.issue_refresh_token(account),
        )
