"""Revoke the access and refresh tokens of the current session."""

from application.dto import LogoutCommand
from application.exceptions import InvalidToken
from application.ports.token_revocation import TokenRevocationStore
from application.ports.token_service import TokenService
from application.use_cases.revocation import revoke_token

_INVALID_TOKEN = "invalid refresh token"


class Logout:
    def __init__(
        self,
        tokens: TokenService,
        revocations: TokenRevocationStore,
    ) -> None:
        self._tokens = tokens
        self._revocations = revocations

    async def execute(self, command: LogoutCommand) -> None:
        claims = self._tokens.decode(command.refresh_token)
        if (
            claims.token_type != "refresh"
            or claims.sub != command.access_claims.sub
        ):
            raise InvalidToken(_INVALID_TOKEN)

        await revoke_token(self._revocations, claims)
        await revoke_token(self._revocations, command.access_claims)
