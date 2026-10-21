"""Offline evaluation suite for the RAG agent (E5.5).

Runs the real pipeline (chunking, retrieval, prompt rendering, answer quality
validation, latency and cost metrics) against a deterministic stub provider, so
results are reproducible without an OpenAI key or network access. The stub
answers by quoting the retrieved fragment, which makes citation and
"no context" behaviour easy to assert in CI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

from application.ports.documents import DocumentSource
from application.ports.embeddings import EmbeddingBatch
from application.ports.llm import LlmCompletion
from application.ports.vector_store import EmbeddedChunk
from application.use_cases.ask_agent import AskAgent
from application.use_cases.reindex_documents import ReindexDocuments
from domain.agent.models import AgentQuestion, RetrievedChunk
from domain.agent.pricing import TokenPrice
from domain.agent.quality import admits_missing_context, contains_pii, redact_pii
from infrastructure.documents.filesystem import MarkdownDocumentLoader
from infrastructure.metrics.memory_store import InMemoryMetricsStore
from infrastructure.prompts.filesystem import FilePromptProvider

SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DOCS = REPO_ROOT / "docs"
DEFAULT_DATASET = Path(__file__).with_name("dataset.json")
DEFAULT_PROMPTS = SERVICE_ROOT / "prompts"

_STOPWORDS = frozenset(
    """
    de la el los las un una unos unas y o que en con por para del al se es son
    como cómo cual cuáles qué quien quién donde cuándo cuanto cuánto hay
    the of and or to in on for is are was what how which who
    """.split()
)


def _tokens(text: str) -> list[str]:
    normalized = "".join(
        char
        for char in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(char)
    )
    return [
        token
        for token in re.findall(r"\w+", normalized)
        if token not in _STOPWORDS
    ]


class StubEmbeddings:
    """Int8 bag-of-words over the corpus vocabulary.

    Tokens outside the corpus produce a zero vector, so an out-of-scope
    question cannot retrieve noise: that is what makes the "no context" case
    reproducible.
    """

    model = "stub-embedding"

    def __init__(self, vocabulary: Sequence[str]) -> None:
        self._index = {
            token: position
            for position, token in enumerate(sorted(set(vocabulary)))
        }
        self._dimension = max(len(self._index), 1)

    def _vector(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self._dimension
        for token in _tokens(text):
            position = self._index.get(token)
            if position is not None:
                vector[position] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return tuple(vector)
        return tuple(value / norm for value in vector)

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            vectors=tuple(self._vector(text) for text in texts),
            input_tokens=sum(len(_tokens(text)) for text in texts),
        )


def _corpus_vocabulary(docs_path: Path) -> set[str]:
    vocabulary: set[str] = set()
    for path in docs_path.rglob("*.md"):
        vocabulary.update(_tokens(path.read_text(encoding="utf-8")))
    return vocabulary


class InMemoryVectorStore:
    """Cosine-similarity store with the same contract as the Qdrant adapter."""

    def __init__(self) -> None:
        self._points: dict[str, EmbeddedChunk] = {}

    async def ensure_collection(self, dimension: int) -> None:
        if dimension < 1:
            raise ValueError("unexpected embedding dimension")

    async def upsert(self, chunks: Sequence[EmbeddedChunk]) -> None:
        for chunk in chunks:
            self._points[chunk.chunk_id] = chunk

    async def search(
        self,
        vector: Sequence[float],
        *,
        limit: int,
        document: str | None = None,
    ) -> tuple[RetrievedChunk, ...]:
        scored: list[RetrievedChunk] = []
        for chunk in self._points.values():
            if document is not None and chunk.document != document:
                continue
            score = sum(a * b for a, b in zip(vector, chunk.vector, strict=True))
            if score > 0.05:
                scored.append(
                    RetrievedChunk(
                        chunk_id=chunk.chunk_id,
                        document=chunk.document,
                        section=chunk.section,
                        text=chunk.text,
                        score=round(score, 4),
                    )
                )
        scored.sort(key=lambda chunk: chunk.score, reverse=True)
        return tuple(scored[:limit])

    async def document_hashes(self) -> dict[str, str]:
        return {chunk.document: chunk.doc_hash for chunk in self._points.values()}

    async def delete_document(self, document: str) -> None:
        self._points = {
            key: chunk
            for key, chunk in self._points.items()
            if chunk.document != document
        }

    async def ping(self) -> bool:
        return True


class DeterministicLlm:
    """Quotes the first retrieved fragment; never invents content."""

    model = "stub-llm"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 800,
        session_id: str | None = None,
    ) -> LlmCompletion:
        self.prompts.append(user)
        fragment = re.search(r"\[1\] ([^\n]+)\n(.+?)(?:\n\n|\Z)", user, re.S)
        if fragment is None:
            text = (
                "No tengo información suficiente en la documentación disponible "
                "para responder esa consulta."
            )
        else:
            snippet = " ".join(fragment.group(2).split())[:200]
            text = f"Según la documentación ({fragment.group(1)}): {snippet} [1]"
        return LlmCompletion(
            text=redact_pii(text),
            model=self.model,
            input_tokens=max(len(system + user) // 4, 1),
            output_tokens=max(len(text) // 4, 1),
        )


@dataclass
class CaseResult:
    case_id: str
    question: str
    passed: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    sources: list[str]
    quality_issues: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    cases: list[CaseResult]
    passed: int
    failed: int
    avg_latency_ms: float
    p95_latency_ms: float
    total_tokens: int
    total_cost_usd: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _evaluate_case(case: dict, answer, latency_ms: float) -> CaseResult:
    expect = case.get("expect", {})
    failures: list[str] = []
    if len(answer.sources) < int(expect.get("sources_min", 0)):
        failures.append("sources_min")
    if expect.get("no_context") and not admits_missing_context(answer.answer):
        failures.append("no_context")
    if expect.get("quality") and not answer.quality.passed:
        failures.append("quality")
    if expect.get("no_pii") and contains_pii(answer.answer):
        failures.append("pii")
    if "max_latency_ms" in expect and latency_ms > float(expect["max_latency_ms"]):
        failures.append("latency")
    if "must_include" in expect and expect["must_include"] not in answer.answer:
        failures.append("must_include")
    return CaseResult(
        case_id=str(case["id"]),
        question=str(case["question"]),
        passed=not failures,
        latency_ms=latency_ms,
        input_tokens=answer.usage.input_tokens,
        output_tokens=answer.usage.output_tokens,
        cost_usd=answer.usage.cost_usd,
        sources=[source.document for source in answer.sources],
        quality_issues=list(answer.quality.issues),
        failures=failures,
    )


async def run_evaluation(
    *,
    docs_path: Path = DEFAULT_DOCS,
    dataset_path: Path = DEFAULT_DATASET,
    prompts_path: Path = DEFAULT_PROMPTS,
) -> EvaluationReport:
    embeddings = StubEmbeddings(_corpus_vocabulary(docs_path))
    vectors = InMemoryVectorStore()
    metrics = InMemoryMetricsStore()
    prices = {
        "chat_price": TokenPrice(
            input_per_million=0.15, output_per_million=0.60
        ),
        "embedding_price": TokenPrice(input_per_million=0.02),
    }

    indexed = await ReindexDocuments(
        loader=MarkdownDocumentLoader(docs_path),
        embeddings=embeddings,
        vectors=vectors,
        max_chars=600,
        overlap=80,
    ).execute()
    if indexed.documents_indexed == 0:
        raise SystemExit(f"no documents found in {docs_path}")

    agent = AskAgent(
        prompts=FilePromptProvider(prompts_path),
        embeddings=embeddings,
        vectors=vectors,
        llm=DeterministicLlm(),
        metrics=metrics,
        **prices,
    )
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    results: list[CaseResult] = []
    for case in cases:
        answer = await agent.execute(
            AgentQuestion(question=str(case["question"])), user="eval"
        )
        results.append(_evaluate_case(case, answer, answer.latency.total_ms))

    summary = await metrics.summary()
    return EvaluationReport(
        cases=results,
        passed=sum(result.passed for result in results),
        failed=sum(not result.passed for result in results),
        avg_latency_ms=summary.avg_latency_ms,
        p95_latency_ms=summary.p95_latency_ms,
        total_tokens=summary.input_tokens + summary.output_tokens,
        total_cost_usd=summary.cost_usd,
    )


def _print_report(report: EvaluationReport) -> None:
    print("id                          result  latency_ms  tokens   cost_usd  failures")
    for case in report.cases:
        print(
            f"{case.case_id:<27} {'PASS' if case.passed else 'FAIL':<7} "
            f"{case.latency_ms:>10.2f}  {case.input_tokens + case.output_tokens:>6}  "
            f"{case.cost_usd:>8.6f}  {', '.join(case.failures) or '-'}"
        )
    print(
        f"\ncases={len(report.cases)} passed={report.passed} failed={report.failed} "
        f"avg_latency_ms={report.avg_latency_ms} p95_latency_ms={report.p95_latency_ms} "
        f"tokens={report.total_tokens} cost_usd={report.total_cost_usd:.6f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--json", action="store_true", help="print the JSON report")
    args = parser.parse_args(argv)

    report = asyncio.run(
        run_evaluation(docs_path=args.docs, dataset_path=args.dataset)
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_report(report)
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
