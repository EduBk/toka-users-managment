"""In-memory doubles for the application ports."""

from types import TracebackType
from uuid import UUID

from application.dto import UserPage
from domain.user.entity import User
from domain.user.events import DomainEvent
from domain.user.exceptions import EmailAlreadyExists
from domain.user.value_objects import Email


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.saved: list[User] = []

    async def get(self, user_id: UUID) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    async def list(
        self, *, page: int, page_size: int
    ) -> tuple[list[User], int]:
        ordered = sorted(
            self.users,
            key=lambda user: (user.created_at, str(user.id)),
            reverse=True,
        )
        start = (page - 1) * page_size
        return ordered[start : start + page_size], len(self.users)

    async def exists_by_email(self, email: Email) -> bool:
        return any(user.email == email for user in self.users)

    async def add(self, user: User) -> None:
        if await self.exists_by_email(user.email):
            raise EmailAlreadyExists(
                f"email '{user.email}' is already registered"
            )
        self.users.append(user)

    async def save(self, user: User) -> None:
        for index, existing in enumerate(self.users):
            if existing.id == user.id:
                self.users[index] = user
                break
        else:
            self.users.append(user)
        self.saved.append(user)


class FakeEventOutbox:
    def __init__(self) -> None:
        self.events: list[tuple[DomainEvent, str]] = []

    async def append(
        self, event: DomainEvent, *, correlation_id: str
    ) -> None:
        self.events.append((event, correlation_id))


class FakeUserCache:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}
        self.pages: dict[tuple[int, int], UserPage] = {}
        self.invalidated: list[UUID] = []
        self.writes = 0

    async def get_user(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def set_user(self, user: User) -> None:
        self.writes += 1
        self.users[user.id] = user

    async def get_page(self, *, page: int, page_size: int) -> UserPage | None:
        return self.pages.get((page, page_size))

    async def set_page(self, page: UserPage) -> None:
        self.writes += 1
        self.pages[(page.page, page.page_size)] = page

    async def invalidate(self, user_id: UUID) -> None:
        self.invalidated.append(user_id)
        self.users.pop(user_id, None)
        self.pages.clear()


class FakeUnitOfWork:
    def __init__(self, users: InMemoryUserRepository | None = None) -> None:
        self.users = users or InMemoryUserRepository()
        self.outbox = FakeEventOutbox()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1
