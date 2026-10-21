from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from domain.audit.entity import AuditEntry
from tests.api.conftest import AuthHeaders
from tests.application.fakes import InMemoryAuditEntryRepository


def _entry(event_type: str, hour: int, actor_id: str | None) -> AuditEntry:
    return AuditEntry.create(
        event_id=uuid4(),
        event_type=event_type,
        version=1,
        occurred_at=datetime(2026, 10, 20, hour, 0, tzinfo=timezone.utc),
        producer="user-service",
        payload={"user_id": actor_id} if actor_id else {"email": "x@example.com"},
        correlation_id="req-1234",
        actor_id=actor_id,
    )


@pytest.fixture
def actor_id(repository: InMemoryAuditEntryRepository) -> str:
    actor = str(uuid4())
    repository.entries.extend(
        [
            _entry("user.logged_in", 10, actor),
            _entry("user.created", 11, actor),
            _entry("user.login_failed", 12, None),
        ]
    )
    return actor


def test_audit_requires_a_token(client: TestClient) -> None:
    response = client.get("/audit")

    assert response.status_code == 401


def test_audit_rejects_accounts_without_auditor_or_admin(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.get("/audit", headers=auth_headers(roles=("user",)))

    assert response.status_code == 403
    assert response.json()["code"] == "insufficient_role"


@pytest.mark.parametrize("role", ["auditor", "admin"])
def test_auditor_and_admin_read_the_audit_log(
    client: TestClient, auth_headers: AuthHeaders, actor_id: str, role: str
) -> None:
    response = client.get("/audit", headers=auth_headers(roles=(role,)))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["items"][0]["type"] == "user.login_failed"
    assert body["items"][0]["actor_id"] is None


def test_audit_filters_by_user_type_and_date_range(
    client: TestClient, auth_headers: AuthHeaders, actor_id: str
) -> None:
    response = client.get(
        "/audit",
        params={
            "user": actor_id,
            "type": "user.created",
            "from": "2026-10-20T10:30:00Z",
            "to": "2026-10-20T11:30:00Z",
        },
        headers=auth_headers(roles=("auditor",)),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["type"] for item in items] == ["user.created"]
    assert items[0]["actor_id"] == actor_id


def test_audit_paginates(
    client: TestClient, auth_headers: AuthHeaders, actor_id: str
) -> None:
    response = client.get(
        "/audit?page=2&page_size=2", headers=auth_headers(roles=("auditor",))
    )

    body = response.json()
    assert body["page"] == 2
    assert len(body["items"]) == 1


@pytest.mark.parametrize(
    "query", ["page=0", "page_size=101", "from=not-a-date"]
)
def test_audit_validates_query_parameters(
    client: TestClient, auth_headers: AuthHeaders, query: str
) -> None:
    response = client.get(
        f"/audit?{query}", headers=auth_headers(roles=("auditor",))
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
