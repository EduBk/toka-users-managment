"""Vector store port (implemented with Qdrant)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from domain.agent.models import RetrievedChunk


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    chunk_id: str
    document: str
    section: str
    text: str
    vector: tuple[float, ...]
    doc_hash: str
    chunk_index: int
    updated_at: str


class VectorStore(Protocol):
    async def ensure_collection(self, dimension: int) -> None: ...

    async def upsert(self, chunks: Sequence[EmbeddedChunk]) -> None: ...

    async def search(
        self,
        vector: Sequence[float],
        *,
        limit: int,
        document: str | None = None,
    ) -> tuple[RetrievedChunk, ...]: ...

    async def document_hashes(self) -> dict[str, str]: ...

    async def delete_document(self, document: str) -> None: ...

    async def ping(self) -> bool: ...
