"""Commands accepted by the auth use cases and their results."""

from dataclasses import dataclass

from domain.auth.entity import Account
from domain.auth.value_objects import IssuedToken, TokenClaims


@dataclass(frozen=True, slots=True)
class RegisterAccountCommand:
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class AuthenticateAccountCommand:
    email: str
    password: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RefreshTokensCommand:
    refresh_token: str


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    refresh_token: str
    access_claims: TokenClaims


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    account: Account
    access_token: IssuedToken
    refresh_token: IssuedToken
