import pytest

from domain.agent.chunking import chunk_document, split_sections


def test_split_sections_uses_markdown_headings() -> None:
    text = "# Intro\nuno\n\n## Detalle\ndos\n"

    assert split_sections(text) == (("Intro", "uno"), ("Detalle", "dos"))


def test_split_sections_without_headings_uses_default_section() -> None:
    assert split_sections("solo texto") == (("introducción", "solo texto"),)


def test_chunk_document_keeps_section_and_sequential_indexes() -> None:
    text = (
        "# Uno\n\n"
        + "palabra " * 60
        + "\n\n# Dos\n\n"
        + "otra " * 60
    )

    chunks = chunk_document(text, max_chars=120, overlap=20)

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert {chunk.section for chunk in chunks} == {"Uno", "Dos"}
    assert all(len(chunk.text) <= 140 for chunk in chunks)
    assert all(chunk.text.strip() for chunk in chunks)


def test_chunk_document_repeats_the_tail_as_overlap() -> None:
    text = "bloque uno.\n\n" + "bloque dos largo. " * 20

    chunks = chunk_document(text, max_chars=80, overlap=20)

    assert len(chunks) > 1
    assert "bloque dos" in chunks[1].text


def test_chunk_document_returns_nothing_for_an_empty_document() -> None:
    assert chunk_document("   \n\n ") == ()


@pytest.mark.parametrize(
    ("max_chars", "overlap"),
    [(0, 0), (100, 100), (100, 120), (100, -1)],
)
def test_chunk_document_rejects_invalid_parameters(
    max_chars: int, overlap: int
) -> None:
    with pytest.raises(ValueError):
        chunk_document("texto", max_chars=max_chars, overlap=overlap)
