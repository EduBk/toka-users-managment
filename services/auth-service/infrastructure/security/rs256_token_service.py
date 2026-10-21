"""RS256 implementation of :class:`TokenService`."""

import time
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization

from application.exceptions import InvalidToken
from domain.auth.entity import Account
from domain.auth.value_objects import IssuedToken, TokenClaims
from infrastructure.security.jwks import jwt_key_id

_ALGORITHM = "RS256"
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


class Rs256TokenService:
    def __init__(
        self,
        *,
        private_key_pem: str,
        public_key_pem: str,
        issuer: str,
        audience: str,
        access_token_ttl_seconds: int,
        refresh_token_ttl_days: int,
    ) -> None:
        self._private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"), password=None
        )
        self._public_key = serialization.load_pem_public_key(
            public_key_pem.encode("utf-8")
        )
        self._kid = jwt_key_id(public_key_pem)
        self._issuer = issuer
        self._audience = audience
        self._access_ttl = access_token_ttl_seconds
        self._refresh_ttl = refresh_token_ttl_days * 24 * 60 * 60

    def issue_access_token(
        self,
        account: Account,
        *,
        roles: tuple[str, ...] = (),
        scopes: tuple[str, ...] = (),
    ) -> IssuedToken:
        return self._issue(
            subject=str(account.id),
            email=account.email.value,
            ttl_seconds=self._access_ttl,
            token_type="access",
            roles=roles,
            scopes=scopes,
        )

    def issue_refresh_token(self, account: Account) -> IssuedToken:
        return self._issue(
            subject=str(account.id),
            email=account.email.value,
            ttl_seconds=self._refresh_ttl,
            token_type="refresh",
            roles=(),
            scopes=(),
        )

    def issue_service_token(
        self, *, subject: str, scopes: tuple[str, ...], ttl_seconds: int
    ) -> IssuedToken:
        """Short-lived access token for calls made by this service itself."""
        return self._issue(
            subject=subject,
            email="",
            ttl_seconds=ttl_seconds,
            token_type="access",
            roles=(),
            scopes=scopes,
        )

    def decode(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=[_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": list(_REQUIRED_CLAIMS)},
            )
        except jwt.ExpiredSignatureError as exc:
            raise InvalidToken("token has expired") from exc
        except jwt.PyJWTError as exc:
            raise InvalidToken("invalid token") from exc

        try:
            scope = payload["scope"]
            scopes = tuple(scope.split()) if isinstance(scope, str) else tuple(scope)
            aud = payload["aud"]
            return TokenClaims(
                sub=str(payload["sub"]),
                email=str(payload["email"]),
                roles=tuple(payload["roles"]),
                scopes=scopes,
                issuer=str(payload["iss"]),
                audience=aud[0] if isinstance(aud, list) else str(aud),
                expires_at=int(payload["exp"]),
                jti=str(payload["jti"]),
                token_type=str(payload["token_type"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidToken("invalid token") from exc

    def _issue(
        self,
        *,
        subject: str,
        email: str,
        ttl_seconds: int,
        token_type: str,
        roles: tuple[str, ...],
        scopes: tuple[str, ...],
    ) -> IssuedToken:
        now = int(time.time())
        jti = str(uuid4())
        payload = {
            "sub": subject,
            "email": email,
            "roles": list(roles),
            "scope": " ".join(scopes),
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "exp": now + ttl_seconds,
            "jti": jti,
            "token_type": token_type,
        }
        token = jwt.encode(
            payload,
            self._private_key,
            algorithm=_ALGORITHM,
            headers={"kid": self._kid},
        )
        return IssuedToken(token=token, jti=jti, expires_in=ttl_seconds)
