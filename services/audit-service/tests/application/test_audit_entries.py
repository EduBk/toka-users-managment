from datetime import datetime, timezone
from uuid import UUID, uuid4

from app_common.event_consumer import IdempotentEventHandler
from app_common.event_envelope import EventEnvelope
from application.dto import (
    RecordAuditEntryCommand,
    SearchAuditEntriesQuery,
)
from application.use_cases.record_audit_entry import RecordAuditEntry
from application.use_cases.search_audit_entries import SearchAuditEntries
from infrastructure.messaging.consumer import AuditEventHandler
from tests.application.fakes import InMemoryAuditEntryRepository

_NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def _command(**overrides: object) -> RecordAuditEntryCommand:
    values: dict[str, object] = {
        "event_id": uuid4(),
        "event_type": "user.created",
        "version": 1,
        "occurred_at": _NOW,
        "producer": "user-service",
        "payload": {"user_id": str(uuid4())},
        "correlation_id": "req-1234",
        "actor_id": None,
    }
    values.update(overrides)
    return RecordAuditEntryCommand(**values)  # type: ignore[arg-type]


class RepositoryProcessedStore:
    def __init__(self, repository: InMemoryAuditEntryRepository) -> None:
        self._repository = repository

    async def is_processed(self, event_id: UUID) -> bool:
        return await self._repository.exists(event_id)

    async def mark_processed(self, event_id: UUID) -> None:
        return None


async def test_record_audit_entry_persists_event() -> None:
    repository = InMemoryAuditEntryRepository()
    command = _command(actor_id=str(uuid4()))

    stored = await RecordAuditEntry(repository).execute(command)

    assert stored is True
    assert len(repository.entries) == 1
    entry = repository.entries[0]
    assert entry.event_id == command.event_id
    assert entry.actor_id is not None
    assert entry.actor_id.value == command.actor_id


async def test_duplicate_event_is_not_inserted_twice() -> None:
    repository = InMemoryAuditEntryRepository()
    use_case = RecordAuditEntry(repository)
    command = _command()

    assert await use_case.execute(command) is True
    assert await use_case.execute(command) is False
    assert len(repository.entries) == 1


async def test_idempotent_handler_skips_repeated_delivery() -> None:
    repository = InMemoryAuditEntryRepository()
    handler = IdempotentEventHandler(
        AuditEventHandler(RecordAuditEntry(repository)),
        RepositoryProcessedStore(repository),
    )
    event = EventEnvelope.create(
        type="user.created",
        producer="user-service",
        payload={"user_id": str(uuid4()), "email": "ana@example.com"},
        correlation_id="req-1234",
    )

    await handler(event)
    await handler(event)

    assert len(repository.entries) == 1


async def test_handler_uses_user_id_as_actor() -> None:
    repository = InMemoryAuditEntryRepository()
    actor_id = str(uuid4())
    event = EventEnvelope.create(
        type="user.logged_in",
        producer="auth-service",
        payload={"user_id": actor_id, "email": "ana@example.com"},
        correlation_id="req-1234",
    )

    await AuditEventHandler(RecordAuditEntry(repository))(event)

    assert repository.entries[0].actor_id is not None
    assert repository.entries[0].actor_id.value == actor_id


async def test_login_failure_has_no_actor_id() -> None:
    repository = InMemoryAuditEntryRepository()
    event = EventEnvelope.create(
        type="user.login_failed",
        producer="auth-service",
        payload={
            "email": "ana@example.com",
            "reason": "invalid_credentials",
        },
        correlation_id="req-1234",
    )

    await AuditEventHandler(RecordAuditEntry(repository))(event)

    assert repository.entries[0].actor_id is None


async def test_search_filters_by_user_type_and_date_range() -> None:
    repository = InMemoryAuditEntryRepository()
    use_case = RecordAuditEntry(repository)
    actor_id = str(uuid4())
    other_actor = str(uuid4())

    await use_case.execute(
        _command(
            event_type="user.created",
            actor_id=actor_id,
            occurred_at=datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc),
        )
    )
    await use_case.execute(
        _command(
            event_type="role.assigned",
            actor_id=actor_id,
            occurred_at=datetime(2026, 10, 20, 11, 0, tzinfo=timezone.utc),
        )
    )
    await use_case.execute(
        _command(
            event_type="user.created",
            actor_id=other_actor,
            occurred_at=datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc),
        )
    )

    page = await SearchAuditEntries(repository).execute(
        SearchAuditEntriesQuery(
            user=actor_id,
            event_type="role.assigned",
            from_at=datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc),
            to_at=datetime(2026, 10, 20, 11, 30, tzinfo=timezone.utc),
            page=1,
            page_size=20,
        )
    )

    assert page.total == 1
    assert page.items[0].type.value == "role.assigned"


async def test_search_paginates_results() -> None:
    repository = InMemoryAuditEntryRepository()
    use_case = RecordAuditEntry(repository)
    for hour in (10, 11, 12):
        await use_case.execute(
            _command(
                occurred_at=datetime(
                    2026, 10, 20, hour, 0, tzinfo=timezone.utc
                )
            )
        )

    page = await SearchAuditEntries(repository).execute(
        SearchAuditEntriesQuery(
            user=None,
            event_type=None,
            from_at=None,
            to_at=None,
            page=2,
            page_size=2,
        )
    )

    assert page.total == 3
    assert len(page.items) == 1
    assert page.page == 2
