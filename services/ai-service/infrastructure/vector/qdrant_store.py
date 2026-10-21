"""Qdrant adapter for the retrieval side of RAG (E5.2, E5.3)."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from qdrant_client import AsyncQdrantClient, models

from app_common.logging import log_event
from application.exceptions import AiUnavailable
from application.ports.vector_store import EmbeddedChunk
from domain.agent.models import RetrievedChunk

logger = logging.getLogger("ai_service.qdrant")

_PAYLOAD_KEYS = ("document", "section", "text", "doc_hash", "chunk_index", "updated_at")
_SCROLL_PAGE = 256


class QdrantVectorStore:
    """One collection per embedding model version (``qdrant_collection``)."""

    def __init__(
        self,
        *,
        url: str,
        collection: str,
        api_key: str | None = None,
        min_score: float = 0.0,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        self._collection = collection
        self._min_score = min_score
        self._client = client or AsyncQdrantClient(url=url, api_key=api_key)

    async def ensure_collection(self, dimension: int) -> None:
        try:
            if await self._client.collection_exists(self._collection):
                return
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=models.VectorParams(
                    size=dimension, distance=models.Distance.COSINE
                ),
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="document",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            raise AiUnavailable("the vector store is not available") from exc
        log_event(
            logger,
            logging.INFO,
            "vector_collection_created",
            collection=self._collection,
            dimension=dimension,
        )

    async def upsert(self, chunks: Sequence[EmbeddedChunk]) -> None:
        if not chunks:
            return
        try:
            await self._client.upsert(
                collection_name=self._collection,
                points=[
                    models.PointStruct(
                        id=chunk.chunk_id,
                        vector=list(chunk.vector),
                        payload={
                            "document": chunk.document,
                            "section": chunk.section,
                            "text": chunk.text,
                            "doc_hash": chunk.doc_hash,
                            "chunk_index": chunk.chunk_index,
                            "updated_at": chunk.updated_at,
                        },
                    )
                    for chunk in chunks
                ],
                wait=True,
            )
        except Exception as exc:
            raise AiUnavailable("the vector store is not available") from exc

    async def search(
        self,
        vector: Sequence[float],
        *,
        limit: int,
        document: str | None = None,
    ) -> tuple[RetrievedChunk, ...]:
        try:
            if not await self._client.collection_exists(self._collection):
                return ()
            response = await self._client.query_points(
                collection_name=self._collection,
                query=list(vector),
                limit=limit,
                query_filter=self._filter(document),
                score_threshold=self._min_score or None,
                with_payload=True,
            )
        except Exception as exc:
            raise AiUnavailable("the vector store is not available") from exc
        return tuple(
            RetrievedChunk(
                chunk_id=str(point.id),
                document=str(point.payload.get("document", "")),
                section=str(point.payload.get("section", "")),
                text=str(point.payload.get("text", "")),
                score=float(point.score),
            )
            for point in response.points
        )

    async def document_hashes(self) -> dict[str, str]:
        hashes: dict[str, str] = {}
        offset: str | int | None = None
        try:
            while True:
                records, offset = await self._client.scroll(
                    collection_name=self._collection,
                    limit=_SCROLL_PAGE,
                    offset=offset,
                    with_payload=["document", "doc_hash"],
                )
                for record in records:
                    payload = record.payload or {}
                    document = payload.get("document")
                    digest = payload.get("doc_hash")
                    if document and digest:
                        hashes[str(document)] = str(digest)
                if offset is None:
                    break
        except Exception as exc:
            # A missing collection means "nothing indexed yet".
            if not await self._collection_exists():
                return {}
            raise AiUnavailable("the vector store is not available") from exc
        return hashes

    async def delete_document(self, document: str) -> None:
        try:
            await self._client.delete(
                collection_name=self._collection,
                points_selector=models.FilterSelector(
                    filter=self._filter(document)
                ),
                wait=True,
            )
        except Exception as exc:
            raise AiUnavailable("the vector store is not available") from exc

    async def ping(self) -> bool:
        try:
            await self._client.get_collections()
        except Exception:
            return False
        return True

    async def aclose(self) -> None:
        await self._client.close()

    async def _collection_exists(self) -> bool:
        try:
            return await self._client.collection_exists(self._collection)
        except Exception:
            return False

    @staticmethod
    def _filter(document: str | None) -> models.Filter | None:
        if document is None:
            return None
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="document", match=models.MatchValue(value=document)
                )
            ]
        )
