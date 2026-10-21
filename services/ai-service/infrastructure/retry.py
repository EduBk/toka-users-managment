"""Provider calls with bounded exponential backoff (E5.1, E5.5)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")
MAX_BACKOFF_SECONDS = 8.0


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 3
    backoff_seconds: float = 0.5
    max_backoff_seconds: float = MAX_BACKOFF_SECONDS

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("attempts must be >= 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be >= 0")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy,
    is_retryable: Callable[[Exception], bool],
    retry_after: Callable[[Exception], int | None] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Run ``operation`` again on retryable failures, then re-raise the last one."""

    for attempt in range(1, policy.attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            if attempt >= policy.attempts or not is_retryable(exc):
                raise
            delay = min(
                policy.backoff_seconds * (2 ** (attempt - 1)),
                policy.max_backoff_seconds,
            )
            if retry_after is not None:
                informed = retry_after(exc)
                if informed is not None:
                    delay = max(delay, float(informed))
            await sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
