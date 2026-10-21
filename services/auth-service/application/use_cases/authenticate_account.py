"""Validate an email/password pair and issue an access/refresh token pair."""

from application.dto import AuthenticateAccountCommand, AuthenticationResult
from application.exceptions import InvalidCredentials
from application.ports.event_outbox import EventOutbox
from application.ports.password_hasher import PasswordHasher
from application.ports.token_service import TokenService
from application.ports.user_access import UserAccessProvider
from domain.auth.events import UserLoggedIn, UserLoginFailed
from domain.auth.repository import AccountRepository
from domain.auth.value_objects import Email

_INVALID_CREDENTIALS = "invalid email or password"
_LOGIN_FAILED_REASON = "invalid_credentials"


class AuthenticateAccount:
    def __init__(
        self,
        accounts: AccountRepository,
        password_hasher: PasswordHasher,
        tokens: TokenService,
        outbox: EventOutbox,
        user_access: UserAccessProvider,
    ) -> None:
        self._accounts = accounts
        self._password_hasher = password_hasher
        self._tokens = tokens
        self._outbox = outbox
        self._user_access = user_access

    async def execute(
        self, command: AuthenticateAccountCommand
    ) -> AuthenticationResult:
        email = Email(command.email)
        account = await self._accounts.get_by_email(email)

        # Unknown, inactive and wrong-password accounts share the same error so
        # the endpoint does not disclose which emails are registered.
        if account is None or not account.is_active:
            await self._record_failure(email, command.correlation_id)
            raise InvalidCredentials(_INVALID_CREDENTIALS)
        if not self._password_hasher.verify(command.password, account.password_hash):
            await self._record_failure(email, command.correlation_id)
            raise InvalidCredentials(_INVALID_CREDENTIALS)

        access = await self._user_access.access_for(account.id)
        access_token = self._tokens.issue_access_token(
            account, roles=access.roles, scopes=access.scopes
        )
        refresh_token = self._tokens.issue_refresh_token(account)
        await self._outbox.append(
            UserLoggedIn(user_id=account.id, email=account.email.value),
            correlation_id=command.correlation_id,
        )

        return AuthenticationResult(
            account=account,
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def _record_failure(self, email: Email, correlation_id: str) -> None:
        await self._outbox.append(
            UserLoginFailed(
                email=email.value,
                reason=_LOGIN_FAILED_REASON,
            ),
            correlation_id=correlation_id,
        )
