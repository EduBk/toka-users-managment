"""User aggregate root."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from domain.user.events import (
    DomainEvent,
    UserCreated,
    UserDeactivated,
    UserUpdated,
)
from domain.user.value_objects import Email, Profile, UserName, UserStatus


@dataclass(slots=True)
class User:
    """User of the system, independent from its credentials.

    Email uniqueness and a non-empty name are enforced here; the repository
    enforces uniqueness at the database level. Deactivation is a logical delete.
    """

    id: UUID
    email: Email
    name: UserName
    status: UserStatus
    profile: Profile
    created_at: datetime
    updated_at: datetime
    _events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        *,
        email: Email,
        name: UserName,
        profile: Profile | None = None,
    ) -> "User":
        now = datetime.now(timezone.utc)
        user = cls(
            id=uuid4(),
            email=email,
            name=name,
            status=UserStatus.ACTIVE,
            profile=profile if profile is not None else Profile.empty(),
            created_at=now,
            updated_at=now,
        )
        user._events.append(
            UserCreated(
                user_id=user.id,
                email=user.email.value,
                name=user.name.value,
                status=user.status.value,
            )
        )
        return user

    def update(
        self,
        *,
        email: Email | None = None,
        name: UserName | None = None,
        profile: Profile | None = None,
    ) -> None:
        changed: list[str] = []
        if email is not None and email != self.email:
            self.email = email
            changed.append("email")
        if name is not None and name != self.name:
            self.name = name
            changed.append("name")
        if profile is not None and profile != self.profile:
            self.profile = profile
            changed.append("profile")
        if not changed:
            return

        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            UserUpdated(
                user_id=self.id,
                email=self.email.value,
                name=self.name.value,
                status=self.status.value,
            )
        )

    def deactivate(self) -> bool:
        """Apply the logical delete. Returns whether the user changed."""
        if self.status is UserStatus.INACTIVE:
            return False

        self.status = UserStatus.INACTIVE
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            UserDeactivated(user_id=self.id, email=self.email.value)
        )
        return True

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events
