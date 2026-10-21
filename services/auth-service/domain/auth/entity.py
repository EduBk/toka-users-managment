"""Account aggregate root."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from domain.auth.exceptions import InvalidAccount
from domain.auth.value_objects import Email


@dataclass(slots=True)
class Account:
    """Credentials of a user in the identity context.

    Only the hash of the password is stored; the plain password never reaches
    this layer.
    """

    id: UUID
    email: Email
    password_hash: str
    is_active: bool
    created_at: datetime

    @classmethod
    def create(cls, *, email: Email, password_hash: str) -> "Account":
        if not password_hash.strip():
            raise InvalidAccount("password hash is required")
        return cls(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
