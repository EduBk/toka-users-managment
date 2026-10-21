"""In-memory doubles for the agent ports."""

from __future__ import annotations

from collections.abc import Sequence

from application.exceptions import AiUnavailable
from application.ports.documents import DocumentSource
from application.ports.embeddings import EmbeddingBatch
from application.ports.llm import LlmCompletion
from application.ports.metrics import InvocationRecord, MetricsSummary
from application.ports.vector_store import EmbeddedChunk
from domain.agent.models import RetrievedChunk
from domain.agent.prompt import FewShot, PromptBundle


class FakeEmbeddings:
    model = "fake-embedding"

    def __init__(self, *, tokens: int = 7, dimension: int = 2) -> None:
        self.tokens = tokens
        self.dimension = dimension
        self.calls: list[tuple[str, ...]] = []
        self.fail_with: Exception | None = None

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        self.calls.append(tuple(texts))
        if self.fail_with is not None:
            raise self.fail_with
        return EmbeddingBatch(
            vectors=tuple(
                tuple(float(index + 1) for index in range(self.dimension))
                for _ in texts
            ),
            input_tokens=self.tokens * len(texts),
        )


class FakeVectorStore:
    def __init__(
        self,
        *,
        results: tuple[RetrievedChunk, ...] = (),
        hashes: dict[str, str] | None = None,
    ) -> None:
        self.results = results
        self.hashes = dict(hashes or {})
        self.upserted: list[EmbeddedChunk] = []
        self.deleted: list[str] = []
        self.dimensions: list[int] = []
        self.searches: list[dict[str, object]] = []
        self.ping_result = True
        self.fail_with: Exception | None = None

    async def ensure_collection(self, dimension: int) -> None:
        self.dimensions.append(dimension)

    async def upsert(self, chunks: Sequence[EmbeddedChunk]) -> None:
        self.upserted.extend(chunks)
        for chunk in chunks:
            self.hashes[chunk.document] = chunk.doc_hash

    async def search(
        self,
        vector: Sequence[float],
        *,
        limit: int,
        document: str | None = None,
    ) -> tuple[RetrievedChunk, ...]:
        self.searches.append(
            {"vector": tuple(vector), "limit": limit, "document": document}
        )
        if self.fail_with is not None:
            raise self.fail_with
        return self.results

    async def document_hashes(self) -> dict[str, str]:
        return dict(self.hashes)

    async def delete_document(self, document: str) -> None:
        self.deleted.append(document)
        self.hashes.pop(document, None)

    async def ping(self) -> bool:
        return self.ping_result


class FakeLlm:
    model = "fake-chat"

    def __init__(
        self,
        *,
        text: str = "Respuesta con cita [1].",
        input_tokens: int = 20,
        output_tokens: int = 8,
        error: Exception | None = None,
    ) -> None:
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 800,
        session_id: str | None = None,
    ) -> LlmCompletion:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "session_id": session_id,
            }
        )
        if self.error is not None:
            raise self.error
        return LlmCompletion(
            text=self.text,
            model=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


class FakeMetrics:
    def __init__(self) -> None:
        self.records: list[InvocationRecord] = []

    async def record(self, record: InvocationRecord) -> None:
        self.records.append(record)

    async def summary(self) -> MetricsSummary:
        return MetricsSummary(
            invocations=len(self.records),
            window_size=200,
            avg_latency_ms=0.0,
            p95_latency_ms=0.0,
            input_tokens=sum(record.input_tokens for record in self.records),
            output_tokens=sum(record.output_tokens for record in self.records),
            cost_usd=round(sum(record.cost_usd for record in self.records), 8),
            by_outcome={},
        )


class FakePrompts:
    def __init__(self) -> None:
        self.bundle = PromptBundle(
            version="v-test",
            system="Eres el asistente del sistema.",
            user_template=(
                "Historial:\n{{history}}\n\nContexto:\n{{context}}\n\n"
                "Pregunta:\n{{question}}"
            ),
            few_shots=(
                FewShot(question="¿Usuarios?", answer="Usa [1]."),
            ),
        )

    def current(self) -> PromptBundle:
        return self.bundle


class FakeDirectory:
    def __init__(self, description: str | None = "user-service: 3 usuarios") -> None:
        self.description = description
        self.tokens: list[str] = []
        self.error: Exception | None = None

    async def describe(self, bearer_token: str) -> str | None:
        self.tokens.append(bearer_token)
        if self.error is not None:
            raise self.error
        return self.description


class FakeLoader:
    def __init__(self, *documents: DocumentSource) -> None:
        self.documents = documents
        self.calls = 0

    async def load(self) -> tuple[DocumentSource, ...]:
        self.calls += 1
        return self.documents


class FailingLoader:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def load(self) -> tuple[DocumentSource, ...]:
        raise self.error


class FailingEmbeddings:
    model = "fake-embedding"

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        self.calls += 1
        raise self.error


__all__ = [
    "AiUnavailable",
    "FailingEmbeddings",
    "FailingLoader",
    "FakeDirectory",
    "FakeEmbeddings",
    "FakeLlm",
    "FakeLoader",
    "FakeMetrics",
    "FakePrompts",
    "FakeVectorStore",
]
