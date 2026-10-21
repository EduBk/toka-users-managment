"""Text embedding port (implemented with the OpenAI SDK)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    input_tokens: int = 0


class EmbeddingClient(Protocol):
    model: str

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch: ...
