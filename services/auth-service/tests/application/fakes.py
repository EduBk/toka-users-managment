"""In-memory doubles for the application ports."""

import time
from uuid import UUID, uuid4

from application.exceptions import InvalidToken
from application.ports.user_access import UserAccess
from domain.auth.entity import Account
from domain.auth.events import DomainEvent
from domain.auth.value_objects import Email, IssuedToken, TokenClaims


class InMemoryAccountRepository:
    def __init__(self) -> None:
        self.accounts: list[Account] = []

    async def get_by_email(self, email: Email) -> Account | None:
        return next(
            (account for account in self.accounts if account.email == email),
            None,
        )

    async def get_by_id(self, account_id: UUID) -> Account | None:
        return next(
            (account for account in self.accounts if account.id == account_id),
            None,
        )

    async def exists_by_email(self, email: Email) -> bool:
        return await self.get_by_email(email) is not None

    async def add(self, account: Account) -> None:
        self.accounts.append(account)


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == self.hash(password)


class FakeTokenService:
    def __init__(self) -> None:
        self._claims: dict[str, TokenClaims] = {}

    def issue_access_token(
        self,
        account: Account,
        *,
        roles: tuple[str, ...] = (),
        scopes: tuple[str, ...] = (),
    ) -> IssuedToken:
        return self._issue(account, roles=roles, scopes=scopes, token_type="access")

    def issue_refresh_token(self, account: Account) -> IssuedToken:
        return self._issue(account, roles=(), scopes=(), token_type="refresh")

    def decode(self, token: str) -> TokenClaims:
        claims = self._claims.get(token)
        if claims is None:
            raise InvalidToken("invalid token")
        return claims

    def register(self, claims: TokenClaims) -> str:
        token = f"{claims.token_type}-{claims.jti}"
        self._claims[token] = claims
        return token

    def _issue(
        self,
        account: Account,
        *,
        roles: tuple[str, ...],
        scopes: tuple[str, ...],
        token_type: str,
    ) -> IssuedToken:
        jti = str(uuid4())
        expires_at = int(time.time()) + 900
        token = f"{token_type}-{jti}"
        self._claims[token] = TokenClaims(
            sub=str(account.id),
            email=account.email.value,
            roles=roles,
            scopes=scopes,
            issuer="auth-service",
            audience="user-management",
            expires_at=expires_at,
            jti=jti,
            token_type=token_type,
        )
        return IssuedToken(token=token, jti=jti, expires_in=900)


class FakeTokenRevocationStore:
    def __init__(self) -> None:
        self.revoked: dict[str, int] = {}

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        self.revoked[jti] = ttl_seconds

    async def is_revoked(self, jti: str) -> bool:
        return jti in self.revoked


class FakeEventOutbox:
    def __init__(self) -> None:
        self.events: list[tuple[DomainEvent, str]] = []

    async def append(
        self, event: DomainEvent, *, correlation_id: str
    ) -> None:
        self.events.append((event, correlation_id))


class FakeUserAccessProvider:
    def __init__(
        self,
        *,
        roles: tuple[str, ...] = (),
        scopes: tuple[str, ...] = (),
    ) -> None:
        self._access = UserAccess(roles=roles, scopes=scopes)
        self.requested: list[UUID] = []

    async def access_for(self, user_id: UUID) -> UserAccess:
        self.requested.append(user_id)
        return self._access
