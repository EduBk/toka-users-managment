import json
from pathlib import Path

import pytest

from infrastructure.documents.filesystem import MarkdownDocumentLoader
from infrastructure.metrics.memory_store import InMemoryMetricsStore
from infrastructure.prompts.filesystem import FilePromptProvider
from application.ports.metrics import InvocationRecord


def _record(latency: float, *, outcome: str = "answered") -> InvocationRecord:
    return InvocationRecord(
        user="acc-1",
        timestamp=0.0,
        outcome=outcome,
        latency_total_ms=latency,
        latency_embedding_ms=1.0,
        latency_retrieval_ms=1.0,
        latency_llm_ms=1.0,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.001,
        sources=1,
    )


async def test_document_loader_reads_markdown_recursively(tmp_path: Path) -> None:
    (tmp_path / "guia.md").write_text("# Guia\n\ncontenido", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "detalle.md").write_text("detalle", encoding="utf-8")
    (tmp_path / "vacio.md").write_text("  ", encoding="utf-8")
    (tmp_path / "imagen.svg").write_text("<svg/>", encoding="utf-8")

    documents = await MarkdownDocumentLoader(tmp_path).load()

    assert [document.document for document in documents] == [
        "guia.md",
        "sub/detalle.md",
    ]
    assert documents[0].text.startswith("# Guia")
    assert documents[0].updated_at


async def test_document_loader_fails_when_the_directory_is_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError):
        await MarkdownDocumentLoader(tmp_path / "missing").load()


def _write_prompts(directory: Path, *, version: str = "v1") -> None:
    (directory / f"system.{version}.md").write_text("reglas", encoding="utf-8")
    (directory / f"rag.{version}.md").write_text(
        "contexto {{context}}", encoding="utf-8"
    )
    (directory / f"few-shots.{version}.json").write_text(
        json.dumps([{"question": "q", "answer": "a"}]), encoding="utf-8"
    )


def test_prompt_provider_loads_and_caches_the_bundle(tmp_path: Path) -> None:
    _write_prompts(tmp_path)
    provider = FilePromptProvider(tmp_path)

    bundle = provider.current()

    assert bundle.version == "v1"
    assert bundle.system == "reglas"
    assert bundle.few_shots[0].question == "q"
    assert provider.current() is bundle


def test_prompt_provider_validates_the_version(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        FilePromptProvider(tmp_path, version="1")


def test_prompt_provider_fails_when_an_artifact_is_missing(tmp_path: Path) -> None:
    _write_prompts(tmp_path)
    (tmp_path / "rag.v1.md").unlink()

    with pytest.raises(FileNotFoundError):
        FilePromptProvider(tmp_path).current()


async def test_metrics_store_summarises_latency_tokens_and_cost() -> None:
    store = InMemoryMetricsStore()

    await store.record(_record(10.0))
    await store.record(_record(30.0))
    await store.record(_record(20.0, outcome="no_context"))

    summary = await store.summary()

    assert summary.invocations == 3
    assert summary.avg_latency_ms == 20.0
    assert summary.p95_latency_ms == 30.0
    assert summary.input_tokens == 30
    assert summary.output_tokens == 15
    assert summary.cost_usd == 0.003
    assert summary.by_outcome == {"answered": 2, "no_context": 1}


async def test_metrics_store_is_empty_by_default() -> None:
    summary = await InMemoryMetricsStore().summary()

    assert summary.invocations == 0
    assert summary.avg_latency_ms == 0.0
    assert summary.p95_latency_ms == 0.0
    assert summary.by_outcome == {}


async def test_metrics_store_keeps_only_the_configured_window() -> None:
    store = InMemoryMetricsStore(window_size=2)

    for latency in (1.0, 2.0, 3.0):
        await store.record(_record(latency))

    summary = await store.summary()

    assert summary.invocations == 2
    assert summary.avg_latency_ms == 2.5


def test_metrics_store_rejects_an_invalid_window() -> None:
    with pytest.raises(ValueError):
        InMemoryMetricsStore(window_size=0)
