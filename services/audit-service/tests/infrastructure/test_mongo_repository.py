from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from pymongo.errors import DuplicateKeyError, OperationFailure

from domain.audit.entity import AuditEntry
from infrastructure.persistence.mongo_repository import (
    MongoAuditEntryRepository,
    MongoProcessedEventStore,
    build_audit_query,
)


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents
        self.calls: list[tuple[str, Any]] = []

    def sort(self, keys: Any) -> "FakeCursor":
        self.calls.append(("sort", keys))
        return self

    def skip(self, count: int) -> "FakeCursor":
        self.calls.append(("skip", count))
        return self

    def limit(self, count: int) -> "FakeCursor":
        self.calls.append(("limit", count))
        return self

    def __aiter__(self) -> "FakeCursor":
        self._iterator = iter(self._documents)
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration from None


class FakeCollection:
    name = "audit_entries"

    def __init__(self, *, ttl_conflict: bool = False) -> None:
        self.documents: list[dict[str, Any]] = []
        self.indexes: list[str] = []
        self.ttl_conflict = ttl_conflict
        self.cursor = FakeCursor(self.documents)
        self.last_query: dict[str, Any] | None = None

    async def create_index(self, _keys: Any, *, name: str, **options: Any) -> str:
        if name == "occurred_at_ttl" and self.ttl_conflict:
            raise OperationFailure("index options conflict", code=85)
        self.indexes.append(name)
        return name

    async def insert_one(self, document: dict[str, Any]) -> None:
        if any(doc["event_id"] == document["event_id"] for doc in self.documents):
            raise DuplicateKeyError("duplicate event_id")
        self.documents.append(document)

    async def find_one(
        self, query: dict[str, Any], _projection: dict[str, int]
    ) -> dict[str, Any] | None:
        return next(
            (doc for doc in self.documents if doc["event_id"] == query["event_id"]),
            None,
        )

    async def count_documents(self, query: dict[str, Any]) -> int:
        self.last_query = query
        return len(self.documents)

    def find(self, query: dict[str, Any], _projection: dict[str, int]) -> FakeCursor:
        return self.cursor


class FakeDatabase:
    def __init__(self, collection: FakeCollection) -> None:
        self.collection = collection
        self.commands: list[tuple[Any, ...]] = []

    def __getitem__(self, _name: str) -> FakeCollection:
        return self.collection

    async def command(self, *args: Any, **kwargs: Any) -> None:
        self.commands.append((*args, kwargs))


def _entry() -> AuditEntry:
    return AuditEntry.create(
        event_id=uuid4(),
        event_type="user.created",
        version=1,
        occurred_at=datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc),
        producer="user-service",
        payload={"user_id": "account-1"},
        correlation_id="req-1234",
        actor_id="account-1",
    )


async def test_ensure_indexes_creates_unique_ttl_and_filter_indexes() -> None:
    collection = FakeCollection()
    repository = MongoAuditEntryRepository(FakeDatabase(collection))  # type: ignore[arg-type]

    await repository.ensure_indexes()

    assert collection.indexes == [
        "event_id_unique",
        "occurred_at_ttl",
        "actor_id",
        "type",
    ]


async def test_ensure_indexes_updates_an_existing_ttl_with_collmod() -> None:
    database = FakeDatabase(FakeCollection(ttl_conflict=True))
    repository = MongoAuditEntryRepository(database, retention_days=30)  # type: ignore[arg-type]

    await repository.ensure_indexes()

    command, collection_name, options = database.commands[0]
    assert (command, collection_name) == ("collMod", "audit_entries")
    assert options["index"]["expireAfterSeconds"] == 30 * 86_400


def test_repository_rejects_a_retention_below_one_day() -> None:
    with pytest.raises(ValueError):
        MongoAuditEntryRepository(FakeDatabase(FakeCollection()), retention_days=0)  # type: ignore[arg-type]


async def test_add_if_absent_is_idempotent_and_round_trips_entries() -> None:
    collection = FakeCollection()
    repository = MongoAuditEntryRepository(FakeDatabase(collection))  # type: ignore[arg-type]
    entry = _entry()

    assert await repository.add_if_absent(entry) is True
    assert await repository.add_if_absent(entry) is False
    assert await repository.exists(entry.event_id) is True

    items, total = await repository.search(
        user="account-1",
        event_type=None,
        from_at=None,
        to_at=None,
        page=2,
        page_size=10,
    )

    assert total == 1
    assert items == [entry]
    assert collection.last_query == {"actor_id": "account-1"}
    assert ("skip", 10) in collection.cursor.calls
    assert ("limit", 10) in collection.cursor.calls


def test_build_query_maps_filters() -> None:
    from_at = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    to_at = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)

    query = build_audit_query(
        user=" account-1 ",
        event_type="user.created",
        from_at=from_at,
        to_at=to_at,
    )

    assert query == {
        "actor_id": "account-1",
        "type": "user.created",
        "occurred_at": {"$gte": from_at, "$lte": to_at},
    }


def test_build_query_omits_empty_filters() -> None:
    assert build_audit_query(user="", event_type="  ") == {}


class FakeRepository:
    def __init__(self, existing: set[UUID]) -> None:
        self._existing = existing

    async def exists(self, event_id: UUID) -> bool:
        return event_id in self._existing


async def test_processed_store_delegates_to_repository() -> None:
    event_id = UUID("00000000-0000-0000-0000-000000000001")
    store = MongoProcessedEventStore(FakeRepository({event_id}))  # type: ignore[arg-type]

    assert await store.is_processed(event_id) is True
    assert await store.is_processed(UUID(int=2)) is False
    await store.mark_processed(event_id)
