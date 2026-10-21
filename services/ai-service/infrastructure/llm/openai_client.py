"""OpenAI-compatible chat completions adapter with retries and error mapping."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import openai
from openai import AsyncOpenAI

from application.exceptions import AiRateLimited, AiUnavailable
from application.ports.llm import LlmCompletion
from infrastructure.openai_retry import (
    is_retryable,
    retry_after_seconds,
    translate_error,
)
from infrastructure.retry import RetryPolicy, retry_async

USER_AGENT = "user-management-ai-service/0.1.0"


class OpenAICompleter:
    """``LlmClient`` over the official SDK; retries 429/timeouts/5xx.

    Works with OpenAI and with OpenAI-compatible gateways (OpenCode Go, ...),
    which receive a stable session id per user for routing and prompt caching.
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

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        session_id: str | None = None,
    ) -> LlmCompletion:
        if self._client is None:
            raise AiUnavailable("OpenAI API key is not configured")
        extra_headers = (
            {"x-opencode-session": session_id} if session_id else None
        )
        try:
            response = await retry_async(
                lambda: self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra_headers=extra_headers,
                ),
                policy=self._policy,
                is_retryable=is_retryable,
                retry_after=retry_after_seconds,
                sleep=self._sleep,
            )
        except openai.RateLimitError as exc:
            raise AiRateLimited(
                "the AI provider rate limit was exceeded",
                retry_after_seconds=retry_after_seconds(exc) or 30,
            ) from exc
        except openai.OpenAIError as exc:
            raise translate_error(exc, provider="the AI provider") from exc

        choices = getattr(response, "choices", None) or []
        content = choices[0].message.content if choices else None
        if not content:
            raise AiUnavailable("the AI provider returned an empty answer")
        usage = getattr(response, "usage", None)
        return LlmCompletion(
            text=content,
            model=getattr(response, "model", self.model),
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )
