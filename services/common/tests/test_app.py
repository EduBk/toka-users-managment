import json
import logging

from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.errors import ConflictError, NotFoundError
from app_common.logging import JsonFormatter, TraceContextFilter, log_event


class _Payload(BaseModel):
    name: str


def _client() -> TestClient:
    router = APIRouter()

    @router.get("/missing")
    async def missing() -> None:
        raise NotFoundError("thing not found", details={"id": "1"})

    @router.get("/conflict")
    async def conflict() -> None:
        raise ConflictError("already exists", code="thing_exists")

    @router.get("/boom")
    async def boom() -> None:
        raise RuntimeError("database password=hunter2")

    @router.post("/things")
    async def create(payload: _Payload) -> _Payload:
        return payload

    app = create_service_app(
        BaseServiceSettings(service_name="test-service"), routers=[router]
    )
    return TestClient(app, raise_server_exceptions=False)


def test_health_reports_service_metadata() -> None:
    response = _client().get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "test-service",
        "version": "0.1.0",
        "environment": "local",
    }


def test_app_errors_use_the_shared_schema() -> None:
    client = _client()

    missing = client.get("/missing")
    conflict = client.get("/conflict")

    assert missing.status_code == 404
    assert missing.json() == {
        "code": "not_found",
        "message": "thing not found",
        "details": {"id": "1"},
    }
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "thing_exists"


def test_validation_errors_return_422_with_details() -> None:
    response = _client().post("/things", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["details"][0]["loc"] == ["body", "name"]


def test_validation_errors_do_not_echo_the_rejected_input() -> None:
    response = _client().post("/things", json={"name": ["top-secret-value"]})

    assert response.status_code == 422
    assert "top-secret-value" not in response.text
    assert "input" not in response.json()["details"][0]


def test_openapi_docs_are_disabled_in_production() -> None:
    local = TestClient(
        create_service_app(BaseServiceSettings(service_name="svc"))
    )
    production = TestClient(
        create_service_app(
            BaseServiceSettings(service_name="svc", environment="production")
        )
    )

    assert local.get("/openapi.json").status_code == 200
    assert production.get("/openapi.json").status_code == 404
    assert production.get("/docs").status_code == 404


def test_unknown_routes_return_404_with_the_shared_schema() -> None:
    response = _client().get("/nope")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_unexpected_errors_hide_internal_details() -> None:
    response = _client().get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Unexpected error",
        "details": None,
    }
    assert "hunter2" not in response.text


def test_trace_id_is_propagated_or_generated() -> None:
    client = _client()

    echoed = client.get("/health", headers={"X-Request-ID": "trace-12345"})
    generated = client.get("/health", headers={"X-Request-ID": "bad id!"})

    assert echoed.headers["X-Request-ID"] == "trace-12345"
    assert generated.headers["X-Request-ID"] != "bad id!"
    assert len(generated.headers["X-Request-ID"]) == 32


def test_json_formatter_includes_context_and_extra_fields() -> None:
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "hello %s", ("world",), None
    )
    record.extra_fields = {"user_id": "u-1"}
    TraceContextFilter("test-service").filter(record)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["service"] == "test-service"
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["user_id"] == "u-1"
    assert payload["timestamp"].endswith("Z")


def test_log_event_attaches_structured_fields() -> None:
    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("test.log_event")
    logger.addHandler(_Collector())
    logger.setLevel(logging.INFO)

    log_event(logger, logging.INFO, "processed", event_id="e-1")

    assert records[0].extra_fields == {"event_id": "e-1"}  # type: ignore[attr-defined]
