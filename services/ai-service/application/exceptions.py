"""Expected errors raised by the agent use cases."""

from __future__ import annotations


class AiUnavailable(Exception):
    """The LLM, embedding provider or vector store cannot serve the request."""


class AiNotConfigured(AiUnavailable):
    """The provider rejected the credentials (missing or invalid API key)."""


class AiModelUnavailable(AiUnavailable):
    """The requested model does not exist or the account cannot use it."""


class AiRateLimited(Exception):
    """The provider rejected the request because of its rate limit."""

    def __init__(self, message: str, *, retry_after_seconds: int = 30) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ReindexFailed(Exception):
    """The embedding pipeline could not index the documentation."""
