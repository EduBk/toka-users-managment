"""Register a new account with a hashed password."""

from application.dto import RegisterAccountCommand
from application.ports.password_hasher import PasswordHasher
from domain.auth.entity import Account
from domain.auth.exceptions import EmailAlreadyRegistered
from domain.auth.repository import AccountRepository
from domain.auth.value_objects import Email


class RegisterAccount:
    def __init__(
        self,
        accounts: AccountRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._accounts = accounts
        self._password_hasher = password_hasher

    async def execute(self, command: RegisterAccountCommand) -> Account:
        email = Email(command.email)
        if await self._accounts.exists_by_email(email):
            raise EmailAlreadyRegistered(f"email '{email}' is already registered")

        account = Account.create(
            email=email,
            password_hash=self._password_hasher.hash(command.password),
        )
        await self._accounts.add(account)
        return account
