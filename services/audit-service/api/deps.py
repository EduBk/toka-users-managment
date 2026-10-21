"""Composition root and audit authorization dependency."""

from typing import Annotated

from fastapi import Depends, Request

from app_common.errors import ForbiddenError
from app_common.jwt_auth import CurrentClaims, TokenClaims
from application.use_cases.search_audit_entries import SearchAuditEntries

_ALLOWED_ROLES = ("admin", "auditor")


async def require_audit_access(claims: CurrentClaims) -> TokenClaims:
    if not set(_ALLOWED_ROLES).intersection(claims.roles):
        raise ForbiddenError(
            "insufficient role",
            code="insufficient_role",
            details={"allowed": list(_ALLOWED_ROLES)},
        )
    return claims


AuditClaims = Annotated[TokenClaims, Depends(require_audit_access)]


def get_search_audit_entries(request: Request) -> SearchAuditEntries:
    return SearchAuditEntries(request.app.state.audit_repository)
