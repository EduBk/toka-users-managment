"""Chat completion port (implemented with the OpenAI SDK)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LlmCompletion:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


class LlmClient(Protocol):
    model: str

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 800,
        session_id: str | None = None,
    ) -> LlmCompletion: ...
