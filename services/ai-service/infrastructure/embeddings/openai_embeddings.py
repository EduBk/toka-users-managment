"""OpenAI embeddings adapter with retries and error mapping."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence

import openai
from openai import AsyncOpenAI

from application.exceptions import AiRateLimited, AiUnavailable
from application.ports.embeddings import EmbeddingBatch
from infrastructure.llm.openai_client import USER_AGENT
from infrastructure.openai_retry import (
    is_retryable,
    retry_after_seconds,
    translate_error,
)
from infrastructure.retry import RetryPolicy, retry_async


class OpenAIEmbeddings:
    """``EmbeddingClient`` over the official SDK.

    Callers batch their texts (the reindex pipeline) so one HTTP request covers
    up to 64 chunks.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout_seconds: float = 60.0,
        policy: RetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.model = model
        self._policy = policy or RetryPolicy()
        self._sleep = sleep
        self._client = (
            AsyncOpenAI(
                api_key=api_key,
                base_url=base_url or None,
                timeout=timeout_seconds,
                max_retries=0,
                default_headers={"User-Agent": USER_AGENT},
            )
            if api_key
            else None
        )

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch(vectors=(), input_tokens=0)
        if self._client is None:
            raise AiUnavailable("OpenAI API key is not configured")
        try:
            response = await retry_async(
                lambda: self._client.embeddings.create(
                    model=self.model, input=list(texts)
                ),
                policy=self._policy,
                is_retryable=is_retryable,
                retry_after=retry_after_seconds,
                sleep=self._sleep,
            )
        except openai.RateLimitError as exc:
            raise AiRateLimited(
                "the embeddings provider rate limit was exceeded",
                retry_after_seconds=retry_after_seconds(exc) or 30,
            ) from exc
        except openai.OpenAIError as exc:
            raise translate_error(exc, provider="the embeddings provider") from exc

        data = sorted(response.data, key=lambda item: item.index)
        vectors = tuple(tuple(float(value) for value in item.embedding) for item in data)
        if len(vectors) != len(texts):
            raise AiUnavailable("the embeddings provider returned an incomplete batch")
        usage = getattr(response, "usage", None)
        return EmbeddingBatch(
            vectors=vectors,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        )
