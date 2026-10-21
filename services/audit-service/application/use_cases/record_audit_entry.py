"""Persist a consumed domain event as an audit entry."""

from application.dto import RecordAuditEntryCommand
from domain.audit.entity import AuditEntry
from domain.audit.repository import AuditEntryRepository


class RecordAuditEntry:
    def __init__(self, repository: AuditEntryRepository) -> None:
        self._repository = repository

    async def execute(self, command: RecordAuditEntryCommand) -> bool:
        entry = AuditEntry.create(
            event_id=command.event_id,
            event_type=command.event_type,
            version=command.version,
            occurred_at=command.occurred_at,
            producer=command.producer,
            payload=command.payload,
            correlation_id=command.correlation_id,
            actor_id=command.actor_id,
        )
        return await self._repository.add_if_absent(entry)
