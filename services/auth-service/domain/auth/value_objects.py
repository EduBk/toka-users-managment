"""Value objects of the identity context."""

import re
from dataclasses import dataclass

from domain.auth.exceptions import InvalidEmail

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_EMAIL_LENGTH = 254


@dataclass(frozen=True, slots=True)
class Email:
    """Validated and normalized email address."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if len(normalized) > _MAX_EMAIL_LENGTH or not _EMAIL_PATTERN.fullmatch(
            normalized
        ):
            raise InvalidEmail(f"'{self.value}' is not a valid email")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class IssuedToken:
    """A signed token together with the id and lifetime used for revocation."""

    token: str
    jti: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Claims embedded in a token issued by this context."""

    sub: str
    email: str
    roles: tuple[str, ...]
    scopes: tuple[str, ...]
    issuer: str
    audience: str
    expires_at: int
    jti: str
    token_type: str
