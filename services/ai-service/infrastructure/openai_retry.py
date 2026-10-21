"""Shared classification of OpenAI SDK errors for retries and HTTP mapping."""

from __future__ import annotations

import openai

from application.exceptions import (
    AiModelUnavailable,
    AiNotConfigured,
    AiUnavailable,
)


def retry_after_seconds(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    value = response.headers.get("retry-after") if response is not None else None
    if not value:
        return None
    try:
        return max(int(float(value)), 0)
    except ValueError:
        return None


def is_retryable(exc: Exception) -> bool:
    """429, timeouts, connection problems and 5xx are worth a retry."""

    if isinstance(
        exc, (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError)
    ):
        return True
    if isinstance(exc, openai.APIStatusError):
        return exc.status_code >= 500
    return False


def translate_error(exc: Exception, *, provider: str) -> AiUnavailable:
    """Map a provider error to the most specific application error.

    OpenAI-compatible gateways (OpenCode Go, OpenRouter...) keep the same status
    codes: 401 for rejected credentials and 403/404/400 for models that the key
    cannot use.
    """

    if isinstance(exc, openai.AuthenticationError):
        return AiNotConfigured(
            f"{provider} rejected the API key: check OPENAI_API_KEY"
        )
    if isinstance(exc, (openai.PermissionDeniedError, openai.NotFoundError)):
        return AiModelUnavailable(
            f"{provider} does not allow the configured model: check OPENAI_MODEL"
        )
    if isinstance(exc, openai.BadRequestError) and "model" in str(exc).lower():
        return AiModelUnavailable(
            f"{provider} reported the model as unavailable: check OPENAI_MODEL"
        )
    return AiUnavailable(f"{provider} is not available ({type(exc).__name__})")
