"""SQLAlchemy implementation of :class:`UserRepository`."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain.user.entity import User
from domain.user.exceptions import EmailAlreadyExists
from domain.user.value_objects import Email, Profile, UserName, UserStatus
from infrastructure.persistence.models import UserModel


class SqlAlchemyUserRepository:
    """Session-scoped repository: the unit of work owns the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return _to_domain(model) if model is not None else None

    async def list(
        self, *, page: int, page_size: int
    ) -> tuple[list[User], int]:
        total = (
            await self._session.scalar(
                select(func.count()).select_from(UserModel)
            )
        ) or 0
        rows = (
            await self._session.scalars(
                select(UserModel)
                .order_by(UserModel.created_at.desc(), UserModel.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [_to_domain(row) for row in rows], total

    async def exists_by_email(self, email: Email) -> bool:
        user_id = await self._session.scalar(
            select(UserModel.id).where(UserModel.email == email.value)
        )
        return user_id is not None

    async def add(self, user: User) -> None:
        self._session.add(_to_model(user))
        await self._flush()

    async def save(self, user: User) -> None:
        await self._session.merge(_to_model(user))
        await self._flush()

    async def _flush(self) -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise EmailAlreadyExists(
                "a user with the same email already exists"
            ) from exc


def _to_model(user: User) -> UserModel:
    return UserModel(
        id=user.id,
        email=user.email.value,
        name=user.name.value,
        status=user.status.value,
        profile=user.profile.value,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=Email(model.email),
        name=UserName(model.name),
        status=UserStatus.parse(model.status),
        profile=Profile(model.profile or {}),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
