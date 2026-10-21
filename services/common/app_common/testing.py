"""Test helpers to issue RS256 access tokens without running ``auth-service``."""

import time
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

TEST_ISSUER = "auth-service"
TEST_AUDIENCE = "user-management"


def generate_rsa_key_pair() -> tuple[str, str]:
    """Return a fresh ``(private_pem, public_pem)`` pair."""
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


def issue_access_token(
    private_pem: str,
    *,
    sub: str | None = None,
    email: str = "tester@example.com",
    roles: tuple[str, ...] = (),
    scopes: tuple[str, ...] = (),
    ttl_seconds: int = 300,
    issuer: str = TEST_ISSUER,
    audience: str = TEST_AUDIENCE,
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub or str(uuid4()),
            "email": email,
            "roles": list(roles),
            "scope": " ".join(scopes),
            "iss": issuer,
            "aud": audience,
            "iat": now,
            "exp": now + ttl_seconds,
            "jti": str(uuid4()),
            "token_type": "access",
        },
        private_pem,
        algorithm="RS256",
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
