from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from api.errors import register_ai_exception_handlers
from api.router import router
from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.jwt_auth import JwtValidator
from app_common.testing import (
    TEST_AUDIENCE,
    TEST_ISSUER,
    bearer,
    generate_rsa_key_pair,
    issue_access_token,
)
from application.ports.documents import DocumentSource
from application.use_cases.ask_agent import AskAgent
from application.use_cases.reindex_documents import ReindexDocuments
from domain.agent.models import RetrievedChunk
from domain.agent.pricing import TokenPrice
from infrastructure.metrics.memory_store import InMemoryMetricsStore
from tests.application.fakes import (
    FakeDirectory,
    FakeEmbeddings,
    FakeLlm,
    FakeLoader,
    FakePrompts,
    FakeVectorStore,
)

AuthHeaders = Callable[..., dict[str, str]]

CHUNK = RetrievedChunk(
    chunk_id="c1",
    document="arquitectura/flujos-de-datos.md",
    section="Validación de tokens",
    text="Cada servicio valida el JWT con el JWKS del auth-service.",
    score=0.9,
)


@pytest.fixture(scope="session")
def key_pair() -> tuple[str, str]:
    return generate_rsa_key_pair()


@pytest.fixture
def auth_headers(key_pair: tuple[str, str]) -> AuthHeaders:
    def build(
        *, roles: tuple[str, ...] = (), scopes: tuple[str, ...] = ("ai:use",)
    ) -> dict[str, str]:
        return bearer(issue_access_token(key_pair[0], roles=roles, scopes=scopes))

    return build


@pytest.fixture
def llm() -> FakeLlm:
    return FakeLlm()


@pytest.fixture
def vectors() -> FakeVectorStore:
    return FakeVectorStore(results=(CHUNK,))


@pytest.fixture
def directory() -> FakeDirectory:
    return FakeDirectory()


@pytest.fixture
def metrics() -> InMemoryMetricsStore:
    return InMemoryMetricsStore()


@pytest.fixture
def client(
    key_pair: tuple[str, str],
    llm: FakeLlm,
    vectors: FakeVectorStore,
    directory: FakeDirectory,
    metrics: InMemoryMetricsStore,
) -> Iterator[TestClient]:
    app = create_service_app(
        BaseServiceSettings(service_name="ai-service"), routers=[router]
    )
    register_ai_exception_handlers(app)
    app.state.jwt_validator = JwtValidator(
        issuer=TEST_ISSUER, audience=TEST_AUDIENCE, public_key=key_pair[1]
    )
    app.state.vector_store = vectors
    app.state.metrics = metrics
    app.state.ask_agent = AskAgent(
        prompts=FakePrompts(),
        embeddings=FakeEmbeddings(tokens=7),
        vectors=vectors,
        llm=llm,
        metrics=metrics,
        chat_price=TokenPrice(input_per_million=0.15, output_per_million=0.60),
        embedding_price=TokenPrice(input_per_million=0.02),
        directory=directory,
    )
    app.state.reindex_documents = ReindexDocuments(
        loader=FakeLoader(
            DocumentSource(
                document="auth.md", text="# Auth\n\ntokens", updated_at="2026-10-20"
            )
        ),
        embeddings=FakeEmbeddings(tokens=3),
        vectors=vectors,
    )
    app.state.rate_limit_ai = None
    app.state.ai_info = {
        "service": "ai-service",
        "version": "0.1.0",
        "environment": "test",
        "llm_model": "fake-chat",
        "llm": "configured",
        "embeddings": "fastembed:fake-model",
        "prompt_version": "v-test",
    }
    with TestClient(app) as test_client:
        yield test_client
