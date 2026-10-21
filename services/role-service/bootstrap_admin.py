"""Assign the seeded ``admin`` role to an account (E2.12).

Usage (inside the container)::

    python bootstrap_admin.py --account-id <uuid>

Idempotent: re-running it does not duplicate the assignment nor the event.
"""

import argparse
import asyncio
import sys
from uuid import UUID, uuid4

from pydantic_settings import BaseSettings, SettingsConfigDict

from application.dto import AssignRoleToUserCommand
from application.use_cases.assign_role_to_user import AssignRoleToUser
from domain.role.value_objects import RoleName
from infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

ADMIN_ROLE = "admin"


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    service_name: str = "role-service"


async def bootstrap_admin(settings: _Settings, account_id: UUID) -> None:
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    def unit_of_work() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory, producer=settings.service_name)

    try:
        async with unit_of_work() as uow:
            role = await uow.roles.get_by_name(RoleName(ADMIN_ROLE))
        if role is None:
            raise RuntimeError("seeded 'admin' role not found; run the migrations")
        await AssignRoleToUser(unit_of_work).execute(
            AssignRoleToUserCommand(
                user_id=account_id,
                role_id=role.id,
                correlation_id=f"bootstrap-{uuid4().hex}",
            )
        )
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, type=UUID)
    args = parser.parse_args()

    asyncio.run(bootstrap_admin(_Settings(), args.account_id))
    print(f"role '{ADMIN_ROLE}' assigned to {args.account_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
