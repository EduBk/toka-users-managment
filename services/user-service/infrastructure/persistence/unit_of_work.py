"""SQLAlchemy unit of work: one session, one transaction per use case."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.persistence.outbox_store import SqlAlchemyOutboxStore
from infrastructure.persistence.user_repository import SqlAlchemyUserRepository


class SqlAlchemyUnitOfWork:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        producer: str,
    ) -> None:
        self._session_factory = session_factory
        self._producer = producer
        self._session: AsyncSession | None = None
        self.users: SqlAlchemyUserRepository
        self.outbox: SqlAlchemyOutboxStore

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self.users = SqlAlchemyUserRepository(self._session)
        self.outbox = SqlAlchemyOutboxStore(
            self._session, producer=self._producer
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        await self._require_session().commit()

    async def rollback(self) -> None:
        await self._require_session().rollback()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        return self._session
