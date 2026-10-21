from fastapi.testclient import TestClient

from app_common.rate_limit import (
    InMemoryRateLimiter,
    RateLimitPolicy,
    RateLimitRule,
)
from application.exceptions import (
    AiModelUnavailable,
    AiNotConfigured,
    AiRateLimited,
    AiUnavailable,
)
from application.use_cases.reindex_documents import ReindexDocuments
from tests.api.conftest import AuthHeaders
from tests.application.fakes import (
    FailingLoader,
    FakeEmbeddings,
    FakeLlm,
    FakeVectorStore,
)


def _ask(client: TestClient, headers: dict[str, str], **payload: object) -> dict:
    body = {"question": "¿Cómo se validan los tokens?"}
    body.update(payload)
    response = client.post("/ai/ask", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_ask_requires_a_token(client: TestClient) -> None:
    response = client.post("/ai/ask", json={"question": "hola"})

    assert response.status_code == 401
    assert response.json()["code"] == "missing_token"


def test_ask_requires_the_ai_use_scope(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    response = client.post(
        "/ai/ask",
        json={"question": "hola"},
        headers=auth_headers(scopes=("users:read",)),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "insufficient_scope"


def test_ask_returns_the_answer_sources_usage_and_latency(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    body = _ask(client, auth_headers())

    assert body["answer"] == "Respuesta con cita [1]."
    assert body["sources"] == [
        {
            "document": "arquitectura/flujos-de-datos.md",
            "section": "Validación de tokens",
            "score": 0.9,
        }
    ]
    assert body["usage"]["input_tokens"] == 27
    assert body["usage"]["output_tokens"] == 8
    assert body["usage"]["total_tokens"] == 35
    assert body["usage"]["cost_usd"] > 0
    assert body["latency"]["total_ms"] >= 0
    assert body["model"] == "fake-chat"
    assert body["prompt_version"] == "v-test"
    assert body["quality"] == {"passed": True, "issues": []}


def test_ask_validates_the_payload(client: TestClient, auth_headers: AuthHeaders) -> None:
    response = client.post(
        "/ai/ask", json={"question": ""}, headers=auth_headers()
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_ask_without_context_admits_it(
    client: TestClient, auth_headers: AuthHeaders, vectors: FakeVectorStore
) -> None:
    vectors.results = ()

    body = _ask(client, auth_headers(), question="¿Capital de Francia?")

    assert body["sources"] == []
    assert body["answer"].startswith("No tengo información suficiente")
    assert body["quality"]["passed"] is True


def test_ask_forwards_the_token_to_the_system_data_provider(
    client: TestClient, auth_headers: AuthHeaders, directory
) -> None:
    body = _ask(client, auth_headers(), include_system_data=True)

    assert len(directory.tokens) == 1
    assert body["sources"][-1]["document"] == "user-service"


def test_ask_returns_503_when_the_provider_is_down(
    client: TestClient, auth_headers: AuthHeaders, llm: FakeLlm
) -> None:
    llm.error = AiUnavailable("down")

    response = client.post(
        "/ai/ask", json={"question": "hola"}, headers=auth_headers()
    )

    assert response.status_code == 503
    assert response.json()["code"] == "ai_unavailable"


def test_ask_returns_429_when_the_provider_rate_limits(
    client: TestClient, auth_headers: AuthHeaders, llm: FakeLlm
) -> None:
    llm.error = AiRateLimited("slow down", retry_after_seconds=15)

    response = client.post(
        "/ai/ask", json={"question": "hola"}, headers=auth_headers()
    )

    assert response.status_code == 429
    assert response.json()["code"] == "ai_rate_limited"
    assert response.headers["Retry-After"] == "15"


def test_ask_reports_a_rejected_api_key(
    client: TestClient, auth_headers: AuthHeaders, llm: FakeLlm
) -> None:
    llm.error = AiNotConfigured("OpenAI rejected the API key")

    response = client.post(
        "/ai/ask", json={"question": "hola"}, headers=auth_headers()
    )

    assert response.status_code == 503
    assert response.json()["code"] == "ai_not_configured"


def test_ask_reports_a_model_without_access(
    client: TestClient, auth_headers: AuthHeaders, llm: FakeLlm
) -> None:
    llm.error = AiModelUnavailable("model access is disabled")

    response = client.post(
        "/ai/ask", json={"question": "hola"}, headers=auth_headers()
    )

    assert response.status_code == 503
    assert response.json()["code"] == "ai_model_unavailable"


def test_ask_is_rate_limited_per_user(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    client.app.state.rate_limit_ai = RateLimitPolicy(
        InMemoryRateLimiter(), RateLimitRule(limit=1, window_seconds=60)
    )
    headers = auth_headers()

    assert client.post("/ai/ask", json={"question": "hola"}, headers=headers).status_code == 200
    response = client.post(
        "/ai/ask", json={"question": "otra"}, headers=headers
    )

    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert "Retry-After" in response.headers


def test_health_reports_the_vector_store_state(
    client: TestClient, auth_headers: AuthHeaders, vectors: FakeVectorStore
) -> None:
    healthy = client.get("/ai/health", headers=auth_headers())
    vectors.ping_result = False
    degraded = client.get("/ai/health", headers=auth_headers())

    assert healthy.status_code == 200
    assert healthy.json()["status"] == "ok"
    assert healthy.json()["vector_store"] == "up"
    assert healthy.json()["llm"] == "configured"
    assert healthy.json()["embeddings"] == "fastembed:fake-model"
    assert degraded.status_code == 200
    assert degraded.json()["status"] == "degraded"
    assert degraded.json()["vector_store"] == "down"


def test_health_requires_the_ai_use_scope(client: TestClient) -> None:
    assert client.get("/ai/health").status_code == 401


def test_reindex_is_restricted_to_admins(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    assert client.post("/ai/reindex", headers=auth_headers()).status_code == 403
    response = client.post(
        "/ai/reindex", headers=auth_headers(roles=("admin",))
    )

    assert response.status_code == 200
    assert response.json()["documents_indexed"] == 1
    assert response.json()["chunks_indexed"] >= 1


def test_reindex_reports_a_missing_corpus(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    client.app.state.reindex_documents = ReindexDocuments(
        loader=FailingLoader(FileNotFoundError("docs")),
        embeddings=FakeEmbeddings(),
        vectors=FakeVectorStore(),
    )

    response = client.post(
        "/ai/reindex", headers=auth_headers(roles=("admin",))
    )

    assert response.status_code == 500
    assert response.json()["code"] == "documentation_unavailable"


def test_metrics_aggregate_the_invocations_for_admins(
    client: TestClient, auth_headers: AuthHeaders
) -> None:
    _ask(client, auth_headers())

    response = client.get("/ai/metrics", headers=auth_headers(roles=("admin",)))

    assert response.status_code == 200
    body = response.json()
    assert body["invocations"] == 1
    assert body["by_outcome"] == {"answered": 1}
    assert body["input_tokens"] == 27
    assert body["cost_usd"] > 0
    assert client.get("/ai/metrics", headers=auth_headers()).status_code == 403
