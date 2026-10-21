"""Audit routes: validate input, delegate to use cases, map the result."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from api.deps import AuditClaims, get_search_audit_entries
from api.schemas import AuditEntryResponse, AuditPageResponse
from application.dto import SearchAuditEntriesQuery
from application.use_cases.search_audit_entries import SearchAuditEntries

router = APIRouter(tags=["audit"])


@router.get(
    "/audit",
    response_model=AuditPageResponse,
    summary="Search audit entries with offset pagination",
)
async def search_audit(
    _claims: AuditClaims,
    user: str | None = Query(default=None, max_length=254),
    event_type: str | None = Query(
        default=None, alias="type", max_length=120
    ),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    use_case: SearchAuditEntries = Depends(get_search_audit_entries),
) -> AuditPageResponse:
    result = await use_case.execute(
        SearchAuditEntriesQuery(
            user=user,
            event_type=event_type,
            from_at=from_at,
            to_at=to_at,
            page=page,
            page_size=page_size,
        )
    )
    return AuditPageResponse(
        items=[
            AuditEntryResponse.from_domain(entry) for entry in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
