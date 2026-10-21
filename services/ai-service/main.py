"""AI microservice entry point: agent, RAG pipeline and metrics."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic import Field, model_validator
from redis.asyncio import Redis

from api.errors import register_ai_exception_handlers
from api.router import router
from app_common.app import create_service_app
from app_common.config import BaseServiceSettings
from app_common.jwt_auth import JwtValidator
from app_common.rate_limit import (
    InMemoryRateLimiter,
    RateLimitPolicy,
    RateLimitRule,
    RedisRateLimiter,
)
from application.use_cases.ask_agent import AskAgent
from application.use_cases.reindex_documents import ReindexDocuments
from domain.agent.pricing import TokenPrice
from infrastructure.directory.http_directory import HttpSystemDataProvider
from infrastructure.documents.filesystem import MarkdownDocumentLoader
from infrastructure.embeddings.fastembed_embeddings import FastEmbedEmbeddings
from infrastructure.embeddings.openai_embeddings import OpenAIEmbeddings
from infrastructure.llm.openai_client import OpenAICompleter
from infrastructure.metrics.memory_store import InMemoryMetricsStore
from infrastructure.prompts.filesystem import FilePromptProvider
from infrastructure.retry import RetryPolicy
from infrastructure.vector.qdrant_store import QdrantVectorStore


class Settings(BaseServiceSettings):
    service_name: str = "ai-service"
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_provider: str = "fastembed"
    fastembed_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    fastembed_cache_dir: str | None = None
    fastembed_threads: int | None = None
    openai_timeout_seconds: float = Field(default=60.0, gt=0)
    ai_max_retries: int = Field(default=3, ge=1)
    ai_retry_backoff_seconds: float = Field(default=0.5, ge=0)
    chat_input_price_per_million: float = Field(default=0.15, ge=0)
    chat_output_price_per_million: float = Field(default=0.60, ge=0)
    embedding_input_price_per_million: float = Field(default=0.0, ge=0)
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "system_docs_fastembed_v1"
    retrieval_min_score: float = Field(default=0.2, ge=0, le=1)
    docs_path: str = "/app/docs"
    prompt_dir: str = "/app/prompts"
    prompt_version: str = "v1"
    chunk_max_chars: int = Field(default=800, ge=100)
    chunk_overlap: int = Field(default=100, ge=0)
    embedding_batch_size: int = Field(default=64, ge=1, le=2048)
    top_k: int = Field(default=4, ge=1, le=20)
    max_question_chars: int = Field(default=2000, ge=1)
    max_answer_tokens: int = Field(default=1200, ge=1)
    temperature: float = Field(default=0.2, ge=0, le=1)
    metrics_window_size: int = Field(default=200, ge=1)
    jwks_url: str
    jwt_issuer: str = "auth-service"
    jwt_audience: str = "user-management"
    user_service_url: str = "http://user-service:8000"
    role_service_url: str = "http://role-service:8000"
    service_request_timeout_seconds: float = Field(default=2.0, gt=0)
    redis_url: str = ""
    ai_rate_limit_requests: int = Field(default=20, ge=1)
    ai_rate_limit_window_seconds: int = Field(default=60, ge=1)

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_max_chars:
            raise ValueError("CHUNK_OVERLAP must be lower than CHUNK_MAX_CHARS")
        if self.embedding_provider not in {"fastembed", "openai"}:
            raise ValueError("EMBEDDING_PROVIDER must be 'fastembed' or 'openai'")
        return self


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    prompts = FilePromptProvider(
        Path(settings.prompt_dir), version=settings.prompt_version
    )
    vectors = QdrantVectorStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key,
        min_score=settings.retrieval_min_score,
    )
    policy = RetryPolicy(
        attempts=settings.ai_max_retries,
        backoff_seconds=settings.ai_retry_backoff_seconds,
    )
    llm = OpenAICompleter(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.openai_timeout_seconds,
        policy=policy,
    )
    if settings.embedding_provider == "fastembed":
        embeddings = FastEmbedEmbeddings(
            model=settings.fastembed_model,
            cache_dir=settings.fastembed_cache_dir,
            threads=settings.fastembed_threads,
        )
        embedding_price = TokenPrice(input_per_million=0.0)
        embedding_label = f"fastembed:{settings.fastembed_model}"
    else:
        embeddings = OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
            policy=policy,
        )
        embedding_price = TokenPrice(
            input_per_million=settings.embedding_input_price_per_million
        )
        embedding_label = f"openai:{settings.embedding_model}"
    metrics = InMemoryMetricsStore(window_size=settings.metrics_window_size)
    directory = HttpSystemDataProvider(
        user_service_url=settings.user_service_url,
        role_service_url=settings.role_service_url,
        timeout_seconds=settings.service_request_timeout_seconds,
    )
    redis_client: Redis | None = (
        Redis.from_url(settings.redis_url, decode_responses=True)
        if settings.redis_url
        else None
    )

    app.state.jwt_validator = JwtValidator(
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        jwks_url=settings.jwks_url,
    )
    app.state.metrics = metrics
    app.state.vector_store = vectors
    app.state.ask_agent = AskAgent(
        prompts=prompts,
        embeddings=embeddings,
        vectors=vectors,
        llm=llm,
        metrics=metrics,
        chat_price=TokenPrice(
            input_per_million=settings.chat_input_price_per_million,
            output_per_million=settings.chat_output_price_per_million,
        ),
        embedding_price=embedding_price,
        top_k=settings.top_k,
        max_question_chars=settings.max_question_chars,
        max_answer_tokens=settings.max_answer_tokens,
        temperature=settings.temperature,
        directory=directory,
    )
    app.state.reindex_documents = ReindexDocuments(
        loader=MarkdownDocumentLoader(Path(settings.docs_path)),
        embeddings=embeddings,
        vectors=vectors,
        max_chars=settings.chunk_max_chars,
        overlap=settings.chunk_overlap,
        batch_size=settings.embedding_batch_size,
    )
    app.state.rate_limit_ai = RateLimitPolicy(
        RedisRateLimiter(redis_client) if redis_client else InMemoryRateLimiter(),
        RateLimitRule(
            limit=settings.ai_rate_limit_requests,
            window_seconds=settings.ai_rate_limit_window_seconds,
        ),
    )
    app.state.ai_info = {
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment,
        "llm_model": settings.openai_model,
        "llm": "configured" if settings.openai_api_key else "missing",
        "embeddings": embedding_label,
        "prompt_version": settings.prompt_version,
    }

    try:
        yield
    finally:
        await directory.aclose()
        await vectors.aclose()
        if redis_client is not None:
            await redis_client.aclose()


app = create_service_app(settings, routers=[router])
app.router.lifespan_context = lifespan
register_ai_exception_handlers(app)
# httpx logs every Qdrant/OpenAI HTTP call at INFO; keep the service log focused.
logging.getLogger("httpx").setLevel(logging.WARNING)
