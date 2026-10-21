"""Local embeddings with FastEmbed (ONNX, CPU): no API key, no per-token cost.

The model is downloaded on first use and cached in ``FASTEMBED_CACHE_DIR`` (a
Docker volume in Compose), so restarts and reindexes reuse it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from fastembed import TextEmbedding

from app_common.logging import log_event
from application.exceptions import AiUnavailable
from application.ports.embeddings import EmbeddingBatch

logger = logging.getLogger("ai_service.fastembed")


class FastEmbedEmbeddings:
    """``EmbeddingClient`` backed by a local ONNX model."""

    def __init__(
        self,
        *,
        model: str,
        cache_dir: str | None = None,
        threads: int | None = None,
    ) -> None:
        self.model = model
        self._cache_dir = cache_dir or None
        self._threads = threads
        self._embedding: TextEmbedding | None = None
        self._lock = asyncio.Lock()

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch(vectors=(), input_tokens=0)
        # TextEmbedding is synchronous and not documented as thread-safe: one
        # call at a time per process.
        async with self._lock:
            vectors = await asyncio.to_thread(self._embed_sync, list(texts))
        return EmbeddingBatch(vectors=vectors, input_tokens=0)

    def _embed_sync(self, texts: list[str]) -> tuple[tuple[float, ...], ...]:
        try:
            return tuple(
                tuple(float(value) for value in vector)
                for vector in self._ensure_model().embed(texts)
            )
        except AiUnavailable:
            raise
        except Exception as exc:
            raise AiUnavailable(
                f"the local embedding model is not available ({type(exc).__name__})"
            ) from exc

    def _ensure_model(self) -> TextEmbedding:
        if self._embedding is None:
            log_event(
                logger,
                logging.INFO,
                "loading_embedding_model",
                model=self.model,
            )
            self._embedding = TextEmbedding(
                model_name=self.model,
                cache_dir=self._cache_dir,
                threads=self._threads,
            )
            log_event(
                logger,
                logging.INFO,
                "embedding_model_ready",
                model=self.model,
            )
        return self._embedding
