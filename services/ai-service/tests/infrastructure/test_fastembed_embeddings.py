"""FastEmbed adapter tests with a fake model (no download, no network)."""

from __future__ import annotations

import pytest

from application.exceptions import AiUnavailable
from infrastructure.embeddings import fastembed_embeddings
from infrastructure.embeddings.fastembed_embeddings import FastEmbedEmbeddings


class FakeTextEmbedding:
    instances: list["FakeTextEmbedding"] = []
    fail = False

    def __init__(self, *, model_name: str, cache_dir: str | None, threads: int | None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.threads = threads
        FakeTextEmbedding.instances.append(self)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if FakeTextEmbedding.fail:
            raise RuntimeError("model files missing")
        return [[float(len(text)), 0.5] for text in texts]


@pytest.fixture(autouse=True)
def fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeTextEmbedding.instances = []
    FakeTextEmbedding.fail = False
    monkeypatch.setattr(
        fastembed_embeddings, "TextEmbedding", FakeTextEmbedding
    )


async def test_fastembed_loads_the_model_lazily_and_returns_vectors() -> None:
    embeddings = FastEmbedEmbeddings(
        model="fake-model", cache_dir="/models", threads=2
    )

    assert FakeTextEmbedding.instances == []

    result = await embeddings.embed(("hola", "mundo"))

    assert result.vectors == ((4.0, 0.5), (5.0, 0.5))
    assert result.input_tokens == 0
    instance = FakeTextEmbedding.instances[0]
    assert (instance.model_name, instance.cache_dir, instance.threads) == (
        "fake-model",
        "/models",
        2,
    )
    assert len(FakeTextEmbedding.instances) == 1
    await embeddings.embed(("otra",))
    assert len(FakeTextEmbedding.instances) == 1


async def test_fastembed_skips_the_model_for_an_empty_batch() -> None:
    embeddings = FastEmbedEmbeddings(model="fake-model")

    result = await embeddings.embed(())

    assert result.vectors == ()
    assert FakeTextEmbedding.instances == []


async def test_fastembed_maps_model_errors() -> None:
    FakeTextEmbedding.fail = True
    embeddings = FastEmbedEmbeddings(model="fake-model")

    with pytest.raises(AiUnavailable):
        await embeddings.embed(("hola",))
