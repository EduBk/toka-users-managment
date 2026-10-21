"""Answer a question with RAG: retrieve context, prompt the LLM, report usage."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from app_common.logging import get_trace_id, log_event
from application.exceptions import AiRateLimited, AiUnavailable
from application.ports.directory import SystemDataProvider
from application.ports.embeddings import EmbeddingClient
from application.ports.llm import LlmClient
from application.ports.metrics import InvocationRecord, MetricsStore
from application.ports.prompts import PromptProvider
from application.ports.vector_store import VectorStore
from domain.agent.models import (
    NO_CONTEXT_ANSWER,
    AgentAnswer,
    AgentQuestion,
    Latency,
    Source,
    Usage,
)
from domain.agent.pricing import TokenPrice
from domain.agent.prompt import (
    MAX_HISTORY_CHARS,
    build_user_prompt,
    render_context,
    render_history,
    sanitize_question,
)
from domain.agent.quality import redact_pii, validate_answer

logger = logging.getLogger("ai_service.agent")


def _elapsed_ms(started: float, finished: float) -> float:
    return round((finished - started) * 1000, 2)


class AskAgent:
    """RAG use case shared by the HTTP adapter and the evaluation suite."""

    def __init__(
        self,
        *,
        prompts: PromptProvider,
        embeddings: EmbeddingClient,
        vectors: VectorStore,
        llm: LlmClient,
        metrics: MetricsStore,
        chat_price: TokenPrice,
        embedding_price: TokenPrice,
        top_k: int = 4,
        max_question_chars: int = 2000,
        max_answer_tokens: int = 800,
        temperature: float = 0.2,
        directory: SystemDataProvider | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._prompts = prompts
        self._embeddings = embeddings
        self._vectors = vectors
        self._llm = llm
        self._metrics = metrics
        self._chat_price = chat_price
        self._embedding_price = embedding_price
        self._top_k = top_k
        self._max_question_chars = max_question_chars
        self._max_answer_tokens = max_answer_tokens
        self._temperature = temperature
        self._directory = directory
        self._clock = clock

    async def execute(
        self,
        question: AgentQuestion,
        *,
        user: str,
        bearer_token: str | None = None,
    ) -> AgentAnswer:
        bundle = self._prompts.current()
        sanitized = sanitize_question(
            question.question, max_chars=self._max_question_chars
        )
        if sanitized.injection_suspected:
            log_event(
                logger,
                logging.WARNING,
                "prompt_injection_suspected",
                user=user,
                correlation_id=get_trace_id(),
            )

        started = self._clock()
        embedding_started = started
        batch = await self._embeddings.embed((sanitized.text,))
        embedding_finished = self._clock()
        embedding_ms = _elapsed_ms(embedding_started, embedding_finished)
        embedding_cost = self._embedding_price.cost(
            input_tokens=batch.input_tokens, output_tokens=0
        )

        retrieval_started = embedding_finished
        chunks = await self._vectors.search(
            batch.vectors[0],
            limit=question.top_k or self._top_k,
            document=question.document,
        )
        retrieval_finished = self._clock()
        retrieval_ms = _elapsed_ms(retrieval_started, retrieval_finished)

        system_data = await self._load_system_data(question, bearer_token)
        sources = tuple(
            Source(document=chunk.document, section=chunk.section, score=chunk.score)
            for chunk in chunks
        )
        if system_data:
            sources = (
                *sources,
                Source(
                    document="user-service",
                    section="datos del sistema",
                    score=1.0,
                ),
            )

        if not chunks and not system_data:
            return await self._answer_without_context(
                embedding_tokens=batch.input_tokens,
                embedding_cost=embedding_cost,
                latency=Latency(
                    total_ms=_elapsed_ms(started, retrieval_finished),
                    embedding_ms=embedding_ms,
                    retrieval_ms=retrieval_ms,
                ),
                model=self._llm.model,
                prompt_version=bundle.version,
                user=user,
            )

        context = render_context(chunks)
        if system_data:
            context = f"{context}\n\n[datos del sistema]\n{system_data}".strip()
        user_prompt = build_user_prompt(
            bundle,
            context=context,
            question=sanitized.text,
            history=render_history(question.history, max_chars=MAX_HISTORY_CHARS),
        )

        llm_started = self._clock()
        try:
            completion = await self._llm.complete(
                system=bundle.render_system(),
                user=user_prompt,
                temperature=self._temperature,
                max_tokens=self._max_answer_tokens,
                session_id=user,
            )
        except (AiUnavailable, AiRateLimited) as exc:
            await self._record(
                user=user,
                outcome="error",
                latency=Latency(
                    total_ms=_elapsed_ms(started, self._clock()),
                    embedding_ms=embedding_ms,
                    retrieval_ms=retrieval_ms,
                    llm_ms=_elapsed_ms(llm_started, self._clock()),
                ),
                input_tokens=batch.input_tokens,
                output_tokens=0,
                cost_usd=embedding_cost,
                sources=len(sources),
            )
            log_event(
                logger,
                logging.ERROR,
                "ai_answer_failed",
                user=user,
                error=type(exc).__name__,
                correlation_id=get_trace_id(),
            )
            raise
        finished = self._clock()

        usage = Usage(
            input_tokens=batch.input_tokens + completion.input_tokens,
            output_tokens=completion.output_tokens,
            cost_usd=round(
                embedding_cost
                + self._chat_price.cost(
                    input_tokens=completion.input_tokens,
                    output_tokens=completion.output_tokens,
                ),
                8,
            ),
        )
        latency = Latency(
            total_ms=_elapsed_ms(started, finished),
            embedding_ms=embedding_ms,
            retrieval_ms=retrieval_ms,
            llm_ms=_elapsed_ms(llm_started, finished),
        )
        quality = validate_answer(completion.text, has_sources=bool(sources))
        answer_text = completion.text.strip()
        if "pii_in_answer" in quality.issues:
            answer_text = redact_pii(answer_text)
        await self._record(
            user=user,
            outcome="answered",
            latency=latency,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
            sources=len(sources),
        )
        log_event(
            logger,
            logging.INFO,
            "ai_answer",
            user=user,
            correlation_id=get_trace_id(),
            latency_ms=latency.total_ms,
            latency_embedding_ms=latency.embedding_ms,
            latency_retrieval_ms=latency.retrieval_ms,
            latency_llm_ms=latency.llm_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
            sources=len(sources),
            quality_passed=quality.passed,
            quality_issues=list(quality.issues),
            model=completion.model,
            prompt_version=bundle.version,
            question=redact_pii(sanitized.text)[:160],
        )
        return AgentAnswer(
            answer=answer_text,
            sources=sources,
            usage=usage,
            latency=latency,
            model=completion.model,
            prompt_version=bundle.version,
            quality=quality,
        )

    async def _load_system_data(
        self, question: AgentQuestion, bearer_token: str | None
    ) -> str | None:
        if not question.include_system_data or not bearer_token or self._directory is None:
            return None
        try:
            return await self._directory.describe(bearer_token)
        except Exception as exc:  # system data is optional context
            log_event(
                logger,
                logging.WARNING,
                "system_data_unavailable",
                error=type(exc).__name__,
            )
            return None

    async def _answer_without_context(
        self,
        *,
        embedding_tokens: int,
        embedding_cost: float,
        latency: Latency,
        model: str,
        prompt_version: str,
        user: str,
    ) -> AgentAnswer:
        answer = AgentAnswer(
            answer=NO_CONTEXT_ANSWER,
            sources=(),
            usage=Usage(
                input_tokens=embedding_tokens, cost_usd=embedding_cost
            ),
            latency=latency,
            model=model,
            prompt_version=prompt_version,
            quality=validate_answer(NO_CONTEXT_ANSWER, has_sources=False),
        )
        await self._record(
            user=user,
            outcome="no_context",
            latency=latency,
            input_tokens=embedding_tokens,
            output_tokens=0,
            cost_usd=embedding_cost,
            sources=0,
        )
        log_event(
            logger,
            logging.INFO,
            "ai_no_context",
            user=user,
            correlation_id=get_trace_id(),
            latency_ms=latency.total_ms,
            input_tokens=embedding_tokens,
            cost_usd=embedding_cost,
        )
        return answer

    async def _record(
        self,
        *,
        user: str,
        outcome: str,
        latency: Latency,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        sources: int,
    ) -> None:
        await self._metrics.record(
            InvocationRecord(
                user=user,
                timestamp=time.time(),
                outcome=outcome,
                latency_total_ms=latency.total_ms,
                latency_embedding_ms=latency.embedding_ms,
                latency_retrieval_ms=latency.retrieval_ms,
                latency_llm_ms=latency.llm_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                sources=sources,
            )
        )
