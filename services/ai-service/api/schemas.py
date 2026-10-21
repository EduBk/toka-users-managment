"""Request and response schemas (Pydantic at the system boundary)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from domain.agent.models import AgentAnswer


class HistoryMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[HistoryMessageRequest] = Field(default_factory=list, max_length=6)
    top_k: int | None = Field(default=None, ge=1, le=20)
    document: str | None = Field(default=None, min_length=1, max_length=200)
    include_system_data: bool = False


class SourceResponse(BaseModel):
    document: str
    section: str
    score: float


class UsageResponse(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float


class LatencyResponse(BaseModel):
    total_ms: float
    embedding_ms: float
    retrieval_ms: float
    llm_ms: float


class QualityResponse(BaseModel):
    passed: bool
    issues: list[str]


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    usage: UsageResponse
    latency: LatencyResponse
    model: str
    prompt_version: str
    quality: QualityResponse

    @classmethod
    def from_domain(cls, answer: AgentAnswer) -> "AskResponse":
        return cls(
            answer=answer.answer,
            sources=[
                SourceResponse(
                    document=source.document,
                    section=source.section,
                    score=source.score,
                )
                for source in answer.sources
            ],
            usage=UsageResponse(
                input_tokens=answer.usage.input_tokens,
                output_tokens=answer.usage.output_tokens,
                total_tokens=answer.usage.total_tokens,
                cost_usd=answer.usage.cost_usd,
            ),
            latency=LatencyResponse(
                total_ms=answer.latency.total_ms,
                embedding_ms=answer.latency.embedding_ms,
                retrieval_ms=answer.latency.retrieval_ms,
                llm_ms=answer.latency.llm_ms,
            ),
            model=answer.model,
            prompt_version=answer.prompt_version,
            quality=QualityResponse(
                passed=answer.quality.passed, issues=list(answer.quality.issues)
            ),
        )


class AiHealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    vector_store: str
    llm: str
    llm_model: str
    embeddings: str
    prompt_version: str


class ReindexResponse(BaseModel):
    documents_seen: int
    documents_indexed: int
    documents_skipped: int
    documents_deleted: int
    chunks_indexed: int
    embedding_tokens: int


class MetricsResponse(BaseModel):
    invocations: int
    window_size: int
    avg_latency_ms: float
    p95_latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    by_outcome: dict[str, int]
