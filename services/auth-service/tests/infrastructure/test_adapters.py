from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from domain.auth.entity import Account
from domain.auth.events import UserLoggedIn
from domain.auth.exceptions import EmailAlreadyRegistered
from domain.auth.value_objects import Email
from infrastructure.persistence.account_repository import SqlAlchemyAccountRepository
from infrastructure.persistence.models import AccountModel, OutboxEventModel
from infrastructure.persistence.outbox_store import SqlAlchemyOutbox
from infrastructure.redis.revocation_store import (
    NullTokenRevocationStore,
    RedisTokenRevocationStore,
)
from infrastructure.security.keys import read_key_pair


class _Rows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class FakeSession:
    def __init__(
        self,
        *,
        model: Any = None,
        rows: list[Any] | None = None,
        commit_error: Exception | None = None,
    ) -> None:
        self.model = model
        self.rows = rows or []
        self.commit_error = commit_error
        self.added: list[Any] = []
        self.executed: list[Any] = []
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        return None

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    async def scalar(self, _statement: Any) -> Any:
        return self.model

    async def scalars(self, _statement: Any) -> _Rows:
        return _Rows(self.rows)

    async def get(self, _model: type, _key: Any) -> Any:
        return self.model

    async def execute(self, statement: Any) -> None:
        self.executed.append(statement)

    async def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, tuple[str, int | None]] = {}
        self.closed = False

    async def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        self.data[key] = (value, ex)

    async def exists(self, key: str) -> int:
        return 1 if key in self.data else 0

    async def aclose(self) -> None:
        self.closed = True


def _account_model() -> AccountModel:
    return AccountModel(
        id=uuid4(),
        email="ana@example.com",
        password_hash="hashed:secret",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


async def test_account_repository_maps_rows_to_accounts() -> None:
    model = _account_model()
    repository = SqlAlchemyAccountRepository(lambda: FakeSession(model=model))  # type: ignore[arg-type]

    by_email = await repository.get_by_email(Email("ana@example.com"))
    by_id = await repository.get_by_id(model.id)

    assert by_email is not None and by_email.id == model.id
    assert by_id is not None and by_id.email.value == "ana@example.com"
    assert await repository.exists_by_email(Email("ana@example.com")) is True


async def test_account_repository_returns_none_when_missing() -> None:
    repository = SqlAlchemyAccountRepository(lambda: FakeSession())  # type: ignore[arg-type]

    assert await repository.get_by_id(uuid4()) is None
    assert await repository.get_by_email(Email("ana@example.com")) is None


async def test_account_repository_commits_new_accounts() -> None:
    session = FakeSession()
    repository = SqlAlchemyAccountRepository(lambda: session)  # type: ignore[arg-type]

    await repository.add(
        Account.create(email=Email("ana@example.com"), password_hash="hash")
    )

    assert session.added[0].email == "ana@example.com"
    assert session.commits == 1


async def test_account_repository_translates_unique_violations() -> None:
    session = FakeSession(
        commit_error=IntegrityError("insert", {}, Exception("duplicate"))
    )
    repository = SqlAlchemyAccountRepository(lambda: session)  # type: ignore[arg-type]

    with pytest.raises(EmailAlreadyRegistered):
        await repository.add(
            Account.create(email=Email("ana@example.com"), password_hash="hash")
        )
    assert session.rollbacks == 1


async def test_outbox_appends_and_reads_pending_events() -> None:
    session = FakeSession()
    outbox = SqlAlchemyOutbox(lambda: session, producer="auth-service")  # type: ignore[arg-type]
    user_id = uuid4()

    await outbox.append(
        UserLoggedIn(user_id=user_id, email="ana@example.com"),
        correlation_id="req-1234",
    )
    record: OutboxEventModel = session.added[0]
    record.attempts = 0
    session.rows = [record]
    pending = await outbox.pending_batch(5)
    await outbox.mark_published(record.event_id)
    await outbox.mark_failed(
        record.event_id, error="boom", retry_at=datetime.now(timezone.utc)
    )

    assert record.type == "user.logged_in"
    assert record.producer == "auth-service"
    assert pending[0].envelope.payload["user_id"] == str(user_id)
    assert len(session.executed) == 2
    assert session.commits == 3


async def test_redis_revocation_store_uses_the_jti_key_with_ttl() -> None:
    redis = FakeRedis()
    store = RedisTokenRevocationStore(redis)  # type: ignore[arg-type]

    await store.revoke("jti-1", 900)

    assert redis.data["auth:revoked:jti-1"] == ("1", 900)
    assert await store.is_revoked("jti-1") is True
    assert await store.is_revoked("jti-2") is False
    await store.close()
    assert redis.closed is True


async def test_null_revocation_store_never_revokes() -> None:
    store = NullTokenRevocationStore()

    await store.revoke("jti-1", 900)

    assert await store.is_revoked("jti-1") is False
    await store.close()


def test_read_key_pair_loads_both_files(tmp_path: Path) -> None:
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    private_key.write_text("private", encoding="utf-8")
    public_key.write_text("public", encoding="utf-8")

    assert read_key_pair(str(private_key), str(public_key)) == (
        "private",
        "public",
    )


def test_read_key_pair_explains_how_to_generate_missing_keys(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="generate_jwt_keys.py"):
        read_key_pair(str(tmp_path / "missing.pem"), str(tmp_path / "x.pem"))
