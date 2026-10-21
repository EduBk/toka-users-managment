"""Create or find an account for the first-admin bootstrap (E2.12).

Usage (inside the container)::

    echo "<password>" | python bootstrap_account.py --email admin@example.com --password-stdin

Prints only the account id on stdout so the host script can chain it.
"""

import argparse
import asyncio
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

from application.dto import RegisterAccountCommand
from application.use_cases.register_account import RegisterAccount
from domain.auth.exceptions import EmailAlreadyRegistered, InvalidEmail
from domain.auth.value_objects import Email
from infrastructure.persistence.account_repository import SqlAlchemyAccountRepository
from infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from infrastructure.security.bcrypt_hasher import BcryptPasswordHasher

_MAX_PASSWORD_BYTES = 72


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str


async def bootstrap_account(database_url: str, email: str, password: str) -> str:
    engine = create_database_engine(database_url)
    accounts = SqlAlchemyAccountRepository(create_session_factory(engine))
    try:
        try:
            account = await RegisterAccount(
                accounts, BcryptPasswordHasher()
            ).execute(RegisterAccountCommand(email=email, password=password))
        except EmailAlreadyRegistered:
            existing = await accounts.get_by_email(Email(email))
            if existing is None:
                raise
            account = existing
        return str(account.id)
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        required=True,
        help="read the password from the first line of stdin",
    )
    args = parser.parse_args()

    password = sys.stdin.readline().rstrip("\r\n")
    if not password or len(password.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        print("password must be 1-72 bytes", file=sys.stderr)
        return 2

    try:
        account_id = asyncio.run(
            bootstrap_account(_Settings().database_url, args.email, password)
        )
    except InvalidEmail as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(account_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
