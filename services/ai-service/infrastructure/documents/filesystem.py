"""Load the markdown corpus from a local directory (E5.2)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from application.ports.documents import DocumentSource


class MarkdownDocumentLoader:
    """Recursively loads ``*.md`` files; the path is mounted read-only."""

    def __init__(self, root: Path, *, suffix: str = ".md") -> None:
        self._root = root
        self._suffix = suffix

    async def load(self) -> tuple[DocumentSource, ...]:
        return await asyncio.to_thread(self._load)

    def _load(self) -> tuple[DocumentSource, ...]:
        if not self._root.is_dir():
            raise FileNotFoundError(
                f"documentation directory not found: {self._root}"
            )
        documents: list[DocumentSource] = []
        for path in sorted(self._root.rglob(f"*{self._suffix}")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            if not text.strip():
                continue
            documents.append(
                DocumentSource(
                    document=path.relative_to(self._root).as_posix(),
                    text=text,
                    updated_at=datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).date().isoformat(),
                )
            )
        return tuple(documents)
