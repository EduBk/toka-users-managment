from types import SimpleNamespace

import pytest

from application.exceptions import AiUnavailable
from application.ports.vector_store import EmbeddedChunk
from domain.agent.models import RetrievedChunk
from infrastructure.vector.qdrant_store import QdrantVectorStore

COLLECTION = "docs_v1"


def _chunk(chunk_id: str = "id-1", document: str = "auth.md") -> EmbeddedChunk:
    return EmbeddedChunk(
        chunk_id=chunk_id,
        document=document,
        section="Auth",
        text="texto",
        vector=(0.1, 0.2),
        doc_hash="hash",
        chunk_index=0,
        updated_at="2026-10-20",
    )


class FakeQdrant:
    def __init__(self) -> None:
        self.exists = False
        self.created: list[dict] = []
        self.indexes: list[dict] = []
        self.points: dict[str, dict] = {}
        self.search_calls: list[dict] = []
        self.deleted: list[object] = []
        self.fail = False
        self.fail_collection_check = True
        self.closed = False
        self.pages: list[tuple[list[object], object]] | None = None

    async def collection_exists(self, collection_name: str) -> bool:
        if self.fail and self.fail_collection_check:
            raise RuntimeError("down")
        return self.exists

    async def create_collection(self, **kwargs: object) -> None:
        self.created.append(kwargs)
        self.exists = True

    async def create_payload_index(self, **kwargs: object) -> None:
        self.indexes.append(kwargs)

    async def upsert(self, **kwargs: object) -> None:
        if self.fail:
            raise RuntimeError("down")
        for point in kwargs["points"]:
            self.points[str(point.id)] = {
                "payload": point.payload,
                "vector": point.vector,
            }

    async def query_points(self, **kwargs: object) -> SimpleNamespace:
        if self.fail:
            raise RuntimeError("down")
        self.search_calls.append(kwargs)
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    id="id-1",
                    payload={
                        "document": "auth.md",
                        "section": "Auth",
                        "text": "los tokens",
                    },
                    score=0.87,
                )
            ]
        )

    async def scroll(self, **kwargs: object) -> tuple[list[object], object]:
        if self.fail:
            raise RuntimeError("down")
        if self.pages is not None:
            return self.pages.pop(0)
        return (
            [
                SimpleNamespace(payload={"document": "auth.md", "doc_hash": "h1"}),
                SimpleNamespace(payload={"document": "auth.md", "doc_hash": "h1"}),
                SimpleNamespace(payload={}),
            ],
            None,
        )

    async def delete(self, **kwargs: object) -> None:
        if self.fail:
            raise RuntimeError("down")
        self.deleted.append(kwargs["points_selector"])

    async def get_collections(self) -> SimpleNamespace:
        if self.fail:
            raise RuntimeError("down")
        return SimpleNamespace(collections=[])

    async def close(self) -> None:
        self.closed = True


def _store(fake: FakeQdrant) -> QdrantVectorStore:
    return QdrantVectorStore(
        url="http://qdrant:6333", collection=COLLECTION, client=fake  # type: ignore[arg-type]
    )


async def test_ensure_collection_creates_it_once_with_a_payload_index() -> None:
    fake = FakeQdrant()
    store = _store(fake)

    await store.ensure_collection(1536)
    await store.ensure_collection(1536)

    assert len(fake.created) == 1
    assert fake.created[0]["collection_name"] == COLLECTION
    assert fake.created[0]["vectors_config"].size == 1536
    assert fake.indexes[0]["field_name"] == "document"


async def test_ensure_collection_maps_failures() -> None:
    fake = FakeQdrant()
    fake.fail = True

    with pytest.raises(AiUnavailable):
        await _store(fake).ensure_collection(3)


async def test_upsert_stores_the_payload_and_skips_empty_batches() -> None:
    fake = FakeQdrant()
    store = _store(fake)

    await store.upsert(())
    await store.upsert((_chunk(),))

    point = fake.points["id-1"]
    assert point["payload"]["document"] == "auth.md"
    assert point["payload"]["doc_hash"] == "hash"
    assert point["vector"] == [0.1, 0.2]


async def test_upsert_maps_failures() -> None:
    fake = FakeQdrant()
    fake.fail = True

    with pytest.raises(AiUnavailable):
        await _store(fake).upsert((_chunk(),))


async def test_search_returns_chunks_and_applies_the_document_filter() -> None:
    fake = FakeQdrant()
    fake.exists = True
    store = _store(fake)

    chunks = await store.search((0.1, 0.2), limit=3, document="auth.md")

    assert chunks == (RetrievedChunk(chunk_id="id-1", document="auth.md", section="Auth", text="los tokens", score=0.87),)
    query_filter = fake.search_calls[0]["query_filter"]
    assert query_filter.must[0].match.value == "auth.md"


async def test_search_without_collection_returns_no_chunks() -> None:
    fake = FakeQdrant()

    assert await _store(fake).search((0.1,), limit=3) == ()
    assert fake.search_calls == []


async def test_search_without_filter_passes_none() -> None:
    fake = FakeQdrant()
    fake.exists = True

    await _store(fake).search((0.1,), limit=2)

    assert fake.search_calls[0]["query_filter"] is None


async def test_search_applies_the_configured_score_threshold() -> None:
    fake = FakeQdrant()
    fake.exists = True
    store = QdrantVectorStore(
        url="http://qdrant:6333",
        collection=COLLECTION,
        min_score=0.3,
        client=fake,  # type: ignore[arg-type]
    )

    await store.search((0.1,), limit=2)

    assert fake.search_calls[0]["score_threshold"] == 0.3


async def test_search_maps_failures() -> None:
    fake = FakeQdrant()
    fake.exists = True
    fake.fail = True

    with pytest.raises(AiUnavailable):
        await _store(fake).search((0.1,), limit=1)


async def test_document_hashes_reads_every_scroll_page() -> None:
    fake = FakeQdrant()
    fake.pages = [
        (
            [SimpleNamespace(payload={"document": "a.md", "doc_hash": "h1"})],
            "next",
        ),
        (
            [SimpleNamespace(payload={"document": "b.md", "doc_hash": "h2"})],
            None,
        ),
    ]

    hashes = await _store(fake).document_hashes()

    assert hashes == {"a.md": "h1", "b.md": "h2"}


async def test_document_hashes_returns_empty_when_the_collection_is_missing() -> None:
    fake = FakeQdrant()
    fake.fail = True
    fake.exists = False

    assert await _store(fake).document_hashes() == {}


async def test_document_hashes_maps_failures_when_the_collection_exists() -> None:
    fake = FakeQdrant()
    fake.fail = True
    fake.exists = True
    fake.fail_collection_check = False

    with pytest.raises(AiUnavailable):
        await _store(fake).document_hashes()


async def test_delete_document_uses_a_filter_selector() -> None:
    fake = FakeQdrant()
    store = _store(fake)

    await store.delete_document("auth.md")

    selector = fake.deleted[0]
    assert selector.filter.must[0].match.value == "auth.md"


async def test_delete_document_maps_failures() -> None:
    fake = FakeQdrant()
    fake.fail = True

    with pytest.raises(AiUnavailable):
        await _store(fake).delete_document("auth.md")


async def test_ping_reports_the_store_state() -> None:
    fake = FakeQdrant()
    store = _store(fake)

    assert await store.ping() is True
    fake.fail = True
    assert await store.ping() is False


async def test_close_closes_the_client() -> None:
    fake = FakeQdrant()

    await _store(fake).aclose()

    assert fake.closed is True
