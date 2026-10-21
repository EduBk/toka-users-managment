"""AI routes: ask (RAG), reindex and metrics."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from api.deps import (
    AccessToken,
    enforce_ai_rate_limit,
    get_ask_agent,
    get_get_agent_metrics,
    get_reindex_documents,
)
from api.schemas import (
    AiHealthResponse,
    AskRequest,
    AskResponse,
    MetricsResponse,
    ReindexResponse,
)
from app_common.jwt_auth import TokenClaims, require_roles, require_scopes
from application.use_cases.ask_agent import AskAgent
from application.use_cases.get_agent_metrics import GetAgentMetrics
from application.use_cases.reindex_documents import ReindexDocuments
from domain.agent.models import AgentQuestion, Message

router = APIRouter(prefix="/ai", tags=["ai"])

AiUse = Annotated[TokenClaims, Depends(require_scopes("ai:use"))]
AdminOnly = [Depends(require_roles("admin"))]


@router.get("/health", response_model=AiHealthResponse, summary="AI readiness probe")
async def ai_health(
    request: Request,
    _claims: AiUse,
) -> AiHealthResponse:
    info = request.app.state.ai_info
    vector_store = request.app.state.vector_store
    reachable = await vector_store.ping()
    return AiHealthResponse(
        status="ok" if reachable else "degraded",
        service=info["service"],
        version=info["version"],
        environment=info["environment"],
        vector_store="up" if reachable else "down",
        llm=info["llm"],
        llm_model=info["llm_model"],
        embeddings=info["embeddings"],
        prompt_version=info["prompt_version"],
    )


@router.post(
    "/ask",
    response_model=AskResponse,
    dependencies=[Depends(enforce_ai_rate_limit)],
    summary="Ask the agent a question (RAG)",
)
async def ask(
    payload: AskRequest,
    claims: AiUse,
    token: AccessToken,
    use_case: AskAgent = Depends(get_ask_agent),
) -> AskResponse:
    answer = await use_case.execute(
        AgentQuestion(
            question=payload.question,
            history=tuple(
                Message(role=message.role, content=message.content)
                for message in payload.history
            ),
            top_k=payload.top_k or 0,
            document=payload.document,
            include_system_data=payload.include_system_data,
        ),
        user=claims.sub,
        bearer_token=token,
    )
    return AskResponse.from_domain(answer)


@router.post(
    "/reindex",
    response_model=ReindexResponse,
    dependencies=AdminOnly,
    summary="Reindex the documentation corpus (admin only)",
)
async def reindex(
    use_case: ReindexDocuments = Depends(get_reindex_documents),
) -> ReindexResponse:
    report = await use_case.execute()
    return ReindexResponse(
        documents_seen=report.documents_seen,
        documents_indexed=report.documents_indexed,
        documents_skipped=report.documents_skipped,
        documents_deleted=report.documents_deleted,
        chunks_indexed=report.chunks_indexed,
        embedding_tokens=report.embedding_tokens,
    )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    dependencies=AdminOnly,
    summary="Aggregated latency, tokens and cost (admin only)",
)
async def metrics(
    use_case: GetAgentMetrics = Depends(get_get_agent_metrics),
) -> MetricsResponse:
    summary = await use_case.execute()
    return MetricsResponse(
        invocations=summary.invocations,
        window_size=summary.window_size,
        avg_latency_ms=summary.avg_latency_ms,
        p95_latency_ms=summary.p95_latency_ms,
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
        cost_usd=summary.cost_usd,
        by_outcome=summary.by_outcome,
    )
