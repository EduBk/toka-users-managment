"""Per-invocation metrics port (latency, tokens and cost)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class InvocationRecord:
    user: str
    timestamp: float
    outcome: str
    latency_total_ms: float
    latency_embedding_ms: float
    latency_retrieval_ms: float
    latency_llm_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    sources: int


@dataclass(frozen=True, slots=True)
class MetricsSummary:
    invocations: int
    window_size: int
    avg_latency_ms: float
    p95_latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    by_outcome: dict[str, int]


class MetricsStore(Protocol):
    async def record(self, record: InvocationRecord) -> None: ...

    async def summary(self) -> MetricsSummary: ...
