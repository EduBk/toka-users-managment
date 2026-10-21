import base64
import os

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from application.exceptions import InvalidToken
from domain.auth.entity import Account
from domain.auth.value_objects import Email
from infrastructure.security.jwks import build_jwks, jwt_key_id
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
def account() -> Account:
    return Account.create(
        email=Email("ana@example.com"), password_hash="hashed:secret"
    )


def test_access_token_contains_the_required_claims(
    service: Rs256TokenService, account: Account
) -> None:
    issued = service.issue_access_token(
        account, roles=("admin",), scopes=("users:write", "ai:use")
    )

    claims = service.decode(issued.token)

    assert claims.sub == str(account.id)
    assert claims.email == "ana@example.com"
    assert claims.roles == ("admin",)
    assert claims.scopes == ("users:write", "ai:use")
    assert claims.issuer == "auth-service"
    assert claims.audience == "user-management"
    assert claims.jti == issued.jti
    assert claims.token_type == "access"
    assert claims.expires_at > 0


def test_token_header_carries_the_key_id(
    service: Rs256TokenService, account: Account, key_pair: tuple[str, str]
) -> None:
    issued = service.issue_access_token(account)

    header = jwt.get_unverified_header(issued.token)

    assert header["alg"] == "RS256"
    assert header["kid"] == jwt_key_id(key_pair[1])


def test_refresh_token_has_no_authorization_claims(
    service: Rs256TokenService, account: Account
) -> None:
    issued = service.issue_refresh_token(account)

    claims = service.decode(issued.token)

    assert claims.token_type == "refresh"
    assert claims.roles == ()
    assert claims.scopes == ()


def test_service_token_carries_only_the_requested_scopes(
    service: Rs256TokenService,
) -> None:
    issued = service.issue_service_token(
        subject="auth-service", scopes=("roles:read",), ttl_seconds=60
    )

    claims = service.decode(issued.token)

    assert claims.sub == "auth-service"
    assert claims.email == ""
    assert claims.roles == ()
    assert claims.scopes == ("roles:read",)
    assert claims.token_type == "access"
    assert issued.expires_in == 60


def test_decode_rejects_a_tampered_signature(
    service: Rs256TokenService, account: Account
) -> None:
    token = service.issue_access_token(account).token
    header, payload, _signature = token.split(".")
    forged_signature = (
        base64.urlsafe_b64encode(os.urandom(256)).rstrip(b"=").decode("ascii")
    )

    with pytest.raises(InvalidToken):
        service.decode(f"{header}.{payload}.{forged_signature}")


def test_decode_rejects_an_expired_token(
    key_pair: tuple[str, str], account: Account
) -> None:
    private_pem, public_pem = key_pair
    service = Rs256TokenService(
        private_key_pem=private_pem,
        public_key_pem=public_pem,
        issuer="auth-service",
        audience="user-management",
        access_token_ttl_seconds=-1,
        refresh_token_ttl_days=7,
    )
    token = service.issue_access_token(account).token

    with pytest.raises(InvalidToken):
        service.decode(token)


def test_decode_rejects_a_token_for_another_audience(
    key_pair: tuple[str, str], account: Account
) -> None:
    private_pem, public_pem = key_pair
    issuer = Rs256TokenService(
        private_key_pem=private_pem,
        public_key_pem=public_pem,
        issuer="auth-service",
        audience="user-management",
        access_token_ttl_seconds=900,
        refresh_token_ttl_days=7,
    )
    verifier = Rs256TokenService(
        private_key_pem=private_pem,
        public_key_pem=public_pem,
        issuer="auth-service",
        audience="another-audience",
        access_token_ttl_seconds=900,
        refresh_token_ttl_days=7,
    )
    token = issuer.issue_access_token(account).token

    with pytest.raises(InvalidToken):
        verifier.decode(token)


def test_jwks_exposes_the_public_key(key_pair: tuple[str, str]) -> None:
    public_pem = key_pair[1]

    jwks = build_jwks(public_pem)

    key = jwks["keys"][0]
    assert key["kty"] == "RSA"
    assert key["use"] == "sig"
    assert key["alg"] == "RS256"
    assert key["kid"] == jwt_key_id(public_pem)
    assert "n" in key and "e" in key
