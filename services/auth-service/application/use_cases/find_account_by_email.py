"""Resolve the account that owns an email (admin lookup, E2.13)."""

from application.exceptions import AccountNotFound
from domain.auth.entity import Account
from domain.auth.repository import AccountRepository
from domain.auth.value_objects import Email


class FindAccountByEmail:
    def __init__(self, accounts: AccountRepository) -> None:
        self._accounts = accounts

    async def execute(self, email: str) -> Account:
        account = await self._accounts.get_by_email(Email(email))
        if account is None:
            raise AccountNotFound("no account is registered with this email")
        return account
