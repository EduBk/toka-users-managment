"""Outbound port for account persistence."""

from typing import Protocol
from uuid import UUID

from domain.auth.entity import Account
from domain.auth.value_objects import Email


class AccountRepository(Protocol):
    async def get_by_email(self, email: Email) -> Account | None: ...

    async def get_by_id(self, account_id: UUID) -> Account | None: ...

    async def exists_by_email(self, email: Email) -> bool: ...

    async def add(self, account: Account) -> None: ...
