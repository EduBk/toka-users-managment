from types import SimpleNamespace

import httpx
import openai
import pytest

from application.exceptions import (
    AiModelUnavailable,
    AiNotConfigured,
    AiRateLimited,
    AiUnavailable,
)
from infrastructure.embeddings.openai_embeddings import OpenAIEmbeddings
from infrastructure.llm.openai_client import OpenAICompleter
from infrastructure.retry import RetryPolicy

REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _rate_limit(retry_after: str | None = None) -> openai.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    return openai.RateLimitError(
        "rate limited",
        response=httpx.Response(429, request=REQUEST, headers=headers),
        body=None,
    )


def _status_error(status_code: int) -> openai.APIStatusError:
    return openai.APIStatusError(
        "boom", response=httpx.Response(status_code, request=REQUEST), body=None
    )


def _auth_error() -> openai.AuthenticationError:
    return openai.AuthenticationError(
        "Incorrect API key provided",
        response=httpx.Response(401, request=REQUEST),
        body=None,
    )


def _permission_error() -> openai.PermissionDeniedError:
    return openai.PermissionDeniedError(
        "Model access is disabled",
        response=httpx.Response(403, request=REQUEST),
        body=None,
    )


def _not_found_error() -> openai.NotFoundError:
    return openai.NotFoundError(
        "model not found", response=httpx.Response(404, request=REQUEST), body=None
    )


def _bad_request_error(message: str) -> openai.BadRequestError:
    return openai.BadRequestError(
        message, response=httpx.Response(400, request=REQUEST), body=None
    )


def _completion(text: str = "hola") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        model="gpt-test",
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=4),
    )


def _embedding_response(count: int) -> SimpleNamespace:
    return SimpleNamespace(
        data=[
            SimpleNamespace(index=index, embedding=[float(index), 0.5])
            for index in reversed(range(count))
        ],
        usage=SimpleNamespace(prompt_tokens=6),
    )


class _Completions:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.requests: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.requests.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _Chat:
    def __init__(self, completions: _Completions) -> None:
        self.completions = completions


class _Client:
    def __init__(self, completions: _Completions) -> None:
        self.chat = _Chat(completions)


def _completer(outcomes: list[object], delays: list[float]) -> OpenAICompleter:
    async def sleep(delay: float) -> None:
        delays.append(delay)

    completer = OpenAICompleter(
        api_key="test",
        model="gpt-test",
        policy=RetryPolicy(attempts=3, backoff_seconds=0.1),
        sleep=sleep,
    )
    completer._client = _Client(_Completions(outcomes))  # type: ignore[assignment]
    return completer


async def test_completion_returns_text_and_token_usage() -> None:
    completer = _completer([_completion("respuesta")], [])

    result = await completer.complete(system="s", user="u")

    assert result.text == "respuesta"
    assert result.model == "gpt-test"
    assert (result.input_tokens, result.output_tokens) == (11, 4)


async def test_completion_retries_a_rate_limit_and_honours_retry_after() -> None:
    delays: list[float] = []
    completer = _completer([_rate_limit("2"), _completion()], delays)

    result = await completer.complete(system="s", user="u")

    assert result.text == "hola"
    assert delays == [2.0]


async def test_completion_raises_rate_limited_after_exhausting_retries() -> None:
    completer = _completer([_rate_limit("4")] * 3, [])

    with pytest.raises(AiRateLimited) as excinfo:
        await completer.complete(system="s", user="u")

    assert excinfo.value.retry_after_seconds == 4


async def test_completion_retries_server_errors_then_fails() -> None:
    delays: list[float] = []
    completer = _completer([_status_error(500), _status_error(503), _status_error(500)], delays)

    with pytest.raises(AiUnavailable):
        await completer.complete(system="s", user="u")

    assert delays == [0.1, 0.2]


async def test_completion_does_not_retry_client_errors() -> None:
    delays: list[float] = []
    completer = _completer([_status_error(400)], delays)

    with pytest.raises(AiUnavailable):
        await completer.complete(system="s", user="u")

    assert delays == []


async def test_completion_retries_timeouts() -> None:
    delays: list[float] = []
    completer = _completer(
        [openai.APITimeoutError(request=REQUEST), _completion()], delays
    )

    assert (await completer.complete(system="s", user="u")).text == "hola"
    assert delays == [0.1]


async def test_completion_without_api_key_is_unavailable() -> None:
    completer = OpenAICompleter(api_key="", model="gpt-test")

    with pytest.raises(AiUnavailable):
        await completer.complete(system="s", user="u")


async def test_completion_with_empty_choices_is_unavailable() -> None:
    completer = _completer(
        [SimpleNamespace(choices=[], model="gpt-test", usage=None)], []
    )

    with pytest.raises(AiUnavailable):
        await completer.complete(system="s", user="u")


async def test_completion_sends_the_session_header() -> None:
    completer = _completer([_completion(), _completion()], [])

    await completer.complete(system="s", user="u", session_id="acc-1")
    await completer.complete(system="s", user="u")

    requests = completer._client.chat.completions.requests  # type: ignore[union-attr]
    assert requests[0]["extra_headers"] == {"x-opencode-session": "acc-1"}
    assert requests[1]["extra_headers"] is None


async def test_completion_maps_an_invalid_key() -> None:
    completer = _completer([_auth_error()], [])

    with pytest.raises(AiNotConfigured):
        await completer.complete(system="s", user="u")


async def test_completion_maps_a_disabled_model() -> None:
    completer = _completer([_permission_error()], [])

    with pytest.raises(AiModelUnavailable):
        await completer.complete(system="s", user="u")


async def test_completion_maps_a_missing_model() -> None:
    completer = _completer([_not_found_error()], [])

    with pytest.raises(AiModelUnavailable):
        await completer.complete(system="s", user="u")


async def test_completion_maps_a_gateway_model_error() -> None:
    completer = _completer([_bad_request_error("Upstream request failed: Model is unavailable.")], [])

    with pytest.raises(AiModelUnavailable):
        await completer.complete(system="s", user="u")


def _embeddings(outcomes: list[object], delays: list[float]) -> OpenAIEmbeddings:
    async def sleep(delay: float) -> None:
        delays.append(delay)

    embeddings = OpenAIEmbeddings(
        api_key="test",
        model="text-embedding-3-small",
        policy=RetryPolicy(attempts=3, backoff_seconds=0.1),
        sleep=sleep,
    )
    embeddings._client = SimpleNamespace(
        embeddings=SimpleNamespace(create=_create(outcomes))
    )
    return embeddings


def _create(outcomes: list[object]):
    async def create(**kwargs: object) -> object:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return create


async def test_embeddings_returns_vectors_in_input_order() -> None:
    embeddings = _embeddings([_embedding_response(2)], [])

    result = await embeddings.embed(("a", "b"))

    assert result.vectors == ((0.0, 0.5), (1.0, 0.5))
    assert result.input_tokens == 6


async def test_embeddings_without_texts_does_not_call_the_api() -> None:
    embeddings = _embeddings([], [])

    assert (await embeddings.embed(())).vectors == ()


async def test_embeddings_without_api_key_is_unavailable() -> None:
    with pytest.raises(AiUnavailable):
        await OpenAIEmbeddings(api_key="", model="m").embed(("a",))


async def test_embeddings_rejects_an_incomplete_batch() -> None:
    embeddings = _embeddings([_embedding_response(1)], [])

    with pytest.raises(AiUnavailable):
        await embeddings.embed(("a", "b"))


async def test_embeddings_maps_rate_limits() -> None:
    delays: list[float] = []
    embeddings = _embeddings([_rate_limit("3"), _embedding_response(1)], delays)

    assert (await embeddings.embed(("a",))).input_tokens == 6
    assert delays == [3.0]


async def test_embeddings_maps_provider_errors() -> None:
    embeddings = _embeddings([_status_error(500)] * 3, [])

    with pytest.raises(AiUnavailable):
        await embeddings.embed(("a",))


async def test_embeddings_map_an_invalid_key() -> None:
    embeddings = _embeddings([_auth_error()], [])

    with pytest.raises(AiNotConfigured):
        await embeddings.embed(("a",))


async def test_embeddings_map_a_disabled_model() -> None:
    embeddings = _embeddings([_permission_error()], [])

    with pytest.raises(AiModelUnavailable):
        await embeddings.embed(("a",))
