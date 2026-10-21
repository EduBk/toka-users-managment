from typing import Annotated

import jwt
import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.errors import UnauthorizedError
from app_common.jwt_auth import (
    CurrentClaims,
    JwtValidator,
    TokenClaims,
    require_roles,
    require_scopes,
)
from app_common.testing import (
    TEST_AUDIENCE,
    TEST_ISSUER,
    bearer,
    generate_rsa_key_pair,
    issue_access_token,
)


@pytest.fixture(scope="module")
def key_pair() -> tuple[str, str]:
    return generate_rsa_key_pair()


class _Revocation:
    def __init__(self, revoked: set[str]) -> None:
        self.revoked = revoked

    async def is_revoked(self, jti: str) -> bool:
        return jti in self.revoked


def _validator(public_pem: str, revoked: set[str] | None = None) -> JwtValidator:
    return JwtValidator(
        issuer=TEST_ISSUER,
        audience=TEST_AUDIENCE,
        public_key=public_pem,
        revocation=_Revocation(revoked or set()),
    )


async def test_validator_returns_typed_claims(key_pair: tuple[str, str]) -> None:
    token = issue_access_token(
        key_pair[0], sub="acc-1", roles=("admin",), scopes=("users:read", "ai:use")
    )

    claims = await _validator(key_pair[1]).validate(token)

    assert claims.sub == "acc-1"
    assert claims.roles == ("admin",)
    assert claims.scopes == ("users:read", "ai:use")
    assert claims.token_type == "access"


@pytest.mark.parametrize(
    "overrides",
    [
        {"ttl_seconds": -10},
        {"issuer": "someone-else"},
        {"audience": "other-api"},
    ],
)
async def test_validator_rejects_expired_or_foreign_tokens(
    key_pair: tuple[str, str], overrides: dict
) -> None:
    token = issue_access_token(key_pair[0], **overrides)

    with pytest.raises(UnauthorizedError):
        await _validator(key_pair[1]).validate(token)


async def test_validator_rejects_tokens_signed_by_another_key(
    key_pair: tuple[str, str],
) -> None:
    foreign_private, _ = generate_rsa_key_pair()

    with pytest.raises(UnauthorizedError):
        await _validator(key_pair[1]).validate(issue_access_token(foreign_private))


async def test_validator_rejects_refresh_and_incomplete_tokens(
    key_pair: tuple[str, str],
) -> None:
    refresh = jwt.encode(
        {
            **jwt.decode(
                issue_access_token(key_pair[0]),
                options={"verify_signature": False},
            ),
            "token_type": "refresh",
        },
        key_pair[0],
        algorithm="RS256",
    )
    incomplete = jwt.encode(
        {"sub": "acc-1", "iss": TEST_ISSUER, "aud": TEST_AUDIENCE},
        key_pair[0],
        algorithm="RS256",
    )
    validator = _validator(key_pair[1])

    for token in (refresh, incomplete, "not-a-jwt"):
        with pytest.raises(UnauthorizedError):
            await validator.validate(token)


async def test_validator_rejects_revoked_tokens(key_pair: tuple[str, str]) -> None:
    token = issue_access_token(key_pair[0])
    jti = jwt.decode(token, options={"verify_signature": False})["jti"]

    with pytest.raises(UnauthorizedError) as error:
        await _validator(key_pair[1], {jti}).validate(token)

    assert error.value.code == "invalid_token"


def test_validator_requires_exactly_one_key_source(
    key_pair: tuple[str, str],
) -> None:
    with pytest.raises(ValueError):
        JwtValidator(issuer=TEST_ISSUER, audience=TEST_AUDIENCE)
    with pytest.raises(ValueError):
        JwtValidator(
            issuer=TEST_ISSUER,
            audience=TEST_AUDIENCE,
            public_key=key_pair[1],
            jwks_url="http://auth-service/.well-known/jwks.json",
        )


def test_dependencies_enforce_authentication_scopes_and_roles(
    key_pair: tuple[str, str],
) -> None:
    router = APIRouter()

    @router.get("/me")
    async def me(claims: CurrentClaims) -> dict[str, str]:
        return {"sub": claims.sub}

    @router.get("/write")
    async def write(
        _claims: Annotated[TokenClaims, Depends(require_scopes("users:write"))],
    ) -> dict[str, bool]:
        return {"ok": True}

    @router.get("/admin")
    async def admin(
        _claims: Annotated[TokenClaims, Depends(require_roles("admin"))],
    ) -> dict[str, bool]:
        return {"ok": True}

    app = create_service_app(
        BaseServiceSettings(service_name="test-service"), routers=[router]
    )
    app.state.jwt_validator = _validator(key_pair[1])
    client = TestClient(app)
    user = bearer(issue_access_token(key_pair[0], sub="acc-1", roles=("user",)))
    admin_user = bearer(
        issue_access_token(key_pair[0], roles=("admin",), scopes=("users:write",))
    )

    assert client.get("/me").json()["code"] == "missing_token"
    assert client.get("/me", headers=user).json() == {"sub": "acc-1"}
    forbidden_scope = client.get("/write", headers=user)
    assert forbidden_scope.status_code == 403
    assert forbidden_scope.json()["details"] == {"missing": ["users:write"]}
    assert client.get("/admin", headers=user).json()["code"] == "insufficient_role"
    assert client.get("/write", headers=admin_user).status_code == 200
    assert client.get("/admin", headers=admin_user).status_code == 200
