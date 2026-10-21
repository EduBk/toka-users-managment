"""Query the audit log with filters and offset pagination."""

from application.dto import AuditEntryPage, SearchAuditEntriesQuery
from domain.audit.repository import AuditEntryRepository


class SearchAuditEntries:
    def __init__(self, repository: AuditEntryRepository) -> None:
        self._repository = repository

    async def execute(self, query: SearchAuditEntriesQuery) -> AuditEntryPage:
        items, total = await self._repository.search(
            user=query.user,
            event_type=query.event_type,
            from_at=query.from_at,
            to_at=query.to_at,
            page=query.page,
            page_size=query.page_size,
        )
        return AuditEntryPage(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
