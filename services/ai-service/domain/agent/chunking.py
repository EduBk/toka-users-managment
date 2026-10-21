"""Deterministic markdown chunking with section and overlap metadata (E5.2)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
DEFAULT_SECTION = "introducción"


@dataclass(frozen=True, slots=True)
class Chunk:
    index: int
    section: str
    text: str


def split_sections(text: str) -> tuple[tuple[str, str], ...]:
    """Split markdown into ``(section, body)`` pairs using its headings."""

    sections: list[tuple[str, str]] = []
    section = DEFAULT_SECTION
    body: list[str] = []
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            if "\n".join(body).strip():
                sections.append((section, "\n".join(body).strip()))
            section = heading.group(2)
            body = []
            continue
        body.append(line)
    if "\n".join(body).strip():
        sections.append((section, "\n".join(body).strip()))
    return tuple(sections)


def _paragraphs(body: str) -> list[str]:
    return [part.strip() for part in _PARAGRAPH_BREAK.split(body) if part.strip()]


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    """Hard-split a paragraph that is longer than the configured chunk size."""

    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        pieces.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return pieces


def _windows(paragraphs: list[str], max_chars: int, overlap: int) -> list[str]:
    windows: list[str] = []
    current: list[str] = []
    for paragraph in paragraphs:
        candidate = "\n\n".join([*current, paragraph])
        if current and len(candidate) > max_chars:
            windows.append("\n\n".join(current))
            # Keep the tail of the previous window as overlap for the next one.
            tail: list[str] = []
            for previous in reversed(current):
                if len("\n\n".join([previous, *tail])) > overlap:
                    break
                tail.insert(0, previous)
            current = [*tail, paragraph]
        else:
            current.append(paragraph)
    if current:
        windows.append("\n\n".join(current))
    return windows


def chunk_document(
    text: str, *, max_chars: int = 800, overlap: int = 100
) -> tuple[Chunk, ...]:
    """Split a document into overlapping chunks, keeping its section names."""

    if max_chars < 1:
        raise ValueError("max_chars must be >= 1")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be >= 0 and < max_chars")

    chunks: list[Chunk] = []
    for section, body in split_sections(text):
        paragraphs: list[str] = []
        for paragraph in _paragraphs(body):
            paragraphs.extend(_split_long(paragraph, max_chars, overlap))
        for window in _windows(paragraphs, max_chars, overlap):
            chunks.append(Chunk(index=len(chunks), section=section, text=window))
    return tuple(chunk for chunk in chunks if chunk.text.strip())
