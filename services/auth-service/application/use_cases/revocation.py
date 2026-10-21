"""Shared helper to revoke a token id for the rest of its lifetime."""

import time

from application.ports.token_revocation import TokenRevocationStore
from domain.auth.value_objects import TokenClaims


async def revoke_token(
    store: TokenRevocationStore, claims: TokenClaims
) -> None:
    ttl_seconds = max(claims.expires_at - int(time.time()), 1)
    await store.revoke(claims.jti, ttl_seconds)
