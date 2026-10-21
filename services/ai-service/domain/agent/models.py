"""Agent request/answer models shared by the application use cases."""

from __future__ import annotations

from dataclasses import dataclass

NO_CONTEXT_ANSWER = (
    "No tengo información suficiente en la documentación disponible para "
    "responder esa consulta. Reformula la pregunta o consulta con el equipo "
    "responsable del sistema."
)


@dataclass(frozen=True, slots=True)
class Message:
    """One turn of the optional short conversation history."""

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class AgentQuestion:
    question: str
    history: tuple[Message, ...] = ()
    top_k: int = 0
    document: str | None = None
    include_system_data: bool = False


@dataclass(frozen=True, slots=True)
class Source:
    """Document fragment cited in an answer."""

    document: str
    section: str
    score: float


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Fragment returned by the vector store before prompting the LLM."""

    chunk_id: str
    document: str
    section: str
    text: str
    score: float


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class Latency:
    total_ms: float = 0.0
    embedding_ms: float = 0.0
    retrieval_ms: float = 0.0
    llm_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class QualityReport:
    passed: bool
    issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentAnswer:
    answer: str
    sources: tuple[Source, ...]
    usage: Usage
    latency: Latency
    model: str
    prompt_version: str
    quality: QualityReport
