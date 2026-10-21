"""Token issuance and verification port (RS256 in production)."""

from typing import Protocol

from domain.auth.entity import Account
from domain.auth.value_objects import IssuedToken, TokenClaims


class TokenService(Protocol):
    def issue_access_token(
        self,
        account: Account,
        *,
        roles: tuple[str, ...] = (),
        scopes: tuple[str, ...] = (),
    ) -> IssuedToken: ...

    def issue_refresh_token(self, account: Account) -> IssuedToken: ...

    def decode(self, token: str) -> TokenClaims: ...
