"""SQLAlchemy implementation of :class:`AccountRepository`."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.auth.entity import Account
from domain.auth.exceptions import EmailAlreadyRegistered
from domain.auth.value_objects import Email
from infrastructure.persistence.models import AccountModel


class SqlAlchemyAccountRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_email(self, email: Email) -> Account | None:
        async with self._session_factory() as session:
            model = await session.scalar(
                select(AccountModel).where(AccountModel.email == email.value)
            )
        return _to_domain(model) if model is not None else None

    async def get_by_id(self, account_id: UUID) -> Account | None:
        async with self._session_factory() as session:
            model = await session.get(AccountModel, account_id)
        return _to_domain(model) if model is not None else None

    async def exists_by_email(self, email: Email) -> bool:
        async with self._session_factory() as session:
            account_id = await session.scalar(
                select(AccountModel.id).where(AccountModel.email == email.value)
            )
        return account_id is not None

    async def add(self, account: Account) -> None:
        async with self._session_factory() as session:
            session.add(
                AccountModel(
                    id=account.id,
                    email=account.email.value,
                    password_hash=account.password_hash,
                    is_active=account.is_active,
                    created_at=account.created_at,
                )
            )
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise EmailAlreadyRegistered(
                    f"email '{account.email}' is already registered"
                ) from exc


def _to_domain(model: AccountModel) -> Account:
    return Account(
        id=model.id,
        email=Email(model.email),
        password_hash=model.password_hash,
        is_active=model.is_active,
        created_at=model.created_at,
    )
