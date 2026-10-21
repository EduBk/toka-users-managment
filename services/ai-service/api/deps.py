"""Composition root and request-scoped dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app_common.jwt_auth import CurrentClaims
from application.ports.metrics import MetricsStore
from application.use_cases.ask_agent import AskAgent
from application.use_cases.get_agent_metrics import GetAgentMetrics
from application.use_cases.reindex_documents import ReindexDocuments

_bearer = HTTPBearer(auto_error=False)


def get_ask_agent(request: Request) -> AskAgent:
    return request.app.state.ask_agent


def get_reindex_documents(request: Request) -> ReindexDocuments:
    return request.app.state.reindex_documents


def get_metrics_store(request: Request) -> MetricsStore:
    return request.app.state.metrics


def get_get_agent_metrics(
    request: Request,
) -> GetAgentMetrics:
    return GetAgentMetrics(request.app.state.metrics)


async def get_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str | None:
    return credentials.credentials if credentials else None


async def enforce_ai_rate_limit(
    request: Request, claims: CurrentClaims
) -> None:
    policy = getattr(request.app.state, "rate_limit_ai", None)
    if policy is not None:
        await policy.enforce("ai:ask", claims.sub)


AccessToken = Annotated[str | None, Depends(get_access_token)]
