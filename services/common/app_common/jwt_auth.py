"""JWT validation shared by every service (E2.4).

Services validate tokens locally with the public key (or the JWKS endpoint) of
``auth-service``; no per-request call to the issuer is required. Revoked token
ids are optionally checked against a store (Redis in production).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Protocol

import jwt
from fastapi import Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app_common.errors import ForbiddenError, UnauthorizedError

_ALGORITHM = "RS256"
_INVALID_TOKEN = "invalid token"
_REQUIRED_CLAIMS = (
    "sub",
    "email",
    "roles",
    "scope",
    "iss",
    "aud",
    "exp",
    "jti",
    "token_type",
)


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Verified claims carried by an access token."""

    sub: str
    email: str
    roles: tuple[str, ...]
    scopes: tuple[str, ...]
    issuer: str
    audience: str
    expires_at: int
    jti: str
    token_type: str


class TokenRevocationChecker(Protocol):
    async def is_revoked(self, jti: str) -> bool: ...


class JwtValidator:
    """Verifies signature, expiry, issuer and audience of an access token.

    Use ``public_key`` (PEM) when the key is available locally, or ``jwks_url``
    to discover and cache the signing keys published by ``auth-service``.
    """

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        public_key: str | None = None,
        jwks_url: str | None = None,
        revocation: TokenRevocationChecker | None = None,
    ) -> None:
        if (public_key is None) == (jwks_url is None):
            raise ValueError("provide exactly one of public_key or jwks_url")
        self._issuer = issuer
        self._audience = audience
        self._public_key = public_key
        self._jwks_client = jwt.PyJWKClient(jwks_url) if jwks_url else None
        self._revocation = revocation

    async def validate(self, token: str) -> TokenClaims:
        claims = await run_in_threadpool(self._decode, token)
        if self._revocation is not None and await self._revocation.is_revoked(
            claims.jti
        ):
            raise UnauthorizedError("token has been revoked", code="invalid_token")
        return claims

    def _decode(self, token: str) -> TokenClaims:
        try:
            key = self._signing_key(token)
            payload = jwt.decode(
                token,
                key,
                algorithms=[_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": list(_REQUIRED_CLAIMS)},
            )
            return _to_claims(payload)
        except jwt.PyJWTError as exc:
            raise UnauthorizedError(_INVALID_TOKEN, code="invalid_token") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise UnauthorizedError(_INVALID_TOKEN, code="invalid_token") from exc

    def _signing_key(self, token: str) -> object:
        if self._jwks_client is None:
            return self._public_key
        return self._jwks_client.get_signing_key_from_jwt(token).key


def _to_claims(payload: dict[str, object]) -> TokenClaims:
    if payload["token_type"] != "access":
        raise ValueError("not an access token")

    scope = payload["scope"]
    scopes = tuple(scope.split()) if isinstance(scope, str) else tuple(scope)
    roles = tuple(payload["roles"])
    aud = payload["aud"]
    return TokenClaims(
        sub=str(payload["sub"]),
        email=str(payload["email"]),
        roles=roles,
        scopes=scopes,
        issuer=str(payload["iss"]),
        audience=aud[0] if isinstance(aud, list) else str(aud),
        expires_at=int(payload["exp"]),
        jti=str(payload["jti"]),
        token_type=str(payload["token_type"]),
    )


_bearer = HTTPBearer(auto_error=False)


def get_jwt_validator(request: Request) -> JwtValidator:
    validator = getattr(request.app.state, "jwt_validator", None)
    if validator is None:
        raise RuntimeError("jwt_validator is not configured in app.state")
    return validator


async def get_token_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    validator: Annotated[JwtValidator, Depends(get_jwt_validator)],
) -> TokenClaims:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("missing bearer token", code="missing_token")
    return await validator.validate(credentials.credentials)


CurrentClaims = Annotated[TokenClaims, Depends(get_token_claims)]


def require_scopes(*required: str):
    """Dependency factory: reject the request unless every scope is granted."""

    async def dependency(claims: CurrentClaims) -> TokenClaims:
        missing = [scope for scope in required if scope not in claims.scopes]
        if missing:
            raise ForbiddenError(
                "insufficient scope",
                code="insufficient_scope",
                details={"missing": missing},
            )
        return claims

    return dependency


def require_roles(*required: str):
    """Dependency factory: reject the request unless every role is granted."""

    async def dependency(claims: CurrentClaims) -> TokenClaims:
        missing = [role for role in required if role not in claims.roles]
        if missing:
            raise ForbiddenError(
                "insufficient role",
                code="insufficient_role",
                details={"missing": missing},
            )
        return claims

    return dependency
