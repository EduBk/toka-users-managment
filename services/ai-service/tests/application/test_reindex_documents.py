import pytest

from application.exceptions import AiUnavailable
from application.ports.documents import DocumentSource
from application.use_cases.reindex_documents import ReindexDocuments
from infrastructure.retry import RetryPolicy, retry_async
from tests.application.fakes import FakeEmbeddings, FakeLoader, FakeVectorStore, FailingEmbeddings

TEXT = "# Auth\n\nLos tokens se validan con JWKS.\n\n# Datos\n\nPostgreSQL guarda usuarios."


def _use_case(
    *documents: DocumentSource,
    vectors: FakeVectorStore | None = None,
    embeddings: FakeEmbeddings | FailingEmbeddings | None = None,
    batch_size: int = 64,
) -> tuple[ReindexDocuments, FakeVectorStore, FakeEmbeddings | FailingEmbeddings]:
    vectors = vectors or FakeVectorStore()
    embeddings = embeddings or FakeEmbeddings(tokens=5)
    use_case = ReindexDocuments(
        loader=FakeLoader(*documents),
        embeddings=embeddings,
        vectors=vectors,
        max_chars=200,
        overlap=20,
        batch_size=batch_size,
    )
    return use_case, vectors, embeddings


def _doc(name: str = "auth.md", text: str = TEXT) -> DocumentSource:
    return DocumentSource(document=name, text=text, updated_at="2026-10-20")


async def test_reindex_chunks_embeds_and_upserts_the_documents() -> None:
    use_case, vectors, _embeddings = _use_case(_doc())

    report = await use_case.execute()

    assert report.documents_seen == 1
    assert report.documents_indexed == 1
    assert report.chunks_indexed == len(vectors.upserted) > 0
    assert report.embedding_tokens == 5 * report.chunks_indexed
    assert vectors.dimensions == [2]
    assert vectors.upserted[0].document == "auth.md"
    assert vectors.upserted[0].section == "Auth"
    assert vectors.upserted[0].updated_at == "2026-10-20"


async def test_reindex_is_idempotent_for_unchanged_documents() -> None:
    use_case, vectors, embeddings = _use_case(_doc())
    await use_case.execute()
    first_upserts = len(vectors.upserted)
    first_calls = len(embeddings.calls)

    report = await use_case.execute()

    assert report.documents_skipped == 1
    assert report.documents_indexed == 0
    assert len(vectors.upserted) == first_upserts
    assert len(embeddings.calls) == first_calls


async def test_reindex_replaces_a_changed_document() -> None:
    vectors = FakeVectorStore(hashes={"auth.md": "old-hash"})
    use_case, vectors, _ = _use_case(_doc(), vectors=vectors)

    report = await use_case.execute()

    assert vectors.deleted == ["auth.md"]
    assert report.documents_deleted == 1
    assert vectors.upserted


async def test_reindex_deletes_documents_missing_from_the_corpus() -> None:
    vectors = FakeVectorStore(hashes={"old.md": "hash"})
    use_case, vectors, _ = _use_case(_doc(), vectors=vectors)

    report = await use_case.execute()

    assert vectors.deleted[0] == "old.md"
    assert report.documents_deleted == 1


async def test_reindex_removes_the_old_chunks_of_an_empty_document() -> None:
    vectors = FakeVectorStore(hashes={"empty.md": "old"})
    use_case, vectors, _ = _use_case(
        DocumentSource(document="empty.md", text="  ", updated_at="2026-10-20"),
        vectors=vectors,
    )

    report = await use_case.execute()

    assert vectors.deleted == ["empty.md"]
    assert report.chunks_indexed == 0
    assert report.documents_indexed == 1


async def test_reindex_batches_embeddings() -> None:
    long_text = "\n\n".join(f"parrafo {index} con contenido" for index in range(20))
    use_case, vectors, embeddings = _use_case(
        _doc(text=long_text),
        embeddings=FakeEmbeddings(tokens=2),
        batch_size=1,
    )

    await use_case.execute()

    assert len(embeddings.calls) > 1
    assert len(vectors.upserted) == len(embeddings.calls)


async def test_reindex_propagates_embedding_failures() -> None:
    use_case, _, _ = _use_case(
        _doc(),
        embeddings=FailingEmbeddings(AiUnavailable("embeddings down")),
    )

    with pytest.raises(AiUnavailable):
        await use_case.execute()


async def test_retry_stops_when_the_error_is_not_retryable() -> None:
    attempts = 0
    delays: list[float] = []

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise ValueError("fatal")

    async def sleep(delay: float) -> None:
        delays.append(delay)

    with pytest.raises(ValueError):
        await retry_async(
            operation,
            policy=RetryPolicy(attempts=3, backoff_seconds=0.1),
            is_retryable=lambda exc: False,
            sleep=sleep,
        )

    assert attempts == 1
    assert delays == []


async def test_retry_backs_off_and_succeeds() -> None:
    attempts = 0
    delays: list[float] = []

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("slow")
        return "ok"

    async def sleep(delay: float) -> None:
        delays.append(delay)

    result = await retry_async(
        operation,
        policy=RetryPolicy(attempts=3, backoff_seconds=0.5, max_backoff_seconds=1.0),
        is_retryable=lambda exc: isinstance(exc, TimeoutError),
        sleep=sleep,
    )

    assert result == "ok"
    assert delays == [0.5, 1.0]


async def test_retry_honours_the_provider_retry_after() -> None:
    attempts = 0
    delays: list[float] = []

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("slow")
        return "ok"

    async def sleep(delay: float) -> None:
        delays.append(delay)

    await retry_async(
        operation,
        policy=RetryPolicy(attempts=2, backoff_seconds=0.1),
        is_retryable=lambda exc: True,
        retry_after=lambda exc: 5,
        sleep=sleep,
    )

    assert delays == [5.0]
