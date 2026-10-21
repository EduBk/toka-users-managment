"""Index the documentation corpus: chunk, embed and upsert idempotently (E5.2)."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from app_common.logging import log_event
from application.ports.documents import DocumentLoader
from application.ports.embeddings import EmbeddingClient
from application.ports.vector_store import EmbeddedChunk, VectorStore
from domain.agent.chunking import Chunk, chunk_document

logger = logging.getLogger("ai_service.reindex")


@dataclass(frozen=True, slots=True)
class ReindexReport:
    documents_seen: int
    documents_indexed: int
    documents_skipped: int
    documents_deleted: int
    chunks_indexed: int
    embedding_tokens: int


def _batches(items: tuple[Chunk, ...], size: int) -> list[tuple[Chunk, ...]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def document_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ReindexDocuments:
    def __init__(
        self,
        *,
        loader: DocumentLoader,
        embeddings: EmbeddingClient,
        vectors: VectorStore,
        max_chars: int = 800,
        overlap: int = 100,
        batch_size: int = 64,
    ) -> None:
        self._loader = loader
        self._embeddings = embeddings
        self._vectors = vectors
        self._max_chars = max_chars
        self._overlap = overlap
        self._batch_size = batch_size

    async def execute(self) -> ReindexReport:
        sources = await self._loader.load()
        existing = await self._vectors.document_hashes()

        documents_indexed = documents_skipped = documents_deleted = 0
        chunks_indexed = embedding_tokens = 0
        collection_ready = False

        current = {source.document for source in sources}
        for stale in sorted(existing.keys() - current):
            await self._vectors.delete_document(stale)
            documents_deleted += 1

        for source in sources:
            digest = document_hash(source.text)
            if existing.get(source.document) == digest:
                documents_skipped += 1
                continue
            if source.document in existing:
                await self._vectors.delete_document(source.document)
                documents_deleted += 1

            chunks = chunk_document(
                source.text, max_chars=self._max_chars, overlap=self._overlap
            )
            embedded: list[EmbeddedChunk] = []
            for batch in _batches(chunks, self._batch_size):
                result = await self._embeddings.embed(
                    tuple(chunk.text for chunk in batch)
                )
                embedding_tokens += result.input_tokens
                if result.vectors and not collection_ready:
                    await self._vectors.ensure_collection(len(result.vectors[0]))
                    collection_ready = True
                embedded.extend(
                    EmbeddedChunk(
                        chunk_id=str(
                            uuid5(
                                NAMESPACE_URL,
                                f"{digest}:{source.document}:{chunk.index}",
                            )
                        ),
                        document=source.document,
                        section=chunk.section,
                        text=chunk.text,
                        vector=vector,
                        doc_hash=digest,
                        chunk_index=chunk.index,
                        updated_at=source.updated_at,
                    )
                    for chunk, vector in zip(batch, result.vectors, strict=True)
                )
            if embedded:
                await self._vectors.upsert(embedded)
            documents_indexed += 1
            chunks_indexed += len(embedded)

        report = ReindexReport(
            documents_seen=len(sources),
            documents_indexed=documents_indexed,
            documents_skipped=documents_skipped,
            documents_deleted=documents_deleted,
            chunks_indexed=chunks_indexed,
            embedding_tokens=embedding_tokens,
        )
        log_event(
            logger,
            logging.INFO,
            "reindex_completed",
            documents_seen=report.documents_seen,
            documents_indexed=report.documents_indexed,
            documents_skipped=report.documents_skipped,
            documents_deleted=report.documents_deleted,
            chunks_indexed=report.chunks_indexed,
            embedding_tokens=report.embedding_tokens,
        )
        return report
