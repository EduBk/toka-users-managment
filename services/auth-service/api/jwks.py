"""Public JWKS endpoint used by every service to verify tokens."""

from fastapi import APIRouter, Request

router = APIRouter(tags=["auth"])


@router.get(
    "/.well-known/jwks.json",
    summary="Public keys used to verify access tokens",
)
async def jwks(request: Request) -> dict:
    return request.app.state.jwks
