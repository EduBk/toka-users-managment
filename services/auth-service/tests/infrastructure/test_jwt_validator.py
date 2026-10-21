import base64
import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app_common.errors import ForbiddenError, UnauthorizedError
from app_common.jwt_auth import JwtValidator, TokenClaims, require_roles, require_scopes
from domain.auth.entity import Account
from domain.auth.value_objects import Email
from infrastructure.security.rs256_token_service import Rs256TokenService


@pytest.fixture(scope="module")
def key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


@pytest.fixture
def service(key_pair: tuple[str, str]) -> Rs256TokenService:
    private_pem, public_pem = key_pair
    return Rs256TokenService(
        private_key_pem=private_pem,
        public_key_pem=public_pem,
        issuer="auth-service",
        audience="user-management",
        access_token_ttl_seconds=900,
        refresh_token_ttl_days=7,
    )


@pytest.fixture
def validator(key_pair: tuple[str, str]) -> JwtValidator:
    return JwtValidator(
        issuer="auth-service",
        audience="user-management",
        public_key=key_pair[1],
    )


@pytest.fixture
def account() -> Account:
    return Account.create(
        email=Email("ana@example.com"), password_hash="hashed:secret"
    )


class _Revocation:
    def __init__(self, revoked: set[str]) -> None:
        self._revoked = revoked

    async def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked


async def test_validator_accepts_a_token_signed_by_auth_service(
    validator: JwtValidator, service: Rs256TokenService, account: Account
) -> None:
    token = service.issue_access_token(
        account, roles=("admin",), scopes=("users:write",)
    ).token

    claims = await validator.validate(token)

    assert claims.sub == str(account.id)
    assert claims.email == "ana@example.com"
    assert claims.roles == ("admin",)
    assert claims.scopes == ("users:write",)


async def test_validator_rejects_a_tampered_token(
    validator: JwtValidator, service: Rs256TokenService, account: Account
) -> None:
    token = service.issue_access_token(account).token
    header, payload, _signature = token.split(".")
    forged_signature = (
        base64.urlsafe_b64encode(os.urandom(256)).rstrip(b"=").decode("ascii")
    )

    with pytest.raises(UnauthorizedError):
        await validator.validate(f"{header}.{payload}.{forged_signature}")


async def test_validator_rejects_a_revoked_token(
    key_pair: tuple[str, str], service: Rs256TokenService, account: Account
) -> None:
    issued = service.issue_access_token(account)
    validator = JwtValidator(
        issuer="auth-service",
        audience="user-management",
        public_key=key_pair[1],
        revocation=_Revocation({issued.jti}),
    )

    with pytest.raises(UnauthorizedError):
        await validator.validate(issued.token)


async def test_validator_rejects_a_refresh_token(
    validator: JwtValidator, service: Rs256TokenService, account: Account
) -> None:
    token = service.issue_refresh_token(account).token

    with pytest.raises(UnauthorizedError):
        await validator.validate(token)


def _claims(*, roles: tuple[str, ...], scopes: tuple[str, ...]) -> TokenClaims:
    return TokenClaims(
        sub="ana",
        email="ana@example.com",
        roles=roles,
        scopes=scopes,
        issuer="auth-service",
        audience="user-management",
        expires_at=4_102_444_800,
        jti="jti",
        token_type="access",
    )


async def test_require_scopes_accepts_a_granted_scope() -> None:
    dependency = require_scopes("users:write")

    claims = await dependency(_claims(roles=("admin",), scopes=("users:write",)))

    assert claims.roles == ("admin",)


async def test_require_scopes_rejects_a_missing_scope() -> None:
    dependency = require_scopes("users:write")

    with pytest.raises(ForbiddenError):
        await dependency(_claims(roles=("user",), scopes=("users:read",)))


async def test_require_roles_rejects_a_missing_role() -> None:
    dependency = require_roles("admin")

    with pytest.raises(ForbiddenError):
        await dependency(_claims(roles=("auditor",), scopes=()))


def test_validator_requires_exactly_one_key_source(
    key_pair: tuple[str, str],
) -> None:
    with pytest.raises(ValueError):
        JwtValidator(issuer="auth-service", audience="user-management")

    with pytest.raises(ValueError):
        JwtValidator(
            issuer="auth-service",
            audience="user-management",
            public_key=key_pair[1],
            jwks_url="http://auth-service/.well-known/jwks.json",
        )
