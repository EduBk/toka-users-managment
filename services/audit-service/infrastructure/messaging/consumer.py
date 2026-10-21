"""RabbitMQ handler that records domain events in the audit log."""

import logging
from typing import Any, Mapping

from app_common.event_envelope import EventEnvelope
from app_common.logging import log_event

from application.dto import RecordAuditEntryCommand
from application.use_cases.record_audit_entry import RecordAuditEntry

logger = logging.getLogger("audit_service.events")


class AuditEventHandler:
    """Maps an event envelope to the audit use case and logs its outcome."""

    def __init__(self, use_case: RecordAuditEntry) -> None:
        self._use_case = use_case

    async def __call__(self, event: EventEnvelope) -> None:
        command = RecordAuditEntryCommand(
            event_id=event.event_id,
            event_type=event.type,
            version=event.version,
            occurred_at=event.occurred_at,
            producer=event.producer,
            payload=event.payload,
            correlation_id=event.correlation_id,
            actor_id=actor_id_from_payload(event.payload),
        )
        try:
            stored = await self._use_case.execute(command)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "audit event processing failed",
                event_id=str(event.event_id),
                event_type=event.type,
                correlation_id=event.correlation_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise

        log_event(
            logger,
            logging.INFO,
            "audit event processed",
            event_id=str(event.event_id),
            event_type=event.type,
            correlation_id=event.correlation_id,
            stored=stored,
        )


def actor_id_from_payload(payload: Mapping[str, Any]) -> str | None:
    """Use ``user_id`` as actor; login failures carry no actor id."""
    value = payload.get("user_id")
    if value is None:
        return None
    actor = str(value).strip()
    return actor or None
