"""MongoDB adapter for audit entries and processed-event checks."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure

from domain.audit.entity import AuditEntry

COLLECTION_NAME = "audit_entries"
_SECONDS_PER_DAY = 86_400


class MongoAuditEntryRepository:
    """Stores audit entries in MongoDB.

    ``event_id`` has a unique index, so ``add_if_absent`` is race-safe even with
    at-least-once delivery and concurrent consumers.
    """

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        *,
        retention_days: int = 90,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        if retention_days < 1:
            raise ValueError("retention_days must be >= 1")
        self._database = database
        self._collection: AsyncIOMotorCollection = database[collection_name]
        self._retention_days = retention_days

    async def ensure_indexes(self) -> None:
        await self._collection.create_index(
            [("event_id", ASCENDING)],
            name="event_id_unique",
            unique=True,
        )
        ttl_seconds = self._retention_days * _SECONDS_PER_DAY
        try:
            await self._collection.create_index(
                [("occurred_at", ASCENDING)],
                name="occurred_at_ttl",
                expireAfterSeconds=ttl_seconds,
            )
        except OperationFailure as exc:
            # Changing AUDIT_RETENTION_DAYS must update the existing TTL index.
            if exc.code not in (85, 86):
                raise
            await self._database.command(
                "collMod",
                self._collection.name,
                index={
                    "name": "occurred_at_ttl",
                    "expireAfterSeconds": ttl_seconds,
                },
            )
        await self._collection.create_index(
            [("actor_id", ASCENDING)],
            name="actor_id",
        )
        await self._collection.create_index(
            [("type", ASCENDING)],
            name="type",
        )

    async def add_if_absent(self, entry: AuditEntry) -> bool:
        try:
            await self._collection.insert_one(_to_document(entry))
        except DuplicateKeyError:
            return False
        return True

    async def exists(self, event_id: UUID) -> bool:
        document = await self._collection.find_one(
            {"event_id": str(event_id)}, {"_id": 1}
        )
        return document is not None

    async def search(
        self,
        *,
        user: str | None,
        event_type: str | None,
        from_at: datetime | None,
        to_at: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[AuditEntry], int]:
        query = build_audit_query(
            user=user,
            event_type=event_type,
            from_at=from_at,
            to_at=to_at,
        )
        total = await self._collection.count_documents(query)
        cursor = (
            self._collection.find(query, {"_id": 0})
            .sort([("occurred_at", DESCENDING), ("event_id", ASCENDING)])
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items = [_to_entry(document) async for document in cursor]
        return items, total


class MongoProcessedEventStore:
    """Idempotency store backed by the unique ``event_id`` of the audit log.

    The audit entry itself is the durable marker: the insert that creates it is
    conditional on the unique index, so no second collection is needed.
    """

    def __init__(self, repository: MongoAuditEntryRepository) -> None:
        self._repository = repository

    async def is_processed(self, event_id: UUID) -> bool:
        return await self._repository.exists(event_id)

    async def mark_processed(self, event_id: UUID) -> None:
        # ``add_if_absent`` already persisted the marker inside the handler.
        return None


def build_audit_query(
    *,
    user: str | None = None,
    event_type: str | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if user and user.strip():
        query["actor_id"] = user.strip()
    if event_type and event_type.strip():
        query["type"] = event_type.strip()

    occurred_at: dict[str, datetime] = {}
    if from_at is not None:
        occurred_at["$gte"] = _as_utc(from_at)
    if to_at is not None:
        occurred_at["$lte"] = _as_utc(to_at)
    if occurred_at:
        query["occurred_at"] = occurred_at
    return query


def _to_document(entry: AuditEntry) -> dict[str, Any]:
    return {
        "event_id": str(entry.event_id),
        "type": entry.type.value,
        "version": entry.version,
        "occurred_at": entry.occurred_at,
        "producer": entry.producer,
        "actor_id": entry.actor_id.value if entry.actor_id else None,
        "payload": entry.payload.value,
        "correlation_id": entry.correlation_id,
    }


def _to_entry(document: dict[str, Any]) -> AuditEntry:
    return AuditEntry.create(
        event_id=UUID(document["event_id"]),
        event_type=document["type"],
        version=int(document["version"]),
        occurred_at=_as_utc(document["occurred_at"]),
        producer=document["producer"],
        actor_id=document.get("actor_id"),
        payload=document["payload"],
        correlation_id=document["correlation_id"],
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "MongoAuditEntryRepository",
    "MongoProcessedEventStore",
    "build_audit_query",
]
