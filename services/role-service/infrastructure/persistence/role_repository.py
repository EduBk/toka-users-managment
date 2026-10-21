"""SQLAlchemy implementations of the role and assignment repositories."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from application.exceptions import RoleAlreadyExists
from domain.role.assignment import UserRoleAssignment
from domain.role.entity import Permission, Role
from domain.role.value_objects import (
    AssignmentKey,
    PermissionName,
    RoleDescription,
    RoleName,
)
from infrastructure.persistence.models import (
    RoleModel,
    RolePermissionModel,
    UserRoleModel,
)


class SqlAlchemyRoleRepository:
    """Session-scoped repository: the unit of work owns the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, role_id: UUID) -> Role | None:
        model = await self._session.get(RoleModel, role_id)
        if model is None:
            return None
        permissions = await self._permissions_for([role_id])
        return _to_domain(model, permissions.get(role_id, frozenset()))

    async def get_by_name(self, name: RoleName) -> Role | None:
        model = await self._session.scalar(
            select(RoleModel).where(RoleModel.name == name.value)
        )
        if model is None:
            return None
        permissions = await self._permissions_for([model.id])
        return _to_domain(model, permissions.get(model.id, frozenset()))

    async def list(self) -> list[Role]:
        models = (
            await self._session.scalars(
                select(RoleModel).order_by(RoleModel.name)
            )
        ).all()
        permissions = await self._permissions_for(
            [model.id for model in models]
        )
        return [
            _to_domain(model, permissions.get(model.id, frozenset()))
            for model in models
        ]

    async def exists_by_name(self, name: RoleName) -> bool:
        role_id = await self._session.scalar(
            select(RoleModel.id).where(RoleModel.name == name.value)
        )
        return role_id is not None

    async def add(self, role: Role) -> None:
        self._session.add(_to_model(role))
        self._session.add_all(_permission_models(role))
        await self._flush()

    async def save(self, role: Role) -> None:
        await self._session.merge(_to_model(role))
        await self._session.execute(
            delete(RolePermissionModel).where(
                RolePermissionModel.role_id == role.id
            )
        )
        self._session.add_all(_permission_models(role))
        await self._flush()

    async def _permissions_for(
        self, role_ids: list[UUID]
    ) -> dict[UUID, frozenset[Permission]]:
        if not role_ids:
            return {}
        rows = (
            await self._session.execute(
                select(
                    RolePermissionModel.role_id,
                    RolePermissionModel.permission,
                )
                .where(RolePermissionModel.role_id.in_(role_ids))
                .order_by(RolePermissionModel.permission)
            )
        ).all()
        grouped: dict[UUID, set[Permission]] = defaultdict(set)
        for role_id, permission in rows:
            grouped[role_id].add(Permission(PermissionName(permission)))
        return {
            role_id: frozenset(permissions)
            for role_id, permissions in grouped.items()
        }

    async def _flush(self) -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise RoleAlreadyExists(
                "a role with the same name already exists"
            ) from exc


class SqlAlchemyAssignmentRepository:
    """Session-scoped repository for ``user_roles``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self, key: AssignmentKey
    ) -> UserRoleAssignment | None:
        model = await self._session.scalar(
            select(UserRoleModel).where(
                UserRoleModel.user_id == key.user_id,
                UserRoleModel.role_id == key.role_id,
            )
        )
        if model is None:
            return None
        return UserRoleAssignment(
            user_id=model.user_id,
            role_id=model.role_id,
            assigned_at=model.assigned_at,
        )

    async def is_assigned(self, key: AssignmentKey) -> bool:
        user_id = await self._session.scalar(
            select(UserRoleModel.user_id).where(
                UserRoleModel.user_id == key.user_id,
                UserRoleModel.role_id == key.role_id,
            )
        )
        return user_id is not None

    async def add(self, assignment: UserRoleAssignment) -> bool:
        statement = (
            pg_insert(UserRoleModel)
            .values(
                user_id=assignment.user_id,
                role_id=assignment.role_id,
                assigned_at=assignment.assigned_at,
            )
            .on_conflict_do_nothing(
                index_elements=[UserRoleModel.user_id, UserRoleModel.role_id]
            )
            .returning(UserRoleModel.user_id)
        )
        return await self._session.scalar(statement) is not None

    async def remove(self, key: AssignmentKey) -> bool:
        result = await self._session.execute(
            delete(UserRoleModel).where(
                UserRoleModel.user_id == key.user_id,
                UserRoleModel.role_id == key.role_id,
            )
        )
        return result.rowcount > 0

    async def roles_for_user(self, user_id: UUID) -> list[Role]:
        role_ids = (
            await self._session.scalars(
                select(UserRoleModel.role_id).where(
                    UserRoleModel.user_id == user_id
                )
            )
        ).all()
        if not role_ids:
            return []

        models = (
            await self._session.scalars(
                select(RoleModel)
                .where(RoleModel.id.in_(role_ids))
                .order_by(RoleModel.name)
            )
        ).all()
        permissions = await self._permissions_for(
            [model.id for model in models]
        )
        return [
            _to_domain(model, permissions.get(model.id, frozenset()))
            for model in models
        ]

    async def permissions_for_user(self, user_id: UUID) -> tuple[str, ...]:
        rows = (
            await self._session.scalars(
                select(RolePermissionModel.permission)
                .join(
                    UserRoleModel,
                    UserRoleModel.role_id == RolePermissionModel.role_id,
                )
                .where(UserRoleModel.user_id == user_id)
                .distinct()
                .order_by(RolePermissionModel.permission)
            )
        ).all()
        return tuple(rows)

    async def _permissions_for(
        self, role_ids: list[UUID]
    ) -> dict[UUID, frozenset[Permission]]:
        if not role_ids:
            return {}
        rows = (
            await self._session.execute(
                select(
                    RolePermissionModel.role_id,
                    RolePermissionModel.permission,
                )
                .where(RolePermissionModel.role_id.in_(role_ids))
                .order_by(RolePermissionModel.permission)
            )
        ).all()
        grouped: dict[UUID, set[Permission]] = defaultdict(set)
        for role_id, permission in rows:
            grouped[role_id].add(Permission(PermissionName(permission)))
        return {
            role_id: frozenset(permissions)
            for role_id, permissions in grouped.items()
        }


def _to_model(role: Role) -> RoleModel:
    return RoleModel(
        id=role.id,
        name=role.name.value,
        description=role.description.value,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def _permission_models(role: Role) -> list[RolePermissionModel]:
    return [
        RolePermissionModel(role_id=role.id, permission=permission.name.value)
        for permission in sorted(
            role.permissions, key=lambda item: item.name.value
        )
    ]


def _to_domain(
    model: RoleModel, permissions: frozenset[Permission]
) -> Role:
    return Role(
        id=model.id,
        name=RoleName(model.name),
        description=RoleDescription(model.description),
        permissions=permissions,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
